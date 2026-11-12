"""Check that every number Section 7.3 of the manuscript states is the number in
results/range_baselines.json, formatted as the text formats it.

    python scripts/check_range_baselines_text.py [body.tex]

Exits non-zero if a stated figure is missing from the text. Failure control:
with --plant the script perturbs one result by 5 % before formatting and must
then fail; run both and expect "ok" and then a non-zero exit.
"""
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
args = [a for a in sys.argv[1:] if not a.startswith("--")]
body = open(args[0] if args else os.path.join(ROOT, "paper", "jisa", "body.tex")).read()
m = re.search(r"\\subsection\{Range queries against alternatives\}(.*?)\\subsection\{", body, re.S)
if not m:
    sys.exit("section not found")
text = re.sub(r"\s+", " ", m.group(1))
d = json.load(open(os.path.join(ROOT, "results", "range_baselines.json")))
rows = d["rows"]
if "--plant" in sys.argv:
    rows[0]["percell"]["provider"]["median_ms"] *= 1.05


def med(r, key, what="provider"):
    return r[key][what]["median_ms"]


def span(vals, digits=2):
    lo, hi = min(vals) / 1000, max(vals) / 1000
    return f"${lo:.{digits}f}$--${hi:.{digits}f}$\\,s"


by = {r["window_minutes"]: r for r in rows}
ss = [r for r in rows if "single_server" in r]
wk = d["workers"]
want = {
    "per-cell, 5 cells": f"${med(by[1], 'percell') / 1000:.2f}$\\,s for the {by[1]['box_cells']} cells",
    "per-cell, 300 cells": f"${med(by[60], 'percell') / 1000:.1f}$\\,s for the {by[60]['box_cells']} cells",
    "per-cell, day and timeline (computed)":
        f"about ${med(by[1440], 'percell') / 60000:.1f}$ and ${med(by[11523], 'percell') / 60000:.0f}$ minutes",
    "per-cell key bytes": f"${by[1440]['percell']['uplink_bytes_per_provider'] / 1e6:.1f}$ and "
                          f"${by[11523]['percell']['uplink_bytes_per_provider'] / 1e6:.1f}$\\,MB of keys",
    "model error at 300 cells":
        f"${100 * (1 - (300 * d['per_key_eval_ms'] + d['contraction_ms']) / med(by[60], 'percell')):.0f}\\%$",
    "verified, one thread": span([med(r, "crshe_session_serial") for r in rows]),
    "unverified, one thread": span([med(r, "crshe_combined_serial") for r in rows]),
    "single server": f"${sum(med(r, 'single_server', 'server') for r in ss) / len(ss) / 1000:.2f}$\\,s",
    "single-server query ciphertexts": f"{ss[0]['single_server']['query_ciphertexts']} fresh ciphertexts",
    "single-server upload": f"${ss[0]['single_server']['uplink_bytes'] / 1e6:.1f}$\\,MB",
    "single-server encryption": span([med(r, "single_server", "client_query_encrypt") for r in ss]),
    "keys, verified": f"${by[1]['crshe_session_serial']['uplink_bytes_per_provider'] / 1000:.1f}$\\,kB of keys",
    "upload ratio": "about $8{,}000$" if round(ss[0]["single_server"]["uplink_bytes"] /
                                               by[1]["crshe_session_serial"]["uplink_bytes_per_provider"], -3) == 8000
                    else "upload ratio is no longer about 8,000",
    f"verified, {wk} workers": span([med(r, f"crshe_session_pool{wk}") for r in rows]),
    f"unverified, {wk} workers": span([med(r, f"crshe_combined_pool{wk}") for r in rows]),
}
iqr = max((t["q3_ms"] - t["q1_ms"]) / t["median_ms"]
          for r in rows for v in r.values() if isinstance(v, dict)
          for k, t in v.items() if isinstance(t, dict) and t.get("reps", 0) > 0)
want["largest interquartile range"] = f"exceeds ${100 * iqr:.0f}\\%$"
bad = [f"{k}: expected {v!r}" for k, v in want.items() if v not in text]
if bad:
    sys.exit("MISMATCH\n" + "\n".join(bad))
print(f"ok: {len(want)} figures of Section 7.3 match results/range_baselines.json")
