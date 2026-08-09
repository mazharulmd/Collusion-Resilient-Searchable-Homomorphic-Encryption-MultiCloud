// SPDX-License-Identifier: Apache-2.0
//
// Baseline (v): a *faithful* homomorphic equality scan.
//
// Earlier work of ours charged one homomorphic addition per item, which badly
// understates the alternative. What a single-server FHE keyword scan actually
// costs is a homomorphic *equality* per record:
//
//     eq(a, b) = 1 - (a - b)^(q-1)        (Fermat, over plaintext prime q)
//
// with a digit decomposition when the tag domain exceeds q, and then one more
// multiplication to mask the value column. The multiplicative depth that
// implies -- 16 levels at q = 65537 -- is the point of the baseline, not an
// artefact of the implementation, and it is why this runs in its own binary:
// context generation alone can take minutes and must not cost the other
// baselines their rows.
//
//   build/bench_fhe_scan --data=data/telemetry.crshe \
//                        --out=bench/results/e5_fhe_scan.csv
//
// q must satisfy q = 1 (mod 2*ring_dim) for BFV batching, which rules out the
// very small primes that would give a shallow circuit: 65537 is the natural
// choice and it covers a 15,347-tag domain in one digit.
//
// One full batch of l slots is measured and the total is extrapolated by the
// batch count. Both the measured batch cost and the extrapolation factor go
// into the CSV, and the figure shades extrapolated bars differently, so the
// extrapolation is visible rather than buried.

#include <cmath>
#include <cstdio>
#include <random>
#include <vector>

#include "crshe/bench_util.hpp"
#include "crshe/dataset.hpp"

#ifdef CRSHE_WITH_OPENFHE
#include "openfhe.h"
#endif

using namespace crshe;

namespace {
struct FheScanResult {
    double batch_ms = 0;
    uint64_t batches = 0;
    double extrapolated_ms = 0;
    uint32_t ring_dim = 0;
    size_t slots = 0;
    uint32_t depth = 0;
    uint64_t q = 0;
    uint32_t digits = 0;
    bool ok = false;
    std::string note;
};

// One batch of l homomorphic equality tests followed by a masked sum.
FheScanResult fhe_equality_scan(uint64_t n_records, uint64_t n_tags, uint64_t q,
                                int reps) {
    using namespace lbcrypto;
    FheScanResult r;
    r.q = q;
    // Digits base q needed to address the tag domain.
    uint32_t digits = 1;
    unsigned __int128 cap = q;
    while (cap < n_tags) { cap *= q; ++digits; }
    r.digits = digits;

    // eq per digit costs log2(q-1) squarings; multiplying `digits` indicators
    // costs ceil(log2(digits)); one more level applies the mask to the value.
    const uint32_t per_digit = (uint32_t)std::ceil(std::log2((double)(q - 1)));
    const uint32_t combine = digits > 1 ? (uint32_t)std::ceil(std::log2((double)digits)) : 0;
    r.depth = per_digit + combine + 1;

    try {
        CCParams<CryptoContextBFVRNS> params;
        params.SetPlaintextModulus(q);
        params.SetMultiplicativeDepth(r.depth);
        params.SetSecurityLevel(HEStd_128_classic);
        auto cc = GenCryptoContext(params);
        cc->Enable(PKE);
        cc->Enable(KEYSWITCH);
        cc->Enable(LEVELEDSHE);
        cc->Enable(ADVANCEDSHE);
        auto kp = cc->KeyGen();
        cc->EvalMultKeyGen(kp.secretKey);
        cc->EvalSumKeyGen(kp.secretKey);

        const size_t slots = cc->GetEncodingParams()->GetBatchSize();
        r.ring_dim = cc->GetRingDimension();
        r.slots = slots;
        r.batches = (n_records + slots - 1) / slots;

        std::mt19937_64 rng(4);
        std::vector<std::vector<int64_t>> tag_digits(digits,
                                                     std::vector<int64_t>(slots));
        std::vector<int64_t> vals(slots);
        for (size_t i = 0; i < slots; ++i) {
            uint64_t t = rng() % n_tags;
            for (uint32_t d = 0; d < digits; ++d) { tag_digits[d][i] = t % q; t /= q; }
            vals[i] = (int64_t)(rng() % 3000);
        }
        std::vector<Ciphertext<DCRTPoly>> ct_tag(digits);
        for (uint32_t d = 0; d < digits; ++d)
            ct_tag[d] = cc->Encrypt(kp.publicKey,
                                    cc->MakePackedPlaintext(tag_digits[d]));
        auto ct_val = cc->Encrypt(kp.publicKey, cc->MakePackedPlaintext(vals));

        // The query tag, held in plaintext by the server as a public constant
        // would be in the most generous version of this baseline.
        uint64_t query = rng() % n_tags;
        std::vector<Plaintext> qd(digits);
        for (uint32_t d = 0; d < digits; ++d) {
            std::vector<int64_t> s(slots, (int64_t)(query % q));
            query /= q;
            qd[d] = cc->MakePackedPlaintext(s);
        }

        const Stat st = repeat(reps, [&] {
            Ciphertext<DCRTPoly> match;
            for (uint32_t d = 0; d < digits; ++d) {
                // z = a - b ; eq_d = 1 - z^(q-1)
                auto z = cc->EvalSub(ct_tag[d], qd[d]);
                auto pw = z;
                for (uint32_t k = 1; k < per_digit; ++k) pw = cc->EvalMult(pw, pw);
                std::vector<int64_t> one(slots, 1);
                auto eq = cc->EvalSub(cc->MakePackedPlaintext(one), pw);
                match = d == 0 ? eq : cc->EvalMult(match, eq);
            }
            auto masked = cc->EvalMult(match, ct_val);
            (void)cc->EvalSum(masked, slots);
        }, 1);

        r.batch_ms = st.median;
        r.extrapolated_ms = st.median * (double)r.batches;
        r.ok = true;
        r.note = "measured one batch of " + std::to_string(slots) +
                 " slots; total = batch x " + std::to_string(r.batches) +
                 " batches (extrapolated)";
    } catch (const std::exception& ex) {
        r.note = std::string("failed: ") + ex.what();
    }
    return r;
}
}  // namespace

int main(int argc, char** argv) {
    Args args(argc, argv);
    banner("bench_fhe_scan (baseline v)");

#ifndef CRSHE_WITH_OPENFHE
    std::fprintf(stderr, "built without OpenFHE; nothing to measure\n");
    return 1;
#else
    const std::string data = args.str("data", "");
    const uint64_t nd = args.u64("nd", 0);
    const uint64_t q = args.u64("fhe-q", 65537);
    const int reps = args.i32("reps", 3);
    const std::string out = args.str("out", "bench/results/e5_fhe_scan.csv");

    Dataset ds = data.empty()
                     ? Dataset::synthetic(args.u64("ntags", 15347),
                                          args.u64("ntotal", 405184), 1.15, 99)
                     : Dataset::load(data);
    if (nd) ds = ds.subsample_records(nd);

    std::fprintf(stderr,
                 "   corpus    : N=%llu Nd=%llu\n"
                 "   q         : %llu\n"
                 "   NOTE: building a deliberately depth-heavy BFV context.\n"
                 "         Key generation alone can take several minutes and\n"
                 "         tens of GB. That cost is the result.\n",
                 (unsigned long long)ds.n_tags, (unsigned long long)ds.n_records,
                 (unsigned long long)q);

    const FheScanResult r = fhe_equality_scan(ds.n_records, ds.n_tags, q, reps);

    Csv csv(out, {"baseline", "N", "Nd", "matched_S", "server_ms_median",
                  "server_ms_p25", "server_ms_p75", "client_ms_median",
                  "downlink_bytes", "reps", "extrapolated", "leakage", "note"});
    char note[512];
    std::snprintf(note, sizeof note,
                  "q=%llu, %u digit(s), depth %u, ring %u, %zu slots; %s",
                  (unsigned long long)r.q, r.digits, r.depth, r.ring_dim, r.slots,
                  r.note.c_str());
    csv.row("fhe-equality-scan", ds.n_tags, ds.n_records, (uint64_t)0,
            r.extrapolated_ms, r.extrapolated_ms, r.extrapolated_ms, 0.0,
            (uint64_t)0, reps, "yes",
            "hides the query and the data from a single server; costs a "
            "homomorphic equality per record", note);

    if (r.ok)
        std::fprintf(stderr,
                     "\n%10.2f ms per batch of %zu slots, %llu batches\n"
                     "%10.1f ms extrapolated for the whole corpus (%.1f s)\n"
                     "depth %u, ring dimension %u\n",
                     r.batch_ms, r.slots, (unsigned long long)r.batches,
                     r.extrapolated_ms, r.extrapolated_ms / 1000.0, r.depth,
                     r.ring_dim);
    else
        std::fprintf(stderr, "\nFAILED: %s\n", r.note.c_str());
    return r.ok ? 0 : 1;
#endif
}
