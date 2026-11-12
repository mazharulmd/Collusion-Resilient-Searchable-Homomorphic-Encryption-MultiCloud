# Submission package for the Journal of Information Security and Applications

Target chosen in [`JOURNAL_SELECTION.md`](JOURNAL_SELECTION.md). Built 2026-11-12 from
`paper/jisa/`, a revision of the JNCA manuscript (what changed and why:
[`REJECTION_ANALYSIS.md`](REJECTION_ANALYSIS.md), section "Third round").

**The JISA Guide for Authors was not read.** `www.sciencedirect.com` is outside the
build environment's network. The package follows the Elsevier guide that was read in
full for JNCA (supplied by the authors as a PDF in October 2026); Elsevier journals share
most of that text, but JISA's own limits may differ. Before submitting, open the JISA
guide and check the five items marked **confirm** below. A search summary of the guide
says JISA uses single anonymized review, which is what the manuscript assumes.

## Files to upload (`paper/jisa/submission/`)

| Upload step | File |
|---|---|
| Manuscript (Word) | `CRSHE_JISA_manuscript.docx` (21 pages as rendered by LibreOffice) |
| Cover letter | `CRSHE_JISA_cover_letter.docx` (one page; dated 12 November 2026) |
| Declaration of competing interests | `CRSHE_JISA_declaration_of_competing_interests.docx`, or the journal's declarations tool |
| Highlights | `CRSHE_JISA_highlights.docx` |
| Figures as separate files | `Figure_1.pdf` … `Figure_11.pdf`, numbered as in the paper |
| Supplementary material | `CRSHE_JISA_supplementary.pdf` (15 pages) |

Build, in `paper/jisa/`: `pdflatex manuscript` → `bibtex manuscript` → `pdflatex` twice;
`python assemble_supplement.py`, then compile `supplementary.tex` the same way;
`python build_docx.py`; `node make_cover_letter.js`. Figures:
`python bench/make_figures.py` (Python 3.12 with `requirements.txt`).

## To confirm in the JISA guide

| Item | What the package has | Status |
|---|---|---|
| Review model | Author names in the manuscript (single anonymized) | **confirm**; search summary agrees |
| Abstract limit | 231 words | **confirm** (Elsevier's usual limit is 250) |
| Keywords | 7 | **confirm** (usual limit 1–7) |
| Highlights | 5 bullets, at most 85 characters | **confirm** |
| Page or word limit | 21 pages, 11 figures, 4 tables, 2 algorithms | **confirm**; none was found in search summaries |

## What differs from the JNCA package

- Two new figures: Fig. 2 (the range mechanism) and Fig. 6 (the same range query answered
  three ways). Eleven figures in all.
- New subsection "Range queries against alternatives", from `results/range_baselines.json`.
- Introduction states what is borrowed and what is new; the system model defines the
  query types; the threat model says which guarantee holds against which adversary.
- The Discussion's "Relation to prior art" moved to the Introduction; the Discussion now
  says what the trust split buys and gives a computed wide-area figure.
- The declaration of generative AI use adds that the synthetic-data experiments were run
  with the assistant on a cloud virtual machine. **Authors: check that this sentence is
  accurate for every experiment before submitting.**
- Cover letter addressed to JISA; its scope sentence names applied cryptography, privacy
  and access control.

## Checks that ran on this build

| Check | Result |
|---|---|
| Test suite (`pytest`, Python 3.12) | 88 passed |
| `scripts/check_range_baselines_text.py` | 16 figures of the new subsection match the result file; fails with `--plant` |
| LaTeX build | 0 undefined references or citations, 21 pages; supplement 15 pages |
| Word build (`build_docx.py`) | Its own checks passed: no underline or strikethrough, no vertical table rules, highlights within 85 characters |
| Word render (LibreOffice) | 21 pages; figures 1–11 each cited; no leftover "JNCA" or repository link |

Not checked: the manuscript in Microsoft Word itself (only LibreOffice was available), and
the reference list against the publishers' records (the reference-lookup service did not
connect in this session).

## Before pressing submit

1. Confirm the manuscript is **not under consideration elsewhere**. If the JNCA
   submission was completed, withdraw it first or wait for its decision.
2. Confirm the postal address, the author order and the CRediT roles.
3. Change the date in the cover letter if you submit on another day.
4. Read the AI declaration and the data availability statement once more; both are the
   authors' statements.
