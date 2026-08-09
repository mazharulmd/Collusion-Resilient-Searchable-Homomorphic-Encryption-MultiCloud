// SPDX-License-Identifier: Apache-2.0
//
// Arithmetic in Z_p, where p is *simultaneously* the DPF output group and the
// BFV plaintext modulus.  Lemma 1 of the paper is exactly the requirement that
// these two moduli be the same ring; instantiating the DPF over Z_{2^k} and the
// homomorphic scheme over an unrelated plaintext modulus silently breaks
// correctness through wraparound, so there is a single modulus type here and
// every component takes it from the same place.

#pragma once

#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

namespace crshe {

// Default plaintext modulus.  Prime, and p = 1 (mod 131072), so BFV batching
// is available for every ring dimension up to 65536.  ~2^36.0, which leaves
// 33x headroom over the largest admissible aggregate of the primary corpus
// (max posting list 404702 x max scaled reading 5000 ~ 2.02e9).
inline constexpr uint64_t kDefaultModulus = 68724326401ULL;

class Modulus {
public:
    Modulus() : Modulus(kDefaultModulus) {}
    explicit Modulus(uint64_t p) : p_(p) {
        if (p < 3) throw std::invalid_argument("modulus too small");
        if (p >= (1ULL << 62)) throw std::invalid_argument("modulus must be < 2^62");
        // Barrett constant floor(2^128 / p) is unnecessary while p < 2^62:
        // a single 128-bit division by a compile-time-unknown p is what the
        // compiler emits anyway, so we use the reciprocal form below.
        mu_ = (__uint128_t(-1)) / p;  // floor((2^128 - 1) / p)
    }

    uint64_t value() const { return p_; }

    inline uint64_t reduce(__uint128_t x) const {
        // Barrett: q = floor(x * mu / 2^128) underestimates floor(x / p) by at
        // most 2 for x < 2^128 (by at most 1 for the x < 2^124 that products of
        // two residues produce), so two conditional subtractions are exact.
        __uint128_t q = mulhi128(x, mu_);
        uint64_t r = (uint64_t)(x - q * p_);
        if (r >= p_) r -= p_;
        if (r >= p_) r -= p_;
        return r;
    }

    inline uint64_t add(uint64_t a, uint64_t b) const {
        uint64_t s = a + b;
        return s >= p_ ? s - p_ : s;
    }
    inline uint64_t sub(uint64_t a, uint64_t b) const {
        return a >= b ? a - b : a + p_ - b;
    }
    inline uint64_t neg(uint64_t a) const { return a == 0 ? 0 : p_ - a; }
    inline uint64_t mul(uint64_t a, uint64_t b) const {
        return reduce((__uint128_t)a * b);
    }
    // Reduce a uniformly random 128-bit block into Z_p.  The statistical
    // distance from uniform is < 2^-(128 - log2 p) ~ 2^-92 at the default p,
    // which is why no rejection sampling is needed.
    inline uint64_t from_block(uint64_t lo, uint64_t hi) const {
        return reduce(((__uint128_t)hi << 64) | lo);
    }
    inline uint64_t from_u64(uint64_t x) const { return x % p_; }

    uint64_t pow(uint64_t a, uint64_t e) const {
        uint64_t r = 1;
        a %= p_;
        while (e) {
            if (e & 1) r = mul(r, a);
            a = mul(a, a);
            e >>= 1;
        }
        return r;
    }
    uint64_t inv(uint64_t a) const { return pow(a, p_ - 2); }  // p prime

    // Signed representative in [-p/2, p/2), which is how BFV packed plaintexts
    // are encoded; used when handing values to and from the HE backend.
    int64_t to_signed(uint64_t a) const {
        return a > p_ / 2 ? (int64_t)a - (int64_t)p_ : (int64_t)a;
    }
    uint64_t from_signed(int64_t a) const {
        int64_t m = a % (int64_t)p_;
        if (m < 0) m += (int64_t)p_;
        return (uint64_t)m;
    }

private:
    static inline __uint128_t mulhi128(__uint128_t a, __uint128_t b) {
        uint64_t a_lo = (uint64_t)a, a_hi = (uint64_t)(a >> 64);
        uint64_t b_lo = (uint64_t)b, b_hi = (uint64_t)(b >> 64);
        __uint128_t ll = (__uint128_t)a_lo * b_lo;
        __uint128_t lh = (__uint128_t)a_lo * b_hi;
        __uint128_t hl = (__uint128_t)a_hi * b_lo;
        __uint128_t hh = (__uint128_t)a_hi * b_hi;
        __uint128_t mid = (ll >> 64) + (uint64_t)lh + (uint64_t)hl;
        return hh + (lh >> 64) + (hl >> 64) + (mid >> 64);
    }

    uint64_t p_;
    __uint128_t mu_;
};

// Miller-Rabin, used by the parameter checker so a user who overrides p on the
// command line finds out immediately rather than at decryption time.
bool is_prime(uint64_t n);
// Smallest prime >= start with prime = 1 (mod 2*ring_dim), i.e. NTT-friendly
// for BFV batching at that ring dimension.
uint64_t find_batching_prime(uint64_t start, uint32_t ring_dim);

}  // namespace crshe
