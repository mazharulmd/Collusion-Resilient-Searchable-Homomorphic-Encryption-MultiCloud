# Submission package for IEEE Transactions on Cloud Computing

Built 2026-11-17 in `paper/tcc/`. The authors asked the assistant to write the whole
paper (reversing the earlier plan in `paper/focused/OUTLINE.md` in which the authors
would write it). The text was written from the focused skeleton, in the style rules of
that outline.

**The journal's own author page was not read.** `www.computer.org` is outside the build
environment's network. The rules below come from search summaries of IEEE Computer
Society pages: regular papers 12 formatted pages including references and author
biographies, an overlength charge for each page beyond (USD 200 in the 2018 policy
document, USD 220 in the 2025 charge list), supplemental material as separate files.
**Confirm these, the review model and the submission system on the TCC author page
before uploading.**

## Files (`paper/tcc/submission/`)

| File | What it is |
|---|---|
| `TCC_manuscript.pdf` | The paper, IEEEtran journal/compsoc, 9 pages |
| `TCC_latex_source.zip` | Source: `manuscript.tex`, `.bbl`, `macros.tex`, `references.bib`, table, figures, supplement source. Checked: compiles from the zip alone |
| `TCC_supplemental_material.pdf` | Full proofs of Theorems 1–3, why the data are encrypted, check layouts with stored keys (3 pages) |
| `TCC_cover_letter.docx` | One page, dated 17 November 2026 |

Build: in `paper/tcc/`, `pdflatex manuscript`, `bibtex manuscript`, `pdflatex` twice; the
same for `supplement`; `node make_cover_letter.js`. Figures:
`python bench/make_figures.py --paper tcc`.

## Checks that ran

| Check | Result |
|---|---|
| `scripts/check_tcc_numbers.py` | 103 numbers in the prose traced to `paper/focused/NUMBERS.md` (generated from `results/*.json`), to figures recomputed from the result files, or to listed parameters. With `--plant` (one figure changed) it fails. Limit: it checks that each number exists in the results, not that it sits in the right sentence |
| LaTeX build | 0 undefined references; one overfull box fixed |
| Readability | 16.4 words per sentence on average (28.1 in the JISA version); no role abbreviations; the scheme is not given a name |
| Test suite | 88 passed (unchanged code) |

Not checked: the reference list against publishers' records (lookup service did not
connect); the proofs by anyone other than the session that wrote them.

## Before you submit

1. **Read the whole paper and the supplement.** The Acknowledgments say that Claude
   drafted all sections and that the authors reviewed and edited every section. That
   last sentence must be true when you upload.
2. **Have the proofs read by someone in applied cryptography**, outside the author team
   if possible. They were adapted by the assistant from earlier versions and checked by
   no one else.
3. Author biographies and photos: IEEE Computer Society journals print them at the end
   and count them in the page limit. Most accept them at the final version; add them if
   the submission system asks.
4. The submission form will probably ask whether the paper was submitted elsewhere
   before. Answer truthfully; the cover letter does not mention it.
5. The code statement says "available from the corresponding author on reasonable
   request". Change it if you decide to publish the code.
