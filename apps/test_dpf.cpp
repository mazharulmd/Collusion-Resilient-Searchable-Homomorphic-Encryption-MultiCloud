// SPDX-License-Identifier: Apache-2.0
//
// Go/no-go test for Phase 1.  Nothing downstream is meaningful unless this
// passes: it checks, exhaustively on small domains and by sampling on large
// ones, that the shares of every party sum to the point function at *every*
// point of the domain, over Z_p rather than over Z_{2^k}.

#include <cstdio>
#include <cstdlib>
#include <random>
#include <vector>

#include "crshe/dpf.hpp"

using namespace crshe;

static int failures = 0;

static void check(bool ok, const char* what) {
    std::printf("  [%s] %s\n", ok ? "PASS" : "FAIL", what);
    if (!ok) ++failures;
}

int main(int argc, char** argv) {
    const uint64_t p = (argc > 1) ? std::strtoull(argv[1], nullptr, 10) : kDefaultModulus;
    Modulus mod(p);
    std::printf("CR-SHE DPF test\n");
    std::printf("  AES backend : %s\n", aes_backend());
    std::printf("  modulus p   : %llu (%d bits)\n", (unsigned long long)p,
                64 - __builtin_clzll(p));
    if (!is_prime(p)) {
        std::printf("  [FAIL] p is not prime\n");
        return 1;
    }

    std::mt19937_64 rng(12345);
    Dpf2 dpf(mod);

    // ---- exhaustive two-party correctness over the whole domain ----
    for (uint32_t depth : {1u, 2u, 3u, 6u, 10u, 12u}) {
        const uint64_t N = 1ULL << depth;
        bool ok = true;
        const int trials = depth <= 6 ? 64 : 8;
        for (int t = 0; t < trials && ok; ++t) {
            const uint64_t alpha = rng() % N;
            const uint64_t beta = 1 + rng() % (p - 1);
            Dpf2Key k0, k1;
            dpf.gen(alpha, beta, depth, k0, k1);

            std::vector<uint64_t> e0(N), e1(N);
            dpf.eval_full(k0, e0.data(), N, 1);
            dpf.eval_full(k1, e1.data(), N, 1);
            for (uint64_t x = 0; x < N && ok; ++x) {
                const uint64_t sum = mod.add(e0[x], e1[x]);
                const uint64_t want = (x == alpha) ? mod.from_u64(beta) : 0;
                if (sum != want) {
                    std::printf("    mismatch depth=%u alpha=%llu x=%llu got=%llu want=%llu\n",
                                depth, (unsigned long long)alpha, (unsigned long long)x,
                                (unsigned long long)sum, (unsigned long long)want);
                    ok = false;
                }
                // eval() and eval_full() must agree, since the benchmarks use
                // one and the correctness argument uses the other.
                if (ok && dpf.eval(k0, x) != e0[x]) {
                    std::printf("    eval/eval_full disagree at x=%llu\n",
                                (unsigned long long)x);
                    ok = false;
                }
            }
        }
        char buf[128];
        std::snprintf(buf, sizeof buf, "2-party exhaustive, depth=%u (N=%llu)",
                      depth, (unsigned long long)N);
        check(ok, buf);
    }

    // ---- non-power-of-two domain, as used by the real tag index ----
    {
        const uint64_t N = 15347;              // tag count of the primary corpus
        uint32_t depth = 0;
        while ((1ULL << depth) < N) ++depth;
        bool ok = true;
        for (int t = 0; t < 4 && ok; ++t) {
            const uint64_t alpha = rng() % N;
            Dpf2Key k0, k1;
            dpf.gen(alpha, 1, depth, k0, k1);
            std::vector<uint64_t> e0(N), e1(N);
            dpf.eval_full(k0, e0.data(), N, 0);
            dpf.eval_full(k1, e1.data(), N, 0);
            for (uint64_t x = 0; x < N; ++x) {
                const uint64_t want = (x == alpha) ? 1u : 0u;
                if (mod.add(e0[x], e1[x]) != want) { ok = false; break; }
            }
        }
        check(ok, "2-party, truncated domain N=15347, multi-threaded");
    }

    // ---- shares are individually uniform-looking (privacy smoke test) ----
    {
        // Not a proof of anything, but it catches the classic bug of leaving a
        // share unmasked at alpha: party 0's output at alpha would then stand
        // out from the rest of its own output vector.
        const uint32_t depth = 12;
        const uint64_t N = 1ULL << depth;
        Dpf2Key k0, k1;
        dpf.gen(777, 1, depth, k0, k1);
        std::vector<uint64_t> e0(N);
        dpf.eval_full(k0, e0.data(), N, 1);
        size_t small = 0;
        for (uint64_t x = 0; x < N; ++x)
            if (e0[x] < p / 1000) ++small;
        check(small < N / 100, "party-0 share has no structural giveaway at alpha");
    }

    // ---- n-party DPF ----
    {
        DpfN dpfn(mod);
        bool ok = true;
        for (uint32_t n : {2u, 3u, 4u, 5u}) {
            const uint64_t N = 4096;
            const uint64_t alpha = rng() % N;
            const uint64_t beta = 1 + rng() % 1000;
            std::vector<DpfNKey> keys;
            dpfn.gen(alpha, beta, N, n, keys);
            std::vector<uint64_t> acc(N, 0), tmp(N);
            for (uint32_t j = 0; j < n; ++j) {
                dpfn.eval_full(keys[j], tmp.data(), N, 1);
                for (uint64_t x = 0; x < N; ++x) acc[x] = mod.add(acc[x], tmp[x]);
            }
            for (uint64_t x = 0; x < N; ++x) {
                const uint64_t want = (x == alpha) ? mod.from_u64(beta) : 0;
                if (acc[x] != want) {
                    std::printf("    n-party mismatch n=%u x=%llu\n", n,
                                (unsigned long long)x);
                    ok = false;
                    break;
                }
            }
            if (!ok) break;
        }
        check(ok, "n-party DPF, n in {2,3,4,5}");
    }

    // ---- the Lemma 1 trap: wrong output group ----
    {
        // Reproduces the failure the paper warns about.  A DPF whose output
        // group is Z_{2^64} composed with a homomorphic plaintext ring Z_p
        // gives shares that sum to beta mod 2^64, not mod p, so the
        // contraction is wrong exactly when the shares wrap.  We check that
        // our shares really do live in Z_p.
        const uint32_t depth = 10;
        const uint64_t N = 1ULL << depth;
        Dpf2Key k0, k1;
        dpf.gen(3, 1, depth, k0, k1);
        std::vector<uint64_t> e0(N), e1(N);
        dpf.eval_full(k0, e0.data(), N, 1);
        dpf.eval_full(k1, e1.data(), N, 1);
        bool in_range = true;
        for (uint64_t x = 0; x < N; ++x)
            if (e0[x] >= p || e1[x] >= p) in_range = false;
        check(in_range, "all shares are reduced representatives of Z_p (Lemma 1)");
    }

    std::printf("%s\n", failures == 0 ? "ALL DPF TESTS PASSED" : "DPF TESTS FAILED");
    return failures == 0 ? 0 : 1;
}
