"""What the MAC catches: four provider deviations, global key against
per-row keys (Remark 2 of the submitted manuscript, which was neither
implemented nor measured there). Counts only; no timing.

inconsistent   adds a random non-zero constant to the value row only
dense          contracts against e_j + d, d uniform, in BOTH rows
scale          contracts against k * e_j in both rows (the submitted example)
single_row     contracts against e_j + c * u_x for a random row x, both rows;
               the provider does not know alpha, so x = alpha with prob 1/N
"""
import argparse

import numpy as np

from common import save, tag_domain_deployment
from crshe import Provider, VerificationError, field, he

ap = argparse.ArgumentParser()
ap.add_argument("--N", type=int, default=11_580)
ap.add_argument("--trials", type=int, default=200)
args = ap.parse_args()

rng = np.random.default_rng(2026)
bfv = he.BFV()
o, tags, postings, values = tag_domain_deployment(args.N, bfv=bfv, templates=("sum",))
layouts = {m: o.fast_layout(["sum"], mac=m) for m in ("global", "row")}
b = o.bundle(layouts=[(m, L) for m, L in layouts.items()])
P = [Provider(j, b) for j in range(2)]
u = o.user()
nonempty = [t for t, p in zip(tags, postings) if len(p)]


def deviate(kind, e):
    if kind == "dense":
        return field.add(e, rng.integers(0, field.P, len(e), dtype=np.uint64)), None
    if kind == "scale":
        k = int(rng.integers(2, field.P))
        return field.mul(e, np.uint64(k)), None
    if kind == "single_row":
        x = int(rng.integers(0, len(e)))
        d = np.zeros(len(e), dtype=np.uint64)
        d[x] = int(rng.integers(1, field.P))
        return field.add(e, d), x
    return e, None


out = {}
for mac, L in layouts.items():
    out[mac] = {}
    for kind in ("inconsistent", "dense", "scale", "single_row"):
        c = {"detected": 0, "undetected_wrong": 0, "undetected_correct": 0}
        for _ in range(args.trials):
            tag = nonempty[int(rng.integers(0, len(nonempty)))]
            truth = int(values[postings[tags.index(tag)]].sum())
            keys = u.token(tag)
            r0 = P[0].fast(keys[0], mac)
            e1 = keys[1].eval_full()
            e1d, _ = deviate(kind, e1)
            r1 = P[1].fast(keys[1], mac, e=e1d)
            if kind == "inconsistent":
                bump = np.zeros(bfv.slots, dtype=np.uint64)
                bump[0] = int(rng.integers(1, field.P))
                r1 = bfv.cc.EvalAdd(r1, bfv.encrypt(bump))
            try:
                y = u.finish_fast(tag, L, [r0, r1])["sum"]
                c["undetected_correct" if y == truth else "undetected_wrong"] += 1
            except VerificationError:
                c["detected"] += 1
        out[mac][kind] = c
        print(f"{mac:6s} {kind:12s} {c}")

save("mac_detection.json", {"N": args.N, "trials": args.trials, "results": out})
