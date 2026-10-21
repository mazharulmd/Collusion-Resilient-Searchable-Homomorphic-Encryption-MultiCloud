#!/usr/bin/env python3
"""
Build the two supporting Word files Elsevier asks for alongside the
manuscript:

  CRSHE_FGCS_TitlePage.docx    author names, affiliations, corresponding
                               author details, ORCIDs and CRediT roles
  CRSHE_FGCS_CoverLetter.docx  cover letter to the FGCS editors

Usage:  python tools/make_submission_docs.py
"""

import os
from datetime import date

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))

FONT = "Times New Roman"

TITLE = ("CR-SHE: Oblivious homomorphic aggregation for collusion-resilient "
         "search and analytics over encrypted multi-cloud IoT data")
SHORT_TITLE = "Oblivious homomorphic aggregation for multi-cloud IoT analytics"

AFFIL = ("Department of Electrical and Computer Engineering, "
         "North South University, Dhaka, Bangladesh")

AUTHORS = [
    dict(name="Md Mazharul Islam",
         orcid="0000-0001-6225-1487",
         email="mazharul.islam1@northsouth.edu",
         corresponding=True,
         credit="Conceptualization, Methodology, Software, Formal analysis, "
                "Investigation, Validation, Writing – original draft, "
                "Writing – review and editing"),
    dict(name="Mubasshir Ahmed",
         orcid="0000-0002-7502-3835",
         email="mubasshir.ahmed@northsouth.edu",
         corresponding=False,
         credit="Software, Data curation, Investigation, "
                "Writing – review and editing"),
    dict(name="Md Redowan Zaman Anik",
         orcid="",
         email="redowan.anik@northsouth.edu",
         corresponding=False,
         credit="Software, Data curation, Visualization, Validation, "
                "Writing – review and editing"),
]

JOURNAL = "Future Generation Computer Systems"


# ---------------------------------------------------------------------------
def new_doc(spacing=WD_LINE_SPACING.SINGLE, size=12):
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = FONT
    st.font.size = Pt(size)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    st.paragraph_format.line_spacing_rule = spacing
    st.paragraph_format.space_after = Pt(0)
    for s in doc.sections:
        s.top_margin = s.bottom_margin = Inches(1.0)
        s.left_margin = s.right_margin = Inches(1.1)
    return doc


def para(doc, text="", size=12, bold=False, italic=False, align=None,
         before=0, after=8, indent=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    if align is not None:
        p.alignment = align
    if indent is not None:
        p.paragraph_format.left_indent = Inches(indent)
    if text:
        r = p.add_run(text)
        r.bold = bold
        r.italic = italic
        r.font.size = Pt(size)
        r.font.name = FONT
    return p


def runs(p, chunks):
    """chunks: list of (text, bold, italic, superscript, size)."""
    for text, bold, italic, sup, size in chunks:
        r = p.add_run(text)
        r.bold = bold
        r.italic = italic
        r.font.superscript = sup
        r.font.size = Pt(size)
        r.font.name = FONT
    return p


def rule(doc):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(10)
    pPr = p._p.get_or_add_pPr()
    b = OxmlElement("w:pBdr")
    bot = OxmlElement("w:bottom")
    bot.set(qn("w:val"), "single")
    bot.set(qn("w:sz"), "6")
    bot.set(qn("w:space"), "1")
    bot.set(qn("w:color"), "999999")
    b.append(bot)
    pPr.append(b)
    return p


# ---------------------------------------------------------------------------
def build_title_page():
    doc = new_doc()

    para(doc, "Title page", size=10, bold=True, italic=True,
         align=WD_ALIGN_PARAGRAPH.RIGHT, after=2)
    para(doc, "Submitted to %s" % JOURNAL, size=10, italic=True,
         align=WD_ALIGN_PARAGRAPH.RIGHT, after=4)
    rule(doc)

    para(doc, "Title", size=11, bold=True, after=4)
    para(doc, TITLE, size=14, bold=True, after=10)

    para(doc, "Short title (running head)", size=11, bold=True, after=4)
    para(doc, SHORT_TITLE, size=12, after=14)

    para(doc, "Authors", size=11, bold=True, after=6)
    p = para(doc, after=10)
    chunks = []
    for k, a in enumerate(AUTHORS):
        if k:
            chunks.append((", ", False, False, False, 12))
        chunks.append((a["name"], False, False, False, 12))
        chunks.append(("a" + ("," + "*" if a["corresponding"] else ""),
                       False, False, True, 12))
    runs(p, chunks)

    para(doc, "Affiliation", size=11, bold=True, after=6)
    p = para(doc, after=14)
    runs(p, [("a", False, False, True, 12), (" " + AFFIL, False, False,
                                             False, 12)])

    para(doc, "Author details", size=11, bold=True, after=6)
    for a in AUTHORS:
        p = para(doc, after=2, indent=0.15)
        runs(p, [(a["name"] + ("*" if a["corresponding"] else ""),
                  True, False, False, 12)])
        para(doc, AFFIL, size=11, after=1, indent=0.15)
        para(doc, "Email: " + a["email"], size=11, after=1, indent=0.15)
        if a["orcid"]:
            para(doc, "ORCID: https://orcid.org/" + a["orcid"], size=11,
                 after=8, indent=0.15)
        else:
            para(doc, "ORCID: not registered", size=11, after=8, indent=0.15)

    corr = next(a for a in AUTHORS if a["corresponding"])
    para(doc, "* Corresponding author", size=11, bold=True, before=6, after=6)
    for line in (corr["name"], AFFIL,
                 "Email: " + corr["email"],
                 "ORCID: https://orcid.org/" + corr["orcid"]):
        para(doc, line, size=11, after=2, indent=0.15)

    para(doc, "CRediT authorship contribution statement", size=11, bold=True,
         before=14, after=6)
    for a in AUTHORS:
        p = para(doc, after=6, indent=0.15)
        runs(p, [(a["name"] + ": ", True, False, False, 11),
                 (a["credit"] + ".", False, False, False, 11)])

    para(doc, "Declarations", size=11, bold=True, before=10, after=6)
    para(doc, "Declaration of competing interest: The authors declare that "
              "they have no known competing financial interests or personal "
              "relationships that could have appeared to influence the work "
              "reported in this paper.", size=11, after=6, indent=0.15)
    para(doc, "Funding: This research did not receive any specific grant "
              "from funding agencies in the public, commercial, or "
              "not-for-profit sectors.", size=11, after=6, indent=0.15)

    out = os.path.join(ROOT, "CRSHE_FGCS_TitlePage.docx")
    doc.save(out)
    return out


# ---------------------------------------------------------------------------
COVER_BODY = [
    "Dear Editors,",

    "We submit for your consideration our manuscript entitled “%s” "
    "for publication in %s as a regular research paper." % (TITLE, JOURNAL),

    "Internet of Things deployments increasingly replicate telemetry across "
    "several independent cloud providers for availability and vendor "
    "independence, and that telemetry is sensitive enough that it must stay "
    "encrypted once it leaves the device domain. A line of distributed-trust "
    "systems already hides which records a query selects by splitting the "
    "query across replicated servers. Our paper addresses the step those "
    "systems leave open. Selection and computation are not the same problem, "
    "and hiding the first is worthless if the second gives it back: once a "
    "scheme aggregates over the matched records, it typically hands the "
    "matched set to the providers, and the coalition recovers exactly the "
    "access pattern the selection phase protected.",

    "We present CR-SHE, in which both keyword retrieval and analytics over "
    "the retrieved records remain oblivious to a coalition of up to n-1 "
    "colluding providers, over data encrypted at rest under a single owner's "
    "key and with no communication between providers. The central "
    "construction, oblivious homomorphic aggregation, has each provider fold "
    "its own distributed point function share directly into the "
    "homomorphically encrypted record column and return a single ciphertext, "
    "so the matched set is never assembled anywhere and its cardinality "
    "never leaves the client. A precomputed-column fast path removes the "
    "dependence on record count, and a one-time-pad index mask, cancelled "
    "inside the ciphertext, removes the posting-list-length leakage a "
    "replicated index otherwise exposes at rest.",

    "The work is supported by proofs of correctness and adaptive leakage "
    "security against n-1 collusion, and by an end-to-end C++ prototype "
    "evaluated on two real IoT corpora against ORAM, single-server "
    "searchable encryption, distributed-trust search and a faithful "
    "homomorphic equality scan. On 405,184 sensor records, a registered "
    "single-keyword aggregate costs 39 ms per provider irrespective of the "
    "record count, returns a fixed 526 kB response, and does 617 times less "
    "work than the homomorphic scan. A frequency attack that re-identifies "
    "every non-temporal metadata tag from an unmasked index recovers none "
    "from the masked one, and the result reproduces on a second, twelve-site "
    "corpus with three times the tag domain.",

    "We believe the paper suits %s because it sits squarely in the journal's "
    "scope on multi-cloud and distributed infrastructure for large-scale "
    "data: it treats replication across independent providers as a systems "
    "property to be exploited rather than merely tolerated, reports measured "
    "performance for a working prototype rather than asymptotics alone, and "
    "states plainly what the evaluation does not establish." % JOURNAL,

    "We confirm that this manuscript is original, has not been published "
    "previously, and is not under consideration for publication elsewhere. "
    "All authors have read and approved the submitted version and agree to "
    "its submission. The authors declare no competing financial interests or "
    "personal relationships that could have appeared to influence this work. "
    "The manuscript has not been posted to a preprint server.",

    "Thank you for considering our submission. We look forward to the "
    "reviewers' comments.",

    "Yours sincerely,",
]


def build_cover_letter():
    doc = new_doc(spacing=WD_LINE_SPACING.ONE_POINT_FIVE)
    corr = next(a for a in AUTHORS if a["corresponding"])

    for line in (corr["name"], AFFIL, corr["email"]):
        para(doc, line, size=11, align=WD_ALIGN_PARAGRAPH.RIGHT, after=1)
    para(doc, date.today().strftime("%d %B %Y"), size=11,
         align=WD_ALIGN_PARAGRAPH.RIGHT, after=14)

    para(doc, "The Editors", size=12, after=1)
    para(doc, JOURNAL, size=12, after=1)
    para(doc, "Elsevier", size=12, after=14)

    p = para(doc, after=12)
    runs(p, [("Subject: ", True, False, False, 12),
             ("Submission of an original research manuscript", False, False,
              False, 12)])

    for k, block in enumerate(COVER_BODY):
        last = k == len(COVER_BODY) - 1
        para(doc, block, size=12,
             align=None if k in (0, len(COVER_BODY) - 1)
             else WD_ALIGN_PARAGRAPH.JUSTIFY,
             after=16 if last else 10)

    for line in (corr["name"],
                 "on behalf of all authors",
                 AFFIL,
                 corr["email"]):
        para(doc, line, size=12, after=1, bold=(line == corr["name"]))

    out = os.path.join(ROOT, "CRSHE_FGCS_CoverLetter.docx")
    doc.save(out)
    return out


# ---------------------------------------------------------------------------
# Declaration of interest statement, following Elsevier's own template
# ---------------------------------------------------------------------------
NONE_BOX = ("The authors declare that they have no known competing financial "
            "interests or personal relationships that could have appeared to "
            "influence the work reported in this paper.")
SOME_BOX = ("The authors declare the following financial "
            "interests/personal relationships which may be considered as "
            "potential competing interests:")


def checkbox_para(doc, ticked, text):
    """A checkbox line. Ticked uses U+2612, empty uses U+2610."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(10)
    p.paragraph_format.left_indent = Inches(0.35)
    p.paragraph_format.first_line_indent = Inches(-0.35)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    box = p.add_run("☒ " if ticked else "☐ ")
    box.font.size = Pt(13)
    # Times New Roman has no box glyphs; name a font that does
    box.font.name = "Segoe UI Symbol"
    box._element.rPr.rFonts.set(qn("w:ascii"), "Segoe UI Symbol")
    box._element.rPr.rFonts.set(qn("w:hAnsi"), "Segoe UI Symbol")
    r = p.add_run(text)
    r.font.size = Pt(12)
    r.font.name = FONT
    return p


def build_declaration():
    doc = new_doc()
    corr = next(a for a in AUTHORS if a["corresponding"])

    para(doc, "Declaration of interests", size=14, bold=True, after=14)

    checkbox_para(doc, True, NONE_BOX)
    checkbox_para(doc, False, SOME_BOX)

    # ruled lines for anything the authors need to write in
    for _ in range(3):
        rule(doc)

    rule(doc)
    para(doc, "Manuscript details", size=11, bold=True, before=6, after=6)

    p = para(doc, after=4, indent=0.15)
    runs(p, [("Title: ", True, False, False, 11),
             (TITLE, False, False, False, 11)])
    p = para(doc, after=4, indent=0.15)
    runs(p, [("Authors: ", True, False, False, 11),
             (", ".join(a["name"] for a in AUTHORS), False, False, False, 11)])
    p = para(doc, after=4, indent=0.15)
    runs(p, [("Journal: ", True, False, False, 11),
             (JOURNAL, False, False, False, 11)])
    p = para(doc, after=14, indent=0.15)
    runs(p, [("Corresponding author: ", True, False, False, 11),
             ("%s, %s" % (corr["name"], corr["email"]),
              False, False, False, 11)])

    para(doc, "Signature (on behalf of all authors)", size=11, bold=True,
         before=8, after=18)
    for label in ("Name: " + corr["name"],
                  "Date: " + date.today().strftime("%d %B %Y")):
        para(doc, label, size=11, after=6, indent=0.15)

    out = os.path.join(ROOT, "CRSHE_FGCS_DeclarationOfInterest.docx")
    doc.save(out)
    return out


# ---------------------------------------------------------------------------
# Author names, affiliations and corresponding author details, on their own
# ---------------------------------------------------------------------------
def build_authors_affiliations():
    doc = new_doc()
    corr = next(a for a in AUTHORS if a["corresponding"])

    para(doc, "Author names, affiliations and corresponding author details",
         size=14, bold=True, after=4)
    para(doc, "Submitted to %s" % JOURNAL, size=10, italic=True, after=4)
    rule(doc)

    para(doc, "Manuscript title", size=11, bold=True, after=4)
    para(doc, TITLE, size=12, bold=True, after=16)

    para(doc, "Author names", size=11, bold=True, after=6)
    p = para(doc, after=16)
    chunks = []
    for k, a in enumerate(AUTHORS):
        if k:
            chunks.append((", ", False, False, False, 12))
        chunks.append((a["name"], False, False, False, 12))
        chunks.append(("a" + (",*" if a["corresponding"] else ""),
                       False, False, True, 12))
    runs(p, chunks)

    para(doc, "Affiliations", size=11, bold=True, after=6)
    p = para(doc, after=16)
    runs(p, [("a", False, False, True, 12),
             (" " + AFFIL, False, False, False, 12)])

    para(doc, "Author details", size=11, bold=True, after=8)
    for a in AUTHORS:
        para(doc, a["name"], size=12, bold=True, after=2, indent=0.15)
        para(doc, "Affiliation: " + AFFIL, size=11, after=2, indent=0.15)
        para(doc, "Email: " + a["email"], size=11, after=2, indent=0.15)
        para(doc, "ORCID: " + ("https://orcid.org/" + a["orcid"] if a["orcid"]
                               else "not registered"),
             size=11, after=12, indent=0.15)

    rule(doc)
    para(doc, "* Corresponding author", size=12, bold=True, after=8)
    for label, value in (("Name", corr["name"]),
                         ("Affiliation", AFFIL),
                         ("Email", corr["email"]),
                         ("ORCID", "https://orcid.org/" + corr["orcid"])):
        p = para(doc, after=3, indent=0.15)
        runs(p, [(label + ": ", True, False, False, 11),
                 (value, False, False, False, 11)])

    out = os.path.join(ROOT, "CRSHE_FGCS_AuthorsAffiliations.docx")
    doc.save(out)
    return out


if __name__ == "__main__":
    print("wrote", build_title_page())
    print("wrote", build_cover_letter())
    print("wrote", build_declaration())
    print("wrote", build_authors_affiliations())
