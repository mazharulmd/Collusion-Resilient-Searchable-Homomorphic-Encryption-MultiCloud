// SPDX-License-Identifier: Apache-2.0
//
// E11: what the MAC column costs and what it actually catches.
//
// Two deviation models, and the difference between them is the boundary
// Remark 4 of the paper draws:
//
//   (a) inconsistent aggregate -- the provider returns a value ciphertext that
//       is not the contraction its MAC ciphertext attests to.  Caught except
//       with probability 1/p.
//   (b) consistent contraction against a different selection vector -- the
//       provider evaluates a perfectly well-formed aggregate, just not the one
//       asked for, in both columns.  ct_mac = delta * ct still holds, so the
//       check passes.  Report this as 0%: it is the gap verifiable function
//       secret sharing would close, and pretending otherwise would overclaim.
//
//   build/bench_verify --data=data/telemetry.crshe --trials=200 \
//                      --out=bench/results/e11_verify.csv

#include <cstdio>
#include <random>
#include <vector>

#include "crshe/bench_util.hpp"
#include "crshe/dataset.hpp"
#include "crshe/index.hpp"
#include "crshe/protocol.hpp"

using namespace crshe;

int main(int argc, char** argv) {
    Args args(argc, argv);
    banner("bench_verify (E11)");

    const std::string data = args.str("data", "");
    const uint64_t nd = args.u64("nd", 100000);
    const int trials = args.i32("trials", 200);
    const int reps = args.i32("reps", 11);
    const std::string out = args.str("out", "bench/results/e11_verify.csv");

    auto he = he_from_args(args);
    Modulus mod(he->plaintext_modulus());

    Dataset full = data.empty()
                       ? Dataset::synthetic(args.u64("ntags", 15347),
                                            args.u64("ntotal", 405184), 1.15, 99)
                       : Dataset::load(data);
    Dataset ds = full.subsample_records(nd);
    Owner owner(ds, mod, 1234);
    const auto templates = default_templates(ds, 7);
    const Template& f = templates[1];
    ProviderState st = build_provider_state(owner, *he, templates, false);

    Csv csv(out, {"metric", "N", "Nd", "trials", "value", "unit", "note",
                  "he_params", "cpu"});

    DpfScheme scheme(mod, 2, ds.n_tags);
    Provider p0(*he, st, mod), p1(*he, st, mod);
    std::mt19937_64 rng(2718);

    Token tok;
    scheme.gen(rng() % ds.n_tags, 1, tok);
    std::vector<uint64_t> e0(ds.n_tags), e1(ds.n_tags);
    scheme.eval_full(tok, 0, e0.data(), ds.n_tags);
    scheme.eval_full(tok, 1, e1.data(), ds.n_tags);

    // ---- cost of the MAC column ----
    // The MAC doubles the homomorphic work and the downlink of an aggregate.
    // Measure both halves rather than asserting the factor.
    const Stat with_mac = repeat(reps, [&] { (void)p0.fast_agg(e0.data(), f.name); });

    AggResponse r = p0.fast_agg(e0.data(), f.name, true);
    const size_t both = r.downlink_bytes;
    const size_t one = he->serialize(r.ct).size();

    csv.row("agg_latency_with_mac_ms", ds.n_tags, nd, reps, with_mac.median, "ms",
            "value and MAC columns contracted", he->param_string(), cpu_model());
    csv.row("downlink_with_mac_bytes", ds.n_tags, nd, 1, (double)both, "bytes",
            "aggregate + MAC ciphertext", he->param_string(), cpu_model());
    csv.row("downlink_without_mac_bytes", ds.n_tags, nd, 1, (double)one, "bytes",
            "aggregate ciphertext only", he->param_string(), cpu_model());
    csv.row("mac_downlink_overhead_x", ds.n_tags, nd, 1,
            one ? (double)both / (double)one : 0.0, "x",
            "MAC column doubles the response", he->param_string(), cpu_model());

    // ---- detection rates ----
    int caught_a = 0, caught_b = 0, effective = 0;
    for (int t = 0; t < trials; ++t) {
        const uint64_t x = rng() % ds.n_tags;
        Token tk;
        scheme.gen(x, 1, tk);
        scheme.eval_full(tk, 0, e0.data(), ds.n_tags);
        scheme.eval_full(tk, 1, e1.data(), ds.n_tags);
        // Only count deviations that actually change the answer: perturbing a
        // tag with an empty posting list leaves the aggregate correct, so there
        // is nothing for the MAC to catch and it must not be scored as a miss.
        std::vector<uint64_t> bad = e1;
        uint64_t pos = rng() % ds.n_tags;
        for (int k = 0; k < 64 && plaintext_aggregate(ds, f, pos, mod) == 0; ++k)
            pos = rng() % ds.n_tags;
        if (plaintext_aggregate(ds, f, pos, mod) == 0) continue;
        bad[pos] = mod.add(bad[pos], 1 + rng() % 1000);
        ++effective;

        {
            AggResponse d = p1.fast_agg(bad.data(), f.name);
            d.ct_mac = p1.fast_agg(e1.data(), f.name).ct_mac;
            std::vector<AggResponse> resp{p0.fast_agg(e0.data(), f.name), d};
            if (!combine_dec(*he, mod, owner.delta(), resp).mac_ok) ++caught_a;
        }
        {
            std::vector<AggResponse> resp{p0.fast_agg(e0.data(), f.name),
                                          p1.fast_agg(bad.data(), f.name)};
            if (!combine_dec(*he, mod, owner.delta(), resp).mac_ok) ++caught_b;
        }
    }

    csv.row("detection_rate_inconsistent_aggregate", ds.n_tags, nd, effective,
            effective ? 100.0 * caught_a / effective : 0.0, "percent",
            "theory: 1 - 1/p, i.e. indistinguishable from 100% at this p",
            he->param_string(), cpu_model());
    csv.row("detection_rate_wrong_selection_vector", ds.n_tags, nd, effective,
            effective ? 100.0 * caught_b / effective : 0.0, "percent",
            "expected 0: a consistent contraction against a different selection "
            "vector satisfies the MAC. Closing this needs verifiable FSS.",
            he->param_string(), cpu_model());

    std::fprintf(stderr,
                 "MAC latency %.3f ms, downlink %zu B (vs %zu B without)\n"
                 "detection (a) inconsistent aggregate      : %d/%d = %.1f%%\n"
                 "detection (b) different selection vector  : %d/%d = %.1f%%  "
                 "(expected 0%%)\n",
                 with_mac.median, both, one, caught_a, effective,
                 effective ? 100.0 * caught_a / effective : 0.0, caught_b,
                 effective, effective ? 100.0 * caught_b / effective : 0.0);
    return 0;
}
