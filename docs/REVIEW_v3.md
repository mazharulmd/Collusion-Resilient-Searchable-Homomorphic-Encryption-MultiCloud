# Review of the v3 manuscript (2026-10-25)

**This is a self-review by the AI session that drafted v3. It is not peer review,
not an outside review, and not an independent AI review.** The research-integrity
rules ask for a separate session briefed only with the paper; that has not been done.

Method: the whole of `paper/v3/CRSHE_v3.tex` was read. Every number in the range and
packed-index sections was checked against `results/range_aggregation.json`,
`results/packed_index.json` and `results/ops_and_retrieval_bound.json`. The paper's
descriptions of the tests and the MAC layout were checked against
`tests/test_rangeagg.py` and `crshe/rangeagg.py`.

## Errors found and fixed

| # | Where | Problem | Fix |
|---|---|---|---|
| 1 | §Range results | Said the edge box makes two of eight corners dummies. The measured box `[[0,0],[0,239],[0,4]]` starts at the origin on every axis, so seven of the eight are dummies (and the whole-timeline box already has four) | Corrected |
| 2 | Related work, §Complexity | Single-server retrieval bound still the unpacked "≥3×" / `NN_d/ℓ`. With packing applied to both sides it is 1.5–3.1× and `N⌈N_d/32⌉/ℓ` | Corrected |
| 3 | Definition 3, proof of Theorem 2 | The static view and query types omitted the summed-area tables and range queries, although the threat model and hybrid H2 include them | Added to the definition and to hybrid H3 |
| 4 | Setup leakage | Cube shapes are public but were not in `L_Setup` | Added `{(s_1..s_d)}` |
| 5 | §Range | Per-cell keys written `F''(c)`, colliding with the fast path's per-row keys `F''(x)`. The code domain-separates them (`DOMAIN_CUBE_MAC`, cube id) | Now `F''(cube, c)`; combined-layout MAC also described |
| 6 | Lemma 3 | Bound `2^d/p` is loose: acceptance needs every segment to pass, so `1/p` | Tightened, proof adjusted |
| 7 | Remark after Lemma 3 | "`T_f[c]=0` only if the box holds no record" is false for `sum` with zero values | Qualified |
| 8 | §Range "why not interval FSS" | Claimed a box "cannot" be formed; unsupported, since FSS for richer classes exists and was not checked | Softened; author check added |
| 9 | Proposition 1 reduction | Needs queries formed independently of the data | Stated |
| 10 | Algorithm 2 | `CombineDec` built `S` from the packed word vector | `unpack(...)` added |
| 11 | Abstract, contribution bullet | "shrinks retrieval 32-fold": the index shrinks 32×; measured retrieval speed-up is 19–27× | Corrected; single-server 44 MB marked as computed |
| 12 | Highlight 4 | "sharing cannot replace HE" overstates Proposition 1, which shows it needs single-server PIR (OT), not HE specifically | Reworded |
| 13 | §Range results | 1,351 × 0.0923 ms = 124.7 ms, printed as 124 | 125 |
| 14 | AI declaration | Did not mention the new range section, lemma, results, or literature search | Extended. The authors must still check it against what they did |

## Weaknesses a referee is likely to raise (not fixable by editing)

1. **Novelty of the range path may be judged incremental.** It is the fast path (one
   DPF read of an encrypted column) applied to a summed-area table at `2^d` points. The
   dummy-key padding, the signed outputs and the per-cell MAC lemma are the new parts.
   The paper should argue why that combination is non-obvious, or add something deeper
   (for example sublinear provider work, or verification of the combined layout).
2. **Prior art is unread.** Hafiz et al. (NDSS 2024), HADES, ARQ and Hayata et al. were
   seen as abstracts or search summaries only. If any of them already supports box
   aggregates over encrypted data at `t = n−1`, the main claim falls.
3. **Evaluation.** The range and packed-index results are synthetic data in a Python
   driver. Other tables come from a C++ prototype in an older layout. A referee will
   ask for one implementation, real corpora, and a cross-region run.
4. **Malicious security.** Only detection, with a global MAC in the combined layout and
   on the flexible path. Per-user authorisation is stated as unsolved.
5. **`n > 2` is non-succinct.** Key-size claims hold only for two providers.
6. **Length.** 29 pages, with C++ subsections (selection latency, core scaling, second
   corpus) that do not support the range claim. Consider moving them to an appendix.

## Not done

- No separate-session adversarial review, and no refutation pass on these findings.
- None of the `\authorcheck` items is resolved. They are hidden in the submission build;
  set `\authorcheckstrue` to see them.
