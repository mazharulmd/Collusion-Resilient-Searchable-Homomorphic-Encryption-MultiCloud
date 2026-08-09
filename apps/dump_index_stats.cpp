// SPDX-License-Identifier: Apache-2.0
//
// Feeds E6.  Emits, for every tag, the two statistics a coalition could
// actually observe at rest:
//
//   unmasked_weight  the row Hamming weight of I, i.e. the posting-list length
//                    -- what a replicated *unmasked* index exposes;
//   masked_rowsum    sum_i I'[x][i] mod p, computed with the real PRF F' --
//                    what CR-SHE's masked index exposes.
//
// python/leakage_attack.py mounts a frequency/volume attack against each.
// Computing the masked statistic honestly means evaluating N x N_d PRF outputs,
// which is why it lives here and not in Python.
//
//   build/dump_index_stats --data=data/telemetry.crshe \
//                          --out=bench/results/e6_index_stats.csv

#include <cstdio>
#include <vector>

#include "crshe/bench_util.hpp"
#include "crshe/dataset.hpp"
#include "crshe/index.hpp"

#ifdef _OPENMP
#include <omp.h>
#endif

using namespace crshe;

int main(int argc, char** argv) {
    Args args(argc, argv);
    banner("dump_index_stats (E6 input)");

    const std::string data = args.str("data", "");
    const uint64_t nd_arg = args.u64("nd", 0);
    const std::string out = args.str("out", "bench/results/e6_index_stats.csv");
    Modulus mod(args.u64("p", kDefaultModulus));

    Dataset ds = data.empty()
                     ? Dataset::synthetic(args.u64("ntags", 15347),
                                          args.u64("ntotal", 405184), 1.15, 99)
                     : Dataset::load(data);
    if (nd_arg) ds = ds.subsample_records(nd_arg);
    const uint64_t nd = ds.n_records;

    Owner owner(ds, mod, args.u64("seed", 1234));

    std::vector<uint64_t> weight(ds.n_tags), rowsum(ds.n_tags);
    std::fprintf(stderr, "   computing %llu x %llu = %.2e PRF values...\n",
                 (unsigned long long)ds.n_tags, (unsigned long long)nd,
                 (double)ds.n_tags * (double)nd);
    const double t0 = now_ms();

#ifdef _OPENMP
#pragma omp parallel
#endif
    {
        std::vector<uint64_t> row(nd);
#ifdef _OPENMP
#pragma omp for schedule(static)
#endif
        for (long long xx = 0; xx < (long long)ds.n_tags; ++xx) {
            const uint64_t x = (uint64_t)xx;
            owner.mask_row(x, nd, row.data());
            uint64_t acc = 0;
            for (uint64_t i = 0; i < nd; ++i) acc = mod.add(acc, row[i]);
            // The membership bits land on top of the pad.
            uint64_t w = 0;
            for (uint64_t k = ds.offset[x]; k < ds.offset[x + 1]; ++k) {
                if (ds.postings[k] < nd) { acc = mod.add(acc, 1); ++w; }
            }
            weight[x] = w;
            rowsum[x] = acc;
        }
    }
    std::fprintf(stderr, "   done in %.1f s\n", (now_ms() - t0) / 1000.0);

    Csv csv(out, {"tag_index", "tag_name", "unmasked_weight", "masked_rowsum", "p",
                  "N", "Nd"});
    for (uint64_t x = 0; x < ds.n_tags; ++x) {
        const std::string name = x < ds.tag_names.size() && !ds.tag_names[x].empty()
                                     ? ds.tag_names[x]
                                     : ("tag" + std::to_string(x));
        csv.row(x, name, weight[x], rowsum[x], mod.value(), ds.n_tags, nd);
    }
    return 0;
}
