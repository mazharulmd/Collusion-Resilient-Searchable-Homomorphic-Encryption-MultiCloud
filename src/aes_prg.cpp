// SPDX-License-Identifier: Apache-2.0
#include "crshe/aes_prg.hpp"

namespace crshe {

const char* aes_backend() {
#if defined(CRSHE_AES_NI)
    return "x86-64 AES-NI";
#elif defined(CRSHE_AES_ARM)
    return "ARMv8 crypto extensions";
#else
    return "portable software AES (SLOW - do not report throughput)";
#endif
}

// ---------------------------------------------------------------------------
// x86-64, AES-NI
// ---------------------------------------------------------------------------
#if defined(CRSHE_AES_NI)

static inline __m128i to_m128(Block b) {
    return _mm_set_epi64x((long long)b.hi, (long long)b.lo);
}
static inline Block from_m128(__m128i v) {
    Block b;
    b.lo = (uint64_t)_mm_cvtsi128_si64(v);
    b.hi = (uint64_t)_mm_cvtsi128_si64(_mm_srli_si128(v, 8));  // SSE2 only
    return b;
}

#define CRSHE_AES_KEY_STEP(k, rcon)                              \
    do {                                                         \
        __m128i t = _mm_aeskeygenassist_si128(k, rcon);           \
        t = _mm_shuffle_epi32(t, 0xff);                           \
        __m128i u = k;                                            \
        u = _mm_xor_si128(u, _mm_slli_si128(u, 4));               \
        u = _mm_xor_si128(u, _mm_slli_si128(u, 4));               \
        u = _mm_xor_si128(u, _mm_slli_si128(u, 4));               \
        k = _mm_xor_si128(u, t);                                  \
    } while (0)

void aes_expand_key(const uint8_t key[16], AesKey& out) {
    __m128i k = _mm_loadu_si128((const __m128i*)key);
    out.rk[0] = k;
    CRSHE_AES_KEY_STEP(k, 0x01); out.rk[1] = k;
    CRSHE_AES_KEY_STEP(k, 0x02); out.rk[2] = k;
    CRSHE_AES_KEY_STEP(k, 0x04); out.rk[3] = k;
    CRSHE_AES_KEY_STEP(k, 0x08); out.rk[4] = k;
    CRSHE_AES_KEY_STEP(k, 0x10); out.rk[5] = k;
    CRSHE_AES_KEY_STEP(k, 0x20); out.rk[6] = k;
    CRSHE_AES_KEY_STEP(k, 0x40); out.rk[7] = k;
    CRSHE_AES_KEY_STEP(k, 0x80); out.rk[8] = k;
    CRSHE_AES_KEY_STEP(k, 0x1b); out.rk[9] = k;
    CRSHE_AES_KEY_STEP(k, 0x36); out.rk[10] = k;
}

Block aes_encrypt_block(const AesKey& k, Block in) {
    __m128i x = _mm_xor_si128(to_m128(in), k.rk[0]);
    x = _mm_aesenc_si128(x, k.rk[1]);
    x = _mm_aesenc_si128(x, k.rk[2]);
    x = _mm_aesenc_si128(x, k.rk[3]);
    x = _mm_aesenc_si128(x, k.rk[4]);
    x = _mm_aesenc_si128(x, k.rk[5]);
    x = _mm_aesenc_si128(x, k.rk[6]);
    x = _mm_aesenc_si128(x, k.rk[7]);
    x = _mm_aesenc_si128(x, k.rk[8]);
    x = _mm_aesenc_si128(x, k.rk[9]);
    x = _mm_aesenclast_si128(x, k.rk[10]);
    return from_m128(x);
}

void aes_encrypt_4(const AesKey& k, Block in[4], Block out[4]) {
    __m128i x0 = _mm_xor_si128(to_m128(in[0]), k.rk[0]);
    __m128i x1 = _mm_xor_si128(to_m128(in[1]), k.rk[0]);
    __m128i x2 = _mm_xor_si128(to_m128(in[2]), k.rk[0]);
    __m128i x3 = _mm_xor_si128(to_m128(in[3]), k.rk[0]);
    for (int r = 1; r <= 9; ++r) {
        x0 = _mm_aesenc_si128(x0, k.rk[r]);
        x1 = _mm_aesenc_si128(x1, k.rk[r]);
        x2 = _mm_aesenc_si128(x2, k.rk[r]);
        x3 = _mm_aesenc_si128(x3, k.rk[r]);
    }
    out[0] = from_m128(_mm_aesenclast_si128(x0, k.rk[10]));
    out[1] = from_m128(_mm_aesenclast_si128(x1, k.rk[10]));
    out[2] = from_m128(_mm_aesenclast_si128(x2, k.rk[10]));
    out[3] = from_m128(_mm_aesenclast_si128(x3, k.rk[10]));
}

// Four blocks under two different keys: lanes 0,2 use kl_, lanes 1,3 use kr_.
void PrgKeys::aes_encrypt_2x2(Block in[4], Block out[4]) const {
    __m128i x0 = _mm_xor_si128(to_m128(in[0]), kl_.rk[0]);
    __m128i x1 = _mm_xor_si128(to_m128(in[1]), kr_.rk[0]);
    __m128i x2 = _mm_xor_si128(to_m128(in[2]), kl_.rk[0]);
    __m128i x3 = _mm_xor_si128(to_m128(in[3]), kr_.rk[0]);
    for (int r = 1; r <= 9; ++r) {
        x0 = _mm_aesenc_si128(x0, kl_.rk[r]);
        x1 = _mm_aesenc_si128(x1, kr_.rk[r]);
        x2 = _mm_aesenc_si128(x2, kl_.rk[r]);
        x3 = _mm_aesenc_si128(x3, kr_.rk[r]);
    }
    out[0] = from_m128(_mm_aesenclast_si128(x0, kl_.rk[10]));
    out[1] = from_m128(_mm_aesenclast_si128(x1, kr_.rk[10]));
    out[2] = from_m128(_mm_aesenclast_si128(x2, kl_.rk[10]));
    out[3] = from_m128(_mm_aesenclast_si128(x3, kr_.rk[10]));
}

// ---------------------------------------------------------------------------
// AArch64, ARMv8 crypto extensions
// ---------------------------------------------------------------------------
#elif defined(CRSHE_AES_ARM)

static const uint8_t kSbox[256] = {
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16};

static void expand_key_bytes(const uint8_t key[16], uint8_t rk[11][16]) {
    static const uint8_t rcon[10] = {0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36};
    std::memcpy(rk[0], key, 16);
    for (int i = 1; i <= 10; ++i) {
        const uint8_t* prev = rk[i - 1];
        uint8_t t[4] = {kSbox[prev[13]], kSbox[prev[14]], kSbox[prev[15]], kSbox[prev[12]]};
        t[0] ^= rcon[i - 1];
        for (int j = 0; j < 4; ++j) rk[i][j] = prev[j] ^ t[j];
        for (int w = 1; w < 4; ++w)
            for (int j = 0; j < 4; ++j)
                rk[i][4 * w + j] = rk[i][4 * (w - 1) + j] ^ prev[4 * w + j];
    }
}

void aes_expand_key(const uint8_t key[16], AesKey& out) {
    uint8_t rk[11][16];
    expand_key_bytes(key, rk);
    for (int i = 0; i <= 10; ++i) out.rk[i] = vld1q_u8(rk[i]);
}

static inline uint8x16_t to_neon(Block b) {
    uint64_t v[2] = {b.lo, b.hi};
    return vreinterpretq_u8_u64(vld1q_u64(v));
}
static inline Block from_neon(uint8x16_t x) {
    uint64_t v[2];
    vst1q_u64(v, vreinterpretq_u64_u8(x));
    return Block{v[0], v[1]};
}

Block aes_encrypt_block(const AesKey& k, Block in) {
    uint8x16_t x = to_neon(in);
    for (int r = 0; r <= 8; ++r) x = vaesmcq_u8(vaeseq_u8(x, k.rk[r]));
    x = vaeseq_u8(x, k.rk[9]);
    x = veorq_u8(x, k.rk[10]);
    return from_neon(x);
}

void aes_encrypt_4(const AesKey& k, Block in[4], Block out[4]) {
    uint8x16_t x0 = to_neon(in[0]), x1 = to_neon(in[1]);
    uint8x16_t x2 = to_neon(in[2]), x3 = to_neon(in[3]);
    for (int r = 0; r <= 8; ++r) {
        x0 = vaesmcq_u8(vaeseq_u8(x0, k.rk[r]));
        x1 = vaesmcq_u8(vaeseq_u8(x1, k.rk[r]));
        x2 = vaesmcq_u8(vaeseq_u8(x2, k.rk[r]));
        x3 = vaesmcq_u8(vaeseq_u8(x3, k.rk[r]));
    }
    out[0] = from_neon(veorq_u8(vaeseq_u8(x0, k.rk[9]), k.rk[10]));
    out[1] = from_neon(veorq_u8(vaeseq_u8(x1, k.rk[9]), k.rk[10]));
    out[2] = from_neon(veorq_u8(vaeseq_u8(x2, k.rk[9]), k.rk[10]));
    out[3] = from_neon(veorq_u8(vaeseq_u8(x3, k.rk[9]), k.rk[10]));
}

void PrgKeys::aes_encrypt_2x2(Block in[4], Block out[4]) const {
    uint8x16_t x0 = to_neon(in[0]), x1 = to_neon(in[1]);
    uint8x16_t x2 = to_neon(in[2]), x3 = to_neon(in[3]);
    for (int r = 0; r <= 8; ++r) {
        x0 = vaesmcq_u8(vaeseq_u8(x0, kl_.rk[r]));
        x1 = vaesmcq_u8(vaeseq_u8(x1, kr_.rk[r]));
        x2 = vaesmcq_u8(vaeseq_u8(x2, kl_.rk[r]));
        x3 = vaesmcq_u8(vaeseq_u8(x3, kr_.rk[r]));
    }
    out[0] = from_neon(veorq_u8(vaeseq_u8(x0, kl_.rk[9]), kl_.rk[10]));
    out[1] = from_neon(veorq_u8(vaeseq_u8(x1, kr_.rk[9]), kr_.rk[10]));
    out[2] = from_neon(veorq_u8(vaeseq_u8(x2, kl_.rk[9]), kl_.rk[10]));
    out[3] = from_neon(veorq_u8(vaeseq_u8(x3, kr_.rk[9]), kr_.rk[10]));
}

// ---------------------------------------------------------------------------
// Portable software AES-128
// ---------------------------------------------------------------------------
#else

static const uint8_t kSbox[256] = {
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16};

static inline uint8_t xtime(uint8_t x) { return (uint8_t)((x << 1) ^ ((x >> 7) * 0x1b)); }

void aes_expand_key(const uint8_t key[16], AesKey& out) {
    static const uint8_t rcon[10] = {0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36};
    std::memcpy(out.rk[0], key, 16);
    for (int i = 1; i <= 10; ++i) {
        const uint8_t* prev = out.rk[i - 1];
        uint8_t t[4] = {kSbox[prev[13]], kSbox[prev[14]], kSbox[prev[15]], kSbox[prev[12]]};
        t[0] ^= rcon[i - 1];
        for (int j = 0; j < 4; ++j) out.rk[i][j] = prev[j] ^ t[j];
        for (int w = 1; w < 4; ++w)
            for (int j = 0; j < 4; ++j)
                out.rk[i][4 * w + j] = out.rk[i][4 * (w - 1) + j] ^ prev[4 * w + j];
    }
}

Block aes_encrypt_block(const AesKey& k, Block in) {
    uint8_t s[16];
    std::memcpy(s, &in.lo, 8);
    std::memcpy(s + 8, &in.hi, 8);
    for (int j = 0; j < 16; ++j) s[j] ^= k.rk[0][j];
    for (int r = 1; r <= 10; ++r) {
        for (int j = 0; j < 16; ++j) s[j] = kSbox[s[j]];
        uint8_t t[16];
        for (int c = 0; c < 4; ++c)
            for (int row = 0; row < 4; ++row)
                t[4 * c + row] = s[4 * ((c + row) & 3) + row];
        std::memcpy(s, t, 16);
        if (r != 10) {
            for (int c = 0; c < 4; ++c) {
                uint8_t* p = s + 4 * c;
                uint8_t a0 = p[0], a1 = p[1], a2 = p[2], a3 = p[3];
                uint8_t x = a0 ^ a1 ^ a2 ^ a3;
                p[0] = a0 ^ x ^ xtime(a0 ^ a1);
                p[1] = a1 ^ x ^ xtime(a1 ^ a2);
                p[2] = a2 ^ x ^ xtime(a2 ^ a3);
                p[3] = a3 ^ x ^ xtime(a3 ^ a0);
            }
        }
        for (int j = 0; j < 16; ++j) s[j] ^= k.rk[r][j];
    }
    Block out;
    std::memcpy(&out.lo, s, 8);
    std::memcpy(&out.hi, s + 8, 8);
    return out;
}

void aes_encrypt_4(const AesKey& k, Block in[4], Block out[4]) {
    for (int i = 0; i < 4; ++i) out[i] = aes_encrypt_block(k, in[i]);
}

void PrgKeys::aes_encrypt_2x2(Block in[4], Block out[4]) const {
    out[0] = aes_encrypt_block(kl_, in[0]);
    out[1] = aes_encrypt_block(kr_, in[1]);
    out[2] = aes_encrypt_block(kl_, in[2]);
    out[3] = aes_encrypt_block(kr_, in[3]);
}

#endif

// ---------------------------------------------------------------------------
// Shared, backend-independent parts
// ---------------------------------------------------------------------------

PrgKeys::PrgKeys() {
    // Nothing-up-my-sleeve constants. These are public protocol parameters:
    // the PRG keys of a fixed-key AES construction are not secret.
    static const uint8_t KL[16] = {0x00,0x11,0x22,0x33,0x44,0x55,0x66,0x77,
                                   0x88,0x99,0xaa,0xbb,0xcc,0xdd,0xee,0xff};
    static const uint8_t KR[16] = {0x0f,0x1e,0x2d,0x3c,0x4b,0x5a,0x69,0x78,
                                   0x87,0x96,0xa5,0xb4,0xc3,0xd2,0xe1,0xf0};
    static const uint8_t KC[16] = {0xa5,0x5a,0xc3,0x3c,0x96,0x69,0xf0,0x0f,
                                   0x12,0x34,0x56,0x78,0x9a,0xbc,0xde,0xf0};
    aes_expand_key(KL, kl_);
    aes_expand_key(KR, kr_);
    aes_expand_key(KC, kc_);
}

CtrPrf::CtrPrf(const uint8_t key[16]) { aes_expand_key(key, k_); }

void CtrPrf::stream(uint64_t start, uint64_t* out, size_t n) const {
    size_t i = 0;
    // Four counters at a time to keep the AES pipeline full: each AES block
    // yields two 64-bit words, so one batch produces eight outputs.
    uint64_t ctr = start / 2;
    if (start & 1ULL) {
        Block b = aes_encrypt_block(k_, Block{ctr, 0});
        out[i++] = b.hi;
        ++ctr;
    }
    while (i + 8 <= n) {
        Block in[4] = {Block{ctr, 0}, Block{ctr + 1, 0}, Block{ctr + 2, 0}, Block{ctr + 3, 0}};
        Block o[4];
        aes_encrypt_4(k_, in, o);
        out[i + 0] = o[0].lo; out[i + 1] = o[0].hi;
        out[i + 2] = o[1].lo; out[i + 3] = o[1].hi;
        out[i + 4] = o[2].lo; out[i + 5] = o[2].hi;
        out[i + 6] = o[3].lo; out[i + 7] = o[3].hi;
        i += 8;
        ctr += 4;
    }
    while (i < n) {
        Block b = aes_encrypt_block(k_, Block{ctr, 0});
        out[i++] = b.lo;
        if (i < n) out[i++] = b.hi;
        ++ctr;
    }
}

}  // namespace crshe
