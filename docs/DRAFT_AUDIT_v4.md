# Audit: did v4 combine the ChatGPT/Gemini drafts? (2026-10-25)

**This is an in-project check by the AI session that assembled v4. It is not an outside review.**

Question asked by the author: were the two drafts edited with ChatGPT and Gemini (draft B,
`paper/v4/inputs/draftB_Cr_She_Upgraded_Manuscript.tex`; draft C,
`paper/v4/inputs/draftC_CRSHE_v3_peer_review_working_draft.tex`) actually combined into v4?

## Short answer

Not completely, before this audit. The first v4 took draft B's ideas and draft C's corrections,
but it had three gaps:

1. **It wrongly dismissed real data that draft B had carried over.** About twenty of draft B's
   numbers are the authors' own C++ measurements from the FGCS submission and its revision
   (second-corpus table, throughput, ingest, DORY gap, headroom, two comparison-table rows). The
   v4 merge log called several of them "no measurement found". That was wrong: they are in
   `paper/revision/CRSHE_revised.tex`. They are now restored, **from the revision, not from
   draft B**, because draft B changed some of them (below).
2. **One draft-C correction was missed**: the deployment section still said a cross-region
   deployment "adds [wide-area latency] unchanged". Fixed.
3. **Draft B's threat-model structure was not used**, so v4's threat model still described the
   MAC checks and authorisation as they were in v3, out of step with v4's own Theorem 2 and
   Proposition 2. Fixed.

After this audit, every item of both drafts is either in v4, superseded by something measured,
or left out for a stated reason. Every number in v4 traces to a results file, an earlier
manuscript, or arithmetic on those.

## Method

`scripts/audit_draft_numbers.py <draft.tex>` extracts every number from a draft and looks it up in
v4, the FGCS submission, the revision (with its generated tables), and `results/*.json` (with
rounded forms). Prose items were checked by reading each draft against v4 section by section.

```
python scripts/audit_draft_numbers.py paper/v4/inputs/draftB_Cr_She_Upgraded_Manuscript.tex
python scripts/audit_draft_numbers.py paper/v4/inputs/draftC_CRSHE_v3_peer_review_working_draft.tex
```

Draft B: **305** distinct numbers. **209** are in v4. **21** appear only in earlier sources (results
files or the authors' earlier manuscripts); each was checked, see below. **75** appear in no source.

Draft C: every number comes from v3 and is either in v4 or superseded by v4's newer measurements.

The reverse check (numbers in v4 found in no source) returns only derived values: seconds from
milliseconds (1.06, 1.27, 1.40, 1,385), sums and doublings (47.0 = 2×23.5, 62.8 = 2×31.4, 520 =
2×260, 588 = 2×294, 825,554 and 46,742 corpus totals, 22 and 33 tag-class sums), counts (79 tests,
4,000 trials), ratios (109 = 67.5/0.62, 6.25 % = 2^32/p), and two computed padding factors
(1,285 and 778, from N·max/total postings), each labelled computed in the text.

## Draft B: numbers that contradict the authors' measurements

These are the reason restored data were taken from the revision, not from draft B.

| Quantity | Measured (revision, C++) | Draft B |
|---|---|---|
| Second-corpus fast path at N_d = 10³ | 54.6 ms (warm-up artefact, stated) | 40.3 ms |
| Second-corpus general path, N_d = 10³…10⁵ | 106.3, 86.9, 99.7, 145.5, 220.8, 382.0 ms | 68.4, 74.2, 83.5, 104.1, 148.6, 218.4 ms (relabelled as a Z_{2^16} path never implemented) |
| Second-corpus general path, N_d = 2×10⁵, 4.05×10⁵ | refused by the harness (memory budget) | 312.0 and 498.5 ms |
| Selection latency at N = 35,162 | the revision states it was **not measured** and declines to quote it | 1.180, 0.680, 0.512, 0.520, 0.610 ms |
| Unauthorised-row extraction | 512/512 rows recovered (no policy existed) | "0/512 recovered under HE-QAuth" |

## Draft B: numbers with no source (75), by group

| Group | Examples | Decision |
|---|---|---|
| Emulated WAN run | 32.20, 33.85, 35.04, 68.39, 70.22, 72.15 ms | No run exists. Left out |
| Padding-attack results | Pow2 50.0–75.0 %, 2.00–9.11 %; VH 0.01 %, 0.003 %; "800–3,200× above random" | `bench_leakage.py` was never run on the corpora. Left out (author action) |
| Padding inflation | 1,272×, 465×; Pow2 1.55× | Do not follow from the corpus statistics. v4 states the **computed** volume-hiding factor instead: 1,285× and 778×. The Pow2 factor needs per-list data we lack |
| Z_{2^16} index | 9.38, 28.49, 14.25, 2.32, 7.03 GB; mask 1.4 s, 4.2 s | Unimplemented design, dominated by 32-bit packing. Left out |
| BGI15 tensor keys | 1,568, 4,832, 5,216, 9,056, 15,248, 48,032 B; "17.8–31.2× less uplink" | Not implemented; formula unchecked. Left out |
| Explicit n-party keys | 8,016 … 8,000,016 B | = 8N+16, correct arithmetic, but beyond what v4 needs; v4 keeps 92,656 and 281,312 B |
| Flexible "coupled MAC" detections | 176/0/24 | Never run. Replaced by measured session-check results (Table 15) |
| Baseline uplinks | ORAM 186,624 B etc. | No source. Left out |
| "Packing cuts 33.6 → 17.4 ms on 64 cores" | 33.6 ms is the C++ contraction without the DPF evaluation (revision); 17.4 has no source | Left out |
| Client CPU "24–108×" | from v4's own numbers the ratio is 27–109× | **Adopted, corrected** |

## Draft B: numbers found only in earlier sources (21), now handled

Restored into v4 from `paper/revision/CRSHE_revised.tex`: second-corpus table (all eight rows) and
per-class leakage table; deployment 38.67/37.65/38.47 ms and 48.17→56.04 ms; DORY-style 305.6 ms
(7.4×); equality scan 24.4 s (592×); throughput 117–124 queries/s; ingest 4.5–11.1 M records/s;
rebuild 28.7–29.1 ms; index build 16.6 s vs 5.6 s; A_f 5 ciphertexts (1.3 MB) and 2 ciphertexts
(0.53 MB); bundle 0.8 s; throughput 56.9 queries/s with two clients and under 135 ms between four
and sixteen clients; headroom 75.6× (908,575,470) and 98.3×; 4,624,070 postings; computed keys 300 B
and 281,312 B; Ubuntu 24.04 and GCC 13; Table 1 rows for pattern-hiding SSE and SHAMC.

Not restored, with reason: 33.6 ms (only meaningful with the unsourced 17.4); 75 % memory budget
(v4 states it as 47.5 GB); remaining values are colour codes, years, or reference-implementation
fields that v4 reports in another form.

## Draft B: ideas and prose

| Item | In v4? |
|---|---|
| "Selection-to-computation composition leak" | Yes (Introduction) |
| Three operational constraints | Yes (Introduction) |
| Two active threats (deviating providers, users exceeding authority) | **Yes, added in this audit** (threat model), with v4's guarantees |
| Per-record coupled MAC on the flexible path | Generalised and measured as the session check (Theorem 2) |
| HE-QAuth | Rebuilt as role-scoped access (Proposition 2), measured |
| Explicit packing layout equation | **Yes, added in this audit** (Section 5.6) |
| Complementary systems (Grotto, Floram-style ORAM) | **Yes, added in this audit** (related work, flagged not re-read) |
| Comparison rows: pattern-hiding SSE, SHAMC | **Yes, restored in this audit** (from the revision; SHAMC's range support marked "?") |
| Durability, graceful degradation, re-dealing | Yes (already in v3) |
| Canonical-embedding noise bound | No: formula not derived or checked; v4 keeps the empirical worst-case check |
| Modulus-decoupled Z_{2^16} ring | No: superseded by packing |
| Succinct BGI15 keys for n > 2 | No: not implemented; v4 states succinct constructions exist |
| LSM tiering bound | No: not implemented |
| Protocol-stage summary table | No: Algorithms 1–2 cover it (Algorithm 2 updated for the session check) |
| "AI used solely for language polishing" | No: inaccurate |

## Draft C: hunk by hunk

| Draft C change | In v4 |
|---|---|
| Abstract: per-provider figures, synthetic data stated, baseline not optimal | Yes |
| Contributions: one key per keyword query, 2^d per range | Yes |
| Per-cell MAC only for a restricted perturbation class | Superseded by Theorem 2 |
| SAT newest-slice update not implemented | Yes (Section 5.7 and Limitations) |
| Proposition 1 is not a universal impossibility | Partly: v4 states the reduction's conditions and limits it to t = n−1 |
| Packed index called an engineering optimisation | Yes |
| Tiered updates need an update-leakage analysis | Yes |
| Related work: novelty is a combination, not priority | Yes, extended with Obscure |
| Setup leakage: layout, cube, tier metadata | Yes, with role metadata |
| Lemma 3 non-adaptive restriction; zero-valued prefixes | Superseded (lemma removed) |
| 32.7 ms for four compressed templates | Yes |
| 1.8–2.9× is per provider; totals 47.0 / 62.8 ms | Yes |
| Total two-party uplink 520 / 588 B | Yes |
| Loopback only; no cross-region increment | **Missed in v4, fixed in this audit** |
| Discussion: per-provider, computed baseline | Yes |
| Limitations: duplicate posting IDs | Fixed in code and tested |
| Prior-art limitation | Yes |
| Conservative conclusion | Partly: v4's conclusion lists what is not yet shown |
| `\authorcheckstrue` | Not in the submission build; open items are in `docs/MERGE_LOG_v4.md` |

## Reviewer findings on v4 itself, fixed in this audit

* Threat model contradicted Theorem 2 and Proposition 2 (see above).
* Notation table lacked δ_s, ρ, R, K'_ρ.
* Algorithm 2 did not show the second key set or the session check.
* Theorem 2 did not name retrieval among the κ = 1 cases.
* The abstract's "every injected deviation … was detected" now says "by this check" (the
  stored-key modes did miss deviations).
* Role-scoped layout under streaming ingest needs one hot buffer per role; now stated.
