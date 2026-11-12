"""The same range query answered four ways on one machine.

Cube: telemetry-shaped synthetic records (3 devices x 11,523 one-minute
windows x 10 value bands, 405,184 records), the dimensions of the real
telemetry cube. Cost depends on the cube's dimensions only, and every timed
answer is checked against a plaintext ground truth.

  crshe            2^d corner keys over the encrypted summed-area table
                   (combined layout), and the verified layout with its second
                   key set; each also with the keys evaluated by a pool of
                   worker processes.
  percell          no prefix sums: the table holds the cell aggregates and the
                   user sends one point key per cell of the box. Measured up
                   to --percell-max keys; beyond that the provider time is
                   computed as keys x (measured time per key) + (measured
                   contraction) and marked "computed".
  single_server    one server, no non-collusion assumption: the user encrypts
                   the signed corner vector (one ciphertext per table chunk)
                   and the server contracts ciphertext by ciphertext.

Everything is one thread unless a pool is named (OMP_NUM_THREADS=1).
"""
import argparse
import multiprocessing as mp
import time

import numpy as np

from common import save, timed

ap = argparse.ArgumentParser()
ap.add_argument("--reps", type=int, default=5)
ap.add_argument("--workers", type=int, default=4)
ap.add_argument("--percell-max", type=int, default=300, help="largest box volume measured for the per-cell baseline")
ap.add_argument("--out", default="range_baselines.json")
args = ap.parse_args()

# Fork the workers before the homomorphic context and the tables exist, so
# they stay small; they only evaluate keys.
pool = mp.get_context("fork").Pool(args.workers)

from crshe import Owner, baselines, he, rangeagg  # noqa: E402

bfv = he.BFV()
pub = bfv.public_view()
rng = np.random.default_rng(7)
DEV, MIN, BAND, ND = 3, 11_523, 10, 405_184
dims = (DEV, MIN, BAND)
cells = np.stack([rng.integers(0, DEV, ND), np.sort(rng.integers(0, MIN, ND)),
                  rng.integers(0, BAND, ND)], axis=1)
values = rng.integers(1900, 3100, ND)
tpl = {"count": np.ones(ND, dtype=np.int64), "sum": values}
owner = Owner(["t"], [np.arange(1)], values[:1], {"s": values[:1]}, n=2, bfv=bfv, seed=1)
co = rangeagg.CubeOwner(owner)
user = owner.user()


def truth(box):
    inside = np.all([(cells[:, k] >= lo) & (cells[:, k] <= hi) for k, (lo, hi) in enumerate(box)], axis=0)
    return {t: int(c[inside].sum()) for t, c in tpl.items()}


def box_for(L):
    start = 2000 if L < MIN - 2000 else 0
    return ((1, 1), (start, start + L - 1), (3, 7))


layouts = {}
for mode in ("combined", "session"):
    layouts[mode] = co.register(f"tele_{mode}", dims, cells, tpl, mode=mode)
lay_c, cts_c = layouts["combined"]
cell_cts = co._encrypt(lay_c, {t: baselines.cell_table(cells, dims, c) for t, c in tpl.items()}, None)
print(f"cube M={lay_c.M:,d}, {lay_c.chunks} ciphertexts per table")

WINDOWS = (1, 60, 1440, MIN)
rows = []
per_key_ms = contraction_ms = None
for L in WINDOWS:
    box = box_for(L)
    want = truth(box)
    row = {"window_minutes": L, "box": box, "box_cells": int(np.prod([hi - lo + 1 for lo, hi in box])),
           "truth": want}

    # ---- CR-SHE, serial and with a worker pool ------------------------------
    for mode in ("combined", "session"):
        layout, cts = layouts[mode]
        keys, meta = rangeagg.range_token(layout, box, 2)
        r1 = rangeagg.range_answer(pub, layout, cts, keys[1], compress=True)
        for label, p in (("serial", None), (f"pool{args.workers}", pool)):
            t, r0 = timed(lambda: rangeagg.range_answer(pub, layout, cts, keys[0], compress=True, pool=p), args.reps)
            assert rangeagg.finish_range(user, layout, None, meta, [r0, r1]) == want
            row[f"crshe_{mode}_{label}"] = {
                "provider": t, "keys_per_provider": len(keys[0]),
                "uplink_bytes_per_provider": sum(k.size_bytes() for k in keys[0]),
                "downlink_bytes_per_provider": he.size_bytes(r0)}
        if mode == "combined" and per_key_ms is None:
            t_keys, ev = timed(lambda: rangeagg.eval_keys(keys[0]), args.reps)
            e = rangeagg._total(ev)
            t_con, _ = timed(lambda: rangeagg.contract(pub, layout, cts, [(e, e)], True), args.reps)
            per_key_ms = t_keys["median_ms"] / len(keys[0])
            contraction_ms = t_con["median_ms"]

    # ---- per-cell keys, no prefix sums --------------------------------------
    V = row["box_cells"]
    if V <= args.percell_max:
        pk = baselines.percell_token(lay_c, box, 2)
        reps = args.reps if V <= 20 else 3
        t, r0 = timed(lambda: baselines.percell_answer(pub, lay_c, cell_cts, pk[0], compress=True), reps)
        r1 = baselines.percell_answer(pub, lay_c, cell_cts, pk[1], compress=True)
        assert rangeagg.finish_range(user, lay_c, None, [None], [r0, r1]) == want
        row["percell"] = {"provider": t, "keys_per_provider": V, "measured": True,
                          "uplink_bytes_per_provider": sum(k.size_bytes() for k in pk[0]),
                          "downlink_bytes_per_provider": he.size_bytes(r0)}
        key_bytes = pk[0][0].size_bytes()
    else:
        row["percell"] = {"provider": {"median_ms": V * per_key_ms + contraction_ms, "reps": 0},
                          "keys_per_provider": V, "measured": False,
                          "uplink_bytes_per_provider": V * key_bytes,
                          "note": "computed: keys x measured time per key + measured contraction; "
                                  "uplink is keys x measured key size"}

    # ---- single server ------------------------------------------------------
    if L in (60, MIN):
        t_q, q = timed(lambda: baselines.single_server_range_query(bfv, lay_c, box), 3)
        t_s, r = timed(lambda: baselines.single_server_range_answer(pub, lay_c, cts_c, q, compress=True), 3)
        assert rangeagg.finish_range(user, lay_c, None, [None], [r]) == want
        row["single_server"] = {"server": t_s, "client_query_encrypt": t_q, "query_ciphertexts": len(q),
                                "uplink_bytes": sum(he.size_bytes(c) for c in q),
                                "downlink_bytes": he.size_bytes(r)}
    rows.append(row)
    msg = (f"L={L:>5} cells={V:>6}: verified {row['crshe_session_serial']['provider']['median_ms']:7.1f} ms, "
           f"pool {row[f'crshe_session_pool{args.workers}']['provider']['median_ms']:7.1f} ms; "
           f"per-cell {row['percell']['provider']['median_ms']:10.1f} ms"
           f"{'' if row['percell']['measured'] else ' (computed)'}")
    if "single_server" in row:
        s = row["single_server"]
        msg += f"; single server {s['server']['median_ms']:7.1f} ms, up {s['uplink_bytes']:,d} B"
    print(msg, flush=True)

pool.close()
save(args.out, {"corpus": "synthetic, telemetry-shaped (3 x 11,523 x 10 cells, 405,184 records)",
                "M": lay_c.M, "chunks": lay_c.chunks, "workers": args.workers,
                "per_key_eval_ms": per_key_ms, "contraction_ms": contraction_ms,
                "rows": rows,
                "note": "pool rows evaluate the DPF keys in worker processes; the homomorphic "
                        "contraction stays on one thread. percell rows with measured=false are computed."})
