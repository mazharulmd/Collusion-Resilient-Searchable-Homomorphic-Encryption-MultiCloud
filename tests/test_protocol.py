import numpy as np
import pytest

from crshe import Owner, Provider, VerificationError, baselines, field, he


def deploy(bfv, db, n, flexible=False, mac="row"):
    o = Owner(db["tags"], db["postings"], db["values"], db["templates"], n=n,
              N=len(db["tags"]) + 20, bfv=bfv, seed=11, build_masked_index=flexible)
    all4 = o.fast_layout(["count", "sum", "weighted", "sumsq"], mac=mac)
    one = o.fast_layout(["sum"], mac=mac)
    b = o.bundle(layouts=[("all", all4), ("sum", one)], legacy=["sum"], flexible=flexible)
    return o, [Provider(j, b) for j in range(n)], o.user(), all4, one


def truth(db, tag):
    post = db["postings"][db["tags"].index(tag)]
    return {name: int(c[post].sum()) for name, c in db["templates"].items()}


@pytest.mark.parametrize("n", [2, 3, 4])
def test_fast_path_all_templates(bfv, small_db, n):
    o, P, u, all4, one = deploy(bfv, small_db, n)
    for tag in ["t000", "t005", "t123", "t298", "t299"]:
        keys = u.token(tag)
        assert u.finish_fast(tag, all4, [p.fast(k, "all") for p, k in zip(P, keys)]) == truth(small_db, tag)
        got = u.finish_fast(tag, one, [p.fast(k, "sum", compress=True) for p, k in zip(P, keys)])
        assert got["sum"] == truth(small_db, tag)["sum"]
        assert u.finish_legacy([p.fast_legacy(k, "sum") for p, k in zip(P, keys)]) == truth(small_db, tag)["sum"]


def test_response_size_independent_of_match(bfv, small_db):
    o, P, u, all4, one = deploy(bfv, small_db, 2)
    sizes = set()
    for tag in ("t298", "t299"):            # |S| = 0 and |S| = N_d - 1
        for k, p in zip(u.token(tag), P):
            sizes.add(he.size_bytes(p.fast(k, "all")))
    assert len(sizes) == 1


def test_compression_halves_response(bfv, small_db):
    o, P, u, all4, one = deploy(bfv, small_db, 2)
    k = u.token("t005")[0]
    full = he.size_bytes(P[0].fast(k, "sum"))
    comp = he.size_bytes(P[0].fast(k, "sum", compress=True))
    legacy = sum(he.size_bytes(c) for c in P[0].fast_legacy(k, "sum"))
    assert comp < 0.55 * full and full < 0.55 * legacy


@pytest.mark.parametrize("n", [2, 3])
def test_retrieval_and_flexible_path(bfv, small_db, n):
    o, P, u, *_ = deploy(bfv, small_db, n, flexible=True)
    vals, w = small_db["values"], small_db["w"]
    for tag in ["t000", "t005", "t298", "t299"]:
        S = u.finish_retrieve(tag, [p.retrieve(k) for p, k in zip(P, u.token(tag))])
        assert (S == small_db["postings"][small_db["tags"].index(tag)]).all()
        y = u.finish_contract([p.contract(k) for p, k in zip(P, u.deal_selection(S, weights=w))])
        assert y == int((w * vals)[S].sum())
    # a conjunction and a disjunction, formed at the user, ad-hoc weights
    S1 = u.finish_retrieve("t001", [p.retrieve(k) for p, k in zip(P, u.token("t001"))])
    S2 = u.finish_retrieve("t299", [p.retrieve(k) for p, k in zip(P, u.token("t299"))])
    adhoc = np.arange(len(vals)) % 7
    for S in (np.intersect1d(S1, S2), np.union1d(S1, S2)):
        y = u.finish_contract([p.contract(k) for p, k in zip(P, u.deal_selection(S, weights=adhoc))])
        assert y == int((adhoc * vals)[S].sum())


def test_provider_holds_no_secret_key(bfv, small_db):
    o, P, *_ = deploy(bfv, small_db, 2)
    with pytest.raises(PermissionError):
        P[0].b.he.decrypt(None, None)


def test_mac_detects_inconsistent_response(bfv, small_db):
    o, P, u, all4, one = deploy(bfv, small_db, 2)
    keys = u.token("t005")
    good = [p.fast(k, "sum") for p, k in zip(P, keys)]
    bump = np.zeros(bfv.slots, dtype=np.uint64)
    bump[0] = 1                                          # value row only
    bad = bfv.cc.EvalAdd(good[1], bfv.encrypt(bump))
    with pytest.raises(VerificationError):
        u.finish_fast("t005", one, [good[0], bad])


def test_linear_substitution_gap_and_row_keys(bfv, small_db):
    """A provider that contracts against e_j + d in BOTH rows passes the
    global-delta MAC but fails the per-row MAC unless d hits only alpha."""
    rng = np.random.default_rng(3)
    tag = "t005"
    for mac, expect_detect in (("global", False), ("row", True)):
        o, P, u, all4, one = deploy(bfv, small_db, 2, mac=mac)
        keys = u.token(tag)
        e = keys[1].eval_full()
        d = rng.integers(0, field.P, len(e), dtype=np.uint64)
        resp = [P[0].fast(keys[0], "sum"), P[1].fast(keys[1], "sum", e=field.add(e, d))]
        if expect_detect:
            with pytest.raises(VerificationError):
                u.finish_fast(tag, one, resp)
        else:
            assert u.finish_fast(tag, one, resp)["sum"] != truth(small_db, tag)["sum"]


def test_template_exceeding_p_is_rejected(bfv, small_db):
    db = dict(small_db)
    db["templates"] = {"huge": np.full(len(db["values"]), field.P // 100, dtype=np.int64)}
    with pytest.raises(ValueError):
        Owner(db["tags"], db["postings"], db["values"], db["templates"], n=2, bfv=bfv)


def test_single_server_baseline(bfv, small_db):
    o, P, u, all4, one = deploy(bfv, small_db, 2)
    for tag in ("t005", "t299"):
        q = baselines.single_server_query(u, one, tag)
        r = baselines.single_server_answer(P[0].b, "sum", q)
        assert u.finish_fast(tag, one, [r])["sum"] == truth(small_db, tag)["sum"]


def test_multi_chunk_noise_budget(bfv):
    """Several packed chunks of full-magnitude Z_p coefficients on both paths:
    13,000 tags span 4 fast-path chunks, 9,000 records span 3 record chunks."""
    rng = np.random.default_rng(9)
    Nd, ntags = 9000, 13_000
    values = rng.integers(0, 5000, Nd)
    postings = [rng.choice(Nd, size=int(rng.integers(0, 40)), replace=False) for _ in range(ntags)]
    tags = [f"x{i:05d}" for i in range(ntags)]
    o = Owner(tags, postings, values, {"sum": values}, n=2, bfv=bfv, seed=2,
              build_masked_index=True)
    one = o.fast_layout(["sum"])
    assert one.chunks == 4
    b = o.bundle(layouts=[("sum", one)], flexible=True)
    assert len(b.records) == 3
    P = [Provider(j, b) for j in range(2)]
    u = o.user()
    for tag in ("x00000", "x06500", "x12999"):
        post = postings[tags.index(tag)]
        keys = u.token(tag)
        assert u.finish_fast(tag, one, [p.fast(k, "sum") for p, k in zip(P, keys)])["sum"] == int(values[post].sum())
        S = u.finish_retrieve(tag, [p.retrieve(k) for p, k in zip(P, keys)])
        assert sorted(S) == sorted(post)
        full = np.arange(Nd)            # every record, so every chunk carries data
        y = u.finish_contract([p.contract(k) for p, k in zip(P, u.deal_selection(full))])
        assert y == int(values.sum())
