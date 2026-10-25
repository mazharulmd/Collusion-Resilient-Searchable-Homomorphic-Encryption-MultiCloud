"""Every number in draft B: where (if anywhere) else it appears."""
import re, glob, json
def nums(text):
    text = re.sub(r'\{,\}', ',', text)
    out = set()
    for m in re.finditer(r'(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+\.\d+|\d{2,})(?![\w])', text):
        s = m.group(1).replace(',', '')
        out.add(s)
    return out
import sys
B = open(sys.argv[1]).read()
B = B.split(r'\begin{thebibliography}')[0].split(r'\bibliography{')[0]
srcs = {
 'v4': open('paper/v4/CRSHE_v4.tex').read(),
 'fgcs': open('paper/fgcs-2026-submission/CRSHE_FGCS.tex').read(),
 'revision': open('paper/revision/CRSHE_revised.tex').read() + ''.join(open(f).read() for f in glob.glob('paper/revision/tables/*.tex')),
 'results': ''.join(open(f).read() for f in glob.glob('results/*.json')),
}
srcnums = {k: nums(v) for k, v in srcs.items()}
# results JSON: also rounded forms of floats
rs = set()
for f in glob.glob('results/*.json'):
    for m in re.finditer(r'-?\d+\.\d+', open(f).read()):
        x = float(m.group())
        for d in (1, 2, 3):
            rs.add(f"{x:.{d}f}")
srcnums['results'] |= rs
missing = []
for n in sorted(nums(B), key=lambda s: float(s)):
    where = [k for k, v in srcnums.items() if n in v]
    if not where:
        missing.append(n)
    elif 'v4' not in where:
        print(f"{n:>12}  in {','.join(where)} but NOT in v4")
print("\nNOT FOUND ANYWHERE:", missing)
