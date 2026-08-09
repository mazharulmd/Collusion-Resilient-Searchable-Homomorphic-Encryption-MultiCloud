// SPDX-License-Identifier: Apache-2.0
//
// E9: dynamic ingest.  The two-tier index of Section V-G keeps a static tier
// rebuilt every B insertions and a hot buffer of at most B records scanned by
// the same oblivious contraction.  This measures the amortised rebuild cost and
// the steady-state insertion throughput as a function of B, and the online
// overhead the buffer adds to a query.
//
//   build/bench_ingest --data=data/telemetry.crshe \
//                      --B=256,1024,4096,16384 --out=bench/results/e9_ingest.csv

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
    banner("bench_ingest (E9)");

    const std::string data = args.str("data", "");
    const auto Bs = args.list("B", {256, 1024, 4096, 16384});
    const uint64_t inserts = args.u64("inserts", 20000);
    const uint64_t tau = args.u64("tau", 4);      // tags carried by a new record
    const int threads = args.i32("threads", 0);
    const std::string out = args.str("out", "bench/results/e9_ingest.csv");

    auto he = he_from_args(args);
    Modulus mod(he->plaintext_modulus());

    Dataset ds = data.empty()
                     ? Dataset::synthetic(args.u64("ntags", 15347),
                                          args.u64("nd", 100000), 1.15, 99)
                     : Dataset::load(data);
    Owner owner(ds, mod, 1234);
    const auto templates = default_templates(ds, 7);
    const Template& f = templates[1];   // sum

    Csv csv(out, {"N", "Nd", "B", "tau", "inserts",
                  "insert_us_median", "inserts_per_sec",
                  "rebuild_ms", "amortised_rebuild_us_per_insert",
                  "buffer_scan_ms_at_full_B", "total_online_overhead_pct",
                  "he_params", "cpu"});

    // The static tier's fast-path column, as a plaintext array; a rebuild
    // recomputes A_f and re-encrypts the affected packed ciphertexts.
    std::vector<uint64_t> A = owner.compute_A(f);
    const size_t slots = he->slots();

    std::mt19937_64 rng(4242);

    // Baseline query cost against the static tier only.
    DpfScheme scheme(mod, 2, ds.n_tags);
    ProviderState st = build_provider_state(owner, *he, templates, false, threads);
    Provider prov(*he, st, mod);
    Token tok;
    scheme.gen(rng() % ds.n_tags, 1, tok);
    std::vector<uint64_t> e(ds.n_tags);
    const Stat base = repeat(7, [&] {
        scheme.eval_full(tok, 0, e.data(), ds.n_tags, threads);
        (void)prov.fast_agg(e.data(), f.name);
    });
    std::fprintf(stderr, "   static-tier query: %.3f ms\n", base.median);

    for (uint64_t B : Bs) {
        // ---- insertion into the hot buffer ----
        // A new record carrying tau tags updates A_f at tau addresses in
        // plaintext at the owner; no decryption is involved.
        std::vector<uint64_t> buf_values;
        std::vector<std::vector<uint32_t>> buf_tags;
        std::vector<double> ins_us;
        for (uint64_t k = 0; k < std::min(inserts, B); ++k) {
            const double t0 = now_ms();
            std::vector<uint32_t> tags(tau);
            for (uint64_t j = 0; j < tau; ++j) tags[j] = (uint32_t)(rng() % ds.n_tags);
            buf_values.push_back(1000 + rng() % 2500);
            buf_tags.push_back(tags);
            for (uint32_t x : tags) A[x] = mod.add(A[x], buf_values.back());
            ins_us.push_back((now_ms() - t0) * 1000.0);
        }
        std::sort(ins_us.begin(), ins_us.end());
        const double ins_med = ins_us.empty() ? 0 : ins_us[ins_us.size() / 2];

        // ---- rebuild of the static tier every B insertions ----
        // Recompute A_f and re-encrypt the ceil(N/l) packed ciphertexts.
        const Stat rb = repeat(3, [&] {
            std::vector<uint64_t> A2 = owner.compute_A(f);
            for (size_t k = 0; k < buf_tags.size(); ++k)
                for (uint32_t x : buf_tags[k]) A2[x] = mod.add(A2[x], buf_values[k]);
            (void)he->encrypt_vector(A2);
        }, 0);

        // ---- online cost of scanning a full buffer ----
        // The buffer is scanned by the same oblivious contraction, over a
        // B-record index, so it costs a DPF pass plus a B-wide inner product.
        Dataset bufds = Dataset::synthetic(ds.n_tags, B, 1.15, 5);
        Owner bufowner(bufds, mod, 99);
        const auto buftpl = default_templates(bufds, 7);
        ProviderState bst = build_provider_state(bufowner, *he, buftpl, false, threads);
        Provider bprov(*he, bst, mod);
        std::vector<uint64_t> be(bufds.n_tags);
        const Stat scan = repeat(7, [&] {
            scheme.eval_full(tok, 0, be.data(), bufds.n_tags, threads);
            (void)bprov.fast_agg(be.data(), f.name);
        });

        const double amort_us = rb.median * 1000.0 / (double)B;
        const double overhead = 100.0 * scan.median / base.median;

        csv.row(ds.n_tags, ds.n_records, B, tau, std::min(inserts, B), ins_med,
                ins_med > 0 ? 1e6 / ins_med : 0.0, rb.median, amort_us,
                scan.median, overhead, he->param_string(), cpu_model());
        std::fprintf(stderr,
                     "B=%-7llu insert=%7.2f us (%.0f/s)  rebuild=%8.1f ms "
                     "(%.2f us/insert amortised)  buffer scan=%.3f ms (+%.0f%%)\n",
                     (unsigned long long)B, ins_med, ins_med > 0 ? 1e6 / ins_med : 0.0,
                     rb.median, amort_us, scan.median, overhead);
        (void)slots;
    }
    return 0;
}
