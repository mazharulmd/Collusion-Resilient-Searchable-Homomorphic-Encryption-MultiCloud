// SPDX-License-Identifier: Apache-2.0
//
// E8 (core scaling) and E10 (sustained throughput).
//
// E8 sweeps the thread count of a single provider over one query.
// E10 saturates the provider with concurrent clients: each worker thread runs
// whole queries single-threaded, which is what a deployment actually does under
// load, and reports queries per second.
//
//   build/bench_scale --data=data/telemetry.crshe --threads=1,2,4,8,16,32 \
//                     --clients=1,4,16,32 --out=bench/results/e8_e10_scale.csv

#include <atomic>
#include <cstdio>
#include <random>
#include <thread>
#include <vector>

#include "crshe/bench_util.hpp"
#include "crshe/dataset.hpp"
#include "crshe/index.hpp"
#include "crshe/protocol.hpp"

using namespace crshe;

int main(int argc, char** argv) {
    Args args(argc, argv);
    banner("bench_scale (E8, E10)");

    const std::string data = args.str("data", "");
    const auto threads = args.list("threads", {1, 2, 4, (uint64_t)max_threads()});
    const auto clients = args.list("clients", {1, 2, 4, (uint64_t)max_threads()});
    const int reps = args.i32("reps", 11);
    const double secs = args.f64("seconds", 5.0);
    const std::string tmpl = args.str("template", "sum");
    const std::string out = args.str("out", "bench/results/e8_e10_scale.csv");

    auto he = he_from_args(args);
    Modulus mod(he->plaintext_modulus());

    Dataset ds = data.empty()
                     ? Dataset::synthetic(args.u64("ntags", 15347),
                                          args.u64("nd", 405184), 1.15, 99)
                     : Dataset::load(data);
    Owner owner(ds, mod, 1234);
    const auto templates = default_templates(ds, 7);
    std::fprintf(stderr, "   building fast-path provider state...\n");
    ProviderState st = build_provider_state(owner, *he, templates, false);

    Csv csv(out, {"experiment", "N", "Nd", "template", "threads", "clients",
                  "latency_ms_median", "latency_ms_p25", "latency_ms_p75",
                  "queries_per_sec", "reps", "he_params", "cpu"});

    DpfScheme scheme(mod, 2, ds.n_tags);
    Provider prov(*he, st, mod);
    std::mt19937_64 rng(77);

    // ---- E8: one query, varying thread count ----
    for (uint64_t t : threads) {
        Token tok;
        scheme.gen(rng() % ds.n_tags, 1, tok);
        std::vector<uint64_t> e(ds.n_tags);
        const Stat s = repeat(reps, [&] {
            scheme.eval_full(tok, 0, e.data(), ds.n_tags, (int)t);
            (void)prov.fast_agg(e.data(), tmpl);
        });
        csv.row("e8-core-scaling", ds.n_tags, ds.n_records, tmpl, t, (uint64_t)1,
                s.median, s.p25, s.p75, 1000.0 / s.median, reps,
                he->param_string(), cpu_model());
        std::fprintf(stderr, "[e8] threads=%-3llu  %8.3f ms\n",
                     (unsigned long long)t, s.median);
    }

    // ---- E10: many concurrent single-threaded queries ----
    for (uint64_t c : clients) {
        std::atomic<uint64_t> done{0};
        std::atomic<bool> stop{false};
        std::vector<double> lat_all;
        std::vector<std::vector<double>> lat(c);
        std::vector<std::thread> workers;
        const double t_start = now_ms();
        for (uint64_t w = 0; w < c; ++w) {
            workers.emplace_back([&, w] {
                std::mt19937_64 r(1000 + w);
                std::vector<uint64_t> e(ds.n_tags);
                while (!stop.load(std::memory_order_relaxed)) {
                    Token tok;
                    scheme.gen(r() % ds.n_tags, 1, tok);
                    const double t0 = now_ms();
                    scheme.eval_full(tok, 0, e.data(), ds.n_tags, 1);
                    (void)prov.fast_agg(e.data(), tmpl);
                    lat[w].push_back(now_ms() - t0);
                    done.fetch_add(1, std::memory_order_relaxed);
                }
            });
        }
        while (now_ms() - t_start < secs * 1000.0)
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
        stop.store(true);
        for (auto& th : workers) th.join();
        const double elapsed = (now_ms() - t_start) / 1000.0;

        for (const auto& v : lat) lat_all.insert(lat_all.end(), v.begin(), v.end());
        std::sort(lat_all.begin(), lat_all.end());
        const double med = lat_all.empty() ? 0 : lat_all[lat_all.size() / 2];
        const double p25 = lat_all.empty() ? 0 : lat_all[lat_all.size() / 4];
        const double p75 = lat_all.empty() ? 0 : lat_all[3 * lat_all.size() / 4];
        const double qps = done.load() / elapsed;

        csv.row("e10-throughput", ds.n_tags, ds.n_records, tmpl, (uint64_t)1, c,
                med, p25, p75, qps, (int)lat_all.size(), he->param_string(),
                cpu_model());
        std::fprintf(stderr, "[e10] clients=%-3llu  %8.2f q/s  median %.3f ms\n",
                     (unsigned long long)c, qps, med);
    }
    return 0;
}
