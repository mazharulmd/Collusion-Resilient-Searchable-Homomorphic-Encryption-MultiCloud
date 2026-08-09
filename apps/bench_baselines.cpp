// SPDX-License-Identifier: Apache-2.0
//
// Baselines (i)-(v) of Section VIII-E, on the same corpus and machine as
// CR-SHE.
//
//   (i)   plaintext linear scan
//   (ii)  single-server searchable encryption
//   (iii) Path ORAM
//   (iv)  distributed-trust search only, DORY-style
//   (v)   faithful homomorphic equality scan -- see apps/bench_fhe_scan.cpp,
//         which is a separate binary because it is slow by construction.

#include <cmath>
#include <cstdio>
#include <random>
#include <vector>

#include "crshe/baselines.hpp"
#include "crshe/bench_util.hpp"
#include "crshe/dataset.hpp"
#include "crshe/index.hpp"
#include "crshe/protocol.hpp"

using namespace crshe;

namespace {

// A tag whose posting list is close to the median *among non-empty lists*, so
// the |S|-dependent baselines are not measured on an outlier -- and, more
// importantly, not on an empty one.  Subsampling the record set empties many
// posting lists, and a probe tag with |S| = 0 would make every baseline that
// scales with |S| look free.
uint64_t median_tag(const Dataset& ds) {
    std::vector<std::pair<uint64_t, uint64_t>> v;
    v.reserve(ds.n_tags);
    for (uint64_t x = 0; x < ds.n_tags; ++x)
        if (ds.posting_len(x) > 0) v.push_back({ds.posting_len(x), x});
    if (v.empty())
        throw std::runtime_error(
            "every posting list is empty at this N_d; raise --nd");
    std::sort(v.begin(), v.end());
    return v[v.size() / 2].second;
}


}  // namespace

int main(int argc, char** argv) {
    Args args(argc, argv);
    banner("bench_baselines");

    const std::string data = args.str("data", "");
    const int reps = args.i32("reps", 11);
    const uint64_t nd = args.u64("nd", 100000);
    const std::string out = args.str("out", "bench/results/e5_baselines.csv");
    const uint64_t fhe_q = args.u64("fhe-q", 65537);
    const int oram_reps = args.i32("oram-reps", 5);

    auto he = he_from_args(args);
    Modulus mod(he->plaintext_modulus());

    Dataset full = data.empty()
                       ? Dataset::synthetic(args.u64("ntags", 15347),
                                            args.u64("ntotal", 405184), 1.15, 99)
                       : Dataset::load(data);
    Dataset ds = full.subsample_records(nd);
    const uint64_t x = median_tag(ds);
    const uint64_t S = ds.posting_len(x);
    std::fprintf(stderr, "   corpus    : N=%llu Nd=%llu, probe tag has |S|=%llu\n",
                 (unsigned long long)ds.n_tags, (unsigned long long)ds.n_records,
                 (unsigned long long)S);

    Csv csv(out, {"baseline", "N", "Nd", "matched_S", "server_ms_median",
                  "server_ms_p25", "server_ms_p75", "client_ms_median",
                  "downlink_bytes", "reps", "extrapolated", "leakage", "note"});

    // ---- (i) plaintext linear scan ----
    {
        PlaintextScan ps(ds);
        volatile uint64_t sink = 0;
        const Stat s = repeat(reps, [&] { sink = ps.aggregate(x); });
        (void)sink;
        csv.row("plaintext-scan", ds.n_tags, ds.n_records, S, s.median, s.p25, s.p75,
                0.0, (uint64_t)8, reps, "no",
                "everything: query, matched set, |S|, result",
                "index lookup + sum over the posting list");
        std::fprintf(stderr, "[plaintext]     %10.4f ms\n", s.median);
    }

    // ---- (ii) single-server searchable encryption ----
    {
        uint8_t key[16];
        std::mt19937_64 rng(8);
        for (int b = 0; b < 16; b += 8) { uint64_t v = rng(); std::memcpy(key + b, &v, 8); }
        SseIndex sse(ds, key);
        const uint64_t tk = sse.token(x);
        volatile size_t sink = 0;
        const Stat s = repeat(reps, [&] { sink = sse.search(tk).size(); });
        (void)sink;
        const auto& blob = sse.search(tk);
        const Stat cs = repeat(reps, [&] { (void)sse.decrypt_and_sum(x, blob); });
        csv.row("sse-single-server", ds.n_tags, ds.n_records, S, s.median, s.p25,
                s.p75, cs.median, (uint64_t)sse.blob_bytes(x), reps, "no",
                "search pattern, access pattern, |S| (downlink grows with |S|)",
                "PRF token -> hash table -> AES-CTR posting list");
        std::fprintf(stderr, "[sse]           %10.4f ms server, %.4f ms client, "
                             "%zu B down\n", s.median, cs.median, sse.blob_bytes(x));
    }

    // ---- (iii) Path ORAM ----
    {
        PathOram oram(ds.n_records, 8, 12345);
        std::mt19937_64 rng(3);
        // Warm the tree so the stash reaches steady state before timing.
        for (uint64_t i = 0; i < std::min<uint64_t>(ds.n_records, 20000); ++i)
            oram.write(i % ds.n_records, std::vector<uint64_t>(8, i));

        std::vector<uint32_t> post(ds.postings.begin() + ds.offset[x],
                                   ds.postings.begin() + ds.offset[x + 1]);
        const Stat per_access = repeat(std::max(reps, 25), [&] {
            (void)oram.read(rng() % ds.n_records);
        });
        // A keyword query costs one access per matched record, plus one to look
        // up the (also oblivious) index entry.
        const double query_ms = per_access.median * (double)(S + 1);
        csv.row("path-oram", ds.n_tags, ds.n_records, S, query_ms,
                per_access.p25 * (double)(S + 1), per_access.p75 * (double)(S + 1),
                0.0, (uint64_t)(oram.bytes_per_access() * (S + 1)),
                std::max(reps, 25), "yes",
                "hides the access pattern from one server; reveals |S| through "
                "the number of accesses",
                "Z=4, " + std::to_string(oram.levels()) + " levels, " +
                    std::to_string(per_access.median) + " ms per access x (|S|+1)");
        std::fprintf(stderr, "[path-oram]     %10.4f ms per access, %.2f ms per query "
                             "(|S|=%llu), stash=%zu\n",
                     per_access.median, query_ms, (unsigned long long)S,
                     oram.stash_size());
        (void)oram_reps;
    }

    // ---- (iv) distributed-trust search only, DORY-style ----
    // The same DPF selection CR-SHE runs, stopping at the selection vector.
    // The difference between this row and the CR-SHE fast-path row in
    // e2_agg.csv is exactly the cost of adding oblivious analytics to
    // oblivious selection.
    {
        Owner owner(ds, mod, 1234);
        const auto templates = default_templates(ds, 7);
        const unsigned __int128 need = masked_index_bytes(ds.n_tags, ds.n_records);
        const uint64_t avail = available_ram_bytes();
        if (avail && need > (unsigned __int128)avail / 2) {
            char note[256];
            std::snprintf(note, sizeof note,
                          "SKIPPED: replicated index would need %.1f GB",
                          (double)need / 1e9);
            csv.row("dory-style-search", ds.n_tags, ds.n_records, S, 0.0, 0.0, 0.0,
                    0.0, (uint64_t)0, 0, "no", "hides query and access pattern "
                    "from n-1 colluding servers; no analytics", note);
            std::fprintf(stderr, "[dory-style]    %s\n", note);
        } else {
            ProviderState st = build_provider_state(owner, *he, templates, true);
            Provider prov(*he, st, mod);
            DpfScheme sc(mod, 2, ds.n_tags);
            Token tok;
            sc.gen(x, 1, tok);
            std::vector<uint64_t> e(ds.n_tags);
            const Stat s = repeat(std::max(3, reps / 3), [&] {
                sc.eval_full(tok, 0, e.data(), ds.n_tags);
                (void)prov.retrieve(e.data());
            }, 0);
            csv.row("dory-style-search", ds.n_tags, ds.n_records, S, s.median, s.p25,
                    s.p75, 0.0, (uint64_t)(ds.n_records * sizeof(uint64_t)),
                    std::max(3, reps / 3), "no",
                    "hides query and access pattern from n-1 colluding servers; "
                    "no analytics, and the client learns S",
                    "DPF full-domain eval + Theta(N*Nd) contraction, no HE");
            std::fprintf(stderr, "[dory-style]    %10.4f ms\n", s.median);
        }
    }

    // Baseline (v), the faithful homomorphic equality scan, lives in its own
    // binary: it builds a deliberately depth-heavy BFV context and can run for
    // many minutes, and a slow or aborted run there must not cost us the rows
    // above. Run bench_fhe_scan separately (run_all.sh wraps it in `timeout`).
    std::fprintf(stderr,
                 "\n[fhe-scan]      run separately:\n"
                 "                build/bench_fhe_scan --data=... "
                 "--out=bench/results/e5_fhe_scan.csv\n");

    return 0;
}
