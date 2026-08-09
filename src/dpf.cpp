// SPDX-License-Identifier: Apache-2.0
#include "crshe/dpf.hpp"

#include <cstring>
#include <random>
#include <stdexcept>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace crshe {

namespace {

Block random_block() {
    static thread_local std::random_device rd;
    static thread_local std::mt19937_64 gen(((uint64_t)rd() << 32) ^ rd());
    return Block{gen(), gen()};
}

inline uint8_t lsb(const Block& b) { return (uint8_t)(b.lo & 1ULL); }

// i-th bit of alpha counted from the most significant of `depth` bits, i in [0,depth).
inline uint8_t bit_at(uint64_t alpha, uint32_t i, uint32_t depth) {
    return (uint8_t)((alpha >> (depth - 1 - i)) & 1ULL);
}

}  // namespace

// ---------------------------------------------------------------------------
// Dpf2::gen
// ---------------------------------------------------------------------------

void Dpf2::gen(uint64_t alpha, uint64_t beta, uint32_t depth,
               Dpf2Key& k0, Dpf2Key& k1) const {
    if (depth == 0 || depth > 63) throw std::invalid_argument("bad DPF depth");
    if (alpha >> depth) throw std::invalid_argument("alpha outside domain");

    const Block root0 = random_block();
    const Block root1 = random_block();
    Block s0 = root0;
    Block s1 = root1;
    uint8_t t0 = 0, t1 = 1;

    k0.cw_seed.assign(depth, Block{});
    k0.cw_tl.assign(depth, 0);
    k0.cw_tr.assign(depth, 0);

    for (uint32_t i = 0; i < depth; ++i) {
        Block l0, r0, l1, r1;
        prg_.expand2(s0, s1, l0, r0, l1, r1);
        const uint8_t tl0 = lsb(l0), tr0 = lsb(r0);
        const uint8_t tl1 = lsb(l1), tr1 = lsb(r1);

        const uint8_t a = bit_at(alpha, i, depth);
        // Correct the seed on the "lose" side so the two parties agree there.
        const Block& lose0 = a ? l0 : r0;
        const Block& lose1 = a ? l1 : r1;
        const Block cw_s = block_xor(lose0, lose1);
        const uint8_t cw_tl = (uint8_t)(tl0 ^ tl1 ^ a ^ 1u);
        const uint8_t cw_tr = (uint8_t)(tr0 ^ tr1 ^ a);

        k0.cw_seed[i] = cw_s;
        k0.cw_tl[i] = cw_tl;
        k0.cw_tr[i] = cw_tr;

        const Block& keep0 = a ? r0 : l0;
        const Block& keep1 = a ? r1 : l1;
        const uint8_t kt0 = a ? tr0 : tl0;
        const uint8_t kt1 = a ? tr1 : tl1;
        const uint8_t cw_keep = a ? cw_tr : cw_tl;

        Block ns0 = keep0, ns1 = keep1;
        uint8_t nt0 = kt0, nt1 = kt1;
        if (t0) { ns0 = block_xor(ns0, cw_s); nt0 = (uint8_t)(nt0 ^ cw_keep); }
        if (t1) { ns1 = block_xor(ns1, cw_s); nt1 = (uint8_t)(nt1 ^ cw_keep); }
        s0 = ns0; t0 = nt0;
        s1 = ns1; t1 = nt1;
    }

    // Final correction so that the two shares differ by beta at alpha.
    const Block c0 = prg_.convert(s0);
    const Block c1 = prg_.convert(s1);
    const uint64_t conv0 = mod_.from_block(c0.lo, c0.hi);
    const uint64_t conv1 = mod_.from_block(c1.lo, c1.hi);
    uint64_t cw = mod_.sub(mod_.add(mod_.from_u64(beta), conv1), conv0);
    if (t1) cw = mod_.neg(cw);

    k0.cw_final = cw;
    k0.depth = depth;
    k1 = k0;                 // correction words are identical for both parties
    k0.party = 0; k0.seed = root0;
    k1.party = 1; k1.seed = root1;
}

// ---------------------------------------------------------------------------

uint64_t Dpf2::eval(const Dpf2Key& k, uint64_t x) const {
    Block s = k.seed;
    uint8_t t = k.party;
    for (uint32_t i = 0; i < k.depth; ++i) {
        Block l, r;
        prg_.expand(s, l, r);
        uint8_t tl = lsb(l), tr = lsb(r);
        if (t) {
            l = block_xor(l, k.cw_seed[i]);
            r = block_xor(r, k.cw_seed[i]);
            tl = (uint8_t)(tl ^ k.cw_tl[i]);
            tr = (uint8_t)(tr ^ k.cw_tr[i]);
        }
        if (bit_at(x, i, k.depth)) { s = r; t = tr; }
        else { s = l; t = tl; }
    }
    const Block c = prg_.convert(s);
    uint64_t v = mod_.from_block(c.lo, c.hi);
    if (t) v = mod_.add(v, k.cw_final);
    return k.party ? mod_.neg(v) : v;
}

void Dpf2::eval_full(const Dpf2Key& k, uint64_t* out, size_t n, int threads) const {
    const uint32_t depth = k.depth;
    const size_t full = (size_t)1 << depth;
    if (n > full) throw std::invalid_argument("eval_full: n exceeds domain");

    // Ping-pong buffers so each level can be filled in parallel.
    std::vector<Block> cur(1), nxt;
    std::vector<uint8_t> tcur(1), tnxt;
    cur[0] = k.seed;
    tcur[0] = k.party;

    for (uint32_t lvl = 0; lvl < depth; ++lvl) {
        const size_t width = (size_t)1 << lvl;
        // Only the leaves below index n can matter; prune the rest. At level
        // lvl a node covers 2^(depth-lvl) leaves.
        const size_t span = (size_t)1 << (depth - lvl);
        const size_t live = (n + span - 1) / span;
        const size_t w = width < live ? width : live;

        nxt.resize(2 * w);
        tnxt.resize(2 * w);
        const Block cw_s = k.cw_seed[lvl];
        const uint8_t cw_tl = k.cw_tl[lvl];
        const uint8_t cw_tr = k.cw_tr[lvl];

        // Two nodes per iteration: expand2 issues four independent AES chains,
        // which is what keeps the AES pipeline full. Processing one node at a
        // time leaves it stalled on a two-deep dependency and costs roughly a
        // factor of two on the whole selection pass.
        const size_t wpair = w & ~(size_t)1;
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(threads > 0 ? threads : omp_get_max_threads()) if (w > 4096)
#endif
        for (long long jj = 0; jj < (long long)wpair; jj += 2) {
            const size_t j = (size_t)jj;
            Block l0, r0, l1, r1;
            prg_.expand2(cur[j], cur[j + 1], l0, r0, l1, r1);
            uint8_t tl0 = lsb(l0), tr0 = lsb(r0), tl1 = lsb(l1), tr1 = lsb(r1);
            if (tcur[j]) {
                l0 = block_xor(l0, cw_s); r0 = block_xor(r0, cw_s);
                tl0 = (uint8_t)(tl0 ^ cw_tl); tr0 = (uint8_t)(tr0 ^ cw_tr);
            }
            if (tcur[j + 1]) {
                l1 = block_xor(l1, cw_s); r1 = block_xor(r1, cw_s);
                tl1 = (uint8_t)(tl1 ^ cw_tl); tr1 = (uint8_t)(tr1 ^ cw_tr);
            }
            nxt[2 * j] = l0;     tnxt[2 * j] = tl0;
            nxt[2 * j + 1] = r0; tnxt[2 * j + 1] = tr0;
            nxt[2 * j + 2] = l1; tnxt[2 * j + 2] = tl1;
            nxt[2 * j + 3] = r1; tnxt[2 * j + 3] = tr1;
        }
        for (size_t j = wpair; j < w; ++j) {
            Block l, r;
            prg_.expand(cur[j], l, r);
            uint8_t tl = lsb(l), tr = lsb(r);
            if (tcur[j]) {
                l = block_xor(l, cw_s);
                r = block_xor(r, cw_s);
                tl = (uint8_t)(tl ^ cw_tl);
                tr = (uint8_t)(tr ^ cw_tr);
            }
            nxt[2 * j] = l;      tnxt[2 * j] = tl;
            nxt[2 * j + 1] = r;  tnxt[2 * j + 1] = tr;
        }
        cur.swap(nxt);
        tcur.swap(tnxt);
    }

    const uint64_t cw_final = k.cw_final;
    const bool negate = k.party != 0;
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(threads > 0 ? threads : omp_get_max_threads()) if (n > 4096)
#endif
    for (long long xx = 0; xx < (long long)(n & ~(size_t)3); xx += 4) {
        const size_t x = (size_t)xx;
        Block cv[4];
        prg_.convert4(&cur[x], cv);
        for (int i = 0; i < 4; ++i) {
            uint64_t v = mod_.from_block(cv[i].lo, cv[i].hi);
            if (tcur[x + i]) v = mod_.add(v, cw_final);
            out[x + i] = negate ? mod_.neg(v) : v;
        }
    }
    for (size_t x = n & ~(size_t)3; x < n; ++x) {
        const Block c = prg_.convert(cur[x]);
        uint64_t v = mod_.from_block(c.lo, c.hi);
        if (tcur[x]) v = mod_.add(v, cw_final);
        out[x] = negate ? mod_.neg(v) : v;
    }
}

bool Dpf2::well_formed(const Dpf2Key& k, uint32_t expected_depth) {
    if (k.depth != expected_depth) return false;
    if (k.party > 1) return false;
    if (k.cw_seed.size() != expected_depth) return false;
    if (k.cw_tl.size() != expected_depth) return false;
    if (k.cw_tr.size() != expected_depth) return false;
    for (uint32_t i = 0; i < expected_depth; ++i)
        if (k.cw_tl[i] > 1 || k.cw_tr[i] > 1) return false;
    // NOTE: this is a *shape* check only, and it is not the soundness check
    // Section VI-F of the paper needs.  The correction words of a well-formed
    // BGI16 key are pseudorandom, so nothing in a single key distinguishes a
    // point function from an arbitrary one; proving well-formedness
    // non-interactively requires a verifiable DPF or a PACL-style
    // authorisation proof.  apps/attack_malformed_key.cpp demonstrates the
    // extraction attack that remains open without one, and reports how many
    // queries it takes -- report that number rather than claiming the check
    // closes the gap.
    return true;
}

// ---------------------------------------------------------------------------
// DpfN
// ---------------------------------------------------------------------------

void DpfN::gen(uint64_t alpha, uint64_t beta, uint64_t domain, uint32_t n_parties,
               std::vector<DpfNKey>& keys, uint32_t heavy) const {
    if (n_parties < 2) throw std::invalid_argument("n_parties >= 2 required");
    if (alpha >= domain) throw std::invalid_argument("alpha outside domain");
    if (heavy == UINT32_MAX) heavy = n_parties - 1;
    if (heavy >= n_parties) throw std::invalid_argument("bad heavy party");

    keys.assign(n_parties, DpfNKey{});
    std::random_device rd;
    std::mt19937_64 rng(((uint64_t)rd() << 32) ^ rd());

    std::vector<uint64_t> acc(domain, 0);
    std::vector<uint64_t> buf(domain);

    for (uint32_t j = 0; j < n_parties; ++j) {
        keys[j].party = j;
        keys[j].n_parties = n_parties;
        keys[j].domain = domain;
        if (j == heavy) { keys[j].explicit_share = true; continue; }
        keys[j].explicit_share = false;
        for (int b = 0; b < 16; b += 8) {
            uint64_t r = rng();
            std::memcpy(keys[j].seed + b, &r, 8);
        }
        CtrPrf prf(keys[j].seed);
        prf.stream(0, buf.data(), domain);
        for (uint64_t x = 0; x < domain; ++x)
            acc[x] = mod_.add(acc[x], mod_.from_u64(buf[x]));
    }

    // The heavy party's share is whatever makes the total the point function.
    keys[heavy].share.resize(domain);
    for (uint64_t x = 0; x < domain; ++x) keys[heavy].share[x] = mod_.neg(acc[x]);
    keys[heavy].share[alpha] = mod_.add(keys[heavy].share[alpha], mod_.from_u64(beta));
}

void DpfN::eval_full(const DpfNKey& k, uint64_t* out, size_t n, int threads) const {
    if (n > k.domain) throw std::invalid_argument("eval_full: n exceeds domain");
    if (k.explicit_share) {
        std::memcpy(out, k.share.data(), n * sizeof(uint64_t));
        return;
    }
    CtrPrf prf(k.seed);
    const size_t kChunk = 1 << 16;
#ifdef _OPENMP
#pragma omp parallel num_threads(threads > 0 ? threads : omp_get_max_threads()) if (n > kChunk)
#endif
    {
        std::vector<uint64_t> buf(kChunk);
#ifdef _OPENMP
#pragma omp for schedule(static)
#endif
        for (long long c = 0; c < (long long)((n + kChunk - 1) / kChunk); ++c) {
            const size_t start = (size_t)c * kChunk;
            const size_t len = (start + kChunk <= n) ? kChunk : (n - start);
            prf.stream(start, buf.data(), len);
            for (size_t i = 0; i < len; ++i)
                out[start + i] = mod_.from_u64(buf[i]);
        }
    }
}

}  // namespace crshe
