# Audit of the second round of ChatGPT/Gemini drafts (2026-10-26)

**An in-project check by the AI session that maintains this repository. It is not an outside review.**

Inputs (kept verbatim in `paper/v5/inputs/`):

| Draft | File | Basis |
|---|---|---|
| D | `draftD_CRSHE_v4_reviewed.tex` ("v4.1, reviewer-corrected") | v4, with cautious rewording and proof caveats |
| E | `draftE_crshe_v5.tex` ("v5") | v4, with algorithm and proof refinements, new prior-art claims, and removed caveats |

Output: `paper/v5/CRSHE_v5.tex`, built on draft E, with draft D's valid corrections and the
fixes below. Method: full diffs of D and E against v4; `scripts/audit_draft_numbers.py` on both;
compiling both; search-summary checks of the new prior-art claims (full texts still blocked:
`arxiv.org` fails DNS resolution, `ndss-symposium.org` and `eprint.iacr.org` are refused by the proxy).

## Draft E (v5): errors found and fixed

| # | Problem | Severity | Fix |
|---|---|---|---|
| 1 | `\let\inputtbl\relax` replaced the table loader: **the file does not compile** (no PDF), and if forced, every generated table is empty | Blocking | Restored `\@@input`; compiles, 33 pages, tables present |
| 2 | `\authorcheck` macro deleted, together with eight open-item markers whose items are still open (C++ rejection sampler, padding baselines, real-corpus correctness, C++ re-measurement, FSS comparison) | Integrity | Macro restored (hidden in the submission build); markers restored |
| 3 | **Unmeasured padding-attack numbers reintroduced**: Pow2 inflation 1.55× / 1.51×, re-identification 50.0–75.0 % and 2.25–9.11 %. They come from draft B and have no source; `bench_leakage.py` has never run on the corpora | Fabricated data | Removed; the computed 1,285× / 778× volume-hiding factors kept; the "not yet run" statement restored |
| 4 | Abstract and conclusion attribute range results to "two real IoT corpora"; range aggregation was measured only on a synthetic cube | Overclaim | Reworded: the C++ single-keyword results are on real corpora, range results on a synthetic cube with real dimensions |
| 5 | The "Evaluation" and "Prior art" limitations and the reason the data are synthetic were deleted | Overclaim | Restored |
| 6 | AI declaration changed to "language polishing, copy-editing, and formatting scripts". AI tools wrote the reference implementation, benchmarks, proofs and sections | Integrity (Elsevier policy) | Accurate declaration restored, now also covering the ChatGPT/Gemini review drafts |
| 7 | Prior-art specifics stated as fact: Obscure needs n ≥ 2ℓt+1 servers (t < c/(2ℓ)), 13–25 servers in its benchmarks, k-way-tree ranges; Hafiz et al. collusion t ≤ n−u with u-batch polynomial coding; Splinter supports ranges; HADES not malicious-secure and hides \|S\|; SHAMC partial ranges. The "no priority claim" sentence and the "?" cells were removed | Unverified | Search summaries confirm only part (see below). Kept what is supported; unverified specifics are hedged, with `\authorcheck` markers; "?" cells and the priority disclaimer restored |
| 8 | Abstract 259 words by the hyphen-split count (over 250) | Format | 246 |

### What the search summaries support (access: `search-summary`, not a reading)

* **Obscure** (arXiv 2004.13115): unary encoding of values, Shamir shares from equal-degree
  polynomials, c non-communicating servers. **Not confirmed:** the server/degree/threshold
  formula, "13–25 servers", the range mechanism.
* **Hafiz et al.** (NDSS 2024): Shamir-shared query vector, servers hold the database and
  multiply by aggregate-query index matrices, a v-Byzantine-robust variant (Sec. VI-C).
  **Not confirmed:** t ≤ n−u, polynomial batch coding, range support.
* **HADES** (PVLDB 18(7), 2025): single server, public data, FHE, point and range predicates,
  one round. **Not confirmed:** malicious security, hiding \|S\|.
* **Splinter** (NSDI 2017): MAX, TOPK, disjunctions, filters and aggregates. **Not confirmed:** range predicates.

### Draft E changes kept (checked correct)

* Theorem 1 and Algorithm 1 restated for the packed index (`pack(I)+P`).
* Algorithm 2 and the flexible-path text show the second key set (`\hat\kappa_j`, `\hat v_j`) and the δ_s check.
* Security bound: 2·Adv^PRF for both flexible shares, and the hybrid covers δ_s.
* Retrieval complexity Θ(N N_d/π).
* Justification that range cost depends only on cube dimensions (kept, with the reason the data are synthetic restored).
* Multi-owner extension as a limitation.
* Obscure, Hafiz et al. and HADES positioned more concretely (to the extent supported, above).

## Draft D (reviewed v4): corrections adopted

| Item | Status |
|---|---|
| Modular-reduction bias: the old estimate N·N_d·2⁻⁶⁴ was wrong; per-word statistical distance r(p−r)/(p·2⁶⁴) ≈ 8.27×10⁻¹⁰, union bound ≈ 0.12 over the 146,625,960 packed words | **Verified numerically and adopted.** Added: over the unpacked C++ index (4.69×10⁹ words) the bound exceeds 1, so Theorem 1 does not cover the index the C++ leakage experiment used |
| "1.06–1.27 s" is the evaluation of both key sets, not the added cost | **Adopted** (combined layout's single set: 0.45–0.51 s) |
| Theorem 2 needs explicit assumptions (≥1 honest provider, secret δ_s, no DU collusion, honest keys unseen) and the trials are not a measurement of the bound | **Adopted** |
| Proposition 2 is conditional on provider-side enforcement | **Adopted** |
| Proposition 1 and its reduction are not a universal lower bound | **Adopted**, kept precise: the e₁ = e₂ case has negligible probability by DPF privacy (D left it open), and the reduction holds within its stated class |
| Single-server retrieval figure is a cost model, not a measured optimised system | **Adopted** |
| Total uplink 11,040 B for two providers | Correct; the abstract states 5,520 B per provider |
| Very defensive abstract | Not adopted verbatim; v5's abstract states the contribution with the scope qualifiers |
| `\authorcheckstrue` | Submission build keeps them hidden; open items remain in the source |

## Numbers

* Draft D: every number traces to v4, the results or arithmetic (11,040 = 2×5,520; 146,625,960 = N·⌈N_d/32⌉; 8.27×10⁻¹⁰ verified).
* Draft E: five numbers have no source (1.55, 2.25, 9.11, 50.0, 75.0), all removed.
* Corrected v5: the only numbers not in a source are 0.51 (512.1 ms), 146,625,960 (computed) and the arXiv identifier.
