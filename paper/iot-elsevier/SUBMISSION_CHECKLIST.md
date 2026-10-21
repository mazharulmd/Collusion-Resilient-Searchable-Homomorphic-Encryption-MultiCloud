# Submission package: Elsevier *Internet of Things* (ISSN 2542-6605)

Prepared against the journal's Guide for Authors as of October 2026. The guide page
itself was blocked from the build environment, so these requirements come from
search excerpts of the official guide. Re-check them on the live page before you
submit.

## Files to upload

| Editorial Manager item | File |
|---|---|
| Manuscript | `CRSHE_IoT.tex` + `references.bib`, `Figures/`, `tables/`, `cas-dc.cls`, `cas-common.sty`, `model1-num-names.bst`, `thumbnails/` (zip them for the LaTeX route), and `CRSHE_IoT.pdf` |
| Highlights | `CRSHE_IoT_Highlights.docx` (or `.txt`) |
| Cover letter | `CRSHE_IoT_CoverLetter.docx`. Fill in **[DATE]** |
| Declaration of interest | Use the declarations tool in Editorial Manager (no competing interests) |

Rebuild: `pdflatex CRSHE_IoT && bibtex CRSHE_IoT && pdflatex CRSHE_IoT && pdflatex CRSHE_IoT`.
Highlights and cover letter: `python make_submission_files.py`. It reads the
highlights from the manuscript and checks the 85-character limit.

## Requirements checked

| Requirement (guide) | Status |
|---|---|
| Abstract ≤ 250 words | 248 words |
| Keywords 1–7 | 7 |
| Highlights 3–5 bullets, ≤ 85 characters each, separate file | 5 bullets, 63–83 characters, `.docx`/`.txt` |
| Single-anonymized review | Author names and affiliations stay in the manuscript |
| CRediT author contributions | `\credit{}` per author. **Confirm the roles** |
| Research data, Option C (deposit, cite and link data, or explain) | Data and code availability section; datasets cited with `[dataset]` tags (Kaggle telemetry; UCI Beijing, DOI 10.24432/C5RK5G) and the code repository |
| AI declaration at the end, before the references | **Drafted.** You must check and edit it (see below) |
| Generative AI not used to create or alter images | Figure 1 is drawn by a matplotlib script; the declaration says so |
| Length limit | None found in the guide |
| References | Numbered (`model1-num-names`). Elsevier applies its own style at proof |

## Cost

The guide says the journal becomes fully open access on 1 January 2027, and that
the article publishing charge applies to articles submitted and accepted after
peer review from 15 September 2026. The listed APC is **USD 3,020** (excluding
taxes). A personalised, possibly reduced price is shown during submission based on
country and institution. Check whether North South University or a waiver covers
it **before** you submit.

## You must do these before submitting

1. **AI declaration.** The draft in the manuscript describes what the repository
   documents: template conversion, editing, the figure script, the reference
   implementation, and drafting parts of Sections 6.2, 6.6, 6.9, 10.5 and 10.6.
   Correct it to match what you actually did. You must personally verify every
   proof and every number you are taking responsibility for.
2. **CRediT roles and affiliation**: confirm them.
3. **Suggested reviewers.** Editorial Manager usually asks for some. Choose
   researchers working on FSS/DPF systems or encrypted search who have no conflict
   with you, and use their official emails.
4. **Archive a release.** Tag the repository and archive it on Zenodo, then add
   the DOI to the `crshe_artifact` reference. Option C asks for a persistent
   identifier.

## Strongly recommended (the previous rejection was "premature")

Set `\authorcheckstrue` in the preamble to see these in red in the PDF.

* Run providers in at least two cloud regions and report wide-area latency
  (Limitations).
* Publish the C++ prototype and re-measure Tables 6, 7, 11 and 14 with the packed,
  compressed layout. Then the abstract's 39 ms becomes the packed figure.
* Download both corpora (`data/README.md`) and run `bench/correctness.py` and
  `bench/bench_leakage.py` on them. The padded and volume-hiding leakage comparison
  is described but not yet run.
* Port rejection-sampled masks to the C++ build and re-measure the index build
  time.

## What changed from the revised manuscript (`paper/revision/`)

* Abstract cut from 345 to 248 words.
* Every reference to "the submitted version / layout / design" is reworded neutrally
  ("two-ciphertext layout", "single-round general path"). An Internet of Things
  reviewer has not seen the FGCS version.
* Sentences that implied experiments on the real corpora had been run are reworded
  to say what was actually run: the unit tests and a synthetic-corpus battery
  (200/200 for n = 2, 3, 4).
* `[Authors: …]` markers are hidden (`\authorchecksfalse`).
* Data and code availability rewritten for Option C; dataset and code references added.
* AI declaration drafted.
