// SPDX-License-Identifier: Apache-2.0
#include "crshe/zp.hpp"

namespace crshe {

namespace {
uint64_t mulmod(uint64_t a, uint64_t b, uint64_t m) {
    return (uint64_t)(((__uint128_t)a * b) % m);
}
uint64_t powmod(uint64_t a, uint64_t e, uint64_t m) {
    uint64_t r = 1;
    a %= m;
    while (e) {
        if (e & 1) r = mulmod(r, a, m);
        a = mulmod(a, a, m);
        e >>= 1;
    }
    return r;
}
}  // namespace

bool is_prime(uint64_t n) {
    if (n < 2) return false;
    for (uint64_t q : {2ULL, 3ULL, 5ULL, 7ULL, 11ULL, 13ULL, 17ULL, 19ULL, 23ULL,
                       29ULL, 31ULL, 37ULL}) {
        if (n % q == 0) return n == q;
    }
    uint64_t d = n - 1;
    int s = 0;
    while ((d & 1) == 0) { d >>= 1; ++s; }
    // Deterministic for all 64-bit n with this witness set.
    for (uint64_t a : {2ULL, 3ULL, 5ULL, 7ULL, 11ULL, 13ULL, 17ULL, 19ULL, 23ULL,
                       29ULL, 31ULL, 37ULL}) {
        uint64_t x = powmod(a, d, n);
        if (x == 1 || x == n - 1) continue;
        bool composite = true;
        for (int i = 1; i < s; ++i) {
            x = mulmod(x, x, n);
            if (x == n - 1) { composite = false; break; }
        }
        if (composite) return false;
    }
    return true;
}

uint64_t find_batching_prime(uint64_t start, uint32_t ring_dim) {
    const uint64_t m = 2ULL * ring_dim;
    uint64_t k = (start + m - 1) / m;
    for (;; ++k) {
        const uint64_t p = k * m + 1;
        if (p > start && is_prime(p)) return p;
    }
}

}  // namespace crshe
