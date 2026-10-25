"""Masked index: one membership bit per Z_p word (the earlier layout) against
32 bits per word, at the primary corpus's tag domain N = 11,580.

Measured: index bytes, masked-index build time, per-provider retrieval time
and retrieval downlink, and exact retrieval against ground truth, for every
N_d both layouts fit in this machine's 16 GB. Computed (labelled): index size
of the unpacked layout at the full 405,184 records.
"""
import argparse

import numpy as np

from common import save, timed
from crshe import Owner, Provider, he
from crshe.protocol import PACK_BITS

ap = argparse.ArgumentParser()
ap.add_argument("--N", type=int, default=11_580)
ap.add_argument("--reps", type=int, default=5)
args = ap.parse_args()

bfv = he.BFV()
rows = []
for Nd, packs in ((10_000, (1, PACK_BITS)), (20_000, (1, PACK_BITS)), (100_000, (PACK_BITS,)),
                  (405_184, (PACK_BITS,))):
    rng = np.random.default_rng(Nd)
    values = rng.integers(1900, 3100, Nd)
    # heavy-tailed postings with the corpus's mean of about 315 per tag
    sizes = np.minimum(Nd, rng.zipf(1.5, args.N) * 20)
    postings = [np.sort(rng.choice(Nd, size=int(s), replace=False)) for s in sizes]
    tags = [f"tag{i:06d}" for i in range(args.N)]
    for pack in packs:
        o = Owner(tags, postings, values, {"sum": values}, n=2, bfv=bfv, seed=1, pack_bits=pack)
        t_build, _ = timed(lambda: o._masked_index(), 1)
        b = o.bundle(flexible=False)
        b.masked_index = o._masked_index()
        P = [Provider(j, b) for j in range(2)]
        u = o.user()
        x = int(np.argmax(sizes))
        keys = u.token(tags[x])
        t_ret, s0 = timed(lambda: P[0].retrieve(keys[0]), args.reps)
        S = u.finish_retrieve(tags[x], [s0, P[1].retrieve(keys[1])])
        assert np.array_equal(S, postings[x])
        row = {"Nd": Nd, "pack_bits": pack, "index_bytes": int(b.masked_index.nbytes),
               "build_masked_index": t_build, "retrieve": t_ret,
               "retrieve_downlink_bytes": int(s0.nbytes), "matched": int(len(S))}
        rows.append(row)
        print(f"Nd={Nd:>7} pack={pack:>2}: index {row['index_bytes']/1e9:6.3f} GB  "
              f"retrieve {t_ret['median_ms']:8.1f} ms  down {row['retrieve_downlink_bytes']:,d} B")
        del o, b, P

full_unpacked = args.N * 405_184 * 8
save("packed_index.json", {"N": args.N, "rows": rows,
                           "computed_unpacked_index_bytes_full_corpus": full_unpacked,
                           "note": "postings are synthetic; index size and retrieval cost depend "
                                   "only on N and N_d"})
print(f"computed: unpacked index at N_d=405,184 would be {full_unpacked/1e9:.1f} GB")
