// SPDX-License-Identifier: Apache-2.0
//
// Backend registry, plus the plaintext stand-in backend.

#include "crshe/he_backend.hpp"

#include <algorithm>
#include <cstring>
#include <sstream>
#include <stdexcept>

namespace crshe {

std::unique_ptr<HeBackend> make_openfhe_backend(const HeParams&);  // he_openfhe.cpp
std::unique_ptr<HeBackend> load_openfhe_backend(const std::string&, const std::string&);

std::string HeBackend::param_string() const {
    std::ostringstream os;
    os << name() << ",p=" << plaintext_modulus() << ",ringdim=" << ring_dim()
       << ",slots=" << slots() << ",sec=" << security_bits();
    return os.str();
}

namespace {

// ---------------------------------------------------------------------------
// Plaintext stand-in.  Same algebra, no security.
// ---------------------------------------------------------------------------
class PlainBackend final : public HeBackend {
public:
    explicit PlainBackend(const HeParams& p)
        : mod_(p.plaintext_modulus),
          slots_(p.ring_dim ? p.ring_dim : 32768u) {}

    std::string name() const override { return "plain"; }
    bool is_secure() const override { return false; }
    uint32_t ring_dim() const override { return slots_; }
    size_t slots() const override { return slots_; }
    int security_bits() const override { return 0; }
    uint64_t plaintext_modulus() const override { return mod_.value(); }

    std::vector<Ct> encrypt_vector(const std::vector<uint64_t>& v) const override {
        const size_t chunks = (v.size() + slots_ - 1) / slots_;
        std::vector<Ct> out;
        out.reserve(chunks ? chunks : 1);
        for (size_t c = 0; c < (chunks ? chunks : 1); ++c) {
            auto buf = std::make_shared<std::vector<uint64_t>>(slots_, 0);
            const size_t start = c * slots_;
            const size_t len = start < v.size()
                                   ? std::min(slots_, v.size() - start)
                                   : 0;
            for (size_t i = 0; i < len; ++i) (*buf)[i] = mod_.from_u64(v[start + i]);
            out.push_back(Ct{buf});
        }
        return out;
    }

    Ct inner_product(const std::vector<Ct>& cts,
                     const std::vector<uint64_t>& plain) const override {
        uint64_t acc = 0;
        for (size_t c = 0; c < cts.size(); ++c) {
            const auto& col = *std::static_pointer_cast<std::vector<uint64_t>>(cts[c].h);
            const size_t start = c * slots_;
            for (size_t i = 0; i < slots_; ++i) {
                const size_t g = start + i;
                if (g >= plain.size()) break;
                acc = mod_.add(acc, mod_.mul(col[i], mod_.from_u64(plain[g])));
            }
        }
        auto buf = std::make_shared<std::vector<uint64_t>>(slots_, acc);
        return Ct{buf};
    }

    Ct add(const Ct& a, const Ct& b) const override { return combine(a, b, true); }
    Ct sub(const Ct& a, const Ct& b) const override { return combine(a, b, false); }

    uint64_t decrypt_scalar(const Ct& c) const override {
        return (*std::static_pointer_cast<std::vector<uint64_t>>(c.h))[0];
    }

    std::string serialize(const Ct& c) const override {
        const auto& v = *std::static_pointer_cast<std::vector<uint64_t>>(c.h);
        return std::string((const char*)v.data(), v.size() * sizeof(uint64_t));
    }

    Ct deserialize(const std::string& s) const override {
        auto buf = std::make_shared<std::vector<uint64_t>>(slots_, 0);
        std::memcpy(buf->data(), s.data(),
                    std::min(s.size(), slots_ * sizeof(uint64_t)));
        return Ct{buf};
    }

    // There is no key material to export: the stand-in has no keys, which is
    // exactly why it must never be used for anything but a correctness run.
    std::string export_public() const override {
        std::ostringstream os;
        os << mod_.value() << " " << slots_;
        return os.str();
    }
    std::string export_secret() const override { return export_public(); }

private:
    Ct combine(const Ct& a, const Ct& b, bool plus) const {
        const auto& x = *std::static_pointer_cast<std::vector<uint64_t>>(a.h);
        const auto& y = *std::static_pointer_cast<std::vector<uint64_t>>(b.h);
        auto buf = std::make_shared<std::vector<uint64_t>>(slots_, 0);
        for (size_t i = 0; i < slots_; ++i)
            (*buf)[i] = plus ? mod_.add(x[i], y[i]) : mod_.sub(x[i], y[i]);
        return Ct{buf};
    }

    Modulus mod_;
    size_t slots_;
};

}  // namespace

bool openfhe_available() {
#ifdef CRSHE_WITH_OPENFHE
    return true;
#else
    return false;
#endif
}

std::unique_ptr<HeBackend> make_he_backend(const std::string& kind,
                                           const HeParams& params) {
    if (kind == "plain") return std::make_unique<PlainBackend>(params);
    if (kind == "bfv-openfhe" || kind == "bfv" || kind == "openfhe") {
#ifdef CRSHE_WITH_OPENFHE
        return make_openfhe_backend(params);
#else
        throw std::runtime_error(
            "this binary was built without OpenFHE; rebuild with -DWITH_OPENFHE=ON "
            "(see scripts/install_openfhe.sh) or pass --he=plain for a "
            "correctness-only run");
#endif
    }
    throw std::runtime_error("unknown HE backend: " + kind);
}

std::unique_ptr<HeBackend> load_he_backend(const std::string& kind,
                                           const std::string& public_blob,
                                           const std::string& secret_blob) {
    if (kind == "plain") {
        HeParams hp;
        std::istringstream is(public_blob);
        uint64_t p = 0, slots = 0;
        is >> p >> slots;
        hp.plaintext_modulus = p ? p : kDefaultModulus;
        hp.ring_dim = (uint32_t)slots;
        return std::make_unique<PlainBackend>(hp);
    }
    if (kind == "bfv-openfhe" || kind == "bfv" || kind == "openfhe") {
#ifdef CRSHE_WITH_OPENFHE
        return load_openfhe_backend(public_blob, secret_blob);
#else
        throw std::runtime_error("built without OpenFHE");
#endif
    }
    throw std::runtime_error("unknown HE backend: " + kind);
}

}  // namespace crshe
