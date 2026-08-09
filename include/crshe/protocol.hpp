// SPDX-License-Identifier: Apache-2.0
//
// Token / FastAgg / GenAgg / Retrieve / CombineDec (Algorithm 2).
//
// The one structural commitment worth restating here: a provider never returns
// anything whose size or content depends on the matched set.  FastAgg and
// GenAgg return a fixed number of ciphertexts; Retrieve returns N_d words
// whatever |S| is.  Any change that makes a response depend on |S| breaks
// Theorem 2, not just a benchmark.

#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "crshe/dpf.hpp"
#include "crshe/he_backend.hpp"
#include "crshe/index.hpp"

namespace crshe {

// ---------------------------------------------------------------------------
// Query token: one DPF key per provider
// ---------------------------------------------------------------------------

struct Token {
    bool two_party = false;
    std::vector<Dpf2Key> k2;
    std::vector<DpfNKey> kn;

    uint32_t n_parties() const {
        return two_party ? 2u : (uint32_t)kn.size();
    }
    size_t key_bytes(uint32_t j) const {
        return two_party ? k2[j].serialized_bytes() : kn[j].serialized_bytes();
    }
    size_t uplink_bytes() const {
        size_t s = 0;
        for (uint32_t j = 0; j < n_parties(); ++j) s += key_bytes(j);
        return s;
    }
};

// Wire format for a single provider's key.  A key is self-describing (it
// carries its own party index), so a provider deserialises into a one-element
// Token and evaluates at index 0.
std::string serialize_token_key(const Token& t, uint32_t party);
Token deserialize_token_key(const std::string& blob);

// Chooses the succinct BGI16 tree DPF for n = 2 and the (n-1)-private
// n-party DPF otherwise.  `force_nparty` makes n = 2 use the n-party
// construction too, which is how the two are compared on the same axes.
class DpfScheme {
public:
    DpfScheme(Modulus mod, uint32_t n_parties, uint64_t domain,
              bool force_nparty = false);

    uint32_t n_parties() const { return n_parties_; }
    uint64_t domain() const { return domain_; }
    uint32_t depth() const { return depth_; }
    bool succinct() const { return succinct_; }
    const Modulus& modulus() const { return mod_; }

    void gen(uint64_t alpha, uint64_t beta, Token& t) const;
    void eval_full(const Token& t, uint32_t party, uint64_t* out, size_t n,
                   int threads = 0) const;

private:
    Modulus mod_;
    uint32_t n_parties_;
    uint64_t domain_;
    uint32_t depth_ = 0;
    bool succinct_ = true;
    Dpf2 dpf2_;
    DpfN dpfn_;
};

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

struct AggResponse {
    Ct ct;
    Ct ct_mac;
    size_t downlink_bytes = 0;   // measured, not estimated
};

class Provider {
public:
    Provider(const HeBackend& he, const ProviderState& st, Modulus mod)
        : he_(he), st_(st), mod_(mod) {}

    // FastAgg: O(N) PRG + O(N/l) packed HE ops, independent of N_d.
    AggResponse fast_agg(const uint64_t* e, const std::string& tmpl,
                         bool measure_downlink = false) const;

    // GenAgg: Theta(N * N_d) ring operations for the selection contraction,
    // then O(N_d/l) packed HE ops and the mask correction.
    AggResponse gen_agg(const uint64_t* e, const Template& f,
                        bool measure_downlink = false, int threads = 0) const;

    // b_j = sum_x e_j[x] * I'[x] -- the Theta(N * N_d) contraction on its own.
    std::vector<uint64_t> contract_index(const uint64_t* e, int threads = 0) const;

    // Retrieve: fixed O(N_d log p) bits whatever |S| is.
    std::vector<uint64_t> retrieve(const uint64_t* e, int threads = 0) const {
        return contract_index(e, threads);
    }

private:
    const std::vector<Ct>& column_for(const Template& f, bool mac) const;

    const HeBackend& he_;
    const ProviderState& st_;
    Modulus mod_;
};

// ---------------------------------------------------------------------------
// Client (data user)
// ---------------------------------------------------------------------------

struct AggResult {
    uint64_t y = 0;
    bool mac_ok = false;
};

// CombineDec for an aggregate: add the n ciphertexts, decrypt twice, check the
// MAC.  A provider that returns an incorrectly evaluated aggregate is caught
// except with probability 1/p over the unknown delta.
AggResult combine_dec(const HeBackend& he, Modulus mod, uint64_t delta,
                      const std::vector<AggResponse>& responses);

// CombineDec for retrieval: add the shares, strip P[alpha], read off S.
std::vector<uint32_t> combine_retrieve(const Owner& owner, uint64_t alpha,
                                       const std::vector<std::vector<uint64_t>>& shares);

// The plaintext ground truth for a template and a tag, for correctness checks.
uint64_t plaintext_aggregate(const Dataset& ds, const Template& f, uint64_t x,
                             Modulus mod);

}  // namespace crshe
