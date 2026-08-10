// SPDX-License-Identifier: Apache-2.0
//
// E2, the central measurement of the paper: oblivious aggregate latency on the
// fast path (should be flat in N_d) and on the general path (should grow like
// N * N_d), on the same axes, with the per-query downlink alongside.
//
//   build/bench_agg --data=data/telemetry.crshe \
//                   --nd=1000,10000,100000,405184 --reps=11 \
//                   --out=bench/results/e2_agg.csv
//
// The general path is skipped automatically at any N_d whose masked index does
// not fit in RAM, and the skip is recorded in the CSV with the size that would
// have been required -- that refusal is a result, not a gap.

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
    banner("bench_agg (E2)");

    const std::string data = args.str("data", "");
    const auto nds = args.list("nd", {1000, 10000, 100000});
    const int reps = args.i32("reps", 11);
    const uint32_t n_parties = (uint32_t)args.u64("n", 2);
    const std::string tmpl = args.str("template", "sum");
    const std::string out = args.str("out", "bench/results/e2_agg.csv");
    const bool skip_general = args.flag("fast-only");
    const int threads = args.i32("threads", 0);
    // Fraction of free RAM the masked index may occupy. The general path also
    // needs per-thread accumulators and the encrypted columns, so this is not
    // 1.0; but a guard at 0.5 refused a 37.5 GB index on a machine with 63.7 GB
    // free, which threw away the most valuable data point in the sweep.
    const double mem_fraction = args.f64("mem-fraction", 0.75);

    auto he = he_from_args(args);
    Modulus mod(he->plaintext_modulus());

    Dataset full = data.empty()
                       ? Dataset::synthetic(args.u64("ntags", 15347),
                                            args.u64("ntotal", 405184), 1.15, 99)
                       : Dataset::load(data);
    std::fprintf(stderr, "   corpus    : %s N=%llu Nd=%llu\n", full.source.c_str(),
                 (unsigned long long)full.n_tags, (unsigned long long)full.n_records);

    Csv csv(out, {"path", "N", "Nd", "n_parties", "template", "threads",
                  "provider_ms_median", "provider_ms_p25", "provider_ms_p75",
                  "client_ms_median", "reps", "downlink_bytes_per_provider",
                  "downlink_bytes_total", "uplink_bytes_total",
                  "index_bytes_per_provider", "he_params", "cpu", "note"});

    std::mt19937_64 rng(555);

    for (uint64_t nd : nds) {
        Dataset ds = full.subsample_records(nd);
        Owner owner(ds, mod, 1234);
        const auto templates = default_templates(ds, 7);
        const Template* f = nullptr;
        for (const auto& t : templates) if (t.name == tmpl) f = &t;
        if (!f) { std::fprintf(stderr, "unknown template %s\n", tmpl.c_str()); return 1; }

        // ---- fast path: no masked index, no correction column ----
        {
            ProviderState st = build_provider_state(owner, *he, templates,
                                                    /*with_general=*/false, threads);
            DpfScheme scheme(mod, n_parties, ds.n_tags);
            std::vector<Provider> ps;
            for (uint32_t j = 0; j < n_parties; ++j) ps.emplace_back(*he, st, mod);

            Token tok;
            scheme.gen(rng() % ds.n_tags, 1, tok);
            std::vector<uint64_t> e(ds.n_tags);

            // One provider's whole online cost: full-domain evaluation plus the
            // packed homomorphic contraction. Providers run in parallel, so
            // this is the latency the client waits on, not the sum over n.
            const Stat s = repeat(reps, [&] {
                scheme.eval_full(tok, 0, e.data(), ds.n_tags, threads);
                (void)ps[0].fast_agg(e.data(), tmpl);
            });

            std::vector<AggResponse> resp;
            for (uint32_t j = 0; j < n_parties; ++j) {
                scheme.eval_full(tok, j, e.data(), ds.n_tags, threads);
                resp.push_back(ps[j].fast_agg(e.data(), tmpl, /*measure_downlink=*/true));
            }
            const Stat cs = repeat(reps, [&] {
                (void)combine_dec(*he, mod, owner.delta(), resp);
            });

            csv.row("fast", ds.n_tags, nd, (uint64_t)n_parties, tmpl,
                    (uint64_t)(threads ? threads : max_threads()),
                    s.median, s.p25, s.p75, cs.median, reps,
                    (uint64_t)resp[0].downlink_bytes,
                    (uint64_t)(resp[0].downlink_bytes * n_parties),
                    (uint64_t)tok.uplink_bytes(), (uint64_t)0,
                    he->param_string(), cpu_model(),
                    "A_f is O(N/l) ciphertexts; independent of Nd");
            std::fprintf(stderr, "[fast] Nd=%-8llu %8.3f ms  down=%zu B/provider\n",
                         (unsigned long long)nd, s.median, resp[0].downlink_bytes);
        }

        // ---- general path: masked index + correction column ----
        if (!skip_general) {
            const unsigned __int128 need = masked_index_bytes(ds.n_tags, nd);
            const uint64_t avail = available_ram_bytes();
            if (avail && (double)need > mem_fraction * (double)avail) {
                char note[256];
                std::snprintf(note, sizeof note,
                              "SKIPPED: I' would need %.1f GB, %.1f GB available "
                              "(budget %.0f%%; raise --mem-fraction to attempt it)",
                              (double)need / 1e9, (double)avail / 1e9,
                              mem_fraction * 100.0);
                csv.row("general", ds.n_tags, nd, (uint64_t)n_parties, tmpl,
                        (uint64_t)(threads ? threads : max_threads()),
                        0.0, 0.0, 0.0, 0.0, 0, (uint64_t)0, (uint64_t)0, (uint64_t)0,
                        (uint64_t)(double)need, he->param_string(), cpu_model(), note);
                std::fprintf(stderr, "[general] Nd=%llu %s\n",
                             (unsigned long long)nd, note);
                continue;
            }

            ProviderState st = build_provider_state(owner, *he, templates,
                                                    /*with_general=*/true, threads);
            DpfScheme scheme(mod, n_parties, ds.n_tags);
            std::vector<Provider> ps;
            for (uint32_t j = 0; j < n_parties; ++j) ps.emplace_back(*he, st, mod);

            Token tok;
            scheme.gen(rng() % ds.n_tags, 1, tok);
            std::vector<uint64_t> e(ds.n_tags);

            const int greps = std::max(3, reps / 3);   // this path is slow by design
            const Stat s = repeat(greps, [&] {
                scheme.eval_full(tok, 0, e.data(), ds.n_tags, threads);
                (void)ps[0].gen_agg(e.data(), *f, false, threads);
            }, 0);

            std::vector<AggResponse> resp;
            for (uint32_t j = 0; j < n_parties; ++j) {
                scheme.eval_full(tok, j, e.data(), ds.n_tags, threads);
                resp.push_back(ps[j].gen_agg(e.data(), *f, true, threads));
            }
            const Stat cs = repeat(reps, [&] {
                (void)combine_dec(*he, mod, owner.delta(), resp);
            });

            csv.row("general", ds.n_tags, nd, (uint64_t)n_parties, tmpl,
                    (uint64_t)(threads ? threads : max_threads()),
                    s.median, s.p25, s.p75, cs.median, greps,
                    (uint64_t)resp[0].downlink_bytes,
                    (uint64_t)(resp[0].downlink_bytes * n_parties),
                    (uint64_t)tok.uplink_bytes(),
                    (uint64_t)st.masked_index_bytes(), he->param_string(), cpu_model(),
                    "Theta(N*Nd) contraction over the masked index");
            std::fprintf(stderr, "[general] Nd=%-8llu %8.3f ms  I'=%.2f GB\n",
                         (unsigned long long)nd, s.median,
                         st.masked_index_bytes() / 1e9);
        }
    }
    return 0;
}
