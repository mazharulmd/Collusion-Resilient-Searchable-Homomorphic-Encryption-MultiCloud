// SPDX-License-Identifier: Apache-2.0
//
// Phase 3 go/no-go: the whole protocol against plaintext ground truth.
//
// If this passes, every number the benchmarks produce is a measurement of the
// construction in Section V of the paper.  If it does not, nothing downstream
// means anything -- so run it first, on the real corpus, before touching the
// manuscript.

#include <cstdio>
#include <random>
#include <vector>

#include "crshe/bench_util.hpp"
#include "crshe/dataset.hpp"
#include "crshe/index.hpp"
#include "crshe/protocol.hpp"

using namespace crshe;

static int failures = 0;
static void check(bool ok, const std::string& what) {
    std::printf("  [%s] %s\n", ok ? "PASS" : "FAIL", what.c_str());
    if (!ok) ++failures;
}

int main(int argc, char** argv) {
    Args args(argc, argv);
    banner("test_e2e");

    const uint64_t trials = args.u64("trials", 200);
    const uint64_t nd = args.u64("nd", 2000);
    const uint64_t ntags = args.u64("ntags", 512);
    const std::string data = args.str("data", "");

    auto he = he_from_args(args);
    Modulus mod(he->plaintext_modulus());

    Dataset ds = data.empty()
                     ? Dataset::synthetic(ntags, nd, 1.1, 4242)
                     : Dataset::load(data).subsample_records(nd);
    std::printf("corpus: %s  N=%llu tags, N_d=%llu records, %llu postings\n",
                ds.source.c_str(), (unsigned long long)ds.n_tags,
                (unsigned long long)ds.n_records,
                (unsigned long long)ds.postings.size());

    Owner owner(ds, mod, 1234);
    const auto templates = default_templates(ds, 7);

    // Lemma 1 magnitude bound, checked rather than assumed.
    for (const auto& f : templates) {
        const uint64_t worst = ds.max_aggregate(f.w);
        const bool ok = worst < mod.value();
        check(ok, "Lemma 1 magnitude bound for template '" + f.name + "' (max " +
                      std::to_string(worst) + " < p)");
    }

    std::printf("building provider state (fast + general)...\n");
    ProviderState st = build_provider_state(owner, *he, templates,
                                            /*with_general=*/true);
    std::printf("  masked index I': %.1f MB per provider\n",
                st.masked_index_bytes() / 1e6);

    std::mt19937_64 rng(31337);

    for (uint32_t n_parties : {2u, 3u, 4u}) {
        DpfScheme scheme(mod, n_parties, ds.n_tags);
        std::vector<Provider> providers;
        for (uint32_t j = 0; j < n_parties; ++j) providers.emplace_back(*he, st, mod);

        // ---- fast path ----
        for (const auto& f : templates) {
            bool ok = true, macs = true;
            const uint64_t reps = std::min<uint64_t>(trials, ds.n_tags);
            for (uint64_t t = 0; t < reps && ok; ++t) {
                const uint64_t x = rng() % ds.n_tags;
                Token tok;
                scheme.gen(x, 1, tok);

                std::vector<AggResponse> resp;
                std::vector<uint64_t> e(ds.n_tags);
                for (uint32_t j = 0; j < n_parties; ++j) {
                    scheme.eval_full(tok, j, e.data(), ds.n_tags);
                    resp.push_back(providers[j].fast_agg(e.data(), f.name));
                }
                const AggResult got = combine_dec(*he, mod, owner.delta(), resp);
                const uint64_t want = plaintext_aggregate(ds, f, x, mod);
                if (got.y != want) {
                    std::printf("      n=%u f=%s tag=%llu got=%llu want=%llu\n",
                                n_parties, f.name.c_str(), (unsigned long long)x,
                                (unsigned long long)got.y, (unsigned long long)want);
                    ok = false;
                }
                if (!got.mac_ok) macs = false;
            }
            check(ok, "fast path n=" + std::to_string(n_parties) + " f=" + f.name +
                          " matches plaintext over " + std::to_string(reps) + " tags");
            check(macs, "fast path n=" + std::to_string(n_parties) + " f=" + f.name +
                            " MAC verifies");
        }

        // ---- general path ----
        for (const auto& f : templates) {
            bool ok = true;
            const uint64_t reps = std::min<uint64_t>(args.u64("gen-trials", 12), ds.n_tags);
            for (uint64_t t = 0; t < reps && ok; ++t) {
                const uint64_t x = rng() % ds.n_tags;
                Token tok;
                scheme.gen(x, 1, tok);
                std::vector<AggResponse> resp;
                std::vector<uint64_t> e(ds.n_tags);
                for (uint32_t j = 0; j < n_parties; ++j) {
                    scheme.eval_full(tok, j, e.data(), ds.n_tags);
                    resp.push_back(providers[j].gen_agg(e.data(), f));
                }
                const AggResult got = combine_dec(*he, mod, owner.delta(), resp);
                const uint64_t want = plaintext_aggregate(ds, f, x, mod);
                if (got.y != want || !got.mac_ok) {
                    std::printf("      GEN n=%u f=%s tag=%llu got=%llu want=%llu mac=%d\n",
                                n_parties, f.name.c_str(), (unsigned long long)x,
                                (unsigned long long)got.y, (unsigned long long)want,
                                (int)got.mac_ok);
                    ok = false;
                }
            }
            check(ok, "general path n=" + std::to_string(n_parties) + " f=" + f.name +
                          " matches plaintext (mask cancelled inside the ciphertext)");
        }

        // ---- retrieval ----
        {
            bool ok = true;
            for (int t = 0; t < 8 && ok; ++t) {
                const uint64_t x = rng() % ds.n_tags;
                Token tok;
                scheme.gen(x, 1, tok);
                std::vector<std::vector<uint64_t>> shares;
                std::vector<uint64_t> e(ds.n_tags);
                for (uint32_t j = 0; j < n_parties; ++j) {
                    scheme.eval_full(tok, j, e.data(), ds.n_tags);
                    shares.push_back(providers[j].retrieve(e.data()));
                }
                const std::vector<uint32_t> S = combine_retrieve(owner, x, shares);
                std::vector<uint32_t> want(ds.postings.begin() + ds.offset[x],
                                           ds.postings.begin() + ds.offset[x + 1]);
                want.erase(std::unique(want.begin(), want.end()), want.end());
                if (S != want) ok = false;
            }
            check(ok, "retrieval n=" + std::to_string(n_parties) +
                          " recovers exactly the posting list");
        }
    }

    // ---- what the MAC does and does not detect (E11) ----
    //
    // Two distinct deviations, and the difference between them is exactly the
    // boundary Remark 4 of the paper draws.
    //
    //  (a) The provider returns an aggregate that is not the contraction it
    //      claims, while the MAC ciphertext is evaluated honestly. It cannot
    //      forge the matching MAC without delta, so this is caught except with
    //      probability 1/p.
    //
    //  (b) The provider performs a *well-formed* contraction against a
    //      different selection vector, consistently in both the value and the
    //      MAC column. Then ct_mac = delta * ct still holds, the check passes,
    //      and the client accepts a wrong answer. This is not a defect in the
    //      implementation: it is the gap that verifiable function secret
    //      sharing would close, and the reason Table I says "detect" rather
    //      than a tick.
    {
        DpfScheme scheme(mod, 2, ds.n_tags);
        Provider p0(*he, st, mod), p1(*he, st, mod);
        const auto& f = templates[1];   // sum
        const int reps = 32;
        int caught_a = 0, caught_b = 0, effective = 0;
        for (int t = 0; t < reps; ++t) {
            const uint64_t x = rng() % ds.n_tags;
            Token tok;
            scheme.gen(x, 1, tok);
            std::vector<uint64_t> e0(ds.n_tags), e1(ds.n_tags);
            scheme.eval_full(tok, 0, e0.data(), ds.n_tags);
            scheme.eval_full(tok, 1, e1.data(), ds.n_tags);

            // Perturb at a tag whose precomputed column entry is non-zero.
            // Perturbing a position where A_f[pos] = 0 -- an empty posting list
            // after subsampling -- leaves the aggregate unchanged, so there is
            // no wrong answer to detect and counting it as a miss would
            // understate the MAC.
            std::vector<uint64_t> bad = e1;
            uint64_t pos = rng() % ds.n_tags;
            for (int k = 0; k < 64 && plaintext_aggregate(ds, f, pos, mod) == 0; ++k)
                pos = rng() % ds.n_tags;
            if (plaintext_aggregate(ds, f, pos, mod) == 0) continue;
            bad[pos] = mod.add(bad[pos], 1 + rng() % 1000);
            ++effective;

            // (a) value column contracted against `bad`, MAC column honest.
            {
                AggResponse r1 = p1.fast_agg(bad.data(), f.name);
                r1.ct_mac = p1.fast_agg(e1.data(), f.name).ct_mac;
                std::vector<AggResponse> resp{p0.fast_agg(e0.data(), f.name), r1};
                if (!combine_dec(*he, mod, owner.delta(), resp).mac_ok) ++caught_a;
            }
            // (b) both columns contracted against `bad`.
            {
                std::vector<AggResponse> resp{p0.fast_agg(e0.data(), f.name),
                                              p1.fast_agg(bad.data(), f.name)};
                if (!combine_dec(*he, mod, owner.delta(), resp).mac_ok) ++caught_b;
            }
        }
        std::printf("  MAC vs (a) inconsistent aggregate : %d/%d caught\n",
                    caught_a, effective);
        std::printf("  MAC vs (b) well-formed contraction against a different\n"
                    "             selection vector       : %d/%d caught "
                    "(expected 0 -- see Remark 4)\n", caught_b, effective);
        check(effective > 0 && caught_a == effective,
              "MAC detects an incorrectly evaluated aggregate (Section VI-E)");
        check(caught_b == 0,
              "MAC does NOT detect a consistent contraction against a different "
              "selection vector -- the documented limit of the semi-honest model");
    }

    // ---- the response is independent of |S| (Theorem 2's downlink claim) ----
    {
        DpfScheme scheme(mod, 2, ds.n_tags);
        Provider p(*he, st, mod);
        uint64_t small_tag = 0, big_tag = 0, small_len = UINT64_MAX, big_len = 0;
        for (uint64_t x = 0; x < ds.n_tags; ++x) {
            const uint64_t l = ds.posting_len(x);
            if (l < small_len) { small_len = l; small_tag = x; }
            if (l > big_len) { big_len = l; big_tag = x; }
        }
        std::vector<uint64_t> e(ds.n_tags);
        size_t bytes[2];
        const uint64_t tags[2] = {small_tag, big_tag};
        for (int i = 0; i < 2; ++i) {
            Token tok;
            scheme.gen(tags[i], 1, tok);
            scheme.eval_full(tok, 0, e.data(), ds.n_tags);
            bytes[i] = p.fast_agg(e.data(), "sum", /*measure_downlink=*/true).downlink_bytes;
        }
        std::printf("  downlink: |S|=%llu -> %zu B, |S|=%llu -> %zu B\n",
                    (unsigned long long)small_len, bytes[0],
                    (unsigned long long)big_len, bytes[1]);
        check(bytes[0] == bytes[1],
              "aggregate downlink is identical for |S|=" + std::to_string(small_len) +
                  " and |S|=" + std::to_string(big_len));
    }

    std::printf("%s\n", failures == 0 ? "ALL END-TO-END TESTS PASSED"
                                      : "END-TO-END TESTS FAILED");
    return failures == 0 ? 0 : 1;
}
