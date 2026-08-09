// SPDX-License-Identifier: Apache-2.0
//
// E1: per-provider selection latency vs domain size N, at 1..T cores, plus the
// measured DPF key size.  This is the symmetric-key half of a query; the
// homomorphic half is bench_agg.
//
//   build/bench_dpf --N=1000,10000,15347,100000,1000000 --threads=1,8,16,32 \
//                   --reps=11 --out=bench/results/e1_dpf.csv

#include <cstdio>
#include <random>
#include <vector>

#include "crshe/bench_util.hpp"
#include "crshe/protocol.hpp"

using namespace crshe;

int main(int argc, char** argv) {
    Args args(argc, argv);
    banner("bench_dpf (E1)");

    const auto Ns = args.list("N", {1000, 10000, 15347, 100000, 1000000});
    auto threads = args.list("threads", {1, (uint64_t)max_threads()});
    const int reps = args.i32("reps", 11);
    const uint64_t p = args.u64("p", kDefaultModulus);
    const std::string out = args.str("out", "bench/results/e1_dpf.csv");
    Modulus mod(p);

    Csv csv(out, {"N", "n_parties", "threads", "construction", "eval_ms_median",
                  "eval_ms_p25", "eval_ms_p75", "eval_ms_min", "eval_ms_max",
                  "reps", "key_bytes_party0", "key_bytes_max",
                  "uplink_bytes_total", "evals_per_sec", "cpu", "aes", "p"});

    std::mt19937_64 rng(2024);
    for (uint64_t N : Ns) {
        for (uint32_t n_parties : {2u, 3u, 4u}) {
            // n = 2 is measured under both constructions, so the succinct-key
            // and explicit-share instantiations sit on the same axes.
            for (int variant = 0; variant < (n_parties == 2 ? 2 : 1); ++variant) {
                const bool force_nparty = (variant == 1);
                DpfScheme scheme(mod, n_parties, N, force_nparty);
                const char* cname = scheme.succinct() ? "bgi16-tree" : "nparty-explicit";

                Token tok;
                scheme.gen(rng() % N, 1, tok);

                size_t kmax = 0;
                for (uint32_t j = 0; j < n_parties; ++j)
                    kmax = std::max(kmax, tok.key_bytes(j));

                for (uint64_t t : threads) {
                    std::vector<uint64_t> e(N);
                    // The client waits on the slowest provider, so report the
                    // worst party rather than party 0: under the n-party
                    // construction the seed parties expand a keystream while
                    // the explicit-share party only copies, and averaging the
                    // two would flatter the scheme.
                    Stat s{};
                    for (uint32_t j = 0; j < n_parties; ++j) {
                        const Stat sj = repeat(reps, [&] {
                            scheme.eval_full(tok, j, e.data(), N, (int)t);
                        });
                        if (sj.median > s.median) s = sj;
                    }
                    csv.row(N, (uint64_t)n_parties, t, cname, s.median, s.p25, s.p75,
                            s.min, s.max, reps, (uint64_t)tok.key_bytes(0),
                            (uint64_t)kmax, (uint64_t)tok.uplink_bytes(),
                            (double)N / (s.median / 1000.0), cpu_model(), aes_backend(),
                            p);
                    std::fprintf(stderr,
                                 "N=%-8llu n=%u %-16s t=%-3llu  %8.3f ms  "
                                 "key0=%zu B keymax=%zu B\n",
                                 (unsigned long long)N, n_parties, cname,
                                 (unsigned long long)t, s.median, tok.key_bytes(0), kmax);
                }
            }
        }
    }
    return 0;
}
