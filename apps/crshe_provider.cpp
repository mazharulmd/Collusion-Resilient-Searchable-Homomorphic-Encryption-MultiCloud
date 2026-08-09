// SPDX-License-Identifier: Apache-2.0
//
// A cloud provider process.  Holds only the public bundle: the crypto context,
// the evaluation keys, pk, and the precomputed columns.  It cannot decrypt, and
// decrypt_scalar() throws if anything tries.
//
//   build/crshe_provider --bundle=deploy --port=9101 [--threads=8]
//
// Protocol (length-prefixed frames, see include/crshe/net.hpp):
//   -> "ping"                                 <- "pong"
//   -> "agg", template, party(u32), key blob   <- compute_ms, ct, ct_mac

#include <cstdio>
#include <fstream>
#include <sstream>
#include <thread>

#include "crshe/bench_util.hpp"
#include "crshe/net.hpp"
#include "crshe/protocol.hpp"

using namespace crshe;

namespace {

std::string read_file(const std::string& path) {
    std::ifstream is(path, std::ios::binary);
    if (!is) throw std::runtime_error("cannot open " + path);
    std::ostringstream ss;
    ss << is.rdbuf();
    return ss.str();
}

std::vector<Ct> unpack_columns(const HeBackend& he, const std::string& blob) {
    size_t off = 0;
    uint64_t n = 0;
    std::memcpy(&n, blob.data(), 8);
    off = 8;
    std::vector<Ct> out;
    out.reserve(n);
    for (uint64_t i = 0; i < n; ++i) {
        uint64_t len = 0;
        std::memcpy(&len, blob.data() + off, 8);
        off += 8;
        out.push_back(he.deserialize(blob.substr(off, len)));
        off += len;
    }
    return out;
}

std::map<std::string, std::string> read_meta(const std::string& path) {
    std::map<std::string, std::string> m;
    std::ifstream is(path);
    std::string line;
    while (std::getline(is, line)) {
        const size_t eq = line.find('=');
        if (eq != std::string::npos) m[line.substr(0, eq)] = line.substr(eq + 1);
    }
    return m;
}

std::vector<std::string> split(const std::string& s, char c) {
    std::vector<std::string> out;
    std::stringstream ss(s);
    std::string tok;
    while (std::getline(ss, tok, c)) if (!tok.empty()) out.push_back(tok);
    return out;
}

}  // namespace

int main(int argc, char** argv) {
    Args args(argc, argv);
    banner("crshe_provider");

    const std::string bundle = args.str("bundle", "deploy");
    const uint16_t port = (uint16_t)args.u64("port", 9101);
    const int threads = args.i32("threads", 0);

    const auto meta = read_meta(bundle + "/public/meta.txt");
    const std::string kind = meta.count("he_kind") ? meta.at("he_kind") : "bfv-openfhe";
    auto he = load_he_backend(kind, read_file(bundle + "/public/he_public.bin"), "");
    Modulus mod(he->plaintext_modulus());

    ProviderState st;
    st.n_tags = std::strtoull(meta.at("n_tags").c_str(), nullptr, 10);
    st.n_records = std::strtoull(meta.at("n_records").c_str(), nullptr, 10);
    for (const auto& name : split(meta.at("templates"), ',')) {
        FastColumns fc;
        fc.A = unpack_columns(*he, read_file(bundle + "/public/A_" + name + ".bin"));
        fc.A_mac = unpack_columns(*he,
                                  read_file(bundle + "/public/Amac_" + name + ".bin"));
        st.fast[name] = std::move(fc);
    }

    Provider prov(*he, st, mod);
    DpfScheme scheme(mod, 2, st.n_tags);   // only used for its evaluator

    // Warm the homomorphic path on the main thread before serving anything.
    // OpenFHE builds transform tables lazily on first use; triggering that from
    // a freshly spawned connection thread is a hazard, and it would also charge
    // the first client for one-off initialisation that no later query pays.
    {
        std::vector<uint64_t> e(st.n_tags, 0);
        e[0] = 1;
        for (const auto& kv : st.fast) (void)prov.fast_agg(e.data(), kv.first);
        std::fprintf(stderr, "   warmed     : %zu template(s)\n", st.fast.size());
    }

    std::fprintf(stderr,
                 "   bundle    : %s (N=%llu, N_d=%llu, %zu templates)\n"
                 "   he        : %s\n"
                 "   listening : port %u\n",
                 bundle.c_str(), (unsigned long long)st.n_tags,
                 (unsigned long long)st.n_records, st.fast.size(),
                 he->param_string().c_str(), (unsigned)port);

    const int lfd = tcp_listen(port);
    for (;;) {
        const int fd = tcp_accept(lfd);
        if (fd < 0) continue;
        std::thread([fd, &prov, &scheme, &st, &he, threads] {
            try {
                for (;;) {
                    const std::string op = recv_msg(fd);
                    if (op.empty()) break;
                    if (op == "ping") { send_msg(fd, "pong"); continue; }
                    if (op != "agg") break;
                    const std::string tmpl = recv_msg(fd);
                    const std::string party_s = recv_msg(fd);
                    const std::string keyblob = recv_msg(fd);
                    (void)party_s;

                    const double t0 = now_ms();
                    // A provider evaluates whatever key it is handed. The shape
                    // check inside deserialize_token_key rejects garbage, but
                    // it is not a proof that the function is a point function
                    // -- see apps/attack_malformed_key.cpp.
                    const Token tok = deserialize_token_key(keyblob);
                    std::vector<uint64_t> e(st.n_tags);
                    scheme.eval_full(tok, 0, e.data(), st.n_tags, threads);
                    const AggResponse r = prov.fast_agg(e.data(), tmpl);
                    const double ms = now_ms() - t0;

                    send_msg(fd, std::to_string(ms));
                    send_msg(fd, he->serialize(r.ct));
                    send_msg(fd, he->serialize(r.ct_mac));
                }
            } catch (const std::exception& ex) {
                std::fprintf(stderr, "[conn] %s\n", ex.what());
            }
            ::close(fd);
        }).detach();
    }
}
