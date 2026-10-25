"""Role-scoped access against the index-extraction attack.

Attack (as in the manuscript's authorisation measurement): a data user sends
raw additive shares of every basis vector e_x, x in [N], and reads every row
of the masked index. With one mask key it strips every row and recovers every
posting list, including records it should not see. With role-scoped keys a
role-0 user strips only role-0 words; we count what it recovers about the
other roles' records, and how many of their words even pass the width check
when it tries its own key on them (chance: 2^32/p).

Also measured: aggregates a role-0 user obtains for every tag through the
fast path and the flexible round, against role-0 and all-role ground truth;
and the per-role storage the owner pays (columns are replicated per role,
the masked index is not).
"""
import argparse

import numpy as np

from common import save
from crshe import Owner, Provider, dpf, field, he, prg
from crshe.protocol import PACK_BITS, role_key, unpack_row

ap = argparse.ArgumentParser()
ap.add_argument("--N", type=int, default=512)
ap.add_argument("--per-role", type=int, default=4096)
ap.add_argument("--roles", type=int, default=3)
args = ap.parse_args()

bfv = he.BFV()
rng = np.random.default_rng(31)
R, N = args.roles, args.N
nd = R * args.per_role
role = np.repeat(np.arange(R), args.per_role)
postings = [np.sort(rng.choice(nd, size=int(min(nd, rng.zipf(1.4) * 15)), replace=False)) for _ in range(N)]
values = rng.integers(1900, 3100, nd)
tags = [f"t{i:04d}" for i in range(N)]
tpl = {"count": np.ones(nd, dtype=np.int64), "sum": values}
words = -(-nd // PACK_BITS)


def extract(owner, user):
    b = owner.bundle(flexible=True, record_mac="session")
    P = [Provider(j, b) for j in range(2)]
    rows_exact = 0
    other_bits_true = other_bits_recovered = 0
    for x in range(N):
        e = np.zeros(N, dtype=np.uint64); e[x] = 1
        shares = dpf.share_vector(e, 2)                  # raw shares, not a DPF key
        acc = field.add(P[0].retrieve(shares[0]), P[1].retrieve(shares[1]))
        got = user.finish_retrieve(tags[x], [acc, np.zeros_like(acc)])
        post = postings[x]
        rows_exact += int(np.array_equal(got, post))
        others = post[role[post] != 0]
        other_bits_true += len(others)
        other_bits_recovered += int(np.isin(others, got).sum())
    return b, P, rows_exact, other_bits_true, other_bits_recovered


res = {}
# one mask key, no role policy
flat = Owner(tags, postings, values, tpl, n=2, bfv=bfv, seed=2, build_masked_index=True)
_, _, ex, tot, rec = extract(flat, flat.user())
res["single_key"] = {"rows_recovered_exactly": ex, "other_role_postings": tot, "other_role_postings_recovered": rec}
print("single key :", res["single_key"])

# role-scoped keys
o = Owner(tags, postings, values, tpl, n=2, bfv=bfv, seed=2, build_masked_index=True, record_role=role)
u0 = o.user(role=0)
b, P, ex, tot, rec = extract(o, u0)
k0 = role_key(o.K_mask, 0)
other = o.word_role != 0
ok = total = 0
for x in range(N):
    row = field.sub(o.masked_index[x], prg.uniform_zp(k0, prg.DOMAIN_MASK, x, words))[other]
    ok += int((row < (1 << PACK_BITS)).sum())
    total += len(row)
res["role_scoped"] = {"rows_recovered_exactly": ex, "other_role_postings": tot,
                      "other_role_postings_recovered": rec,
                      "other_role_words_passing_width_check": ok, "other_role_words": total,
                      "chance_rate": (1 << PACK_BITS) / field.P}
print("role keys  :", res["role_scoped"])

# aggregates a role-0 user can obtain, for every tag and for every record
lay = o.fast_layout(["count", "sum"], mac="session", role=0)
bf = o.bundle(layouts=[("r0", lay)], flexible=True, record_mac="session", role=0)
Pf = [Provider(j, bf) for j in range(2)]
match_role = match_all = 0
for x, t in enumerate(tags):
    keys, hats, ds = u0.token_session(t)
    got = u0.finish_fast(t, lay, [p.fast(keys[j], "r0", compress=True, key_hat=hats[j])
                                 for j, p in enumerate(Pf)], delta_s=ds)["sum"]
    post = postings[x]
    mine = int(values[post[role[post] == 0]].sum())
    allr = int(values[post].sum())
    match_role += int(got == mine)
    match_all += int(got == allr and allr != mine)
sh, hats, ds = u0.deal_selection(np.arange(nd), session=True)
every = u0.finish_contract([Pf[j].contract(sh[j], compress=True, hat_key=hats[j]) for j in range(2)], delta_s=ds)
res["aggregates"] = {"tags": N, "fast_equal_role0_truth": match_role, "fast_equal_all_role_truth": match_all,
                     "flexible_all_records": every, "role0_total": int(values[role == 0].sum()),
                     "all_roles_total": int(values.sum())}
print("aggregates :", res["aggregates"])

fresh = he.size_bytes(bfv.encrypt(np.zeros(8, dtype=np.uint64)))
res["storage_per_role"] = {"fast_column_ciphertexts": lay.chunks, "record_column_ciphertexts": len(bf.records),
                           "fresh_ciphertext_bytes": fresh,
                           "note": "columns and cube tables are replicated per role; the masked index is shared"}
save("role_access.json", {"N": N, "roles": R, "records": nd, "results": res})
