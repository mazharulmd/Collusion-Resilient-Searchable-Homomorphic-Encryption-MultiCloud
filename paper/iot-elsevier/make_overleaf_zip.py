"""Export an Overleaf-ready project: one self-contained .tex (generated tables
written inline, no command-line switches), the bibliography, the Elsevier
CAS class files, the CAS icons and only the figures the paper uses.

    python make_overleaf_zip.py  ->  CRSHE_IoT_overleaf.zip

In Overleaf: New Project > Upload Project > choose the zip. Compiler pdfLaTeX.
"""
import os
import re
import shutil
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "CRSHE_IoT_overleaf")
ZIP = os.path.join(HERE, "CRSHE_IoT_overleaf.zip")

src = open(os.path.join(HERE, "CRSHE_IoT.tex")).read()

# 1. inline the generated tables
def inline(m):
    body = open(os.path.join(HERE, m.group(1))).read().rstrip("\n")
    return f"% --- generated from results/*.json by bench/make_tables.py ---\n{body}\n% ---"

src, n = re.subn(r"\\inputtbl (tables/[a-z]+\.tex) ", inline, src)
assert n == 4, n
src = src.replace(
    "% \\input is not expandable, so it cannot open a tabular row that starts with\n"
    "% \\multicolumn or a rule; the TeX primitive can.\n"
    "\\makeatletter\\let\\inputtbl\\@@input\\makeatother\n", "")

# 2. replace the command-line toggle with a line to edit in Overleaf
old = src[src.index("% ANONYMIZED BUILD."):src.index("\\ifdefined\\FULLVERSION \\anonymousfalse \\fi\n")
                                               + len("\\ifdefined\\FULLVERSION \\anonymousfalse \\fi\n")]
src = src.replace(old, (
    "% ANONYMIZED BUILD. The submission system asks for a manuscript without\n"
    "% author details plus a separate title page.\n"
    "%   \\anonymoustrue   -> manuscript without author details (upload this)\n"
    "%   \\anonymousfalse  -> full version with authors, CRediT and highlights page\n"
    "\\newif\\ifanonymous\n"
    "\\anonymoustrue\n"))
assert "FULLVERSION" not in src and "inputtbl" not in src

# 3. assemble the project
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT)
with open(os.path.join(OUT, "CRSHE_IoT.tex"), "w") as f:
    f.write(src)
for name in ("references.bib", "cas-sc.cls", "cas-common.sty", "model1-num-names.bst"):
    shutil.copy(os.path.join(HERE, name), OUT)
shutil.copytree(os.path.join(HERE, "thumbnails"), os.path.join(OUT, "thumbnails"))
for fig in sorted(set(re.findall(r"\\includegraphics\[[^]]*\]\{([^}]+)\}", src))):
    dst = os.path.join(OUT, fig)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy(os.path.join(HERE, fig), dst)

if os.path.exists(ZIP):
    os.remove(ZIP)
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(OUT):
        for fn in sorted(files):
            full = os.path.join(root, fn)
            z.write(full, os.path.relpath(full, OUT))   # files at the zip root
print("wrote", os.path.relpath(ZIP, HERE))
