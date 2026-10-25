"""What each verification mode catches, on every query path. Counts only.

Modes
  global    one owner MAC key delta in row 1 (fast, flexible, combined range)
  row       per-row keys delta_x (fast path) / per-cell keys (per-corner range)
  session   row 1 is a copy; the user's second key set carries a fresh secret
            delta_s per query (all paths)

Deviations by provider 1 (provider 0 honest), each in BOTH rows unless noted:
  inconsistent  random constant added to the value slot only
  dense         share + d, d uniform
  scale         k * share
  random_point  share + c * u_x, x uniform
  hidden_point  share + c * u_x with x the point the query reads: an attacker
                that knows the query, which bounds every deviation aimed at it
Counts are detected / undetected-and-wrong / undetected-and-correct.
"""
import argparse

import numpy as np

from common import save, tag_domain_deployment
from crshe import Owner, Provider, VerificationError, dpf, field, he, rangeagg

ap = argparse.ArgumentParser()
ap.add_argument("--N", type=int, default=11_580)
ap.add_argument("--trials", type=int, default=200)
ap.add_argument("--paths", nargs="+", default=["fast", "flexible", "range", "retrieval"])
args = ap.parse_args()

rng = np.random.default_rng(2027)
bfv = he.BFV()
pub = bfv.public_view()
KINDS = ("inconsistent", "dense", "scale", "random_point", "hidden_point")


def deviate(kind, e, point):
    n = len(e)
    if kind == "dense":
        d = rng.integers(0, field.P, n, dtype=np.uint64)
        return lambda v: field.add(v, d)
    if kind == "scale":
        k = np.uint64(int(rng.integers(2, field.P)))
        return lambda v: field.mul(v, k)
    if kind in ("random_point", "hidden_point"):
        x = point if kind == "hidden_point" else int(rng.integers(0, n))
        d = np.zeros(n, dtype=np.uint64)
        d[x] = int(rng.integers(1, field.P))
        return lambda v: field.add(v, d)
    return lambda v: v


def bump(ct):
    b = np.zeros(bfv.slots, dtype=np.uint64)
    b[0] = int(rng.integers(1, field.P))
    return bfv.cc.EvalAdd(ct, bfv.encrypt(b))


def tally():
    return {"detected": 0, "undetected_wrong": 0, "undetected_correct": 0}


def record(c, fn, truth):
    try:
        c["undetected_correct" if fn() == truth else "undetected_wrong"] += 1
    except VerificationError:
        c["detected"] += 1


import json, os
prev = os.path.join(os.path.dirname(__file__), "..", "results", "verification_modes.json")
out = json.load(open(prev))["results"] if os.path.exists(prev) and set(args.paths) != {"fast", "flexible", "range", "retrieval"} else {}
for pth in args.paths:
    out[pth] = {}

# ---- fast path ---------------------------------------------------------------
o, tags, postings, values = tag_domain_deployment(args.N, bfv=bfv, templates=("sum",))
lays = {m: o.fast_layout(["sum"], mac=m) for m in ("global", "row", "session")}
b = o.bundle(layouts=list(lays.items()))
P = [Provider(j, b) for j in range(2)]
u = o.user()
nonempty = [t for t, p in zip(tags, postings) if len(p)]
for mac, L in (lays.items() if "fast" in args.paths else ()):
    out["fast"][mac] = {}
    for kind in KINDS:
        c = tally()
        for _ in range(args.trials):
            tag = nonempty[int(rng.integers(0, len(nonempty)))]
            truth = int(values[postings[tags.index(tag)]].sum())
            if mac == "session":
                keys, hats, ds = u.token_session(tag)
            else:
                keys, hats, ds = u.token(tag), [None, None], None
            f = deviate(kind, None if kind == "inconsistent" else np.zeros(o.N), o.D[tag]) \
                if kind != "inconsistent" else (lambda v: v)
            r0 = P[0].fast(keys[0], mac, key_hat=hats[0])
            e1 = f(keys[1].eval_full())
            eh1 = f(hats[1].eval_full()) if mac == "session" else None
            r1 = P[1].fast(keys[1], mac, e=e1, ehat=eh1)
            if kind == "inconsistent":
                r1 = bump(r1)
            record(c, lambda: u.finish_fast(tag, L, [r0, r1], delta_s=ds)["sum"], truth)
        out["fast"][mac][kind] = c
        print(f"fast     {mac:8s} {kind:13s} {c}")

# ---- flexible round two ------------------------------------------------------
Nd = 4096
vals = rng.integers(1900, 3100, Nd)
of = Owner(["t"], [np.arange(3)], vals, {"sum": vals}, n=2, bfv=bfv, seed=4)
bundles = {m: of.bundle(flexible=True, record_mac=m) for m in ("global", "session")}
uf = of.user()
for mac, bb in (bundles.items() if "flexible" in args.paths else ()):
    Pf = [Provider(j, bb) for j in range(2)]
    out["flexible"][mac] = {}
    for kind in KINDS:
        c = tally()
        for _ in range(args.trials):
            sel = np.flatnonzero(rng.random(Nd) < 0.1)
            truth = int(vals[sel].sum())
            if mac == "session":
                sh, hats, ds = uf.deal_selection(sel, session=True)
            else:
                sh, hats, ds = uf.deal_selection(sel), [None, None], None
            f = deviate(kind, np.zeros(Nd), int(sel[0])) if kind != "inconsistent" else (lambda v: v)
            r0 = Pf[0].contract(sh[0], hat_key=hats[0])
            k1 = dpf.VectorKey(1, f(sh[1].eval_full()), Nd)
            h1 = dpf.VectorKey(1, f(hats[1].eval_full()), Nd) if mac == "session" else None
            r1 = Pf[1].contract(k1, hat_key=h1)
            if kind == "inconsistent":
                r1 = bump(r1)
            record(c, lambda: uf.finish_contract([r0, r1], delta_s=ds), truth)
        out["flexible"][mac][kind] = c
        print(f"flexible {mac:8s} {kind:13s} {c}")

# ---- range (d = 3) -----------------------------------------------------------
dims, nd = (3, 200, 10), 20_000
cells = np.stack([rng.integers(0, s, nd) for s in dims], axis=1)
rv = rng.integers(1900, 3100, nd)
oc = Owner(["t"], [np.arange(3)], rv, {"sum": rv}, n=2, bfv=bfv, seed=5)
co = rangeagg.CubeOwner(oc)
uc = oc.user()
cubes = {m: co.register(f"c_{m}", dims, cells, {"sum": rv}, mode=m, cube_id=20 + i)
         for i, m in enumerate(("per_corner", "combined", "session"))}
for mode, (lay, cts) in (cubes.items() if "range" in args.paths else ()):
    secret = co.client_secret(f"c_{mode}")
    out["range"][mode] = {}
    for kind in KINDS:
        c = tally()
        for _ in range(args.trials):
            box = []
            for s in dims:
                lo, hi = sorted(rng.integers(1, s, 2))
                box.append((int(lo), int(hi)))
            inside = np.all([(cells[:, k] >= lo) & (cells[:, k] <= hi) for k, (lo, hi) in enumerate(box)], axis=0)
            truth = {"sum": int(rv[inside].sum())}
            keys, meta = rangeagg.range_token(lay, box, 2)
            corner0 = meta[0][3]                     # the (hi, ..., hi) corner, always real here
            f = deviate(kind, np.zeros(lay.M), corner0) if kind != "inconsistent" else (lambda v: v)
            dev = list(keys[1])
            dev[0] = dpf.VectorKey(1, f(dev[0].eval_full()), lay.M)
            if mode == "session":
                dev[lay.corners] = dpf.VectorKey(1, f(dev[lay.corners].eval_full()), lay.M)
            r0 = rangeagg.range_answer(pub, lay, cts, keys[0])
            r1 = rangeagg.range_answer(pub, lay, cts, dev)
            if kind == "inconsistent":
                r1 = bump(r1)
            record(c, lambda: rangeagg.finish_range(uc, lay, secret, meta, [r0, r1]), truth)
        out["range"][mode][kind] = c
        print(f"range    {mode:10s} {kind:13s} {c}")

# ---- retrieval (masked index, packed) ---------------------------------------
# Unchecked retrieval relies only on the 4-bit width check; the session check
# compares delta_s * b with the second share word by word.
if "retrieval" in args.paths:
    Nr = 512
    ndr = 4096
    rv2 = rng.integers(1, 100, ndr)
    post_r = [np.sort(rng.choice(ndr, size=int(rng.integers(1, 300)), replace=False)) for _ in range(Nr)]
    orr = Owner([f"r{i}" for i in range(Nr)], post_r, rv2, {"sum": rv2}, n=2, bfv=bfv, seed=6,
                build_masked_index=True)
    br = orr.bundle(flexible=True)
    Pr = [Provider(j, br) for j in range(2)]
    ur = orr.user()
    for mac in ("width_only", "session"):
        out["retrieval"][mac] = {}
        for kind in ("inconsistent", "dense", "scale", "random_point", "hidden_point"):
            c = tally()
            for _ in range(args.trials):
                x = int(rng.integers(0, Nr))
                tag = f"r{x}"
                truth = post_r[x]
                if mac == "session":
                    keys, hats, ds = ur.token_session(tag)
                else:
                    keys, hats, ds = ur.token(tag), [None, None], None
                f = deviate(kind, np.zeros(Nr), x) if kind not in ("inconsistent",) else (lambda v: v)
                s0 = Pr[0].retrieve(keys[0], key_hat=hats[0])
                k1 = dpf.VectorKey(1, f(keys[1].eval_full()), Nr)
                if mac == "session":
                    h1 = dpf.VectorKey(1, f(hats[1].eval_full()), Nr)
                    b1, bh1 = Pr[1].retrieve(k1, key_hat=h1)
                    if kind == "inconsistent":          # flip one membership bit in the value share only
                        b1 = b1.copy(); b1[0] = (int(b1[0]) + 1) % field.P
                    s1 = (b1, bh1)
                else:
                    s1 = Pr[1].retrieve(k1)
                    if kind == "inconsistent":
                        s1 = s1.copy(); s1[0] = (int(s1[0]) + 1) % field.P
                def fin():
                    got = ur.finish_retrieve(tag, [s0, s1], delta_s=ds)
                    return tuple(got.tolist())
                record(c, fin, tuple(truth.tolist()))
            out["retrieval"][mac][kind] = c
            print(f"retrieve {mac:10s} {kind:13s} {c}")

save("verification_modes.json", {"N_fast": args.N, "Nd_flexible": Nd, "cube": dims,
                                 "trials": args.trials, "results": out})
