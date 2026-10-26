# Submission package for the Journal of Network and Computer Applications

Checked against the journal's Guide for Authors (PDF supplied by the authors, printed
2026-10-27; read in full) and the submission-page text the authors pasted.

## Files to upload (`paper/jnca/submission/`)

| Upload step | File |
|---|---|
| Manuscript (required, Word) | `CRSHE_JNCA_manuscript.docx` |
| Declaration of competing interests (required, Word) | `CRSHE_JNCA_declaration_of_competing_interests.docx`, or tick the "no competing interests" box on the upload page |
| Highlights (optional) | `CRSHE_JNCA_highlights.docx` |
| Figures (artwork as separate files) | `Figure_1.pdf`, `Figure_2.pdf` |
| Supplementary material (optional) | `CRSHE_JNCA_supplementary.pdf` |

Build: in `paper/jnca/`, run `pdflatex manuscript` → `bibtex manuscript` → `pdflatex` twice;
`python assemble_supplement.py` and compile `supplementary.tex`; then `python build_docx.py`.

## Guide for authors, item by item

| Guide requirement (section) | Status |
|---|---|
| Single-anonymized review (Peer review) | Author details stay in the manuscript; the anonymized copy and the separate title page were dropped |
| .doc/.docx, single-column Word (File format) | Single column, A4 |
| No strikethrough or underline (File format) | Checked by the build: 0 underline and 0 strikethrough elements; links keep colour only |
| Title concise; avoid abbreviations where possible (Title page) | "IoT" spelled out: *Collusion-resilient, tamper-evident range analytics over homomorphically encrypted Internet of Things data in multi-cloud storage* |
| Authors, lowercase superscript affiliation, full postal address with country (Title page) | Page 1: superscript a; North South University, Plot 15, Block B, Bashundhara R/A, Dhaka 1229, Bangladesh. **The authors should confirm the address.** |
| Corresponding author with e-mail on title page (Title page) | Page 1, marked * |
| Abstract ≤ 250 words, stand-alone, no references, abbreviations defined (Abstract) | 231 words (249 with hyphenated words split); CR-SHE and IoT defined; "BFV" replaced by "lattice-based"; no references |
| 1–7 keywords; avoid "and"/"of" phrases (Keywords) | 7: Homomorphic encryption; Multi-cloud storage; IoT; Distributed point function; Range aggregation; Privacy-preserving analytics; Verifiable computation ("Internet of Things" became "IoT") |
| Highlights: separate editable file with "highlights" in the name, 3–5 bullets ≤ 85 characters (Highlights) | 5 bullets, 65–76 characters; the build fails if any exceeds 85; "DPF" removed from the bullets |
| Graphical abstract (encouraged, optional) | Not supplied |
| SI units (Units) | s, ms, GHz; bytes as B, kB and MB |
| Tables as editable text, cited, numbered, captioned, no vertical rules or shading (Tables) | Tables 1–6 editable and cited in order; horizontal rules only (build check: 0 vertical borders) |
| Figures supplied as separate files named Figure_1, Figure_2; cited; captioned (Figures) | `Figure_1.pdf` and `Figure_2.pdf` are vector files with embedded fonts, also embedded in the manuscript |
| Algorithms | Editable tables in Word (previously images) |
| Disclose generative-AI help with figures in each caption and in the declaration (GenAI and figures) | Both captions state that the figures were drawn by plotting scripts written with AI assistance; the declaration names the plotting scripts and replaces "No image was generated or altered" with an exact statement |
| Supplementary material cited, with a caption describing its content (Supplementary material) | "Supplementary material" section after the Conclusion lists S1–S6; the text cites S1–S6 |
| Research data Option C: deposit, cite and link (Research data) | Data availability cites both public datasets and the public GitHub repository as references [48], [50], [51]. **The code is on branch `claude/stoic-bohr-lf0t6v`; merge it into the default branch, or tag a release (ideally archived on Zenodo with a DOI), before submitting.** |
| Dataset and software references marked "[dataset]" / "[software]" (References) | Done in the reference list |
| References complete, real, DOIs where available (References) | Four entries that listed "and others" now have full author lists (OpenFHE, PVLDB Obscure, Choudhuri et al., Ji et al.) from search summaries; no "and others" remains among cited entries. Format is free at submission. |
| CRediT statement (Author contributions) | Present, with the role names written with en dashes |
| Funding sentence (Funding sources) | The exact sentence the guide gives |
| Competing interests (Declaration of competing interests) | Separate Word file plus a section in the manuscript; the guide says the declarations tool "should always be completed", so use it or tick the box on the upload page |
| AI declaration in a new section directly before the references (Declaration of generative AI use) | Last section before References, titled as the guide gives |
| Acknowledgements directly before the references, if any (Article structure) | None needed |
| Submission checklist: corresponding author, all files, references cited both ways, permissions | Corresponding author set; every cited key exists in the bibliography, and citeproc lists only cited works |

## Page count

Word manuscript: 18 pages as rendered by LibreOffice (A4, 11 pt Times New Roman, single
spacing, line numbers). The guide sets no page limit for research articles.

## Why one paper, not two

The work has one central contribution: oblivious range aggregation over owner-encrypted replicas
with key-carried tamper evidence. A split would give (a) range aggregation plus tamper evidence
and (b) keyword search plus the masked index. Part (b) is the material the Elsevier IoT journal
desk-rejected for lack of novelty, and its masked index follows DORY. The two halves also share the
system model, threat model, primitives and security proof. The guide's policy on multiple,
redundant or concurrent publication makes two papers with that much overlap a risk.

## Number audit

Every number in the main text appears in `paper/v5/CRSHE_v5.tex`, its generated tables or
`results/*.json`, except two roundings of source values (5.2 kB = 5,248 B; 75 % = 75.0 %).
