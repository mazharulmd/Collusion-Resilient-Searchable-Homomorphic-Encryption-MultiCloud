"""Assemble supplementary.tex from the full-length manuscript (paper/v5/CRSHE_v5.tex).

The supplement holds what the condensed JNCA manuscript moved out: the full
proofs and the secondary experiments. Text is copied from v5 line ranges, not
retyped; labels that the main text defines are turned into references to it
(xr package, prefix M-), and restated results carry the main text's numbers.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
V5 = os.path.join(HERE, "..", "v5", "CRSHE_v5.tex")
lines = open(V5).read().split("\n")


def chunk(a, b):
    """v5 lines a..b inclusive, 1-indexed."""
    return "\n".join(lines[a - 1:b])


# section title, list of (v5 range) or literal strings
PLAN = [
    ("S1. Why a homomorphic layer at $t=n-1$: the full argument", [
        r"This section completes Section~\mref{sec:whyrep} of the main text.",
        chunk(817, 863), chunk(971, 985)]),
    ("S2. Tamper evidence: verification modes and full proof", [
        chunk(1162, 1251)]),
    ("S3. Correctness: full proof", [chunk(1534, 1587)]),
    ("S4. Leakage security: definition and full proof", [chunk(1486, 1532), chunk(1589, 1694)]),
    ("S5. Additional design details and results", [
        chunk(1351, 1370),
        chunk(1697, 1770),
        r"\subsection{Range layouts and cube size on a synthetic cube}" + "\n" +
        r"\label{sec:rangesynth}" + "\n" +
        r"The measurements below use a synthetic cube with the telemetry dataset's "
        r"dimensions, $3\times11{,}523\times10$ ($M=345{,}690$ cells), on the "
        r"Intel Xeon VM, with the same queries as Section~\mref{sec:rangeresult}." + "\n\n" +
        chunk(1892, 1968),
        chunk(2009, 2090),
        chunk(2136, 2243),
        chunk(2245, 2356),
        chunk(2474, 2500),
        chunk(2546, 2630), chunk(2636, 2649)]),
    ("S6. Withdrawn leakage figures from the C++ prototype", [chunk(2442, 2472)]),
]

MAIN = {  # v5 label -> label in the condensed manuscript
    "sec:prelim": "sec:system", "sec:threat": "sec:system", "sec:packing": "sec:fast",
    "sec:flex": "sec:auth", "sec:resultsdisc": "sec:results",
}
MAIN_LABELS = {"sec:intro", "sec:related", "sec:system", "sec:construction", "sec:whyrep",
               "sec:oha", "sec:mask", "sec:fast", "sec:range", "sec:verify", "sec:auth",
               "sec:security", "sec:impl", "sec:results", "sec:correctness", "sec:rangeresult",
               "sec:verifyresult", "sec:aggresult", "sec:leakeval", "sec:authresult", "sec:limits",
               "sec:conclusion", "tab:compare", "tab:notation", "tab:rangereal", "tab:verify",
               "tab:baselines", "tab:leakage", "fig:arch", "fig:leakage", "thm:mask", "thm:tamper",
               "thm:correct", "thm:sec", "lem:compat", "prop:nolocal", "prop:role", "def:sec",
               "eq:ie", "alg:setup", "alg:query"}

body = []
for title, parts in PLAN:
    body.append("\\section*{" + title + "}\n\\addcontentsline{toc}{section}{" + title + "}")
    body.extend(parts)
T = "\n\n".join(body)

# results that the main text states are restated with its numbers
for env, name in (("theorem", "Theorem"), ("definition", "Definition"), ("proposition", "Proposition")):
    T = re.sub(r"\\begin\{" + env + r"\}\[([^\]]*)\]\s*\n\\label\{([^}]*)\}",
               lambda m: "\\begin{restated}{" + name + "~\\mref{" + MAIN.get(m.group(2), m.group(2)) +
               "} (" + m.group(1) + ")}", T)
    T = T.replace("\\end{" + env + "}", "\\end{restated}")
# demote the one \section heading a chunk carries
T = T.replace("\\section{Complexity analysis}", "\\subsection{Complexity analysis}")
T = T.replace("\\begin{pf}", "\\begin{proof}").replace("\\end{pf}", "\\end{proof}")
T = T.replace("\\qed", "")
# v5 named its algorithm procedures; the condensed text describes the steps instead
T = T.replace("Then $\\mathsf{CombineDec}$\nreturns", "Then the data user's combination step\nreturns")
T = T.replace("$\\mathsf{Retrieve}$\nreturns", "a retrieval\nreturns")
T = T.replace("runs $\\mathsf{Setup}$, $\\mathsf{BuildIndex}$,\n$\\mathsf{Precompute}$, $\\mathsf{EncData}$", "runs the outsourcing of Algorithm~\\mref{alg:setup}")
T = re.sub(r"\[pos=([^\],]*)(,width=[^\]]*)?\]", r"[\1]", T)
T = T.replace("\\begin{table*}", "\\begin{table}").replace("\\end{table*}", "\\end{table}")
T = T.replace("Figures/telemetry/fig_aggregate_latency.pdf", "figures/fig_aggregate_latency.pdf")

local = set(re.findall(r"\\label\{([^}]*)\}", T))


def fix(m):
    cmd, lab = m.group(1), m.group(2)
    lab2 = MAIN.get(lab, lab)
    if lab2 in local:
        return "\\%s{%s}" % (cmd, lab2)
    if lab2 in MAIN_LABELS:
        return "\\m%s{%s}" % ("ref" if cmd == "ref" else "eqref", lab2)
    sys.exit(f"unresolved reference {lab}")


T = re.sub(r"\\(ref|eqref)\{([^}]*)\}", fix, T)

PRE = r"""\documentclass[11pt,a4paper]{article}
\usepackage[margin=2.5cm]{geometry}
\usepackage{amsmath,amssymb,amsthm,booktabs,array,graphicx,xcolor}
\usepackage[numbers,sort&compress]{natbib}
\usepackage{xr}
\externaldocument[M-]{manuscript}
\newcommand{\mref}[1]{\ref{M-#1}}
\newcommand{\meqref}[1]{(\ref{M-#1})}
\makeatletter\let\inputtbl\@@input\makeatother
\newlength{\tblwidth}\setlength{\tblwidth}{\linewidth}
\providecommand{\checkmark}{\ensuremath{\surd}}
\newcommand{\authorcheck}[1]{}
\newtheorem{remark}{Remark}[section]
\renewcommand{\theremark}{S\arabic{remark}}
\newenvironment{restated}[1]{\par\medskip\noindent\textbf{#1.}\ \itshape}{\par\medskip}
\renewcommand{\thetable}{S\arabic{table}}
\renewcommand{\thefigure}{S\arabic{figure}}
\renewcommand{\thesubsection}{S5.\arabic{subsection}}
\input{macros}
\newcommand{\BuildIndex}{\mathsf{BuildIndex}}
\newcommand{\EncData}{\mathsf{EncData}}
\newcommand{\Compute}{\mathsf{Compute}}
\newcommand{\Token}{\mathsf{Token}}
\newcommand{\Setupp}{\mathsf{Setup}}
\newcommand{\bminus}{\boxminus}
\newcommand{\Search}{\mathsf{Search}}
\begin{document}
\begin{center}
{\Large\bfseries Supplementary Material}\\[4pt]
{\large Collusion-resilient, tamper-evident range analytics over homomorphically
encrypted Internet of Things data in multi-cloud storage}
\end{center}
\noindent Section, theorem, table and equation numbers without an ``S'' refer to
the main text. Tables and figures here are numbered S1, S2, \dots
\medskip
"""
POST = r"""
\bibliographystyle{model1-num-names}
\bibliography{references}
\end{document}
"""
open(os.path.join(HERE, "supplementary.tex"), "w").write(PRE + T + POST)
print("wrote supplementary.tex,", len(T.split()), "words")
