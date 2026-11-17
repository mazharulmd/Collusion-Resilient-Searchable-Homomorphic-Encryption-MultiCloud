# Focused manuscript: outline and writing guide

*2026-11-17: the authors then asked the assistant to write the full paper for IEEE Transactions on Cloud Computing. That version is `paper/tcc/`; it follows this outline and its style rules.*

Decided on 2026-11-17, after the JISA desk rejection ("presentation is below standard"):

- **Scope:** one contribution, verified one-round range aggregation over encrypted data
  stored at several clouds. Everything else is cut or moved to the supplement.
- **Writing:** the authors write the prose. The assistant checks numbers, proofs,
  references and the build.
- **Format:** LaTeX. Upload the source `.zip` and the compiled PDF.

`manuscript.tex` is a skeleton that compiles. It is 13 pages with the writing boxes and
7 without them, so the finished paper should come to about 13–15 pages. Each grey box is
one paragraph: **Write** gives the point the paragraph must make, and **Use** gives the
facts and numbers it may draw on. Delete each box once its paragraph is written. To see
the paper without the boxes, set `\skeletonfalse`.

## The argument in five sentences

Write these five sentences first; every section serves one of them.

1. IoT analysts need sums and counts over ranges of time, place and value, on data that
   is encrypted and stored at several clouds.
2. Existing systems either leave the clouds able to see which records a range touches,
   compute on plaintext, need an honest majority and server-to-server rounds, or cannot
   detect a wrong answer from colluding clouds.
3. We store encrypted running totals (summed-area tables), so that any box is a signed
   sum of 2^d entries. The analyst hides those entries in DPF keys, one share per cloud,
   and each cloud returns one ciphertext.
4. A fresh secret number sent inside a second set of keys lets the analyst detect any
   wrong answer from up to n−1 clouds at no extra homomorphic cost. This works only
   because no cloud holds the whole query.
5. On two real IoT datasets a checked range query costs under 1.2 s per cloud on one
   thread, whatever the range. It needs about 5 kB of keys where one server would need a
   44 MB query, and no tampered answer was accepted.

## Structure and page budget

| Section | Pages | Figures and tables (already in place) |
|---|---|---|
| Abstract, highlights | – | – |
| 1 Introduction | 1.5 | – |
| 2 Related work | 1 | Table 1 (closest systems) |
| 3 Model and building blocks | 1.5 | Fig. 1 (system), Table 2 (notation, 7 rows) |
| 4 Construction | 3 | Fig. 2 (box as corners), Algorithm 1 |
| 5 Security | 1.5 | Definition 1, Theorems 1–3, Remark 1 |
| 6 Implementation and setup | 1 | – |
| 7 Evaluation | 3 | Fig. 3 (real cubes), Fig. 4 (three ways), Table 3 (tamper), Fig. 5 (layouts) |
| 8 Discussion and limitations | 0.5 | – |
| 9 Conclusion | 0.3 | – |

## What was cut, and where it went

| Material in the JISA version | Now |
|---|---|
| Keyword aggregates over precomputed columns, C++ keyword figure | Cut. One sentence notes that a one-cell box covers single-cell aggregates |
| Masked, packed index; retrieval; leakage attack and padding baselines | Cut. A possible second paper |
| Flexible two-round queries (conjunctions, query-time weights) | Cut |
| Role-scoped access | Cut |
| "Why a homomorphic layer" proposition | One paragraph in Section 5, full argument in Supplementary S4 |
| Full proofs | Supplementary S1–S3, to be cut down to the range-only scheme (the theorems in the skeleton are already restricted to it) |
| "Plotted with an AI-assisted script" on every caption | Removed. The plots are drawn from measured data by a script, which is code and is covered by the AI declaration. They are not AI-generated images. **Check this against the target journal's rule on AI and figures.** |

Supplement (to build after the prose): S1 correctness proof, S2 privacy proof, S3
tamper-detection proof, S4 why a homomorphic layer is needed, S5 extra layouts. The
existing `paper/jisa/supplementary.tex` holds the material; it must be cut to the
range-only scheme.

## Style rules

These rules address what the editor criticised. Check each section against them before
moving on.

1. **One idea per sentence.** Aim for 15–25 words, and split anything over 30 words. The
   JISA version averaged 28 words per sentence, and 65 of its sentences ran over 35.
2. **No semicolon chains.** Use at most one semicolon per paragraph.
3. **Explain the idea in plain words before the symbols.** Give the intuition first, then
   the formula.
4. **No role abbreviations.** Write "data owner", "cloud" and "analyst", never DO, CP or
   DU. Define DPF and BFV once.
5. **No run-in italic headings inside paragraphs.** If a paragraph needs a heading, make
   it a subsection.
6. **Keep one running example**, the air-quality question from the Introduction, all the
   way through.
7. **Every number comes from `NUMBERS.md`, with its unit.** Say "computed" whenever a
   value was not measured. Do not round toward a claim.
8. **No "first", "novel" or "state of the art".** Say what differs from named systems, and
   say "to our knowledge".
9. **Present tense for the paper and past tense for experiments.** "We show…", "The query
   took…".
10. **Captions are one sentence that says what is plotted.** The result goes in the text.

## Prior work the novelty sentence rests on

Read in full on 2026-10-26 (`docs/NOVELTY_SEARCH.md`): Splinter, DORY, Boyle–Gilboa–Ishai
(CCS'16), ARQ, PVODTE, Obscure, Hafiz et al., HADES. Hayata et al. and SHAMC were read
from abstracts only. Phrase the claim as "to our knowledge, none of the systems in
Table 1 provides…", not as a priority claim.

## Venue

JISA has rejected the paper and should not receive it again. Choose the next venue only
once the draft is written and has been read by an outside expert. The skeleton uses the
Elsevier `cas-sc` class; if the venue is IEEE, the text moves to `IEEEtran` without
change.

## Checklist before submission

- [ ] Every grey box replaced by the authors' paragraph; `\skeletonfalse` shows no box.
- [ ] Abstract at most 200 words; highlights written.
- [ ] Every number in the text found in `NUMBERS.md`. The assistant can run a check of
      the text against the result files on request.
- [ ] Supplement cut to the range-only scheme; theorem numbering consistent.
- [ ] References checked against the publishers' records (the reference-lookup service
      did not connect in the session that made this skeleton).
- [ ] Read by a researcher in applied cryptography outside the author team, who has
      reported in writing.
- [ ] AI declaration describes what was actually done for this version, in the
      journal's required wording.
- [ ] Data and code availability statement settled.
- [ ] Built from a clean checkout; the PDF the submission system generates has been
      opened and checked.
