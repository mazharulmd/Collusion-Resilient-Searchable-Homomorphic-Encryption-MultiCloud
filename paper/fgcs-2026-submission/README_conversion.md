# CR-SHE, Elsevier FGCS submission package

Converted from the IEEE Internet of Things Journal manuscript
(`IEEE Internet of Things/paper/CRSHE_v2_full.tex`) to the Elsevier CAS
double-column class for *Future Generation Computer Systems*.

## Contents

```
CRSHE_FGCS.tex              the manuscript (LaTeX, authoritative)
CRSHE_FGCS_Manuscript.docx  Word version of the manuscript
CRSHE_FGCS_TitlePage.docx   authors, affiliations, corresponding author
CRSHE_FGCS_CoverLetter.docx cover letter to the FGCS editors
CRSHE_FGCS_DeclarationOfInterest.docx  Elsevier declaration form
CRSHE_FGCS_AuthorsAffiliations.docx  authors and affiliations only
tools/tex_to_docx.py        rebuilds the manuscript .docx from the .tex
tools/make_submission_docs.py  rebuilds the four supporting .docx files
references.bib              unchanged from the IEEE version (70 entries)
cas-dc.cls, cas-common.sty  Elsevier CAS double-column class
model1-num-names.bst        Elsevier numbered bibliography style
Figures/fig_architecture.*  NEW full-text-width overview figure
Figures/telemetry/          result figures, primary corpus
Figures/beijing/            result figures, second corpus
figures_src/fig_architecture.py   script that regenerates Fig. 1
```

## Build

```
pdflatex CRSHE_FGCS
bibtex   CRSHE_FGCS
pdflatex CRSHE_FGCS
pdflatex CRSHE_FGCS
```

No LaTeX toolchain was available on the machine where this conversion was
made, so the file has not been compiled here. It has been checked mechanically
for: balanced braces, matched environments, every `\ref` resolving to a
`\label`, every `\cite` key present in `references.bib`, every
`\includegraphics` path existing on disk, and no macro name colliding with one
defined by `cas-dc.cls` or `cas-common.sty`.

## What changed against the IEEE version

**Class and front matter.** `IEEEtran` to `cas-dc`. `\author`/`\thanks` block
replaced by CAS `\author[...]{...}[orcid=...]`, `\ead`, `\credit`,
`\affiliation`, `\cormark`/`\cortext`. `\markboth` replaced by `\shorttitle`
and `\shortauthors`. Dropped `orcidlink` and `svg` (the class renders ORCID
icons from the `orcid=` key). Dropped `cite`, `hyperref`, `xcolor`,
`graphicx`, `booktabs`, `amsmath`: all are loaded by the class, and `cite` is
incompatible with `natbib`.

**Bibliography.** `\usepackage[numbers,sort&compress]{natbib}` with
`model1-num-names.bst`; `\cite` calls became `\citep`/`\citet`. The `.bib`
file itself is untouched.

**Theorem environments.** `amsthm` dropped in favour of the class's own
`\newtheorem`, `\newdefinition` and `\newproof`. Proofs are now `pf`
environments ending in `\qed`, which is what the CAS class expects.

**Floats.** Tables use `\begin{table}[pos=t]` with `\begin{tabular*}{\tblwidth}`;
the comparison table is a `table*`. Figures use `\begin{figure}[pos=t]` with
`\centering` (the class defaults figure alignment to `\raggedleft`).

**Elsevier front and back matter added.** Research highlights (five bullets,
each under 85 characters), `\sep`-separated keywords, CRediT statement via
`\printcredits`, declaration of competing interest and generative-AI
declaration. No data availability statement: no repository is shared.

**Title.** Changed from "CR-SHE: End-to-End Oblivious Keyword Search and
Analytics for Multi-Cloud IoT Data Sharing" to one that names the mechanism
and the differentiator against Splinter, DORY and Waldo. The old title still
works; revert the `\title` line if you prefer it.

**Abstract.** Rewritten to the requested six movements in order: context,
existing problem, what we propose, contribution, result, conclusion. Trimmed
to about 250 words, which is Elsevier's guideline.

**Em dashes.** All 178 occurrences of `---` removed and each sentence
rewritten with commas, colons, semicolons or parentheses. `grep -- '---'`
returns nothing. Double hyphens remain only as en dashes inside numeric ranges
(`38.8--41.2`), which is Elsevier's convention for ranges; say the word and
they can become "to" as well.

**Figure 1.** Redrawn as a full-text-width (`figure*`) icon-based overview:
three trust zones, drawn icons for sensors, relays, the owner, the clouds and
the user, and five numbered steps tracing one query end to end. The mechanism
detail lives in Section 6 and Algorithms 1 and 2, not in the figure.

**Column overflow.** Five display equations became `multline`/`gather`, both
algorithms were re-broken into shorter steps at a smaller size, and every
table was re-fitted: wrapping `p{}` columns for the notation, entity and
baseline tables, `\scriptsize` for the complexity and comparison tables, and
a reduced `\tabcolsep` throughout. Widths were checked against the 237pt
cas-dc column with font metrics rather than by eye.

**Captions** for every table and figure were cut to one or two lines.

**Data availability section removed**, along with the repository URL and every
sentence that promised a released artefact.

## Before you submit, please check

1. **CRediT roles.** `\credit{...}` for each author is a plausible default.
   Only the authors can say what is actually correct.
2. **Affiliation address.** The postal address in `\affiliation` is the North
   South University campus address; confirm the form your department uses.
3. **Funding and acknowledgements.** Not present in the IEEE version, so not
   added. If there is a funder, add `\tnotetext` or an acknowledgements
   section.
4. **Generative-AI declaration.** Elsevier requires one only if such tools
   were used. Delete that section if they were not.
5. **Author biographies.** The CAS class supports `\bio{...}...\endbio`. FGCS
   does not print them, so none were added.


## Word files

Three `.docx` files sit beside the LaTeX, rebuilt with:

```
python tools/tex_to_docx.py
python tools/make_submission_docs.py
```

There is no pandoc or LibreOffice on this machine, so `tools/tex_to_docx.py`
is a purpose-built converter that knows this manuscript's structure. It
produces a single-column, double-spaced file with continuous line numbers,
embedded figures, real Word tables, and maths set with genuine subscript and
superscript runs rather than images.

**The LaTeX remains authoritative.** The Word maths is readable but it is a
linearisation: a superscript nested inside a subscript flattens, and stacked
limits on a summation sit inline. Read the converted equations before you
submit the Word file, and prefer the LaTeX submission route if FGCS accepts
it.
