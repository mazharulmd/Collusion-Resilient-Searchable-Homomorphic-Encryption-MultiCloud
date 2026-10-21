"""Correctness battery of Section 10.1 on a subsample of a real corpus (or the
synthetic one): every template on the fast path for n in {2,3,4}, retrieval,
the flexible path with ad-hoc weights, MAC verification, and byte-identical
responses for the emptiest and fullest posting lists."""
import argparse

import numpy as np

from common import save
from crshe import Owner, Provider, corpus, he

ap = argparse.ArgumentParser()
ap.add_argument("--corpus", choices=["telemetry", "beijing", "synthetic"], default="synthetic")
ap.add_argument("--nd", type=int, default=5000)
ap.add_argument("--tags", type=int, default=200, help="random tags checked per n")
args = ap.parse_args()

full = {"telemetry": corpus.load_telemetry, "beijing": corpus.load_beijing,
        "synthetic": lambda: corpus.synthetic(N=2000, Nd=args.nd)}[args.corpus]()
c = full.subsample(args.nd)
vals = c.values
w = (np.arange(c.Nd) % 5) + 1
templates = {"count": np.ones(c.Nd, dtype=np.int64), "sum": vals, "weighted": w * vals,
             "sumsq_coarse": (vals // 100) ** 2}
rng = np.random.default_rng(0)
bfv = he.BFV()
report = {"corpus": c.summary(), "checks": {}}
for n in (2, 3, 4):
    o = Owner(c.tags, c.postings, vals, templates, n=n, bfv=bfv, seed=n, build_masked_index=True)
    L = o.fast_layout(list(templates))
    b = o.bundle(layouts=[("all", L)], flexible=True)
    P = [Provider(j, b) for j in range(n)]
    u = o.user()
    picks = rng.choice(c.N, size=min(args.tags, c.N), replace=False)
    ok_fast = ok_ret = ok_flex = 0
    for x in picks:
        tag, post = c.tags[x], c.postings[x]
        keys = u.token(tag)
        got = u.finish_fast(tag, L, [p.fast(k, "all", compress=True) for p, k in zip(P, keys)])
        ok_fast += got == {k: int(t[post].sum()) for k, t in templates.items()}
        S = u.finish_retrieve(tag, [p.retrieve(k) for p, k in zip(P, keys)])
        ok_ret += np.array_equal(S, post)
        adhoc = rng.integers(0, 10, c.Nd)
        y = u.finish_contract([p.contract(k, compress=True) for p, k in zip(P, u.deal_selection(S, weights=adhoc))])
        ok_flex += y == int((adhoc * vals)[S].sum())
    lens = c.lengths()
    sizes = {he.size_bytes(P[0].fast(u.token(c.tags[x])[0], "all", compress=True))
             for x in (int(lens.argmin()), int(lens.argmax()))}
    report["checks"][f"n={n}"] = {"tags": len(picks), "fast_ok": ok_fast, "retrieve_ok": ok_ret,
                                  "flexible_ok": ok_flex, "response_sizes_min_max_posting": sorted(sizes)}
    print(n, report["checks"][f"n={n}"])
    assert ok_fast == ok_ret == ok_flex == len(picks) and len(sizes) == 1
save(f"correctness_{args.corpus}.json", report)
