# Submission package for the Journal of Network and Computer Applications (2026-10-26)

Files in `paper/jnca/submission/`:

| File | Use |
|---|---|
| `CRSHE_JNCA_manuscript.docx` | Manuscript with author details (17 pages rendered: A4, 11 pt Times, single spacing, line numbers) |
| `CRSHE_JNCA_manuscript_anonymized.docx` | Same without authors and CRediT, if the journal runs double-anonymized review |
| `CRSHE_JNCA_title_page.docx` | Title page: authors, affiliation, corresponding author, CRediT, declarations |
| `CRSHE_JNCA_highlights.docx` | Five highlights, each at most 85 characters |
| `CRSHE_JNCA_supplementary.pdf` | Supplementary Material S1–S6: full proofs and secondary experiments |
| `CRSHE_JNCA_manuscript.pdf` | The same manuscript typeset in the Elsevier CAS template (17 pages, the first being the highlights page) |

Build: `paper/jnca/` → `pdflatex/bibtex manuscript`, `python assemble_supplement.py`, compile
`supplementary.tex`, then `python build_docx.py`. Word numbering (sections, tables, figures,
equations, algorithms) is read from `manuscript.aux`, so it matches the PDF.

## Why one paper, not two

The work has one central contribution: oblivious range aggregation over owner-encrypted replicas
with key-carried tamper evidence. A split would give (a) range aggregation plus tamper evidence
and (b) keyword search plus the masked index. Part (b) is the material the Elsevier IoT journal
desk-rejected for lack of novelty, and its masked index follows DORY. The two halves also share
the system model, threat model, primitives and security proof. Elsevier's policy on redundant
publication makes two papers with that much overlap a risk, and each half would be weaker than
the whole. The paper was condensed instead.

## What the condensed version keeps and moves

Kept in the main text:
- title, a structured-flow abstract (232 words), five highlights and seven keywords;
- comparison table, architecture figure and notation table;
- both algorithms (outsourcing; verified range query);
- Proposition 1, Lemma 1 and Theorem 1 with short proofs;
- Theorem 2 (tamper evidence) and Theorems 3–4 with proof sketches;
- Proposition 2 (roles);
- results tables: range on real cubes, tamper detection, baselines and leakage, plus the leakage
  figure.

Moved to the supplement:
- the full Proposition 1 argument and the full proofs of Theorems 2–4;
- the complexity table;
- the synthetic-cube layout comparison and cube-size sweep;
- the selection latency, packing, uplink, flexible-path, packed-index, deployment, setup and
  scaling tables;
- the second-corpus C++ table, the role-extraction table and dynamic ingest;
- the note withdrawing the C++ leakage figures.

Number audit: every number in the main text appears in `paper/v5/CRSHE_v5.tex`, its generated
tables or `results/*.json`, except two roundings of source values (5.2 kB = 5,248 B; 75 % = 75.0 %).

## Not verified here (check against the journal's Guide for Authors)

`sciencedirect.com` and `elsevier.com` could not be reached from the build environment, so the
following follow Elsevier's usual rules and the limits recorded for the earlier Elsevier submission:
- abstract at most 250 words;
- 1–7 keywords;
- 3–5 highlights of at most 85 characters, as a separate file;
- the review model (single- or double-anonymized), which decides between the two manuscript files;
- the page or word limit for a research article;
- the reference style: Elsevier numeric is used.

The rendering check used LibreOffice; open the .docx in Word once before uploading to confirm that
the equations look right.
