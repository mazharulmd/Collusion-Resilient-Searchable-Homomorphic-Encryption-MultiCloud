// SPDX-License-Identifier: Apache-2.0
//
// Setup / BuildIndex / Precompute / EncData, writing a deployment bundle.
//
// The bundle splits along the trust boundary: everything under public/ goes to
// a provider host, and secret/ never leaves the data owner.  Copy only the
// public directory to the cloud instances.
//
//   build/crshe_setup --data=data/telemetry.crshe --bundle=deploy/
//
// This builds the fast-path columns only.  The general path needs the masked
// index I', which at full scale is tens of gigabytes per provider; use
// --with-general --nd=... to build a subsampled one for a general-path
// deployment test.

#include <cstdio>
#include <fstream>
#include <sys/stat.h>

#include "crshe/bench_util.hpp"
#include "crshe/dataset.hpp"
#include "crshe/index.hpp"
#include "crshe/protocol.hpp"

using namespace crshe;

static void write_file(const std::string& path, const std::string& blob) {
    std::ofstream os(path, std::ios::binary);
    if (!os) throw std::runtime_error("cannot write " + path);
    os.write(blob.data(), blob.size());
    std::fprintf(stderr, "   wrote %-40s %10.2f MB\n", path.c_str(), blob.size() / 1e6);
}

static std::string pack_columns(const HeBackend& he, const std::vector<Ct>& cts) {
    std::string s;
    const uint64_t n = cts.size();
    s.append((const char*)&n, 8);
    for (const auto& c : cts) {
        const std::string b = he.serialize(c);
        const uint64_t len = b.size();
        s.append((const char*)&len, 8);
        s.append(b);
    }
    return s;
}

int main(int argc, char** argv) {
    Args args(argc, argv);
    banner("crshe_setup");

    const std::string data = args.str("data", "");
    const std::string bundle = args.str("bundle", "deploy");
    const bool with_general = args.flag("with-general");
    const uint64_t nd = args.u64("nd", 0);

    auto he = he_from_args(args);
    Modulus mod(he->plaintext_modulus());

    Dataset ds = data.empty()
                     ? Dataset::synthetic(args.u64("ntags", 15347),
                                          args.u64("ntotal", 405184), 1.15, 99)
                     : Dataset::load(data);
    if (nd) ds = ds.subsample_records(nd);

    ::mkdir(bundle.c_str(), 0755);
    ::mkdir((bundle + "/public").c_str(), 0755);
    ::mkdir((bundle + "/secret").c_str(), 0700);

    Owner owner(ds, mod, args.u64("seed", 1234));
    const auto templates = default_templates(ds, 7);

    // Lemma 1 is a precondition of correctness, so refuse to build a bundle
    // that violates it rather than shipping one that decrypts to garbage.
    for (const auto& f : templates) {
        const uint64_t worst = ds.max_aggregate(f.w);
        if (worst >= mod.value()) {
            std::fprintf(stderr,
                         "\nREFUSING: template '%s' can reach %llu, which is >= p = "
                         "%llu.\nLemma 1's magnitude bound would be violated and "
                         "aggregates would wrap.\nPick a larger --p (must be prime "
                         "and = 1 mod 2*ringdim) or rescale the computable field.\n",
                         f.name.c_str(), (unsigned long long)worst,
                         (unsigned long long)mod.value());
            return 2;
        }
    }

    std::fprintf(stderr, "   precomputing columns (this is the one-off cost)...\n");
    const double t0 = now_ms();
    ProviderState st = build_provider_state(owner, *he, templates, with_general);
    std::fprintf(stderr, "   precompute took %.1f s\n", (now_ms() - t0) / 1000.0);

    write_file(bundle + "/public/he_public.bin", he->export_public());
    write_file(bundle + "/secret/he_secret.bin", he->export_secret());

    for (const auto& f : templates) {
        write_file(bundle + "/public/A_" + f.name + ".bin",
                   pack_columns(*he, st.fast.at(f.name).A));
        write_file(bundle + "/public/Amac_" + f.name + ".bin",
                   pack_columns(*he, st.fast.at(f.name).A_mac));
    }

    {
        std::ofstream meta(bundle + "/public/meta.txt");
        meta << "he_kind=" << he->name() << "\n"
             << "p=" << mod.value() << "\n"
             << "ring_dim=" << he->ring_dim() << "\n"
             << "slots=" << he->slots() << "\n"
             << "n_tags=" << ds.n_tags << "\n"
             << "n_records=" << ds.n_records << "\n"
             << "source=" << ds.source << "\n";
        meta << "templates=";
        for (size_t i = 0; i < templates.size(); ++i)
            meta << templates[i].name << (i + 1 < templates.size() ? "," : "");
        meta << "\n";
    }
    {
        // delta is MAC key material: it belongs on the client side only.
        std::ofstream sec(bundle + "/secret/owner.txt");
        sec << "delta=" << owner.delta() << "\n"
            << "seed=" << args.u64("seed", 1234) << "\n"
            << "data=" << data << "\n";
    }

    std::fprintf(stderr,
                 "\nBundle written to %s\n"
                 "  copy %s/public/ to each provider host\n"
                 "  keep %s/secret/ on the data owner / data user host only\n",
                 bundle.c_str(), bundle.c_str(), bundle.c_str());
    return 0;
}
