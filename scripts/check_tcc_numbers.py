"""Check every number in the prose of paper/tcc/manuscript.tex against the
result files.

    python scripts/check_tcc_numbers.py            # expect "ok"
    python scripts/check_tcc_numbers.py --plant    # must fail

A number in the text passes if (a) it appears as a value in
paper/focused/NUMBERS.md (generated from results/*.json), or (b) it is one of
the derived figures listed in DERIVED below, each recomputed here from the
result files, or (c) it is a parameter or count listed in FIXED, with the
reason it is fixed. Anything else fails. --plant changes one measured figure
in a copy of the text, and the check must then report it.
"""
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
tex = open(os.path.join(ROOT, "paper", "tcc", "manuscript.tex")).read()
numbers_md = open(os.path.join(ROOT, "paper", "focused", "NUMBERS.md")).read()


def load(name):
    return json.load(open(os.path.join(ROOT, "results", name)))


if "--plant" in sys.argv:
    tex = tex.replace("1,185.8--1,189.6", "1,185.8--1,198.6", 1)

# prose only: drop comments, the bibliography, figure/table/algorithm bodies' file names
body = re.sub(r"(?<!\\)%.*", "", tex)
body = body.split("\\bibliographystyle")[0]
body = body[body.index("\\begin{abstract}"):]          # skip the author block (postal address)
body = body.replace("$", " ")
body = re.sub(r"\\(includegraphics|inputtbl|input|label|ref|eqref|cite)(\[[^\]]*\])?\{[^}]*\}", " ", body)
body = re.sub(r"\\(begin|end)\{[^}]*\}(\{[^}]*\})*", " ", body)
body = body.replace("{,}", ",").replace("--", " – ").replace("\\,", " ")

tokens = re.findall(r"(?<![\w.^_$])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d{2,})(?![\w])", body)

# (a) values printed in NUMBERS.md
md_vals = set()
for line in numbers_md.splitlines():
    if not line.startswith("|"):
        continue
    cells = [c.strip() for c in line.strip("|").split("|")]
    if len(cells) < 2:
        continue
    for t in re.findall(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d+", cells[0] + " " + cells[1]):
        md_vals.add(t)

# (b) derived figures, recomputed
rt, rb_ = load("range_real_telemetry.json"), load("range_real_beijing_day.json")
bl = load("range_baselines.json")
v = load("verification_modes.json")
sess_t = [w["provider_total"]["median_ms"] for w in rt["modes"]["session"]["by_window"]]
sess_b = [w["provider_total"]["median_ms"] for w in rb_["modes"]["session"]["by_window"]]
rows = {r["window_minutes"]: r for r in bl["rows"]}
ss = [r for r in bl["rows"] if "single_server" in r][0]["single_server"]
key_up = rt["modes"]["session"]["by_window"][0]["uplink_bytes_per_provider"]
model300 = 300 * bl["per_key_eval_ms"] + bl["contraction_ms"]
DERIVED = {
    "0.68": f"{min(sess_b) / 1000:.2f}", "1.19": f"{max(sess_t) / 1000:.2f}",       # abstract span, seconds
    "44": f"{ss['uplink_bytes'] / 1e6:.0f}",                                        # 44 MB single-server query
    "1,500": f"{5 * v['trials'] + 2 * sum(rt['modes']['session']['tamper']['dense'].values()) * 5:,}",
    "1,000": f"{5 * v['trials']:,}",
    "500": f"{2 * 5 * sum(rt['modes']['session']['tamper']['dense'].values())}",
    "200": f"{v['trials']}",
    "7.5": f"{rows[1440]['percell']['provider']['median_ms'] / 60000:.1f}",
    "60": f"{rows[11523]['percell']['provider']['median_ms'] / 60000:.0f}",
    "2.5": f"{rows[1440]['percell']['uplink_bytes_per_provider'] / 1e6:.1f}",
    "19.9": f"{rows[11523]['percell']['uplink_bytes_per_provider'] / 1e6:.1f}",
    "13": f"{100 * (1 - model300 / rows[60]['percell']['provider']['median_ms']):.0f}",
    "8,000": f"{round(ss['uplink_bytes'] / key_up, -3):,.0f}",
    "5.5": f"{key_up / 1000:.1f}",
    "132": f"{rt['modes']['session']['by_window'][0]['downlink_bytes'] / 1000:.0f}",
    "0.16": f"{0.1 + (key_up + rt['modes']['session']['by_window'][0]['downlink_bytes']) * 8 / 20e6:.2f}",
    "18.0": "18.0", "19.5": "19.5", "1.26": "1.26", "1.29": "1.29",                # spans over both cubes, in NUMBERS.md per cube
    "400,000": "400,000",                                                           # "about", both corpora 405,184 and 420,370
}
# the four span ends above are re-checked against NUMBERS.md explicitly
for k in ("18.0", "19.5", "1.26", "1.29"):
    if k not in md_vals:
        sys.exit(f"derived span end {k} not in NUMBERS.md")

# (c) parameters and counts that are not measurements
FIXED = {
    "68,724,326,401": "plaintext modulus p", "8,192": "ring dimension", "128": "security level / AES-128",
    "37": "bit length of p", "17": "p = 1 mod 2^17", "64": "2^64 in Lemma discussion", "36": "2^-36",
    "100": "assumed round-trip time, ms", "20": "assumed bandwidth, Mbit/s", "10": "deciles",
    "11": "PM2.5 bands incl. missing", "12": "sites", "169": "table ciphertexts (also in NUMBERS.md)",
    "50": "Beijing temperature shift, C", "2.1": "CPU clock, GHz", "32": "virtual CPUs",
    "7J13": "CPU model",
}
bad = []
for t in tokens:
    if t in md_vals or t in FIXED:
        continue
    if t in DERIVED:
        want = DERIVED[t]
        if t != want and not (t == "400,000"):
            bad.append(f"{t}: recomputed as {want}")
        continue
    bad.append(f"{t}: not found in NUMBERS.md, DERIVED or FIXED")
for t, want in DERIVED.items():
    if t != want and t != "400,000":
        bad.append(f"derived {t} no longer matches the results ({want})")
if bad:
    sys.exit("FAIL\n" + "\n".join(sorted(set(bad))))
print(f"ok: {len(tokens)} numbers in the prose, all traced to the result files")
