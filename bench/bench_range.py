"""Oblivious range aggregation: cost against window length and cube size, and
against the alternatives for the same query.

Corpus: telemetry-shaped synthetic records (3 devices, 11,523 one-minute
windows, 10 value bands, 405,184 records), because the real corpora could not
be downloaded here. The cost of a range query depends only on the cube's
dimensions, not on record values, so the latencies carry over; the
correctness checks compare against a plaintext ground truth on these records.

Measured, per provider: full-domain DPF evaluation of the 2^d corner keys and
the homomorphic contraction, separately; downlink; user-side cost. Computed
(and labelled so): the uplink of a single server answering the same query
with encrypted one-hot corner vectors, from the measured size of a fresh
ciphertext.
"""
import argparse
import time

import numpy as np

from common import save, timed
from crshe import Owner, dpf, field, he, rangeagg

ap = argparse.ArgumentParser()
ap.add_argument("--reps", type=int, default=5)
args = ap.parse_args()

bfv = he.BFV()
pub = bfv.public_view()
rng = np.random.default_rng(7)
DEV, MIN, BAND, ND = 3, 11_523, 10, 405_184
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


def run_query(layout, cts, secret, box, reps):
    keys, meta = rangeagg.range_token(layout, box, 2)
    t_tok, _ = timed(lambda: rangeagg.range_token(layout, box, 2), reps)
    t_dpf, _ = timed(lambda: [k.eval_full() for k in keys[0]], reps)
    t_all, r0 = timed(lambda: rangeagg.range_answer(pub, layout, cts, keys[0], compress=True), reps)
    r1 = rangeagg.range_answer(pub, layout, cts, keys[1], compress=True)
    t_fin, got = timed(lambda: rangeagg.finish_range(user, layout, secret, meta, [r0, r1]), reps)
    assert got == truth(box), (box, got, truth(box))
    return {"box": box, "token": t_tok, "dpf_eval_all_corners": t_dpf, "provider_total": t_all,
            "user_finish": t_fin, "downlink_bytes": he.size_bytes(r0),
            "uplink_bytes_per_provider": sum(k.size_bytes() for k in keys[0]),
            "keys_per_provider": len(keys[0]), "result": got}


rows = {}
for mode in ("per_corner", "combined"):
    t0 = time.perf_counter()
    layout, cts = co.register(f"tele_{mode}", (DEV, MIN, BAND), cells, tpl, mode=mode)
    setup_s = time.perf_counter() - t0
    secret = co.client_secret(f"tele_{mode}")
    res = []
    for L in (1, 60, 240, 1440, MIN):
        start = 2000 if L < MIN - 2000 else 0
        box = ((1, 1), (start, start + L - 1), (3, 7))
        r = run_query(layout, cts, secret, box, args.reps)
        r["window_minutes"] = L
        res.append(r)
        print(f"{mode:10s} L={L:>5}: dpf {r['dpf_eval_all_corners']['median_ms']:7.1f} ms  "
              f"provider {r['provider_total']['median_ms']:7.1f} ms  down {r['downlink_bytes']:,d} B  "
              f"up {r['uplink_bytes_per_provider']:,d} B")
    # a box on the cube's edge (dummy corners) costs the same
    edge = run_query(layout, cts, secret, ((0, 0), (0, 239), (0, 4)), args.reps)
    rows[mode] = {"M": layout.M, "chunks": layout.chunks, "segments_per_template":
                  layout.corners if mode == "per_corner" else 1, "setup_s": setup_s,
                  "column_ciphertexts": len(cts), "by_window": res, "edge_box": edge}

# ---- cube-size scaling (d = 2, combined) --------------------------------------
scale = []
for side in (100, 316, 1000):
    dims = (side, side)
    c2 = np.stack([rng.integers(0, side, 50_000), rng.integers(0, side, 50_000)], axis=1)
    v2 = rng.integers(1, 100, 50_000)
    lay, cts2 = co.register(f"sq{side}", dims, c2, {"sum": v2}, mode="combined", cube_id=10 + side)
    box = ((side // 4, side // 2), (side // 5, side // 3))
    keys, meta = rangeagg.range_token(lay, box, 2)
    t_dpf, _ = timed(lambda: [k.eval_full() for k in keys[0]], 3)
    t_all, r0 = timed(lambda: rangeagg.range_answer(pub, lay, cts2, keys[0], compress=True), 3)
    r1 = rangeagg.range_answer(pub, lay, cts2, keys[1], compress=True)
    got = rangeagg.finish_range(user, lay, None, meta, [r0, r1])["sum"]
    inside = (c2[:, 0] >= box[0][0]) & (c2[:, 0] <= box[0][1]) & (c2[:, 1] >= box[1][0]) & (c2[:, 1] <= box[1][1])
    assert got == int(v2[inside].sum())
    scale.append({"M": lay.M, "dpf_eval_all_corners": t_dpf, "provider_total": t_all,
                  "chunks": lay.chunks, "downlink_bytes": he.size_bytes(r0)})
    print(f"M={lay.M:>8,d}: dpf {t_dpf['median_ms']:7.1f} ms  provider {t_all['median_ms']:7.1f} ms")

# ---- what the alternatives would need for the same query ----------------------
# Fresh-ciphertext size measured here; a single server answering the combined
# query needs one encrypted signed-corner vector of `chunks` ciphertexts.
fresh = he.size_bytes(bfv.encrypt(np.zeros(8, dtype=np.uint64)))
comb = rows["combined"]
alt = {"fresh_ciphertext_bytes": fresh,
       "single_server_uplink_bytes_computed": comb["chunks"] * fresh,
       "crshe_uplink_bytes": comb["by_window"][0]["uplink_bytes_per_provider"],
       "note": "single-server uplink is computed as chunks x fresh-ciphertext size, not measured"}
print("single-server uplink (computed):", f"{alt['single_server_uplink_bytes_computed']:,d} B",
      "vs CR-SHE", f"{alt['crshe_uplink_bytes']:,d} B")

save("range_aggregation.json", {"corpus": "synthetic, telemetry-shaped (3 x 11,523 x 10 cells, 405,184 records)",
                                "modes": rows, "cube_scaling": scale, "alternatives": alt})
