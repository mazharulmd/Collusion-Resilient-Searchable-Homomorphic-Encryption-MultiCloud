// SPDX-License-Identifier: Apache-2.0
//
// Setup / BuildIndex / Precompute (Algorithm 1) and the provider-side state
// they produce.

#pragma once

#include <cstdint>
#include <map>
#include <memory>
#include <string>
#include <vector>

#include "crshe/aes_prg.hpp"
#include "crshe/dataset.hpp"
#include "crshe/he_backend.hpp"
#include "crshe/zp.hpp"

namespace crshe {

// An aggregate template: public per-record weights w_f, and which encrypted
// column the contraction runs against.
//   Column::kValue -> Enc(m_i)   (sums, weighted inner products)
//   Column::kUnit  -> Enc(1)     (counts; mean is a count and a sum, divided
//                                 at the client)
struct Template {
    enum class Column { kValue, kUnit };
    std::string name;
    Column column = Column::kValue;
    std::vector<uint64_t> w;   // length n_records, entries in Z_p
};

// The registered set used in the paper.
std::vector<Template> default_templates(const Dataset& ds, uint64_t seed = 7);

// ---------------------------------------------------------------------------
// Data owner
// ---------------------------------------------------------------------------

class Owner {
public:
    Owner(const Dataset& ds, Modulus mod, uint64_t seed);

    const Dataset& dataset() const { return ds_; }
    const Modulus& modulus() const { return mod_; }
    uint64_t delta() const { return delta_; }

    // alpha_w = F_K(w), the pseudonymous address of a tag name.
    uint64_t address(const std::string& tag) const;
    // The keyword -> address map the client uses; tags are addressed by their
    // index in the corpus, so this is the identity composed with the PRF only
    // when address collisions are being studied. Kept explicit because
    // Theorem 3's Q^2/2^lambda term is about exactly this map.
    uint64_t address_of_tag_index(uint64_t x) const { return x; }

    // P[x][0..nd) = F'_{K'}(x || i) mod p.
    void mask_row(uint64_t x, uint64_t nd, uint64_t* out) const;

    // I'[x][i] = I[x][i] + P[x][i] mod p, materialised as an N x nd matrix.
    // Throws with a clear message if that would not fit in RAM.
    std::vector<uint64_t> build_masked_index(uint64_t nd, int threads = 0) const;

    // A_f[x] = sum_{i in postings(x)} w_f[i] * v_i, where v_i is m_i for a
    // value template and 1 for a unit template.  O(total postings).
    std::vector<uint64_t> compute_A(const Template& f) const;

    // U_f[x] = sum_{i in [nd]} P[x][i] * w_f[i] * v_i.  Theta(N * nd); this is
    // the one-off precomputation cost reported as E7.
    std::vector<uint64_t> compute_U(const Template& f, uint64_t nd,
                                    int threads = 0) const;

    std::vector<uint64_t> scale(const std::vector<uint64_t>& v, uint64_t c) const;

private:
    Dataset ds_;
    Modulus mod_;
    uint8_t k_[16];    // F  : tag addressing
    uint8_t kp_[16];   // F' : index mask
    uint64_t delta_;   // MAC scalar
    std::unique_ptr<CtrPrf> mask_prf_;
};

// ---------------------------------------------------------------------------
// Provider-side state
// ---------------------------------------------------------------------------

struct FastColumns {
    std::vector<Ct> A, A_mac;
};
struct GenColumns {
    std::vector<Ct> U, U_mac;
};

struct ProviderState {
    // Encrypted record columns, packed over the record axis.
    std::vector<Ct> value, value_mac;   // Enc(m_i), Enc(delta m_i)
    std::vector<Ct> unit, unit_mac;     // Enc(1),   Enc(delta)
    // Per-template precomputed columns, packed over the tag axis.
    std::map<std::string, FastColumns> fast;
    std::map<std::string, GenColumns> gen;
    // The masked index I'. Empty when only the fast path is exercised, which
    // is the point of the fast path: at full scale I' is 50 GB per provider.
    std::vector<uint64_t> masked_index;
    uint64_t n_tags = 0;
    uint64_t n_records = 0;

    size_t masked_index_bytes() const { return masked_index.size() * sizeof(uint64_t); }
};

// Builds everything a provider stores.  The record count is whatever the
// owner's dataset has, so a general-path sweep over N_d is driven by
// constructing the Owner over ds.subsample_records(nd).  `with_general`
// controls whether the masked index I' and the correction columns U_f are
// built at all: the fast path needs neither, which is why it is the only path
// that runs at full scale.
ProviderState build_provider_state(const Owner& owner, const HeBackend& he,
                                   const std::vector<Template>& templates,
                                   bool with_general, int threads = 0);

// Estimated bytes for a masked index of these dimensions, for the
// out-of-memory guard and for the storage table.
inline unsigned __int128 masked_index_bytes(uint64_t n_tags, uint64_t nd) {
    return (unsigned __int128)n_tags * nd * sizeof(uint64_t);
}
uint64_t available_ram_bytes();

}  // namespace crshe
