// SPDX-License-Identifier: Apache-2.0
//
// The homomorphic layer, behind an interface narrow enough that the protocol,
// the servers and the benchmarks never see an OpenFHE type.
//
// Two implementations:
//   "bfv-openfhe"  real leveled BFV (OpenFHE), the only one whose numbers may
//                  be reported;
//   "plain"        a plaintext stand-in with the same algebra, so that
//                  end-to-end correctness and the whole harness can be
//                  exercised on a machine without OpenFHE.  It provides no
//                  confidentiality and says so; every benchmark refuses to
//                  emit a results row from it unless --allow-insecure-he is
//                  passed, and tags the row `he=plain` when it does.

#pragma once

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "crshe/zp.hpp"

namespace crshe {

struct HeParams {
    uint64_t plaintext_modulus = kDefaultModulus;
    uint32_t ring_dim = 0;   // 0 => let the library pick for the security level
    uint32_t depth = 1;      // one plaintext-ciphertext product
    int security_bits = 128;
};

// Opaque ciphertext handle.
struct Ct {
    std::shared_ptr<void> h;
    explicit operator bool() const { return (bool)h; }
};

class HeBackend {
public:
    virtual ~HeBackend() = default;

    virtual std::string name() const = 0;
    virtual bool is_secure() const = 0;
    virtual uint32_t ring_dim() const = 0;
    virtual size_t slots() const = 0;
    virtual int security_bits() const = 0;
    virtual uint64_t plaintext_modulus() const = 0;

    // Data-owner side: pack v into ceil(|v| / slots) ciphertexts, zero-padded.
    virtual std::vector<Ct> encrypt_vector(const std::vector<uint64_t>& v) const = 0;

    // Provider side.  Computes sum_i plain[i] * (slot i of the packed column)
    // and collapses the slots, so every slot of the result holds the scalar
    // inner product.  This is the whole of FastAgg's homomorphic work and the
    // second half of GenAgg's.
    virtual Ct inner_product(const std::vector<Ct>& cts,
                             const std::vector<uint64_t>& plain) const = 0;

    virtual Ct add(const Ct& a, const Ct& b) const = 0;
    virtual Ct sub(const Ct& a, const Ct& b) const = 0;

    // Client side.
    virtual uint64_t decrypt_scalar(const Ct& c) const = 0;

    // Wire format, used by the WAN deployment and by every downlink
    // measurement.  Sizes reported in the paper come from serialize().size().
    virtual std::string serialize(const Ct& c) const = 0;
    virtual Ct deserialize(const std::string& s) const = 0;

    // Deployment bundle.  export_public() is everything a provider needs --
    // the crypto context, the evaluation keys and pk -- and nothing that would
    // let it decrypt.  export_secret() is sk, which stays with the data owner
    // and the authorised data users and is never written to a provider host.
    virtual std::string export_public() const = 0;
    virtual std::string export_secret() const = 0;

    // A short human-readable parameter string for the results CSVs, so every
    // measured row records the parameters it was taken under.
    std::string param_string() const;
};

// kind: "bfv-openfhe" or "plain".  Throws if OpenFHE support was not compiled
// in and "bfv-openfhe" is requested.
std::unique_ptr<HeBackend> make_he_backend(const std::string& kind,
                                           const HeParams& params);

// Rebuild a backend from an exported bundle.  Pass an empty `secret` on a
// provider host: the resulting backend evaluates but cannot decrypt, and
// decrypt_scalar() throws if called.
std::unique_ptr<HeBackend> load_he_backend(const std::string& kind,
                                           const std::string& public_blob,
                                           const std::string& secret_blob);

bool openfhe_available();

}  // namespace crshe
