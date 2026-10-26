"""Data user of a multi-machine deployment: send queries to every provider in
parallel, measure end-to-end latency, provider compute, transport and client
cost, check every answer against the ground truth, and write
results/deploy_<label>.json.

    python scripts/deploy/client_bench.py --client deploy_bundle/client \
        --providers 10.0.1.5:9101 10.0.2.7:9101 --label us-east_eu-west --queries 50
"""
import argparse
import json
import os
import platform
import statistics
import sys
import threading
import time

import numpy as np
import openfhe as fhe

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [ROOT, os.path.join(ROOT, "bench")]
from common import save  # noqa: E402
from crshe import dpf, field, rangeagg, wire  # noqa: E402
from crshe.protocol import fresh_unit  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--client", required=True)
ap.add_argument("--providers", nargs="+", required=True, help="host:port of every provider, in order")
ap.add_argument("--label", required=True)
ap.add_argument("--queries", type=int, default=50)
ap.add_argument("--range-queries", type=int, default=20)
args = ap.parse_args()

C = args.client
meta = json.load(open(os.path.join(C, "meta.json")))
n = meta["n"]
if len(args.providers) != n:
    sys.exit(f"the bundle was built for n={n} providers, got {len(args.providers)} addresses")
cc, _ = fhe.DeserializeCryptoContext(os.path.join(C, "cc.bin"), fhe.BINARY)
sk, _ = fhe.DeserializePrivateKey(os.path.join(C, "sk.bin"), fhe.BINARY)
truth = np.load(os.path.join(C, "truth.npz"))
H = meta["half"]
socks = [wire.connect(a) for a in args.providers]


def rtt(s):
    t = time.perf_counter()
    wire.send_msg(s, {"op": "ping"})
    wire.recv_msg(s)
    return 1e3 * (time.perf_counter() - t)


ping = {a: statistics.median(rtt(s) for _ in range(20)) for a, s in zip(args.providers, socks)}
print("median RTT (ms):", {a: round(v, 2) for a, v in ping.items()})


def ask(op, per_provider_keys):
    """Send provider j its keys, all in parallel; return responses and timings."""
    res = [None] * n

    def one(j):
        meta_k, blobs = wire.keys_to_wire(per_provider_keys[j])
        t = time.perf_counter()
        wire.send_msg(socks[j], {"op": op, "k": meta_k}, blobs)
        h, b = wire.recv_msg(socks[j])
        wall = 1e3 * (time.perf_counter() - t)
        if not h.get("ok"):
            raise RuntimeError(h)
        res[j] = (fhe.DeserializeCiphertextString(b[0], fhe.BINARY), h["compute_ms"], wall,
                  sum(len(x) for x in blobs), len(b[0]))

    t0 = time.perf_counter()
    th = [threading.Thread(target=one, args=(j,)) for j in range(n)]
    for x in th:
        x.start()
    for x in th:
        x.join()
    return res, 1e3 * (time.perf_counter() - t0)


def decrypt_sum(cts):
    acc = cts[0]
    for c in cts[1:]:
        acc = cc.EvalAdd(acc, c)
    pt = cc.Decrypt(sk, acc)
    pt.SetLength(meta["slots"])
    return np.array(pt.GetPackedValue(), dtype=np.int64) % field.P


class RangeUser:
    """What rangeagg.finish_range needs from a data user."""
    bfv = type("Half", (), {"half": H})

    def _combine(self, cts):
        return decrypt_sum(cts)


def summarise(rows):
    keys = rows[0].keys()
    return {k: {"median": statistics.median(r[k] for r in rows), "min": min(r[k] for r in rows),
                "max": max(r[k] for r in rows)} for k in keys if isinstance(rows[0][k], (int, float))}


rng = np.random.default_rng(3)
fast_rows, ok = [], 0
N, seg = meta["N"], meta["fast"]["seg"]
for q in range(args.queries):
    a = int(rng.integers(0, N))
    t = time.perf_counter()
    ds = fresh_unit()
    k1, k2 = dpf.gen(a, N, n), dpf.gen(a, N, n, beta=ds)
    t_tok = 1e3 * (time.perf_counter() - t)
    res, e2e_send = ask("fast", [[k1[j], k2[j]] for j in range(n)])
    t = time.perf_counter()
    slots = decrypt_sum([r[0] for r in res])
    good = True
    for r, name in enumerate(meta["fast"]["templates"]):
        y, yh = int(slots[r * seg]), int(slots[H + r * seg])
        good &= yh == y * ds % field.P and y == int(truth[f"A_{name}"][a])
    t_fin = 1e3 * (time.perf_counter() - t)
    ok += good
    fast_rows.append({"end_to_end_ms": t_tok + e2e_send + t_fin, "token_ms": t_tok, "client_finish_ms": t_fin,
                      "max_provider_compute_ms": max(r[1] for r in res),
                      "max_provider_wall_ms": max(r[2] for r in res),
                      "transport_ms": max(r[2] - r[1] for r in res),
                      "uplink_bytes_per_provider": res[0][3], "downlink_bytes_per_provider": res[0][4]})
print(f"fast path: {ok}/{args.queries} correct; median end-to-end "
      f"{statistics.median(r['end_to_end_ms'] for r in fast_rows):.1f} ms")
out = {"label": args.label, "providers": args.providers, "client_host": platform.node(), "n": n,
       "rtt_ms": ping, "fast": {"queries": args.queries, "correct": ok, "summary": summarise(fast_rows),
                                "rows": fast_rows}}

if "cube" in meta and args.range_queries:
    cm = meta["cube"]
    lay = rangeagg.CubeLayout(cm["name"], tuple(cm["dims"]), cm["templates"], cm["mode"], cm["seg"], cm["chunks"])
    cells, cv = truth["cube_cells"], truth["cube_values"]
    rows, okr = [], 0
    for q in range(args.range_queries):
        box = tuple(tuple(sorted(int(v) for v in rng.integers(0, s, 2))) for s in lay.dims)
        t = time.perf_counter()
        keys, mt = rangeagg.range_token(lay, box, n)
        t_tok = 1e3 * (time.perf_counter() - t)
        res, e2e_send = ask("range", keys)
        t = time.perf_counter()
        got = rangeagg.finish_range(RangeUser(), lay, None, mt, [r[0] for r in res])
        t_fin = 1e3 * (time.perf_counter() - t)
        inside = np.all([(cells[:, k] >= lo) & (cells[:, k] <= hi) for k, (lo, hi) in enumerate(box)], axis=0)
        good = got == {"count": int(inside.sum()), "sum": int(cv[inside].sum())}
        okr += good
        rows.append({"end_to_end_ms": t_tok + e2e_send + t_fin, "token_ms": t_tok, "client_finish_ms": t_fin,
                     "max_provider_compute_ms": max(r[1] for r in res),
                     "max_provider_wall_ms": max(r[2] for r in res),
                     "transport_ms": max(r[2] - r[1] for r in res),
                     "uplink_bytes_per_provider": res[0][3], "downlink_bytes_per_provider": res[0][4]})
    print(f"range: {okr}/{args.range_queries} correct; median end-to-end "
          f"{statistics.median(r['end_to_end_ms'] for r in rows):.1f} ms")
    out["range"] = {"queries": args.range_queries, "correct": okr, "cube": cm, "summary": summarise(rows),
                    "rows": rows}

for s in socks:
    s.close()
save(f"deploy_{args.label}.json", out)
