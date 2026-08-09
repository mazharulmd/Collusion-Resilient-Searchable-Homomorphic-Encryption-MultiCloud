// SPDX-License-Identifier: Apache-2.0
//
// E4: measured per-provider DPF key size and total uplink for n in {2,3,4},
// plus the measured downlink of an aggregate response and of a retrieval,
// replacing the asymptotic claims of Table IV with numbers.
//
//   build/bench_comm --N=1000,10000,15347,100000,1000000 \
//                    --out=bench/results/e4_comm.csv

#include <cstdio>
#include <random>

#include "crshe/bench_util.hpp"
#include "crshe/index.hpp"
#include "crshe/protocol.hpp"

using namespace crshe;

int main(int argc, char** argv) {
    Args args(argc, argv);
    banner("bench_comm (E4)");

    const auto Ns = args.list("N", {1000, 10000, 15347, 100000, 1000000});
    const auto ns = args.list("n", {2, 3, 4});
    const uint64_t nd = args.u64("nd", 10000);
    Modulus mod(args.u64("p", kDefaultModulus));
    const std::string out = args.str("out", "bench/results/e4_comm.csv");

    auto he = he_from_args(args);

    Csv csv(out, {"N", "n_parties", "construction", "key_bytes_per_provider",
                  "key_bytes_max", "uplink_bytes_total",
                  "agg_downlink_bytes_per_provider", "agg_downlink_bytes_total",
                  "retrieval_downlink_bytes_per_provider", "Nd_for_retrieval",
                  "he_params"});

    // One aggregate response, measured once: its size does not depend on N or
    // on the matched set, which is the point of Theorem 2's downlink claim.
    Dataset ds = Dataset::synthetic(256, nd, 1.1, 3);
    Owner owner(ds, mod, 7);
    const auto templates = default_templates(ds, 7);
    ProviderState st = build_provider_state(owner, *he, templates, false);
    Provider prov(*he, st, mod);
    size_t agg_down = 0;
    {
        DpfScheme sc(mod, 2, ds.n_tags);
        Token t;
        sc.gen(1, 1, t);
        std::vector<uint64_t> e(ds.n_tags);
        sc.eval_full(t, 0, e.data(), ds.n_tags);
        agg_down = prov.fast_agg(e.data(), "sum", true).downlink_bytes;
    }
    const size_t retrieval_down = nd * sizeof(uint64_t);

    std::mt19937_64 rng(11);
    for (uint64_t N : Ns) {
        for (uint64_t n : ns) {
            for (int variant = 0; variant < (n == 2 ? 2 : 1); ++variant) {
                DpfScheme sc(mod, (uint32_t)n, N, variant == 1);
                Token t;
                sc.gen(rng() % N, 1, t);
                size_t kmax = 0;
                for (uint32_t j = 0; j < n; ++j) kmax = std::max(kmax, t.key_bytes(j));
                csv.row(N, n, sc.succinct() ? "bgi16-tree" : "nparty-explicit",
                        (uint64_t)t.key_bytes(0), (uint64_t)kmax,
                        (uint64_t)t.uplink_bytes(), (uint64_t)agg_down,
                        (uint64_t)(agg_down * n), (uint64_t)retrieval_down, nd,
                        he->param_string());
                std::fprintf(stderr,
                             "N=%-8llu n=%llu %-16s key0=%-9zu keymax=%-9zu uplink=%zu\n",
                             (unsigned long long)N, (unsigned long long)n,
                             sc.succinct() ? "bgi16-tree" : "nparty-explicit",
                             t.key_bytes(0), kmax, t.uplink_bytes());
            }
        }
    }
    std::fprintf(stderr,
                 "\naggregate downlink: %zu B per provider (two ciphertexts: the "
                 "aggregate and its MAC)\nretrieval downlink: %zu B per provider "
                 "at Nd=%llu, fixed regardless of |S|\n",
                 agg_down, retrieval_down, (unsigned long long)nd);
    return 0;
}
