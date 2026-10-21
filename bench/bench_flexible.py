"""Retrieval and the two-round flexible path, against N_d.

Round 1 (retrieval) is the Theta(N N_d) contraction over the masked index;
round 2 contracts fresh additive shares of the user's selection vector
against the record column, O(N_d / H) plaintext-ciphertext products plus
log2(H) rotations, and returns one ciphertext. Uplink of round 2 is one
16-byte seed per light provider and 8 N_d bytes for the heavy one.
"""
import argparse

import numpy as np

from common import save, timed
from crshe import Owner, Provider, he

ap = argparse.ArgumentParser()
ap.add_argument("--N", type=int, default=11_580)
ap.add_argument("--nd", type=int, nargs="+", default=[1_000, 5_000, 10_000, 20_000])
ap.add_argument("--reps", type=int, default=5)
args = ap.parse_args()

bfv = he.BFV()
rows = []
for Nd in args.nd:
    rng = np.random.default_rng(Nd)
    values = rng.integers(1900, 3100, Nd)
    postings = [rng.choice(Nd, size=int(min(Nd, rng.zipf(1.4))), replace=False) for _ in range(args.N)]
    tags = [f"tag{i:07d}" for i in range(args.N)]
    o = Owner(tags, postings, values, {"sum": values}, n=2, bfv=bfv, seed=1)
    t_build, _ = timed(lambda: o._masked_index(), 1)
    b = o.bundle(flexible=True)
    P = [Provider(j, b) for j in range(2)]
    u = o.user()
    tag = max(tags, key=lambda t: len(postings[tags.index(t)]))
    keys = u.token(tag)
    t_ret, bj = timed(lambda: P[0].retrieve(keys[0]), args.reps)
    shares = [P[0].retrieve(keys[0]), P[1].retrieve(keys[1])]
    S = u.finish_retrieve(tag, shares)
    assert sorted(S) == sorted(postings[tags.index(tag)])
    w = (np.arange(Nd) % 7)
    sk = u.deal_selection(S, weights=w)
    t_deal, _ = timed(lambda: u.deal_selection(S, weights=w), args.reps)
    t_con, r = timed(lambda: P[1].contract(sk[1]), args.reps)
    t_conc, rc = timed(lambda: P[1].contract(sk[1], compress=True), args.reps)
    y = u.finish_contract([P[0].contract(sk[0], compress=True), rc])
    assert y == int((w * values)[S].sum())
    row = {"Nd": Nd, "N": args.N, "masked_index_bytes": int(b.masked_index.nbytes),
           "build_masked_index": t_build, "retrieve": t_ret, "deal_shares": t_deal,
           "contract": t_con, "contract_compressed": t_conc,
           "retrieve_downlink_bytes": int(len(bj) * 8),
           "round2_uplink_bytes": [k.size_bytes() for k in sk],
           "round2_downlink_bytes": he.size_bytes(r), "round2_downlink_bytes_compressed": he.size_bytes(rc),
           "record_ciphertexts": len(b.records), "matched": int(len(S))}
    rows.append(row)
    print(f"Nd={Nd:>6}: retrieve {t_ret['median_ms']:8.1f} ms  contract {t_con['median_ms']:6.1f} ms  "
          f"index {row['masked_index_bytes']/1e9:.2f} GB  up2 {row['round2_uplink_bytes']}")
    del o, b, P

save("flexible_path.json", {"rows": rows})
