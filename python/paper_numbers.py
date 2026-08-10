#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Emit the paper's numeric table rows straight from the results CSVs, and
check the manuscript against them.

Every number in Section IX was, at some point, copied by hand from a benchmark
into LaTeX. That is the step where a paper silently stops matching its own
artefact -- a re-run changes a CSV, the table does not follow, and nobody
notices until a reviewer reproduces it. This closes the loop:

  # print the rows to paste
  python3 python/paper_numbers.py --results bench/results

  # verify the manuscript still agrees with the CSVs (exit 1 if not)
  python3 python/paper_numbers.py --results bench/results \\
      --check paper/CRSHE_v2_full.tex

Run the check before every submission, and after every re-run.
"""

import argparse
import csv
import os
import re
import sys


def load(path):
    if not os.path.exists(path):
        return None
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def fmt(x, places=3):
    """Match the manuscript's convention: thousands separated with \\,{} groups."""
    s = f"{x:.{places}f}".rstrip("0").rstrip(".") if places else f"{x:.0f}"
    if "." in s:
        whole, frac = s.split(".")
    else:
        whole, frac = s, ""
    if len(whole) > 3:
        whole = f"{int(whole):,}".replace(",", "{,}")
    return whole + ("." + frac if frac else "")


def table_selection(rows):
    """Table V: selection latency and key size vs N, two-party construction."""
    by = {}
    for r in rows:
        if r["construction"] != "bgi16-tree":
            continue
        by.setdefault(int(r["N"]), {})[int(r["threads"])] = (
            float(r["eval_ms_median"]), int(r["key_bytes_max"]))
    out = []
    for N in sorted(by):
        v = by[N]
        if not all(t in v for t in (1, 4, 16)):
            continue
        out.append((N, v[1][0], v[4][0], v[16][0], v[1][1]))
    return out


def table_aggregate(agg_rows, fast_rows):
    """Table II: fast vs general aggregate latency and index size vs N_d.

    Fast-path figures come from the order-controlled (decreasing N_d) sweep when
    it is present, because the increasing-order sweep carries a warm-up ramp.
    """
    fast = {}
    src = fast_rows if fast_rows else agg_rows
    for r in src:
        if r["path"] != "fast":
            continue
        fast[int(r["Nd"])] = float(r["provider_ms_median"])
    gen, idx = {}, {}
    for r in agg_rows:
        if r["path"] != "general":
            continue
        nd = int(r["Nd"])
        idx[nd] = int(r["index_bytes_per_provider"])
        m = float(r["provider_ms_median"])
        gen[nd] = m if m > 0 else None
    out = []
    for nd in sorted(set(fast) | set(gen)):
        out.append((nd, fast.get(nd), gen.get(nd), idx.get(nd)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", default="bench/results")
    ap.add_argument("--check", default="", help="path to the .tex to verify")
    a = ap.parse_args()

    e1 = load(os.path.join(a.results, "e1_dpf.csv"))
    e2 = load(os.path.join(a.results, "e2_agg.csv"))
    e2f = load(os.path.join(a.results, "e2_fast_reversed.csv"))

    expected = []          # (label, value) pairs the manuscript must contain

    if e1:
        print("% ---- Table V: selection latency and key size ----")
        for N, t1, t4, t16, key in table_selection(e1):
            print(f"${fmt(N,0)}$ & ${fmt(t1)}$ & ${fmt(t4)}$ & ${fmt(t16)}$ "
                  f"& ${key}$ \\\\")
            for v in (t1, t4, t16):
                expected.append((f"E1 N={N}", fmt(v)))
        print()

    if e2:
        print("% ---- Table II: aggregate latency, fast vs general ----")
        for nd, f, g, ib in table_aggregate(e2, e2f):
            gs = fmt(g, 1) if g else "---"
            gb = f"{ib/1e9:.2f}" if ib else "---"
            print(f"${fmt(nd,0)}$ & ${fmt(f,1) if f else '---'}$ & ${gs}$ "
                  f"& ${gb}$ & $525{{,}}950$ \\\\")
            if f:
                expected.append((f"E2 fast Nd={nd}", fmt(f, 1)))
            if g:
                expected.append((f"E2 general Nd={nd}", fmt(g, 1)))
        print()

    if not a.check:
        return 0

    tex = open(a.check).read()
    missing = [(what, v) for what, v in expected if v not in tex]
    if missing:
        print(f"MANUSCRIPT OUT OF SYNC WITH {a.results}:", file=sys.stderr)
        for what, v in missing:
            print(f"  {what}: CSV says {v}, not found in {a.check}", file=sys.stderr)
        print(f"\n{len(missing)} of {len(expected)} values do not appear in the "
              f"manuscript.\nRe-run the benchmark, or paste the rows above into "
              f"the tables.", file=sys.stderr)
        return 1

    print(f"OK: all {len(expected)} table values in {a.check} appear in the "
          f"CSVs under {a.results}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
