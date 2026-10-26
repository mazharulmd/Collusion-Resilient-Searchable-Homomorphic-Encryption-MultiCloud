"""Range aggregation on the REAL corpora (requires data/raw/, see data/README.md).

telemetry  device x one-minute window x CO decile band, aggregating temperature
beijing    site x day (or hour) x PM2.5 decile band (+ missing), aggregating
           temperature

For each layout: per-provider cost against window length, a box at the cube's
origin (dummy corners), user-side cost, sizes, every answer checked against the
plaintext ground truth on the real records; then tamper trials on the real
cube (one provider deviates, five deviation kinds), as in bench_verify.py.
"""
import argparse
import sys
import time

import numpy as np

from common import save, timed
from crshe import Owner, VerificationError, corpus, dpf, field, he, rangeagg

ap = argparse.ArgumentParser()
ap.add_argument("--corpus", choices=["telemetry", "beijing"], required=True)
ap.add_argument("--time", choices=["day", "hour"], default="day", help="beijing time axis")
ap.add_argument("--modes", nargs="+", default=["combined", "session"])
ap.add_argument("--reps", type=int, default=5)
ap.add_argument("--trials", type=int, default=50, help="tamper trials per deviation and layout")
args = ap.parse_args()

try:
    c = corpus.cube_telemetry() if args.corpus == "telemetry" else corpus.cube_beijing(time=args.time)
except (FileNotFoundError, OSError) as exc:
    sys.exit(f"corpus not available: {exc}  (see data/README.md)")
print(f"{c.name}: dims {c.dims}  M={c.M:,}  records={len(c.values):,}")

bfv = he.BFV()
pub = bfv.public_view()
owner = Owner(["t"], [np.arange(1)], c.values[:1], {"s": c.values[:1]}, n=2, bfv=bfv, seed=1)
co = rangeagg.CubeOwner(owner)
user = owner.user()
tpl = {"count": np.ones(len(c.values), dtype=np.int64), "sum": c.values}
T = c.dims[1]
windows = {"telemetry": [1, 60, 240, 1440, T], "beijing": ([1, 7, 30, 365, T] if args.time == "day"
                                                            else [1, 24, 168, 720, T])}[args.corpus]
windows = sorted({min(L, T) for L in windows})
unit = "minutes" if args.corpus == "telemetry" else args.time + "s"


def truth(box):
    return {t: c.truth(box, v) for t, v in tpl.items()}


def run_query(layout, cts, secret, box):
    keys, meta = rangeagg.range_token(layout, box, 2)
    t_tok, _ = timed(lambda: rangeagg.range_token(layout, box, 2), args.reps)
    t_dpf, _ = timed(lambda: [k.eval_full() for k in keys[0]], args.reps)
    t_all, r0 = timed(lambda: rangeagg.range_answer(pub, layout, cts, keys[0], compress=True), args.reps)
    r1 = rangeagg.range_answer(pub, layout, cts, keys[1], compress=True)
    t_fin, got = timed(lambda: rangeagg.finish_range(user, layout, secret, meta, [r0, r1]), args.reps)
    assert got == truth(box), (box, got, truth(box))
    return {"box": box, "token": t_tok, "dpf_eval_all_keys": t_dpf, "provider_total": t_all,
            "user_finish": t_fin, "downlink_bytes": he.size_bytes(r0),
            "uplink_bytes_per_provider": sum(k.size_bytes() for k in keys[0]),
            "keys_per_provider": len(keys[0]), "result": got}


def tamper(layout, cts, secret, rng):
    kinds = ("inconsistent", "dense", "scale", "random_point", "hidden_point")
    out = {}
    for kind in kinds:
        cnt = {"detected": 0, "undetected_wrong": 0, "undetected_correct": 0}
        for _ in range(args.trials):
            box = []
            for s in c.dims:
                lo, hi = sorted(rng.integers(1, s, 2)) if s > 1 else (0, 0)
                box.append((int(lo), int(hi)))
            box = tuple(box)
            keys, meta = rangeagg.range_token(layout, box, 2)
            want = truth(box)
            n = layout.M
            d = np.zeros(n, dtype=np.uint64)
            if kind == "dense":
                d = rng.integers(0, field.P, n, dtype=np.uint64)
            elif kind in ("random_point", "hidden_point"):
                x = meta[0][3] if kind == "hidden_point" else int(rng.integers(0, n))
                d[x] = int(rng.integers(1, field.P))
            k = np.uint64(int(rng.integers(2, field.P)))

            def f(v):
                return field.mul(v, k) if kind == "scale" else field.add(v, d)

            dev = list(keys[1])
            if kind != "inconsistent":
                dev[0] = dpf.VectorKey(1, f(dev[0].eval_full()), n)
                if layout.mode == "session":
                    dev[layout.corners] = dpf.VectorKey(1, f(dev[layout.corners].eval_full()), n)
            r0 = rangeagg.range_answer(pub, layout, cts, keys[0])
            r1 = rangeagg.range_answer(pub, layout, cts, dev)
            if kind == "inconsistent":
                bump = np.zeros(bfv.slots, dtype=np.uint64)
                bump[0] = int(rng.integers(1, field.P))
                r1 = bfv.cc.EvalAdd(r1, bfv.encrypt(bump))
            try:
                got = rangeagg.finish_range(user, layout, secret, meta, [r0, r1])
                cnt["undetected_correct" if got == want else "undetected_wrong"] += 1
            except VerificationError:
                cnt["detected"] += 1
        out[kind] = cnt
        print(f"  tamper {layout.mode:9s} {kind:13s} {cnt}")
    return out


rng = np.random.default_rng(11)
rows = {}
for i, mode in enumerate(args.modes):
    t0 = time.perf_counter()
    layout, cts = co.register(f"{c.name}_{mode}", c.dims, c.cells, tpl, mode=mode, cube_id=40 + i)
    setup_s = time.perf_counter() - t0
    secret = co.client_secret(f"{c.name}_{mode}")
    res = []
    for L in windows:
        start = min(T // 3, T - L)
        box = ((1 % c.dims[0], 1 % c.dims[0]), (start, start + L - 1), (3, 7))
        r = run_query(layout, cts, secret, box)
        r["window"] = L
        res.append(r)
        print(f"{mode:9s} L={L:>6} {unit}: dpf {r['dpf_eval_all_keys']['median_ms']:9.1f} ms  "
              f"provider {r['provider_total']['median_ms']:9.1f} ms  up {r['uplink_bytes_per_provider']:,d} B  "
              f"down {r['downlink_bytes']:,d} B")
    edge = run_query(layout, cts, secret, ((0, 0), (0, min(T, windows[2]) - 1), (0, 4)))
    rows[mode] = {"M": layout.M, "chunks": layout.chunks, "setup_s": setup_s, "column_ciphertexts": len(cts),
                  "by_window": res, "edge_box": edge,
                  "tamper": tamper(layout, cts, secret, rng) if args.trials else None}

fresh = he.size_bytes(bfv.encrypt(np.zeros(8, dtype=np.uint64)))
first = rows[args.modes[0]]
save(f"range_real_{args.corpus}{'_' + args.time if args.corpus == 'beijing' else ''}.json",
     {"corpus": c.name, "dims": c.dims, "axes": c.axes, "records": int(len(c.values)), "window_unit": unit,
      "modes": rows, "single_server_uplink_bytes_computed": first["chunks"] * fresh,
      "note": "single-server uplink computed as chunks x fresh-ciphertext size, not measured"})
