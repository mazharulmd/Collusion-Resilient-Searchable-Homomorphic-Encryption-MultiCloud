# Real-corpus results from the authors' server (2026-10-26)

**Checked by the AI session that maintains this repository. This is an in-project check, not
an outside review.**

Input: `crshe_server_results_test-instance_20261026_1602.tar.gz`, produced by
`scripts/run_server_experiments.sh` on the authors' server (AMD EPYC 7J13, 32 vCPUs, 31 GB,
Python 3.12.3, OpenFHE-python 1.5.1, one thread). New files copied to `results/`; logs to
`results/server_logs_20261026/`. Files in the tarball that were already in `results/` are
byte-identical to the committed ones (they were not re-run).

## What the run established

| Step | Result | Source field |
|---|---|---|
| Unit tests | 83 passed | `server_logs_20261026/pytest.log` |
| Corpus statistics | telemetry matches the C++ builder on N, N_d, postings, max (404,702) and largest sum (908,575,470); Beijing matches on N, N_d, postings, median, mean, but **not** on max (98,878 vs 102,344) or largest sum (676,076,034 vs 698,963,226) | `corpus_stats.json` |
| Correctness | both corpora, n = 2, 3, 4, 200 tags each: fast, retrieval and flexible all correct; response 132,081 B | `correctness_{telemetry,beijing}.json` |
| Range, primary cube 3 × 11,523 × 10 (M = 345,690) | combined 767.8–788.3 ms, verified 1,185.8–1,189.6 ms per provider; uplink 2,760 / 5,520 B; edge box 775.9 / 1,192.6 ms | `range_real_telemetry.json` → `modes.*.by_window[*].provider_total.median_ms`, `edge_box` |
| Range, Beijing cube 12 × 1,461 × 11 (M = 192,852) | combined 443.5–482.3 ms, verified 682.2–768.4 ms; uplink 2,624 / 5,248 B; edge box 446.9 / 758.9 ms | `range_real_beijing_day.json` |
| Range correctness | every box checked against plaintext ground truth (`assert got == truth(box)` in `bench/bench_range_real.py`; the run used plain `python`, not `-O`) | script line 59 |
| Tamper trials on real cubes | verified layout: 250/250 detected per cube; combined layout: 50/250 detected (the inconsistent deviation), 200 wrong answers unflagged | `modes.*.tamper` |
| Leakage, four schemes × four f | see table below | `leakage_{telemetry,beijing}.json` → `runs[*].overall`, `per_class`, `random_guess` |

Leakage at f = 1 (overall share of tags re-identified; random guessing 0.0086 % and 0.0028 %):

| | Unmasked | Power of two | Volume-hiding | Masked |
|---|---|---|---|---|
| Telemetry | 0.484 % (56×) | 0.078 % (9×) | 0.0086 % (1×) | 0.0086 % (1×) |
| Beijing | 0.324 % (114×) | 0.031 % (11×) | 0.0028 % (1×) | 0.0028 % (1×) |

## Findings that changed the manuscript

1. **The corpus check was weaker than it looked.** N, N_d and the posting total are the same for
   any band rule. The script now also checks the maximum posting length and largest single-tag
   sum. Failure control: run on this tarball's `corpus_stats.json`, it prints `telemetry OK` and
   `beijing MISMATCH` on max and largest sum. Observed: as stated.
2. **The C++ leakage figures are withdrawn.** The reference run disagrees with the C++ table
   (e.g. telemetry CO/LPG/smoke bands 32.5 % vs 100 %, Beijing sites 33.3 % vs 100 %, minute
   windows 0.2 % vs 3.80 %). One C++ figure is impossible under the attack model:
   - Claim: an attacker who sees only row statistics expects at most one correct assignment per
     distinct observed value, whatever its strategy and auxiliary knowledge.
   - Status: proved (rows with equal statistics are indistinguishable, so for a group of k such
     rows the attacker's guess has the same distribution for each, and the expected number of
     correct guesses is Σ_x P(guess = x) ≤ 1).
   - Access: reasoning.
   - Applied: a Beijing hourly window holds at most one record per site, so its length is one of
     at most 12 values, and at most 12 of 35,046 hourly windows (0.034 %) can be re-identified.
     The C++ table reports 0.31 %.
   - Not claimed: which mechanism the C++ attack used. The most plausible is tie-breaking in an
     order that follows the true labels; the C++ code is not in this repository.
3. **Volume-hiding inflation for Beijing** is 752× with this loader's maximum (35,162 × 98,878 /
   4,624,070), not 778× (the C++ maximum). Both are computed, not measured.
4. **Range on real data** replaces the "synthetic cube only" limitation in the abstract,
   contributions, evaluation, limitations and conclusion. The synthetic-cube tables stay, for the
   layout comparison and the cube-size sweep.

## Follow-up: per-tag lengths (Job 1b, same day)

Input: `results/lengths_{telemetry,beijing}.csv.gz` and `lengths_summary.json` from
`bench/dump_lengths.py` on the server. Analysis: `bench/leakage_bounds.py` →
`results/leakage_bounds.json`.

```
Check: bench/leakage_bounds.py for the leakage table and the length-only bounds
Binds: results/lengths_*.csv.gz (server, 2026-10-26), results/leakage_*.json
Success match: "reproduced=True control_failed=True" per corpus; exit status 0
Failure control: one non-time tag given the length of another unique tag (a planted tie) must
  break the reproduction, because at f = 1 a miss happens only on ties. Observed: breaks it
  (telemetry 0.4836 % -> 0.4750 %, Beijing 0.3242 % -> 0.3214 %). A first control (+1 to a
  unique length) did not fail on Beijing, since the length stayed unique; it was replaced.
Number taken from: leakage_bounds.json -> <corpus>.per_class.<class>.length_only_bound,
  overall_length_only_bound, inflation_power_of_two, inflation_volume_hiding
```

| Quantity | Telemetry | Beijing |
|---|---|---|
| Distinct posting lengths / tags | 56 / 11,580 | 114 / 35,162 |
| Overall length-only bound (= reference rate at f = 1) | 0.484 % | 0.324 % |
| C++ overall claim | 4.27 % | not reported |
| Time class: distinct lengths, bound, C++ claim | minutes: 20 (14–43), 0.174 %, 3.80 % | hours: 7 (4–12), 0.020 %, 0.31 % |
| Sites: distinct lengths, bound, C++ claim | n/a | 4 of 12, 33.3 %, 100 % |
| Power-of-two padding storage | 1.549× | 1.536× |
| Volume-hiding padding storage | 1,285.1× | 751.9× |

The bounds use this repository's corpus build. Only the hourly bound (≤ 12 values, one record per
site per hour) holds for any build. Site lengths depend only on which records lack a temperature,
which both builders drop (both report N_d = 420,370). The minute bound would need minutes with at
least 438 messages under another bucketing, against a mean of 35 (reasoning, not checked against
the C++ build).

## Still open

- C++ port of the range path; cross-region deployment; an outside reading of the proofs.
