// SPDX-License-Identifier: Apache-2.0
//
// E7: what masking and the correction columns cost.
//
// Reports, per provider: the storage of the masked index against the plaintext
// bitmap it replaces, the storage of the encrypted A_f / U_f / G_f columns,
// the one-off precomputation time for each, and the per-query overhead the
// mask correction adds to the general path.  Also E8's ingest-side number:
// how long it takes to encrypt the whole corpus.
//
//   build/bench_setup --data=data/telemetry.crshe --nd=1000,10000,100000 \
//                     --out=bench/results/e7_setup.csv

#include <cstdio>
#include <vector>

#include "crshe/bench_util.hpp"
#include "crshe/dataset.hpp"
#include "crshe/index.hpp"
#include "crshe/protocol.hpp"

using namespace crshe;

int main(int argc, char** argv) {
    Args args(argc, argv);
    banner("bench_setup (E7)");

    const std::string data = args.str("data", "");
    const auto nds = args.list("nd", {1000, 10000, 100000});
    const int threads = args.i32("threads", 0);
    const std::string out = args.str("out", "bench/results/e7_setup.csv");

    auto he = he_from_args(args);
    Modulus mod(he->plaintext_modulus());

    Dataset full = data.empty()
                       ? Dataset::synthetic(args.u64("ntags", 15347),
                                            args.u64("ntotal", 405184), 1.15, 99)
                       : Dataset::load(data);

    Csv csv(out, {"N", "Nd", "template", "masked_index_bytes",
                  "plaintext_bitmap_bytes", "mask_expansion_x",
                  "A_column_ct_count", "A_column_bytes", "U_column_bytes",
                  "encrypt_corpus_ms", "compute_A_ms", "compute_U_ms",
                  "build_masked_index_ms", "mask_prf_values",
                  "mask_throughput_Mvals_per_s", "he_params", "cpu", "threads"});

    for (uint64_t nd : nds) {
        Dataset ds = full.subsample_records(nd);
        Owner owner(ds, mod, 1234);
        const auto templates = default_templates(ds, 7);

        const Stat enc = repeat(3, [&] {
            std::vector<uint64_t> m(ds.n_records);
            for (uint64_t i = 0; i < ds.n_records; ++i) m[i] = mod.from_u64(ds.values[i]);
            (void)he->encrypt_vector(m);
        }, 0);

        const unsigned __int128 need = masked_index_bytes(ds.n_tags, nd);
        const uint64_t avail = available_ram_bytes();
        double idx_ms = 0;
        uint64_t idx_bytes = 0;
        if (!avail || need < (unsigned __int128)avail / 2) {
            const Stat ix = repeat(1, [&] {
                (void)owner.build_masked_index(nd, threads);
            }, 0);
            idx_ms = ix.median;
            idx_bytes = (uint64_t)need;
        }

        for (const auto& f : templates) {
            const Stat sa = repeat(3, [&] { (void)owner.compute_A(f); }, 0);
            const Stat su = repeat(1, [&] { (void)owner.compute_U(f, nd, threads); }, 0);

            const auto A = owner.compute_A(f);
            const auto ctA = he->encrypt_vector(A);
            size_t abytes = 0;
            for (const auto& c : ctA) abytes += he->serialize(c).size();

            const uint64_t bitmap = (ds.n_tags * nd + 7) / 8;
            const uint64_t maskvals = ds.n_tags * nd;

            csv.row(ds.n_tags, nd, f.name, idx_bytes, bitmap,
                    bitmap ? (double)need / (double)bitmap : 0.0,
                    (uint64_t)ctA.size(), (uint64_t)abytes, (uint64_t)abytes,
                    enc.median, sa.median, su.median, idx_ms, maskvals,
                    su.median > 0 ? (double)maskvals / (su.median / 1000.0) / 1e6 : 0.0,
                    he->param_string(), cpu_model(),
                    (uint64_t)(threads ? threads : max_threads()));
            std::fprintf(stderr,
                         "Nd=%-8llu f=%-9s  A=%7.1f ms  U=%9.1f ms  I'=%8.1f ms  "
                         "A_ct=%zu (%.1f MB)\n",
                         (unsigned long long)nd, f.name.c_str(), sa.median, su.median,
                         idx_ms, ctA.size(), abytes / 1e6);
        }
    }
    return 0;
}
