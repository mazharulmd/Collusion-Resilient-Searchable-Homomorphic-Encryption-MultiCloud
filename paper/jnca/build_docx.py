"""Build the JNCA submission files from manuscript.tex + body.tex.

Run after the LaTeX build (it reads manuscript.aux so that every section, table,
figure, equation and algorithm number in Word matches the PDF):

    pdflatex manuscript; bibtex manuscript; pdflatex manuscript; pdflatex manuscript
    python build_docx.py

Writes, in submission/, the files the JNCA guide for authors (October 2026) asks for:
  CRSHE_JNCA_manuscript.docx                  manuscript, single column, title-page details
                                              on page 1 (the journal uses single-anonymized review)
  CRSHE_JNCA_highlights.docx                  3-5 highlights of at most 85 characters,
                                              separate file with "highlights" in its name
  CRSHE_JNCA_declaration_of_competing_interests.docx
  Figure_1.pdf, Figure_2.pdf                  artwork as separate vector files
  CRSHE_JNCA_supplementary.pdf                supplementary material, cited in the text
Equations become native Word equations (pandoc/OMML); algorithms and tables are
editable text; references use elsevier-numeric.csl; no underlined text.
"""
import os
import re
import shutil
import subprocess
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
OUT = os.path.join(HERE, "submission")
os.makedirs(BUILD, exist_ok=True)
if os.path.isdir(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT)


def run(cmd, cwd=HERE):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"failed: {' '.join(cmd)}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r


def read(name):
    with open(os.path.join(HERE, name)) as f:
        return f.read()


# ---------------------------------------------------------------- labels -----
aux = read("manuscript.aux")
LABEL = {m.group(1): m.group(2) for m in re.finditer(r"\\newlabel\{([^}]*)\}\{\{([^}]*)\}", aux)}
if "sec:range" not in LABEL:
    sys.exit("manuscript.aux has no labels: compile manuscript.tex first")

# ---------------------------------------------------------- images ----------
FIGURES = {"fig_architecture": "Figure_1", "fig_leakage_reference": "Figure_2"}
for fig, out in FIGURES.items():
    run(["pdftoppm", "-r", "300", "-png", "-singlefile", f"figures/{fig}.pdf", f"build/{fig}"])
    shutil.copy(os.path.join(HERE, "figures", fig + ".pdf"), os.path.join(OUT, out + ".pdf"))

# ---------------------------------------------------------- front matter ----
man = read("manuscript.tex")


def between(tag):
    return man[man.index(f"%%{tag}%%") + len(tag) + 4:man.index("%%END%%", man.index(f"%%{tag}%%"))]


title = re.sub(r"\s+", " ", re.search(r"\\title\[[^\]]*\]\{(.*?)\}\s*$", between("TITLE").strip(), re.S).group(1))
abstract = re.search(r"\\begin\{abstract\}(.*)\\end\{abstract\}", between("ABSTRACT"), re.S).group(1).strip()
keywords = [k.strip() for k in re.search(r"\\begin\{keywords\}(.*)\\end\{keywords\}", between("KEYWORDS"),
                                         re.S).group(1).split("\\sep")]
highlights = re.findall(r"\\item (.*)", between("HIGHLIGHTS"))
declarations = between("DECLARATIONS")

authors = []
for m in re.finditer(r"\\author\[(\d+)\]\{([^}]*)\}(?:\[orcid=([^\]]*)\])?(.*?)\\credit\{(.*?)\}", man, re.S):
    block = m.group(4)
    email = re.search(r"\\ead\{([^}]*)\}", block)
    authors.append({"name": m.group(2), "orcid": m.group(3), "corr": "\\cormark" in block,
                    "email": email.group(1) if email else None,
                    "credit": re.sub(r"\s+", " ", m.group(5)).replace("--", "\u2013")})
aff_block = re.search(r"\\affiliation\[1\]\{(.*?)\}\s*\n\s*\n", man, re.S).group(1)
aff_fields = dict(re.findall(r"(\w+)=\{([^}]*)\}", aff_block))
affiliation = re.sub(r"\s+", " ", ", ".join(
    [aff_fields["organization"], aff_fields.get("addressline", ""),
     (aff_fields["city"] + " " + aff_fields.get("postcode", "")).strip(), aff_fields["country"]]).replace(", ,", ","))

# ---------------------------------------------------------- body ------------
body = read("body.tex")
body = "\n".join(l for l in body.split("\n") if not l.lstrip().startswith("%"))


def inline_tables(t):
    return re.sub(r"\\inputtbl\s+(\S+)", lambda m: read(m.group(1) if m.group(1).endswith(".tex")
                                                         else m.group(1) + ".tex"), t)


IND = "\u2003\u2003"   # one algorithmic indentation level


def algorithm_table(src, n, cap):
    """The algorithmic source as an editable three-column table: line, step, comment."""
    text = read(src + ".tex").split("\\begin{algorithmic}[1]")[1].split("\\end{algorithmic}")[0]
    items = []
    for line in text.strip().split("\n"):
        l = line.strip()
        if re.match(r"\\(State|Statex|ForAll|EndFor|Require)\b", l) or not items:
            items.append(l)
        else:
            items[-1] += " " + l
    rows, depth, k = [], 0, 0
    for it in items:
        comment = ""
        c = re.search(r"\\Comment\{(.*)\}\s*$", it)
        if c:
            comment, it = c.group(1), it[:c.start()].strip()
        if it.startswith("\\Require"):
            rows.append(("", "\\textbf{Input:} " + it[len("\\Require"):].strip(), comment))
        elif it.startswith("\\Statex"):
            b = it[len("\\Statex"):].strip()
            if b.startswith("\\hspace{\\algorithmicindent}"):
                rows.append(("", IND * (depth + 1) + b[len("\\hspace{\\algorithmicindent}"):].strip(), comment))
            else:
                rows.append(("", b, comment))
        elif it.startswith("\\EndFor"):
            depth -= 1
            k += 1
            rows.append((str(k), IND * depth + "\\textbf{end for}", comment))
        elif it.startswith("\\ForAll"):
            k += 1
            arg = re.match(r"\\ForAll\{(.*)\}$", it).group(1)
            rows.append((str(k), IND * depth + "\\textbf{for all} " + arg + " \\textbf{do}", comment))
            depth += 1
        elif it.startswith("\\State"):
            k += 1
            rows.append((str(k), IND * depth + it[len("\\State"):].strip().replace("\\Return", "\\textbf{return}"),
                         comment))
        else:
            sys.exit(f"unhandled algorithm line: {it}")
    lines = ["%s & %s & %s \\\\" % (a, b, "\u25b7 \\emph{%s}" % c if c else "") for a, b, c in rows]
    return ("\\begin{table}\n\\caption{Algorithm %s. %s}\n\\begin{tabular}{p{0.06\\linewidth}p{0.66\\linewidth}p{0.24\\linewidth}}\n%s\n\\end{tabular}\n\\end{table}"
            % (n, re.sub(r"\s+", " ", cap), "\n".join(lines)))


def algorithms(t):
    def rep(m):
        cap = re.search(r"\\caption\{(.*?)\}\s*\\label\{([^}]*)\}", m.group(0), re.S)
        src = re.search(r"\\input\{([^}]*)\}", m.group(0)).group(1)
        return algorithm_table(src, LABEL[cap.group(2)], cap.group(1))
    return re.sub(r"\\begin\{algorithm\}.*?\\end\{algorithm\}", rep, t, flags=re.S)


def captions(t, env, word):
    def rep(m):
        block = m.group(0)
        lab = re.search(r"\\label\{([^}]*)\}", block)
        if lab:
            n = LABEL[lab.group(1)]
            block = re.sub(r"\\caption\{", lambda _: "\\caption{%s %s. " % (word, n), block, count=1)
        return block
    return re.sub(r"\\begin\{%s\*?\}.*?\\end\{%s\*?\}" % (env, env), rep, t, flags=re.S)


def equations(t):
    def rep(m):
        lab = re.search(r"\\label\{([^}]*)\}", m.group(1))
        inner = re.sub(r"\\label\{[^}]*\}", "", m.group(1)).strip()
        tag = "\\qquad\\qquad(%s)" % LABEL[lab.group(1)] if lab else ""
        return "\\[\n" + inner + tag + "\n\\]"
    return re.sub(r"\\begin\{equation\}(.*?)\\end\{equation\}", rep, t, flags=re.S)


def tabulars(t):
    t = re.sub(r"\\begin\{tabular\*\}\{[^}]*\}\{@\{\\extracolsep\{\\fill\}\}([^}]*?)@\{\}\}",
               r"\\begin{tabular}{\1}", t)
    t = t.replace("\\end{tabular*}", "\\end{tabular}")
    t = re.sub(r"\\begin\{tabular\}\{@\{\}([^}]*?)@\{\}\}", r"\\begin{tabular}{\1}", t)
    t = t.replace("{@{}l}", "{l}")
    t = re.sub(r"\\cmidrule\([^)]*\)\{[^}]*\}", "", t)
    return t


body = inline_tables(body)
body = algorithms(body)
body = captions(body, "table", "Table")
body = captions(body, "figure", "Fig.")
body = equations(body)
body = tabulars(body)
body = re.sub(r"\[pos=[^\]]*\]", "", body)
body = body.replace("\\begin{table*}", "\\begin{table}").replace("\\end{table*}", "\\end{table}")
body = body.replace("\\begin{figure*}", "\\begin{figure}").replace("\\end{figure*}", "\\end{figure}")
body = re.sub(r"figures/(fig_[a-z_]+)\.pdf", r"\1.png", body)
body = re.sub(r"\\begin\{pf\}(\[[^\]]*\])?", lambda m: "\\begin{proof}" + (m.group(1) or ""), body)
body = body.replace("\\end{pf}", "\\end{proof}").replace("\\qed", "")
body = body.replace("$\\checkmark$", "\u2713")
# plain numbers are text in Word, not equations: $1{,}440$ -> 1,440, $100.0\%$ -> 100.0%,
# $\mathbf{39.2}$ -> bold text, so that table cells and prose use the body font
NUM = r"[0-9][0-9.]*(?:\{,\}[0-9]+)*(?:\.[0-9]+)?"


def numtext(t):
    t = re.sub(r"\$\\mathbf\{(" + NUM + r")\}\$", lambda m: "\\textbf{" + m.group(1).replace("{,}", ",") + "}", t)
    return re.sub(r"\$(" + NUM + r")(\\%)?\$", lambda m: m.group(1).replace("{,}", ",") + ("\\%" if m.group(2) else ""), t)


body = numtext(body)
abstract = numtext(abstract)
declarations_doc = numtext(declarations)
# chemical subscripts (PM$_{2.5}$, NO$_2$) and comparison numbers as text; grouped numbers
# inside equations as upright text, so Word does not space them as "11 , 580"
body = re.sub(r"([A-Za-z])\$_\{?([0-9.]+)\}?\$", r"\1\\textsubscript{\2}", body)
body = re.sub(r"\$([<>])(" + NUM + r")\$", lambda m: ("\\textless{}" if m.group(1) == "<" else "\\textgreater{}")
              + m.group(2).replace("{,}", ","), body)
body = body.replace("$\\mathrm{class}(q)$", "class(\\emph{q})")
body = re.sub(r"\$([0-9]+)/([0-9]+)\$", r"\1/\2", body)                       # detection counts
body = re.sub(r"\$(" + NUM + r")\^\{\\dagger\}\$", lambda m: m.group(1).replace("{,}", ",")
              + "\\textsuperscript{\u2020}", body)


def group_in_math(t):
    def fix(m):
        return re.sub(r"[0-9]{1,3}(?:\{,\}[0-9]{3})+", lambda n: "\\text{" + n.group(0).replace("{,}", ",") + "}",
                      m.group(0))
    t = re.sub(r"\$[^$]+\$", fix, t)
    return re.sub(r"\\\[.*?\\\]", fix, t, flags=re.S)


body = group_in_math(body)


def resolve(t):
    t = re.sub(r"\\(eq)?ref\{([^}]*)\}", lambda m: ("(%s)" if m.group(1) else "%s") % LABEL[m.group(2)], t)
    return re.sub(r"\\label\{[^}]*\}", "", t)


body = resolve(body)
declarations_doc = resolve(declarations_doc)
left = re.findall(r"\\(?:ref|eqref|label|inputtbl|input)\{", body + declarations_doc)
if left:
    sys.exit(f"unresolved commands: {left}")

credit = "\\section*{CRediT authorship contribution statement}\n" + " ".join(
    "\\textbf{%s:} %s." % (a["name"], a["credit"]) for a in authors)


def front():
    names = ", ".join(a["name"] + "\\textsuperscript{a%s}" % (",*" if a["corr"] else "") for a in authors)
    corr = [a for a in authors if a["corr"]][0]
    emails = "; ".join(f"{a['name']}: {a['email']}" for a in authors if a["email"])
    return ("\\noindent %s\n\n\\noindent\\textsuperscript{a}%s\n\n"
            "\\noindent\\textsuperscript{*}Corresponding author: %s (%s).\n\n"
            "\\noindent E-mail addresses: %s.\n\n" % (names, affiliation, corr["name"], corr["email"], emails))


MACROS = read("macros.tex")
doc_tex = ("\\documentclass{article}\n\\usepackage{amsthm,amsmath,amssymb,natbib,booktabs,graphicx}\n"
           "\\newtheorem{theorem}{Theorem}\n\\newtheorem{lemma}{Lemma}\n"
           "\\newtheorem{proposition}{Proposition}\n\\newtheorem{definition}{Definition}\n"
           + MACROS + "\n\\title{" + title + "}\n\\date{}\n\\begin{document}\n\\maketitle\n"
           + front()
           + "\\section*{Abstract}\n" + abstract + "\n\n\\noindent\\textbf{Keywords:} "
           + "; ".join(keywords) + "\n\n" + body + "\n\n" + credit + "\n\n" + declarations_doc
           + "\n\\end{document}\n")
with open(os.path.join(BUILD, "manuscript_docx.tex"), "w") as f:
    f.write(doc_tex)

# ---------------------------------------------------------- reference doc ---
ref = os.path.join(BUILD, "reference.docx")
run(["pandoc", "-o", ref, "--print-default-data-file", "reference.docx"])
rd = Document(ref)
for st in rd.styles:
    if st.type != 1:  # paragraph and character styles only
        continue
    try:
        st.font.name = "Times New Roman"
        rpr = st.element.get_or_add_rPr()
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None:
            fonts = OxmlElement("w:rFonts")
            rpr.append(fonts)
        for k in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            fonts.set(qn(k), "Times New Roman")
        for k in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
            if fonts.get(qn(k)) is not None:
                del fonts.attrib[qn(k)]
        st.font.color.rgb = None
    except (AttributeError, ValueError):
        pass
SIZES = {"Normal": 11, "BodyText": 11, "FirstParagraph": 11, "Compact": 9, "Title": 16, "Author": 11,
         "Abstract": 10, "Heading1": 12, "Heading2": 11, "Heading3": 11, "TableCaption": 9.5,
         "ImageCaption": 9.5, "Bibliography": 9.5, "CaptionedFigure": 11}
BY_ID = {st.style_id: st for st in rd.styles}
for sid, size in SIZES.items():
    st = BY_ID.get(sid)
    if st is None:
        sys.exit(f"reference.docx has no style {sid}")
    st.font.size = Pt(size)
    pf = st.paragraph_format
    pf.line_spacing = 1.0
    pf.space_before = Pt(8 if sid.startswith("Heading") else 0)
    pf.space_after = Pt(3 if sid.startswith("Heading") else 4)
    if sid.startswith("Heading") or sid == "Title":
        st.font.bold = True
        st.font.italic = sid == "Heading2"
    if sid in ("BodyText", "FirstParagraph", "Abstract"):
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
# the guide asks for no underline formatting: links keep their colour only
if "Hyperlink" in BY_ID:
    BY_ID["Hyperlink"].font.underline = False
for sec in rd.sections:
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.left_margin = sec.right_margin = Cm(2.5)
    sec.top_margin = sec.bottom_margin = Cm(2.5)
rd.save(ref)


# ---------------------------------------------------------- pandoc ----------
REF_TAGS = (("environmental sensor telemetry data", "[dataset] "), ("beijing multi-site air quality", "[dataset] "),
            ("reference implementation, benchmark scripts", "[software] "))


def border(parent_tag, edges, size):
    b = OxmlElement(parent_tag)
    for edge in edges:
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), str(size))
        e.set(qn("w:color"), "000000")
        b.append(e)
    return b


def finish(path):
    d = Document(path)
    sect = d.sections[-1]
    ln = OxmlElement("w:lnNumType")
    ln.set(qn("w:countBy"), "1")
    ln.set(qn("w:restart"), "continuous")
    ln.set(qn("w:distance"), "283")
    sect._sectPr.append(ln)
    p = sect.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for tag, text in (("begin", None), (None, "PAGE"), ("end", None)):
        r = p.add_run()
        if tag:
            fc = OxmlElement("w:fldChar")
            fc.set(qn("w:fldCharType"), tag)
            r._r.append(fc)
        else:
            it = OxmlElement("w:instrText")
            it.set(qn("xml:space"), "preserve")
            it.text = text
            r._r.append(it)
    # horizontal rules only (the guide asks for no vertical rules or shading):
    # top and bottom of every table, and below the header row where there is one
    for tbl in d.tables:
        tbl._tbl.tblPr.append(border("w:tblBorders", ("top", "bottom"), 8))
        if tbl.rows and tbl.rows[0]._tr.find(qn("w:trPr")) is not None and \
                tbl.rows[0]._tr.find(qn("w:trPr")).find(qn("w:tblHeader")) is not None:
            for cell in tbl.rows[0].cells:
                cell._tc.get_or_add_tcPr().append(border("w:tcBorders", ("bottom",), 4))
    for p_ in d.paragraphs:
        if re.match(r"(Algorithm|Table) \d+\.", p_.text):
            p_.paragraph_format.keep_with_next = True
    # the reference list sits inside a content control, so walk every paragraph element;
    # Elsevier asks for [dataset] / [software] immediately before such references
    for p_el in d.element.body.iter(qn("w:p")):
        text = "".join(t.text or "" for t in p_el.iter(qn("w:t")))
        if not re.match(r"\[\d+\]", text):
            continue
        for needle, tag in REF_TAGS:
            if needle in text.lower():
                # prefix the first text after the "[n]" label and its tab
                for t in p_el.iter(qn("w:t")):
                    if t.text and t.text.strip() and not re.fullmatch(r"\s*\[\d+\]\s*", t.text):
                        t.text = tag + t.text.lstrip()
                        t.set(qn("xml:space"), "preserve")
                        break
                break
    # strip any underline that survived (the guide asks for none)
    for u in d.element.body.iter(qn("w:u")):
        u.getparent().remove(u)
    d.save(path)


MANUSCRIPT = os.path.join(OUT, "CRSHE_JNCA_manuscript.docx")
run(["pandoc", os.path.join(BUILD, "manuscript_docx.tex"), "-f", "latex", "-o", MANUSCRIPT, "--citeproc",
     "--bibliography", "references.bib", "--csl", "elsevier-numeric.csl", "--number-sections",
     "--reference-doc", ref, "--resource-path", f"{BUILD}:{HERE}",
     "-M", "reference-section-title=References", "-M", "link-citations=false"])
finish(MANUSCRIPT)


# ---------------------------------------------------------- small files -----
def plain(s):
    s = s.replace("$2^d$", "2\u1d48").replace("2^d", "2\u1d48")
    return re.sub(r"[{}\\$]", "", s)


def md_docx(md, name):
    path = os.path.join(BUILD, name + ".md")
    with open(path, "w") as f:
        f.write(md)
    run(["pandoc", path, "-o", os.path.join(OUT, name + ".docx"), "--reference-doc", ref])


for h in highlights:
    if len(plain(h)) > 85:
        sys.exit(f"highlight over 85 characters: {plain(h)}")
md_docx("# Highlights\n\n" + "".join(f"- {plain(h)}\n" for h in highlights), "CRSHE_JNCA_highlights")

competing = re.search(r"\\section\*\{Declaration of competing interest\}\s*(.*?)(?=\\section\*)", declarations,
                      re.S).group(1)
md_docx("# Declaration of competing interests\n\n" + f"**Manuscript title:** {title}\n\n"
        + "**Authors:** " + ", ".join(a["name"] for a in authors) + "\n\n"
        + re.sub(r"\s+", " ", competing).strip() + "\n", "CRSHE_JNCA_declaration_of_competing_interests")

shutil.copy(os.path.join(HERE, "supplementary.pdf"), os.path.join(OUT, "CRSHE_JNCA_supplementary.pdf"))
print("wrote", sorted(os.listdir(OUT)))
