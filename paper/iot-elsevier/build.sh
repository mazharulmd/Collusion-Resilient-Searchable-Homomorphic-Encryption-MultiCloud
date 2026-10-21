#!/bin/sh
# Builds the two manuscript PDFs and the Word submission files.
#   CRSHE_IoT_Manuscript_Anonymized.pdf  upload as "Manuscript without author details"
#   CRSHE_IoT_full.pdf                   with authors, for your records and for revision
set -e
cd "$(dirname "$0")"
run() { pdflatex -interaction=nonstopmode -jobname="$1" "$2" >/dev/null; }
run CRSHE_IoT_Manuscript_Anonymized CRSHE_IoT.tex
bibtex CRSHE_IoT_Manuscript_Anonymized >/dev/null
run CRSHE_IoT_Manuscript_Anonymized CRSHE_IoT.tex
run CRSHE_IoT_Manuscript_Anonymized CRSHE_IoT.tex
run CRSHE_IoT_full '\def\FULLVERSION{}\input{CRSHE_IoT}'
bibtex CRSHE_IoT_full >/dev/null
run CRSHE_IoT_full '\def\FULLVERSION{}\input{CRSHE_IoT}'
run CRSHE_IoT_full '\def\FULLVERSION{}\input{CRSHE_IoT}'
python3 make_submission_files.py
rm -f ./*.aux ./*.log ./*.bbl ./*.blg ./*.out ./*.spl ./*.abs
