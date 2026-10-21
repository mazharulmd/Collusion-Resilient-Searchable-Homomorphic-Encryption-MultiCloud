"""Per-operation costs in the reference implementation, and a lower bound on
a single server's retrieval cost.

A single server answering a retrieval must bring every entry of the N x N_d
index into contact with the encrypted query. With ell slots per ciphertext,
that is at least ceil(N * N_d / ell) plaintext-ciphertext products, before
any rotation or query expansion. Multiplying that count by the measured
product cost gives a LOWER bound on the single server's time, which is
compared with CR-SHE's measured retrieval in the same implementation
(results/flexible_path.json)."""
import json
import os

import numpy as np

from common import save, timed
from crshe import dpf, he, protocol

bfv = he.BFV()
cc = bfv.cc
rng = np.random.default_rng(0)
v = rng.integers(0, 1000, bfv.slots, dtype=np.uint64)
ct = bfv.encrypt(v)
ct2 = bfv.encrypt(v)
pt = bfv.encode(rng.integers(0, 2**36, bfv.slots, dtype=np.uint64))
reps = 51
ops = {
    "encrypt": timed(lambda: bfv.encrypt(v), reps)[0],
    "decrypt": timed(lambda: bfv.decrypt(bfv.secret_key(), ct), reps)[0],
    "mul_plain": timed(lambda: cc.EvalMult(ct, pt), reps)[0],
    "mul_ct": timed(lambda: cc.EvalMult(ct, ct2), reps)[0],
    "rotate": timed(lambda: cc.EvalRotate(ct, 1), reps)[0],
    "add": timed(lambda: cc.EvalAdd(ct, ct2), reps)[0],
    "compress": timed(lambda: he.compress(cc, ct), reps)[0],
}
for dom in (11_580, 35_162):
    ops[f"dpf_gen2_N{dom}"] = timed(lambda: dpf.gen2(dom // 2, dom), reps)[0]
N, Nd = 2048, 20_000
M = rng.integers(0, 2**36, (N, Nd), dtype=np.uint64)
e = rng.integers(0, 2**36, N, dtype=np.uint64)
t = timed(lambda: protocol.matvec_mod(e, M), 5)[0]
ops["word_muladd_ns"] = t["median_ms"] * 1e6 / (N * Nd)
ops["slot_op_ns"] = ops["mul_plain"]["median_ms"] * 1e6 / bfv.slots

flex = json.load(open(os.path.join(os.path.dirname(__file__), "..", "results", "flexible_path.json")))
bound = []
for r in flex["rows"]:
    products = -(-r["N"] * r["Nd"] // bfv.slots)
    lb = products * ops["mul_plain"]["median_ms"]
    bound.append({"N": r["N"], "Nd": r["Nd"], "products_lower_bound": products,
                  "single_server_lower_bound_ms": lb,
                  "crshe_retrieve_ms": r["retrieve"]["median_ms"],
                  "ratio_at_least": lb / r["retrieve"]["median_ms"]})
for k, val in ops.items():
    print(k, val if not isinstance(val, dict) else round(val["median_ms"], 3))
for b in bound:
    print(b)
save("ops_and_retrieval_bound.json", {"ops": ops, "retrieval_bound": bound})
