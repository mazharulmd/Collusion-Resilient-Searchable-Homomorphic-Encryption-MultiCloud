// SPDX-License-Identifier: Apache-2.0
//
// Fixed-key AES-128 used as the DPF pseudorandom generator and as the PRF F'
// for the one-time-pad index mask.
//
// Three code paths, selected at compile time and reported at run time by
// crshe::aes_backend():
//   * x86-64 with AES-NI          (CRSHE_AES_NI)
//   * AArch64 with ARMv8 crypto   (CRSHE_AES_ARM)
//   * portable software AES-128   (CRSHE_AES_SOFT)  -- correctness only,
//                                                      never use for reported
//                                                      throughput numbers.
//
// The PRG is the Matyas-Meyer-Oseas construction G(s) = AES_k(s) XOR s with
// three independent fixed keys, giving two child seeds and one conversion
// block per node.  This is the standard instantiation used by BGI16 and by
// every fast FSS implementation; a hash-based PRG (as in the v1 prototype)
// costs two to three orders of magnitude more per node.

#pragma once

#include <cstdint>
#include <cstddef>
#include <cstring>
#include <string>

#if defined(__x86_64__) || defined(_M_X64)
#include <wmmintrin.h>
#include <emmintrin.h>
#define CRSHE_AES_NI 1
#elif defined(__aarch64__) && defined(__ARM_FEATURE_CRYPTO)
#include <arm_neon.h>
#define CRSHE_AES_ARM 1
#else
#define CRSHE_AES_SOFT 1
#endif

namespace crshe {

// A 128-bit block. Kept as a plain POD so it can live in flat arrays.
struct Block {
    uint64_t lo = 0;
    uint64_t hi = 0;
};

inline Block block_xor(const Block& a, const Block& b) {
    return Block{a.lo ^ b.lo, a.hi ^ b.hi};
}
inline bool block_eq(const Block& a, const Block& b) {
    return a.lo == b.lo && a.hi == b.hi;
}
inline Block block_from_u64(uint64_t x) { return Block{x, 0}; }

const char* aes_backend();

// ---------------------------------------------------------------------------
// AES-128 key schedule + single-block encryption.
// ---------------------------------------------------------------------------

struct AesKey {
#if defined(CRSHE_AES_NI)
    __m128i rk[11];
#elif defined(CRSHE_AES_ARM)
    uint8x16_t rk[11];
#else
    uint8_t rk[11][16];
#endif
};

void aes_expand_key(const uint8_t key[16], AesKey& out);
Block aes_encrypt_block(const AesKey& k, Block in);

// Encrypt four independent blocks. On AES-NI/ARM this interleaves the rounds so
// the four chains fill the AES pipeline; this is where most of the throughput
// comes from and it is why the DPF evaluator batches nodes in groups of two
// (two children per node -> four PRG outputs per pair of nodes).
void aes_encrypt_4(const AesKey& k, Block in[4], Block out[4]);

// ---------------------------------------------------------------------------
// The DPF pseudorandom generator: three fixed keys, MMO.
// ---------------------------------------------------------------------------

class PrgKeys {
public:
    PrgKeys();  // deterministic, protocol-wide constants (public by design)
    // G(s) -> (left child, right child).  Control bits are the LSBs.
    inline void expand(Block s, Block& l, Block& r) const {
        l = block_xor(aes_encrypt_block(kl_, s), s);
        r = block_xor(aes_encrypt_block(kr_, s), s);
    }
    // Two nodes at once: fills the AES pipeline with four independent blocks.
    inline void expand2(Block s0, Block s1,
                        Block& l0, Block& r0, Block& l1, Block& r1) const {
        Block in[4] = {s0, s0, s1, s1};
        Block out[4];
        aes_encrypt_2x2(in, out);
        l0 = block_xor(out[0], s0);
        r0 = block_xor(out[1], s0);
        l1 = block_xor(out[2], s1);
        r1 = block_xor(out[3], s1);
    }
    // Convert(s): the leaf-to-group map. Returns 128 pseudorandom bits; the
    // caller reduces them into Z_p.
    inline Block convert(Block s) const {
        return block_xor(aes_encrypt_block(kc_, s), s);
    }
    // Four leaves at once. The leaf pass is one AES per leaf with no data
    // dependence between leaves, so batching it is pure throughput.
    inline void convert4(const Block in[4], Block out[4]) const {
        Block tmp[4] = {in[0], in[1], in[2], in[3]};
        aes_encrypt_4(kc_, tmp, out);
        for (int i = 0; i < 4; ++i) out[i] = block_xor(out[i], in[i]);
    }

private:
    void aes_encrypt_2x2(Block in[4], Block out[4]) const;
    AesKey kl_, kr_, kc_;
};

// ---------------------------------------------------------------------------
// AES in counter mode, used as the PRF F' for the index mask P[x][i] and as
// the share PRG of the n-party DPF.  One AES call yields 128 bits = two
// 64-bit words, so the 6.2e9 mask values of the full-scale index cost about
// 3.1e9 AES calls rather than 6.2e9.
// ---------------------------------------------------------------------------

class CtrPrf {
public:
    explicit CtrPrf(const uint8_t key[16]);
    // Fill out[0..n) with the counter-mode keystream starting at `start`.
    void stream(uint64_t start, uint64_t* out, size_t n) const;

private:
    AesKey k_;
};

}  // namespace crshe
