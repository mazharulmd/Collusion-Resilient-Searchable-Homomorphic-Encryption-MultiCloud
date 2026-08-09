// SPDX-License-Identifier: Apache-2.0
//
// Distributed point functions over Z_p.
//
//  Dpf2  -- Boyle-Gilboa-Ishai two-party DPF (GGM tree, fixed-key AES PRG).
//           Key size O(lambda * log N); full-domain evaluation in ~3N AES
//           calls via a single tree traversal (NOT N independent Eval calls,
//           which would cost O(N log N)).
//
//  DpfN  -- n-party DPF with (n-1)-privacy, for n >= 2.  Parties 1..n-1 hold a
//           lambda-bit seed whose counter-mode expansion is their share;
//           party n holds the explicit difference vector.  Correct by
//           construction and (n-1)-private under the PRF assumption: a
//           coalition of any n-1 parties is missing at least one seed
//           expansion, which masks alpha perfectly.  Key size is lambda bits
//           for n-1 of the parties and N*ceil(log p) bits for one of them.
//
//           This is deliberately not the succinct BGI15 multi-party
//           construction (O(2^{n/2} sqrt(N) lambda) keys).  It is
//           information-theoretically simple, testable, and its uplink is
//           measured rather than asserted; see docs/DESIGN.md for the
//           trade-off and what a succinct instantiation would buy.
//
// Both expose the same evaluation interface so the protocol layer, the
// benchmarks and the servers are agnostic to which is in use.

#pragma once

#include <cstdint>
#include <memory>
#include <vector>

#include "crshe/aes_prg.hpp"
#include "crshe/zp.hpp"

namespace crshe {

// ---------------------------------------------------------------------------
// Two-party DPF (BGI16)
// ---------------------------------------------------------------------------

struct Dpf2Key {
    uint8_t party = 0;           // 0 or 1
    Block seed;                  // root seed
    std::vector<Block> cw_seed;  // one per level
    std::vector<uint8_t> cw_tl;  // control-bit corrections, left
    std::vector<uint8_t> cw_tr;  // control-bit corrections, right
    uint64_t cw_final = 0;       // last correction word, in Z_p
    uint32_t depth = 0;          // log2 of the padded domain

    // Bytes on the wire: seed + per-level (seed correction + 2 control bits,
    // packed into one byte) + the final Z_p word.
    size_t serialized_bytes() const {
        return 16 + (size_t)depth * (16 + 1) + 8 + 4;
    }
};

class Dpf2 {
public:
    explicit Dpf2(Modulus mod) : mod_(mod) {}

    // Gen for the point function f_{alpha,beta} : [2^depth] -> Z_p.
    void gen(uint64_t alpha, uint64_t beta, uint32_t depth,
             Dpf2Key& k0, Dpf2Key& k1) const;

    // Single-point evaluation. Used by the correctness tests and by the
    // well-formedness check; the hot path is eval_full below.
    uint64_t eval(const Dpf2Key& k, uint64_t x) const;

    // Full-domain evaluation: writes out[0..n) with out[x] = Eval(k, x).
    // One traversal of the GGM tree, so ~2 AES per internal node plus one
    // per leaf, independent of how many outputs the caller reads.
    // `n` may be smaller than 2^depth; the extra leaves are simply not written.
    void eval_full(const Dpf2Key& k, uint64_t* out, size_t n,
                   int threads = 0) const;

    const Modulus& modulus() const { return mod_; }

    // Rejects keys that are structurally malformed (Section VI-F of the
    // paper: a client that submits a key for a non-point function can extract
    // arbitrary linear combinations of the index).  This checks the shape of
    // the key only; a full soundness check needs a verifiable DPF, which the
    // paper lists as future work.
    static bool well_formed(const Dpf2Key& k, uint32_t expected_depth);

private:
    Modulus mod_;
    PrgKeys prg_;
};

// ---------------------------------------------------------------------------
// n-party DPF with (n-1)-privacy
// ---------------------------------------------------------------------------

struct DpfNKey {
    uint32_t party = 0;
    uint32_t n_parties = 0;
    uint64_t domain = 0;
    bool explicit_share = false;      // true for the single "heavy" party
    uint8_t seed[16] = {0};           // used when !explicit_share
    std::vector<uint64_t> share;      // used when explicit_share

    size_t serialized_bytes() const {
        return explicit_share ? 16 + share.size() * 8 : 16 + 16;
    }
};

class DpfN {
public:
    explicit DpfN(Modulus mod) : mod_(mod) {}

    // The heavy key is assigned to party `heavy` (default: the last one).
    // Rotating it across queries balances uplink without affecting privacy,
    // because which party is heavy is public and query-independent.
    void gen(uint64_t alpha, uint64_t beta, uint64_t domain, uint32_t n_parties,
             std::vector<DpfNKey>& keys, uint32_t heavy = UINT32_MAX) const;

    void eval_full(const DpfNKey& k, uint64_t* out, size_t n,
                   int threads = 0) const;

    const Modulus& modulus() const { return mod_; }

private:
    Modulus mod_;
};

}  // namespace crshe
