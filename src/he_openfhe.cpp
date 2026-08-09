// SPDX-License-Identifier: Apache-2.0
//
// Leveled BFV through OpenFHE.
//
// The only subtlety is the packing convention.  OpenFHE's packed BFV encoder
// takes signed slot values in [-p/2, p/2); everything above the encoder is in
// unsigned Z_p, so every value crossing the boundary goes through
// Modulus::to_signed / from_signed.  Getting this wrong produces results that
// are correct for small aggregates and wrong for large ones, which is exactly
// the class of bug that survives testing.

#include "crshe/he_backend.hpp"

#ifdef CRSHE_WITH_OPENFHE

#include <sstream>
#include <stdexcept>

#include "openfhe.h"
#include "ciphertext-ser.h"
#include "cryptocontext-ser.h"
#include "key/key-ser.h"
#include "scheme/bfvrns/bfvrns-ser.h"

using namespace lbcrypto;

namespace crshe {

namespace {

using CtImpl = Ciphertext<DCRTPoly>;

class OpenFheBackend final : public HeBackend {
public:
    // Rebuild from an exported bundle. `secret` may be empty on a provider
    // host, in which case decryption is refused rather than silently wrong.
    OpenFheBackend(const std::string& public_blob, const std::string& secret_blob)
        : mod_(kDefaultModulus) {
        std::stringstream ss(public_blob);
        Serial::Deserialize(cc_, ss, SerType::BINARY);
        if (!cc_) throw std::runtime_error("bundle: cannot deserialize crypto context");
        if (!cc_->DeserializeEvalMultKey(ss, SerType::BINARY))
            throw std::runtime_error("bundle: cannot deserialize EvalMult keys");
        if (!cc_->DeserializeEvalSumKey(ss, SerType::BINARY))
            throw std::runtime_error("bundle: cannot deserialize EvalSum keys");
        Serial::Deserialize(kp_.publicKey, ss, SerType::BINARY);
        if (!kp_.publicKey) throw std::runtime_error("bundle: cannot deserialize pk");

        if (!secret_blob.empty()) {
            std::stringstream ss2(secret_blob);
            Serial::Deserialize(kp_.secretKey, ss2, SerType::BINARY);
            if (!kp_.secretKey)
                throw std::runtime_error("bundle: cannot deserialize sk");
        }
        mod_ = Modulus(cc_->GetCryptoParameters()->GetPlaintextModulus());
        slots_ = cc_->GetEncodingParams()->GetBatchSize();
        if (slots_ == 0) slots_ = cc_->GetRingDimension();
        sec_bits_ = 128;
    }

    explicit OpenFheBackend(const HeParams& hp) : mod_(hp.plaintext_modulus) {
        if (!is_prime(hp.plaintext_modulus))
            throw std::runtime_error("plaintext modulus must be prime");

        CCParams<CryptoContextBFVRNS> params;
        params.SetPlaintextModulus(hp.plaintext_modulus);
        params.SetMultiplicativeDepth(hp.depth);
        switch (hp.security_bits) {
            case 128: params.SetSecurityLevel(HEStd_128_classic); break;
            case 192: params.SetSecurityLevel(HEStd_192_classic); break;
            case 256: params.SetSecurityLevel(HEStd_256_classic); break;
            default: throw std::runtime_error("security_bits must be 128/192/256");
        }
        if (hp.ring_dim) {
            params.SetRingDim(hp.ring_dim);
            // Forcing the ring dimension overrides the library's own security
            // check, so the caller owns the consequence; we record the request
            // and report it in param_string().
            forced_ring_dim_ = true;
        }
        cc_ = GenCryptoContext(params);
        cc_->Enable(PKE);
        cc_->Enable(KEYSWITCH);
        cc_->Enable(LEVELEDSHE);
        cc_->Enable(ADVANCEDSHE);

        kp_ = cc_->KeyGen();
        cc_->EvalMultKeyGen(kp_.secretKey);
        cc_->EvalSumKeyGen(kp_.secretKey);

        slots_ = cc_->GetEncodingParams()->GetBatchSize();
        if (slots_ == 0) slots_ = cc_->GetRingDimension();
        sec_bits_ = hp.security_bits;
    }

    std::string name() const override { return "bfv-openfhe"; }
    bool is_secure() const override { return true; }
    uint32_t ring_dim() const override { return cc_->GetRingDimension(); }
    size_t slots() const override { return slots_; }
    int security_bits() const override { return forced_ring_dim_ ? -sec_bits_ : sec_bits_; }
    uint64_t plaintext_modulus() const override { return mod_.value(); }

    std::vector<Ct> encrypt_vector(const std::vector<uint64_t>& v) const override {
        const size_t chunks = v.empty() ? 1 : (v.size() + slots_ - 1) / slots_;
        std::vector<Ct> out;
        out.reserve(chunks);
        for (size_t c = 0; c < chunks; ++c) {
            std::vector<int64_t> slot(slots_, 0);
            const size_t start = c * slots_;
            for (size_t i = 0; i < slots_ && start + i < v.size(); ++i)
                slot[i] = mod_.to_signed(mod_.from_u64(v[start + i]));
            Plaintext pt = cc_->MakePackedPlaintext(slot);
            out.push_back(wrap(cc_->Encrypt(kp_.publicKey, pt)));
        }
        return out;
    }

    Ct inner_product(const std::vector<Ct>& cts,
                     const std::vector<uint64_t>& plain) const override {
        if (cts.empty()) throw std::runtime_error("inner_product: no ciphertexts");
        CtImpl acc;
        for (size_t c = 0; c < cts.size(); ++c) {
            std::vector<int64_t> slot(slots_, 0);
            const size_t start = c * slots_;
            bool any = false;
            for (size_t i = 0; i < slots_ && start + i < plain.size(); ++i) {
                slot[i] = mod_.to_signed(mod_.from_u64(plain[start + i]));
                if (slot[i]) any = true;
            }
            if (!any) continue;  // an all-zero chunk contributes nothing
            Plaintext pt = cc_->MakePackedPlaintext(slot);
            CtImpl term = cc_->EvalMult(unwrap(cts[c]), pt);
            acc = acc ? cc_->EvalAdd(acc, term) : term;
        }
        if (!acc) {
            // Degenerate but legal: every plaintext coefficient was zero.
            std::vector<int64_t> zero(slots_, 0);
            acc = cc_->Encrypt(kp_.publicKey, cc_->MakePackedPlaintext(zero));
            return wrap(acc);
        }
        // Collapse the slots: rotate-and-sum over the whole batch, so every
        // slot of the result holds the scalar inner product.
        return wrap(cc_->EvalSum(acc, slots_));
    }

    Ct add(const Ct& a, const Ct& b) const override {
        return wrap(cc_->EvalAdd(unwrap(a), unwrap(b)));
    }
    Ct sub(const Ct& a, const Ct& b) const override {
        return wrap(cc_->EvalSub(unwrap(a), unwrap(b)));
    }

    uint64_t decrypt_scalar(const Ct& c) const override {
        if (!kp_.secretKey)
            throw std::runtime_error(
                "this backend was loaded from a public-only bundle and holds no "
                "secret key. Decryption belongs to the data owner and authorised "
                "data users, never to a provider.");
        Plaintext pt;
        cc_->Decrypt(kp_.secretKey, unwrap(c), &pt);
        pt->SetLength(1);
        return mod_.from_signed(pt->GetPackedValue()[0]);
    }

    std::string export_public() const override {
        std::stringstream ss;
        Serial::Serialize(cc_, ss, SerType::BINARY);
        if (!cc_->SerializeEvalMultKey(ss, SerType::BINARY))
            throw std::runtime_error("cannot serialize EvalMult keys");
        if (!cc_->SerializeEvalSumKey(ss, SerType::BINARY))
            throw std::runtime_error("cannot serialize EvalSum keys");
        Serial::Serialize(kp_.publicKey, ss, SerType::BINARY);
        return ss.str();
    }

    std::string export_secret() const override {
        if (!kp_.secretKey) throw std::runtime_error("no secret key held");
        std::stringstream ss;
        Serial::Serialize(kp_.secretKey, ss, SerType::BINARY);
        return ss.str();
    }

    std::string serialize(const Ct& c) const override {
        std::stringstream ss;
        Serial::Serialize(unwrap(c), ss, SerType::BINARY);
        return ss.str();
    }

    Ct deserialize(const std::string& s) const override {
        std::stringstream ss(s);
        CtImpl ct;
        Serial::Deserialize(ct, ss, SerType::BINARY);
        return wrap(ct);
    }

private:
    static Ct wrap(const CtImpl& c) { return Ct{std::make_shared<CtImpl>(c)}; }
    static const CtImpl& unwrap(const Ct& c) {
        return *std::static_pointer_cast<CtImpl>(c.h);
    }

    Modulus mod_;
    CryptoContext<DCRTPoly> cc_;
    KeyPair<DCRTPoly> kp_;
    size_t slots_ = 0;
    int sec_bits_ = 128;
    bool forced_ring_dim_ = false;
};

}  // namespace

std::unique_ptr<HeBackend> make_openfhe_backend(const HeParams& p) {
    return std::make_unique<OpenFheBackend>(p);
}

std::unique_ptr<HeBackend> load_openfhe_backend(const std::string& public_blob,
                                                const std::string& secret_blob) {
    return std::make_unique<OpenFheBackend>(public_blob, secret_blob);
}

}  // namespace crshe

#endif  // CRSHE_WITH_OPENFHE
