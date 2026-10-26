"""Re-analyse the leakage experiment from per-tag posting lengths
(results/lengths_<corpus>.csv.gz, written by dump_lengths.py on a machine with
the raw data), without the raw corpora:

1. reproduce the unmasked, padded and volume-hiding runs of
   results/leakage_<corpus>.json at every f, and check that a planted tie
   breaks the reproduction (failure control);
2. the length-only bound: an attacker that sees only row statistics cannot
   tell apart rows with equal statistics, so it expects at most one correct
   assignment per distinct value; per class and overall;
3. storage inflation of power-of-two and volume-hiding padding.

Exits non-zero if the reproduction fails or the control does not.
"""
import csv
import gzip
import json
import os
import sys

import numpy as np

from common import save
from crshe import attack

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
# the C++ prototype's earlier per-class figures (unmasked, f = 1), as the
# revision manuscript reported them; compared against the bound below
CPP = {"telemetry": {"overall": 0.0427, "device": 1, "light": 1, "motion": 1, "co": 1, "humidity": 1,
                     "lpg": 1, "smoke": 1, "temp": 1, "minute": 0.0380},
       "beijing": {"site": 1, "wd": 1, "CO": 1, "NO2": 1, "O3": 1, "PM2.5": 1, "PM10": 1, "SO2": 1,
                   "PRES": 1, "DEWP": 1, "hour": 0.0031}}

out, failed = {}, False
for corpus in ("telemetry", "beijing"):
    path = os.path.join(ROOT, "results", f"lengths_{corpus}.csv.gz")
    if not os.path.exists(path):
        print(f"{corpus}: {path} missing (run dump_lengths.py where the raw data are)")
        continue
    with gzip.open(path, "rt") as f:
        rows = list(csv.DictReader(f))
    cls = [r["class"] for r in rows]
    L = np.array([int(r["length"]) for r in rows])
    with open(os.path.join(ROOT, "results", f"leakage_{corpus}.json")) as f:
        ref = {(r["scheme"], r["fraction"]): r for r in json.load(f)["runs"]}

    def same(a, b):
        return abs(a["overall"] - b["overall"]) < 1e-12 and all(
            abs(a["per_class"][k] - b["per_class"][k]) < 1e-12 for k in a["per_class"])

    reproduced = all(same(attack.run(L, cls, s, fraction=fr), ref[(s, fr)])
                     for fr in (1.0, 0.5, 0.1, 0.01) for s in ("unmasked", "padded", "volume_hiding"))
    vals, counts = np.unique(L, return_counts=True)
    uniq = set(vals[counts == 1].tolist())
    idx = [i for i, x in enumerate(L) if x in uniq and cls[i] not in ("minute", "hour")]
    planted = L.copy()
    planted[idx[0]] = L[idx[1]]
    control_failed = not same(attack.run(planted, cls, "unmasked", fraction=1.0), ref[("unmasked", 1.0)])
    failed |= not reproduced or not control_failed

    per = {}
    for k in sorted(set(cls)):
        lk = L[np.array(cls) == k]
        d = len(set(lk.tolist()))
        per[k] = {"tags": int(len(lk)), "distinct_lengths": d, "length_only_bound": d / len(lk),
                  "reference": ref[("unmasked", 1.0)]["per_class"][k], "cpp": CPP[corpus].get(k)}
    overall_bound = len(vals) / len(L)
    out[corpus] = {
        "reproduces_leakage_json": reproduced, "planted_tie_breaks_reproduction": control_failed,
        "distinct_lengths": int(len(vals)), "tags": int(len(L)),
        "overall_length_only_bound": overall_bound,
        "overall_reference": ref[("unmasked", 1.0)]["overall"], "overall_cpp": CPP[corpus].get("overall"),
        "per_class": per,
        "inflation_power_of_two": float(attack.pad_pow(L, 2).sum() / L.sum()),
        "inflation_volume_hiding": float(len(L) * L.max() / L.sum())}
    print(f"{corpus}: reproduced={reproduced} control_failed={control_failed} "
          f"bound={100 * overall_bound:.3f}% reference={100 * out[corpus]['overall_reference']:.3f}% "
          f"pow2={out[corpus]['inflation_power_of_two']:.3f}x vh={out[corpus]['inflation_volume_hiding']:.1f}x")
    for k, v in per.items():
        over = v["cpp"] is not None and v["cpp"] > v["length_only_bound"] + 1e-12
        print(f"  {k:9s} tags={v['tags']:6d} distinct={v['distinct_lengths']:5d} "
              f"bound={100 * v['length_only_bound']:7.3f}% ref={100 * v['reference']:7.3f}%"
              + (f" C++={100 * v['cpp']:.2f}% EXCEEDS BOUND" if over else ""))
save("leakage_bounds.json", out)
sys.exit(1 if failed else 0)
