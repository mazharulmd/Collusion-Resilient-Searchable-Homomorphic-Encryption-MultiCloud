"""Session MAC: row 1 holds a copy of the data and the user's second key set
carries a fresh secret delta_s. Every deviation that changes the answer must
be caught, including the hidden-row rescaling that per-row keys miss; an
attacker handed delta_s (the failure control) must get through."""
import numpy as np
import pytest

from crshe import Owner, Provider, VerificationError, dpf, field, rangeagg
from crshe.protocol import fresh_unit


@pytest.fixture(scope="module")
def dep(bfv, small_db):
    o = Owner(small_db["tags"], small_db["postings"], small_db["values"], small_db["templates"],
              n=2, bfv=bfv, seed=5)
    lay = o.fast_layout(["count", "sum"], mac="session")
    b = o.bundle(layouts=[("s", lay)], flexible=True, record_mac="session")
    return o, lay, [Provider(j, b) for j in range(2)], o.user()


def busiest(o):
    return o.tags[int(np.argmax([len(p) for p in o.postings]))]


def answer(P, lay, keys, hats, compress=True, j_dev=None, e=None, eh=None):
    out = []
    for j, p in enumerate(P):
        if j == j_dev:
            out.append(p.fast(keys[j], "s", compress=compress, e=e, ehat=eh))
        else:
            out.append(p.fast(keys[j], "s", compress=compress, key_hat=hats[j]))
    return out


def test_session_fast_path_is_correct(dep, small_db):
    o, lay, P, u = dep
    for t in o.tags[:40] + [busiest(o)]:
        keys, hats, ds = u.token_session(t)
        got = u.finish_fast(t, lay, answer(P, lay, keys, hats), delta_s=ds)
        x = o.D[t]
        assert got == {"count": int(o.A["count"][x]), "sum": int(o.A["sum"][x])}


def deviations(o, keys, hats, alpha, rng):
    e, eh = keys[0].eval_full(), hats[0].eval_full()
    c = np.uint64(int(rng.integers(1, field.P)))
    k = np.uint64(int(rng.integers(2, field.P)))
    d = np.asarray(rng.integers(0, field.P, o.N), dtype=np.uint64)
    u = np.zeros(o.N, dtype=np.uint64); u[alpha] = c
    return {
        "uniform substitution": (field.add(e, d), field.add(eh, d)),
        "scaled share": (field.mul(e, k), field.mul(eh, k)),
        "hidden-row rescale": (field.add(e, u), field.add(eh, u)),
        "value row only": (field.add(e, u), eh),
    }


def test_session_mac_catches_every_answer_changing_deviation(dep):
    o, lay, P, u = dep
    rng = np.random.default_rng(9)
    t = busiest(o)
    alpha = o.D[t]
    for name in ("uniform substitution", "scaled share", "hidden-row rescale", "value row only"):
        for _ in range(5):
            keys, hats, ds = u.token_session(t)
            e, eh = deviations(o, keys, hats, alpha, rng)[name]
            with pytest.raises(VerificationError):
                u.finish_fast(t, lay, answer(P, lay, keys, hats, j_dev=0, e=e, eh=eh), delta_s=ds)


def test_failure_control_attacker_who_knows_delta_s_passes(dep):
    """The detection must come from the secrecy of delta_s: a provider told
    delta_s rescales the hidden row consistently and is accepted with a
    wrong answer."""
    o, lay, P, u = dep
    t = busiest(o)
    alpha = o.D[t]
    keys, hats, ds = u.token_session(t)
    e, eh = keys[0].eval_full(), hats[0].eval_full()
    du = np.zeros(o.N, dtype=np.uint64); du[alpha] = 7
    dh = np.zeros(o.N, dtype=np.uint64); dh[alpha] = 7 * ds % field.P
    got = u.finish_fast(t, lay, answer(P, lay, keys, hats, j_dev=0, e=field.add(e, du), eh=field.add(eh, dh)),
                        delta_s=ds)
    assert got["count"] == 8 * int(o.A["count"][alpha]) % field.P != int(o.A["count"][alpha])


def test_replayed_response_is_caught(dep):
    o, lay, P, u = dep
    t = busiest(o)
    k1, h1, d1 = u.token_session(t)
    old = P[0].fast(k1[0], "s", compress=True, key_hat=h1[0])
    k2, h2, d2 = u.token_session(t)
    fresh = P[1].fast(k2[1], "s", compress=True, key_hat=h2[1])
    with pytest.raises(VerificationError):
        u.finish_fast(t, lay, [old, fresh], delta_s=d2)


def test_session_flexible_round_catches_scaled_share(dep):
    """Under the global MAC a provider that scales its share in both rows
    passes; under the session MAC it must not."""
    o, lay, P, u = dep
    sel = np.flatnonzero(np.arange(o.Nd) % 3 == 0)
    sh, hats, ds = u.deal_selection(sel, session=True)
    honest = [p.contract(sh[j], compress=True, hat_key=hats[j]) for j, p in enumerate(P)]
    assert u.finish_contract(honest, delta_s=ds) == int(o.values[sel].sum())
    k = np.uint64(5)
    bad0 = dpf.VectorKey(0, field.mul(sh[0].eval_full(), k), o.Nd)
    badh = dpf.VectorKey(0, field.mul(hats[0].eval_full(), k), o.Nd)
    resp = [P[0].contract(bad0, compress=True, hat_key=badh), honest[1]]
    with pytest.raises(VerificationError):
        u.finish_contract(resp, delta_s=ds)


def test_failure_control_global_mac_misses_scaled_share(bfv, small_db):
    """Control for the test above: the same deviation against the global-MAC
    record column is accepted with a wrong answer."""
    o = Owner(small_db["tags"], small_db["postings"], small_db["values"], small_db["templates"],
              n=2, bfv=bfv, seed=5)
    b = o.bundle(flexible=True)
    P, u = [Provider(j, b) for j in range(2)], o.user()
    sel = np.flatnonzero(np.arange(o.Nd) % 3 == 0)
    sh = u.deal_selection(sel)
    bad0 = dpf.VectorKey(0, field.mul(sh[0].eval_full(), np.uint64(5)), o.Nd)
    got = u.finish_contract([P[0].contract(bad0, compress=True), P[1].contract(sh[1], compress=True)])
    assert got != int(o.values[sel].sum())


@pytest.fixture(scope="module")
def cube(bfv):
    rng = np.random.default_rng(2)
    dims, nd = (4, 30, 6), 2500
    cells = np.stack([rng.integers(0, s, nd) for s in dims], axis=1)
    values = rng.integers(1000, 4000, nd)
    o = Owner(["t"], [np.arange(3)], values, {"sum": values}, n=2, bfv=bfv, seed=3)
    tpl = {"count": np.ones(nd, dtype=np.int64), "sum": values}
    lay, cts = rangeagg.CubeOwner(o).register("c", dims, cells, tpl, mode="session")
    return o.user(), lay, cts, cells, tpl, bfv.public_view()


def test_session_range_is_correct(cube):
    from test_rangeagg import boxes, truth
    u, lay, cts, cells, tpl, pub = cube
    for box in boxes(lay.dims, np.random.default_rng(4), 6):
        keys, meta = rangeagg.range_token(lay, box, 2)
        assert all(len(k) == 2 * lay.corners for k in keys)
        resp = [rangeagg.range_answer(pub, lay, cts, keys[j], compress=True) for j in range(2)]
        assert rangeagg.finish_range(u, lay, None, meta, resp) == truth(cells, tpl, box)


def test_session_range_catches_substitution_and_control_passes(cube):
    u, lay, cts, cells, tpl, pub = cube
    box = ((1, 2), (5, 20), (0, 3))
    keys, meta = rangeagg.range_token(lay, box, 2)
    ds = meta[-1][1]
    honest = rangeagg.range_answer(pub, lay, cts, keys[1], compress=True)
    x = 77                                              # any cell
    for scale_hat, caught in ((1, True), (ds, False)):  # (1: blind attacker), (ds: control)
        dev = list(keys[0])
        bump = np.zeros(lay.M, dtype=np.uint64); bump[x] = 1
        bumph = np.zeros(lay.M, dtype=np.uint64); bumph[x] = scale_hat
        dev[0] = dpf.VectorKey(0, field.add(dev[0].eval_full(), bump), lay.M)
        dev[lay.corners] = dpf.VectorKey(0, field.add(dev[lay.corners].eval_full(), bumph), lay.M)
        resp = [rangeagg.range_answer(pub, lay, cts, dev, compress=True), honest]
        if caught:
            with pytest.raises(VerificationError):
                rangeagg.finish_range(u, lay, None, meta, resp)
        else:
            assert rangeagg.finish_range(u, lay, None, meta, resp) != truth_box(cells, tpl, box)


def truth_box(cells, tpl, box):
    from test_rangeagg import truth
    return truth(cells, tpl, box)


def test_fresh_unit_is_a_unit():
    for _ in range(1000):
        d = fresh_unit()
        assert 0 < d < field.P


def test_session_retrieval_is_correct_and_catches_flipped_bit(dep, small_db):
    o, lay, P, u = dep
    # a sparse tag, so that adding 1 to a word flips a bit instead of overflowing the width check
    t = next(t for t, p in zip(o.tags, o.postings) if 0 < len(p) < 50 and 0 not in p)
    keys, hats, ds = u.token_session(t)
    sh = [p.retrieve(keys[j], key_hat=hats[j]) for j, p in enumerate(P)]
    assert np.array_equal(u.finish_retrieve(t, sh, delta_s=ds), o.postings[o.D[t]])
    b0, h0 = sh[0]
    flip = b0.copy(); flip[0] = field.add(flip[:1], np.ones(1, dtype=np.uint64))[0]   # one membership bit
    with pytest.raises(VerificationError):
        u.finish_retrieve(t, [(flip, h0), sh[1]], delta_s=ds)
    # failure control: the same flip passes when the check is not requested
    got = u.finish_retrieve(t, [flip, sh[1][0]])
    assert not np.array_equal(got, o.postings[o.D[t]])
