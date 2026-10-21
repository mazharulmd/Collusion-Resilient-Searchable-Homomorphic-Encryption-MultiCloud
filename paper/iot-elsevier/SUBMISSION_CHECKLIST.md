# Submission package: Elsevier *Internet of Things* (ISSN 2542-6605)

Checked against the journal's Guide for Authors and the Editorial Manager upload
screen (October 2026). Layout: **single column** (`cas-sc`). The guide says Word files must
be single-column and double-column is only permitted for LaTeX, so single column is
the journal's default and what reviewers expect. The guide page was blocked from the build environment, so
the guide's requirements come from search excerpts. The upload screen is quoted
from what the author saw.

## Upload screen → file

| Editorial Manager item | Upload | Notes |
|---|---|---|
| **Manuscript without author details** (required) | `CRSHE_IoT_Manuscript_Anonymized.pdf` | LaTeX papers upload a PDF; the source is not needed until revision. No names, affiliations, ORCIDs, e-mails, CRediT or repository link; PDF metadata has no author |
| **Title page with author details** (required) | `CRSHE_IoT_TitlePage.docx` | Title, authors, affiliation, corresponding author e-mail, ORCIDs, acknowledgements (no-funding statement), CRediT |
| **Declaration of competing interests** (required) | Tick the confirmation box, **or** upload `CRSHE_IoT_DeclarationOfInterest.docx`, **or** generate the official file with the [declarations tool](https://declarations.elsevier.com/home?journalAcronym=IOT) | Tick the box only if it is true for every author, including the editorial-board clause. Confirm the yellow line in the Word file |
| Highlights (optional) | `CRSHE_IoT_Highlights.docx` | 5 bullets, 63–83 characters |
| Cover letter (optional) | `CRSHE_IoT_CoverLetter.docx` | Fill in **[DATE]** |
| "Did you use generative AI?" | **Yes** | The statement sits directly before the references, in Elsevier's template wording. **Check it is accurate** |

Rebuild everything: `./build.sh`. It needs pdflatex, bibtex and Python with
`python-docx`. It writes the anonymized PDF, `CRSHE_IoT_full.pdf` (with authors,
for revision) and the Word files. The CRediT roles on the title page are read from
the manuscript source, so the two cannot disagree.

## Errors found and fixed in this pass

1. **The manuscript identified the authors.** The upload screen requires a manuscript
   *without* author details. The previous package kept names in, following the
   guide's "single anonymized" line. Fixed with an anonymized build that removes:
   the author block, the running header, the CRediT section, the highlights page
   (the CAS class prints the author list on it), the empty "ORCID(s):" footnote, the
   GitHub link and the code reference naming the authors. All of these move to the
   title page. One `\ifanonymous` switch keeps a single source.
2. **Five theorem/remark titles ran past the column edge** (Proposition 1,
   Remarks 1–4; Remark 4's was already in the FGCS PDF). Shortened. A long tuple in
   §3 overflowed the margin; it can now break.
3. **The AI declaration did not follow Elsevier's template** ("used … in order to …
   reviewed and edited the content as needed and take full responsibility …").
   Reworded to match.
4. **Leakage notation was inconsistent:** class(f) in Fig. 1 and Table 7, class(q)
   in the text. Unified to class(q), and Fig. 1 regenerated.
5. Spell-check (aspell, en-GB): no real errors.

## Requirements checked

| Requirement | Status |
|---|---|
| Abstract ≤ 250 words | 248 |
| Keywords 1–7 | 7 |
| Highlights 3–5, ≤ 85 characters, separate file | 5, 63–83 characters |
| Title page: title, authors, affiliations, acknowledgements, corresponding e-mail | Yes (acknowledgements are yours to write) |
| CRediT | On the title page |
| Research data | "Data will be made available on request." (authors' choice); the public datasets are still cited in §9 with `[dataset]` tags |
| AI declaration directly before the references | Yes |
| No generative-AI images | Fig. 1 is drawn by a matplotlib script; the declaration says so |

## Before you press submit

2. **Declaration:** confirm the editorial-board statement, or adjust it.
3. **AI declaration:** make it describe exactly what you did. You must check
   every proof and number yourself.
4. **Anonymity:** the public GitHub repository contains the full manuscript with
   your names under the same title. A reviewer who searches the title will find
   it. Consider making the repository private during review, or putting an
   anonymized copy on an anonymous code-sharing service.
5. **Fee:** the article publishing charge is USD 3,020 (excluding taxes) for
   articles submitted and accepted from 15 September 2026; a personalised price
   appears during submission.
6. **Suggested reviewers,** if Editorial Manager asks for them: use official e-mail
   addresses and people with no conflict of interest.

## Still recommended (the FGCS rejection was "premature")

Rebuild with `\authorcheckstrue` to see these in red: a multi-region deployment,
publishing the C++ prototype and re-measuring Tables 6, 7, 11 and 14 with the
packed layout, and running `bench/correctness.py` and `bench/bench_leakage.py` on
the real corpora.
