"""Write every tag's posting-list length, with its class, for the real corpora:
results/lengths_<corpus>.csv.gz (tag,class,length). Tag names and counts are
aggregate statistics of public datasets; no record is written.

These files let the leakage results be re-analysed without the raw data: tie
groups per class (at f = 1 a tag is missed only when another tag has exactly
the same length), the power-of-two padding inflation, and a comparison with
the C++ corpus builder's tag lengths.
"""
import argparse
import csv
import gzip
import os
import sys

from common import save
from crshe import corpus

ap = argparse.ArgumentParser()
ap.add_argument("--corpus", choices=["telemetry", "beijing"], nargs="+",
                default=["telemetry", "beijing"])
args = ap.parse_args()

summary = {}
for name in args.corpus:
    loader = corpus.load_telemetry if name == "telemetry" else corpus.load_beijing
    try:
        c = loader()
    except (FileNotFoundError, OSError) as exc:
        print(f"{name}: corpus not available: {exc}", file=sys.stderr)
        continue
    L = c.lengths()
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results",
                        f"lengths_{name}.csv.gz")
    with gzip.open(path, "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tag", "class", "length"])
        for t, k, n in zip(c.tags, c.tag_class, L):
            w.writerow([t, k, int(n)])
    distinct = len(set(int(x) for x in L))
    summary[name] = {"tags": len(L), "distinct_lengths": distinct,
                     "file": f"results/lengths_{name}.csv.gz"}
    print(f"{name}: {len(L)} tags, {distinct} distinct lengths -> results/lengths_{name}.csv.gz")
save("lengths_summary.json", summary)
