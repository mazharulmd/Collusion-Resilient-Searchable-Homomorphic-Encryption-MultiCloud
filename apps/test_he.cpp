// SPDX-License-Identifier: Apache-2.0
//
// Phase 2 go/no-go.  Checks that the packed contraction the providers run is
// exactly equal -- not approximately equal -- to the same computation done in
// plaintext Z_p, including the noise-worst case where every plaintext
// coefficient is a uniform element of Z_p (which is what a DPF share is).

#include <cstdio>
#include <random>
#include <vector>

#include "crshe/bench_util.hpp"
#include "crshe/he_backend.hpp"
#include "crshe/zp.hpp"

using namespace crshe;

static int failures = 0;
static void check(bool ok, const char* what) {
    std::printf("  [%s] %s\n", ok ? "PASS" : "FAIL", what);
    if (!ok) ++failures;
}

int main(int argc, char** argv) {
    Args args(argc, argv);
    banner("test_he");
    auto he = he_from_args(args);
    Modulus mod(he->plaintext_modulus());
    std::mt19937_64 rng(9001);

    std::printf("CR-SHE HE backend test\n");
    std::printf("  backend  : %s\n", he->param_string().c_str());
    std::printf("  slots    : %zu\n", he->slots());

    // ---- inner product over a single chunk, small coefficients ----
    {
        const size_t n = std::min<size_t>(he->slots(), 4096);
        std::vector<uint64_t> col(n), pl(n);
        for (size_t i = 0; i < n; ++i) {
            col[i] = 1000 + rng() % 2500;     // sensor readings
            pl[i] = rng() % 2;                // a 0/1 selection vector
        }
        auto cts = he->encrypt_vector(col);
        auto ct = he->inner_product(cts, pl);
        unsigned __int128 want = 0;
        for (size_t i = 0; i < n; ++i) want += (unsigned __int128)col[i] * pl[i];
        check(he->decrypt_scalar(ct) == mod.reduce(want),
              "packed inner product, 0/1 coefficients, one chunk");
    }

    // ---- multi-chunk: more entries than slots ----
    {
        const size_t n = he->slots() * 2 + 137;
        std::vector<uint64_t> col(n), pl(n);
        for (size_t i = 0; i < n; ++i) {
            col[i] = rng() % 5000;
            pl[i] = rng() % 3;
        }
        auto cts = he->encrypt_vector(col);
        check(cts.size() == (n + he->slots() - 1) / he->slots(),
              "column packs into ceil(n/l) ciphertexts");
        auto ct = he->inner_product(cts, pl);
        unsigned __int128 want = 0;
        for (size_t i = 0; i < n; ++i) want += (unsigned __int128)col[i] * pl[i];
        check(he->decrypt_scalar(ct) == mod.reduce(want),
              "packed inner product across multiple chunks");
    }

    // ---- worst case for noise: coefficients uniform in Z_p ----
    // This is the general path.  b_j[i] is an additive share, so it is uniform
    // in Z_p, and the plaintext multiplied into the ciphertext therefore has
    // full magnitude.  If BFV parameters are too tight this is where it breaks,
    // not on the fast path.
    {
        const size_t n = std::min<size_t>(he->slots(), 8192);
        std::vector<uint64_t> col(n), pl(n);
        for (size_t i = 0; i < n; ++i) {
            col[i] = rng() % mod.value();
            pl[i] = rng() % mod.value();
        }
        auto cts = he->encrypt_vector(col);
        auto ct = he->inner_product(cts, pl);
        uint64_t want = 0;
        for (size_t i = 0; i < n; ++i) want = mod.add(want, mod.mul(col[i], pl[i]));
        const uint64_t got = he->decrypt_scalar(ct);
        if (got != want)
            std::printf("      got=%llu want=%llu  (BFV noise budget exhausted: "
                        "raise --depth or lower p)\n",
                        (unsigned long long)got, (unsigned long long)want);
        check(got == want, "full-magnitude Z_p coefficients (general-path worst case)");
    }

    // ---- additive homomorphism across providers ----
    {
        const size_t n = 1024;
        std::vector<uint64_t> col(n), a(n), b(n);
        for (size_t i = 0; i < n; ++i) {
            col[i] = rng() % 5000;
            a[i] = rng() % mod.value();
            b[i] = mod.sub(rng() % mod.value(), a[i]);   // a + b is a share pair
        }
        auto cts = he->encrypt_vector(col);
        auto ca = he->inner_product(cts, a);
        auto cb = he->inner_product(cts, b);
        const uint64_t got = he->decrypt_scalar(he->add(ca, cb));
        uint64_t want = 0;
        for (size_t i = 0; i < n; ++i)
            want = mod.add(want, mod.mul(col[i], mod.add(a[i], b[i])));
        check(got == want, "shares from two providers combine additively (Lemma 1)");
    }

    // ---- subtraction, used for the mask correction ----
    {
        const size_t n = 512;
        std::vector<uint64_t> col(n, 3), p1(n, 5), p2(n, 2);
        auto cts = he->encrypt_vector(col);
        const uint64_t got = he->decrypt_scalar(
            he->sub(he->inner_product(cts, p1), he->inner_product(cts, p2)));
        check(got == mod.from_u64(3ull * 3 * n), "ciphertext subtraction (mask correction)");
    }

    // ---- serialization round trip, which is what downlink is measured on ----
    {
        std::vector<uint64_t> col(64, 42);
        auto cts = he->encrypt_vector(col);
        auto ct = he->inner_product(cts, std::vector<uint64_t>(64, 1));
        const std::string s = he->serialize(ct);
        const uint64_t got = he->decrypt_scalar(he->deserialize(s));
        std::printf("  serialized ciphertext: %zu bytes\n", s.size());
        check(got == 42 * 64, "serialize/deserialize round trip");
    }

    std::printf("%s\n", failures == 0 ? "ALL HE TESTS PASSED" : "HE TESTS FAILED");
    return failures == 0 ? 0 : 1;
}
