"""Fast-path response: the submitted two-ciphertext layout against the
row-packed single ciphertext, compression, and several templates per
response; and the single-server encrypted-selection baseline.

Downlink and uplink are byte counts and do not depend on the machine.
Latencies are per provider, medians with IQR, on the machine stamped in
the output, all from this one implementation so the rows are comparable.
"""
import argparse

import numpy as np

from common import save, tag_domain_deployment, timed
from crshe import Provider, baselines, he

ap = argparse.ArgumentParser()
ap.add_argument("--domains", type=int, nargs="+", default=[11_580, 35_162])
ap.add_argument("--reps", type=int, default=11)
args = ap.parse_args()

bfv = he.BFV()
rows = []
for N in args.domains:
    four = ("count", "sum", "weighted", "sumsq")
    o, tags, postings, values = tag_domain_deployment(N, bfv=bfv, templates=four)
    L1 = o.fast_layout(["sum"])
    L4 = o.fast_layout(list(four))
    b = o.bundle(layouts=[("one", L1), ("four", L4)], legacy=list(four))
    P = [Provider(j, b) for j in range(2)]
    u = o.user()
    tag = tags[N // 2]
    keys = u.token(tag)
    t_dpf, e0 = timed(lambda: keys[0].eval_full(), args.reps)
    cc = bfv.cc

    def legacy_one():
        return P[0].fast_legacy(keys[0], "sum", e=e0)

    def legacy_four():
        return [P[0].fast_legacy(keys[0], t, e=e0) for t in four]

    configs = {
        "submitted_2ct_1tpl": (legacy_one, lambda r: sum(he.size_bytes(c) for c in r)),
        "packed_1ct_1tpl": (lambda: P[0].fast(keys[0], "one", e=e0), he.size_bytes),
        "packed_1ct_1tpl_compressed": (lambda: P[0].fast(keys[0], "one", compress=True, e=e0), he.size_bytes),
        "submitted_2ct_x4_4tpl": (legacy_four, lambda r: sum(he.size_bytes(c) for pair in r for c in pair)),
        "packed_1ct_4tpl": (lambda: P[0].fast(keys[0], "four", e=e0), he.size_bytes),
        "packed_1ct_4tpl_compressed": (lambda: P[0].fast(keys[0], "four", compress=True, e=e0), he.size_bytes),
    }
    res = {"N": N, "dpf_key_bytes": keys[0].size_bytes(), "dpf_eval": t_dpf,
           "chunks_packed_1tpl": L1.chunks, "chunks_packed_4tpl": L4.chunks,
           "chunks_submitted_per_column": -(-N // bfv.slots), "configs": {}}
    for name, (fn, size) in configs.items():
        t, out = timed(fn, args.reps)
        res["configs"][name] = {"provider": t, "downlink_bytes_per_provider": size(out)}

    # correctness of what was timed
    truth = {k: int(o.templates[k][postings[N // 2]].sum()) for k in four}
    got = u.finish_fast(tag, L4, [p.fast(k, "four", compress=True) for p, k in zip(P, keys)])
    assert got == truth, (got, truth)
    assert u.finish_legacy([p.fast_legacy(k, "sum") for p, k in zip(P, keys)]) == truth["sum"]

    # client: combine two responses, decrypt once, check MACs
    resp = [p.fast(k, "four", compress=True) for p, k in zip(P, keys)]
    res["client_finish_4tpl"], _ = timed(lambda: u.finish_fast(tag, L4, resp), args.reps)

    # single-server baseline: same columns, encrypted one-hot query
    q = baselines.single_server_query(u, L1, tag)
    t_q, _ = timed(lambda: baselines.single_server_query(u, L1, tag), max(3, args.reps // 3))
    t_s, r = timed(lambda: baselines.single_server_answer(b, "one", q), args.reps)
    t_sc, rc = timed(lambda: baselines.single_server_answer(b, "one", q, compress=True), args.reps)
    assert u.finish_fast(tag, L1, [rc])["sum"] == truth["sum"]
    res["single_server"] = {"server": t_s, "server_compressed": t_sc, "client_query_encrypt": t_q,
                            "uplink_bytes": sum(he.size_bytes(c) for c in q),
                            "query_ciphertexts": len(q),
                            "downlink_bytes": he.size_bytes(r), "downlink_bytes_compressed": he.size_bytes(rc)}
    rows.append(res)
    c = res["configs"]
    print(f"N={N}: key={res['dpf_key_bytes']}B dpf={t_dpf['median_ms']:.2f}ms")
    for name in configs:
        print(f"  {name:32s} {c[name]['provider']['median_ms']:8.2f} ms  {c[name]['downlink_bytes_per_provider']:>9,d} B")
    s = res["single_server"]
    print(f"  single-server                    {s['server']['median_ms']:8.2f} ms  up {s['uplink_bytes']:,d} B  down {s['downlink_bytes']:,d} B")

save("response_and_single_server.json", {"rows": rows})
