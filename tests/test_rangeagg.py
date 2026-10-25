import itertools

import numpy as np
import pytest

from crshe import Owner, VerificationError, field, he, rangeagg


def setup(bfv, dims, n, mode, seed=0, nd=3000):
    rng = np.random.default_rng(seed)
    cells = np.stack([rng.integers(0, s, nd) for s in dims], axis=1)
    values = rng.integers(1000, 4000, nd)
    owner = Owner(["t0"], [np.arange(5)], values, {"sum": values}, n=n, bfv=bfv, seed=seed)
    co = rangeagg.CubeOwner(owner)
    tpl = {"count": np.ones(nd, dtype=np.int64), "sum": values}
    layout, cts = co.register("cube", dims, cells, tpl, mode=mode)
    return owner.user(), layout, cts, co.client_secret("cube"), cells, tpl, bfv.public_view()


def truth(cells, tpl, box):
    inside = np.all([(cells[:, k] >= lo) & (cells[:, k] <= hi) for k, (lo, hi) in enumerate(box)], axis=0)
    return {t: int(c[inside].sum()) for t, c in tpl.items()}


def ask(user, layout, cts, secret, pub, box, n, compress=True):
    keys, meta = rangeagg.range_token(layout, box, n)
    resp = [rangeagg.range_answer(pub, layout, cts, keys[j], compress=compress) for j in range(n)]
    return rangeagg.finish_range(user, layout, secret, meta, resp), resp


def boxes(dims, rng, k):
    out = [tuple((0, s - 1) for s in dims), tuple((0, 0) for _ in dims),
           tuple((s - 1, s - 1) for s in dims)]
    for _ in range(k):
        b = []
        for s in dims:
            lo, hi = sorted(rng.integers(0, s, 2))
            b.append((int(lo), int(hi)))
        out.append(tuple(b))
    return out


@pytest.mark.parametrize("dims,n,mode", [((97,), 2, "per_corner"), ((12, 9), 2, "per_corner"),
                                         ((3, 40, 5), 3, "per_corner"), ((12, 9), 2, "combined"),
                                         ((3, 40, 5), 2, "combined")])
def test_range_aggregates_match_ground_truth(bfv, dims, n, mode):
    user, layout, cts, secret, cells, tpl, pub = setup(bfv, dims, n, mode)
    rng = np.random.default_rng(1)
    for box in boxes(dims, rng, 6):
        got, _ = ask(user, layout, cts, secret, pub, box, n)
        assert got == truth(cells, tpl, box), (box, got)


def test_failure_control_wrong_corner_sign(bfv, monkeypatch):
    """The correctness test must be able to fail: flipping one corner's sign
    (a mutation of inclusion-exclusion) has to produce a wrong answer."""
    dims = (12, 9)
    user, layout, cts, secret, cells, tpl, pub = setup(bfv, dims, 2, "combined")
    box = ((3, 8), (2, 6))
    real = rangeagg.corners

    def flipped(b, d):
        out = real(b, d)
        mask, x, beta = out[1]
        out[1] = (mask, x, (field.P - beta) % field.P)
        return out
    monkeypatch.setattr(rangeagg, "corners", flipped)
    got, _ = ask(user, layout, cts, secret, pub, box, 2)
    assert got != truth(cells, tpl, box)


def test_failure_control_dropped_dummy_rule(bfv, monkeypatch):
    """Mutation: treat an out-of-cube corner (lo = 0) as a real corner at
    index 0 instead of a zero contribution. The test must catch it."""
    dims = (12, 9)
    user, layout, cts, secret, cells, tpl, pub = setup(bfv, dims, 2, "combined")
    box = ((0, 8), (2, 6))
    real = rangeagg.corners

    def no_dummy(b, d):
        return [(m, x if x is not None else 0, beta if x is not None else field.P - 1)
                for m, x, beta in real(b, d)]
    monkeypatch.setattr(rangeagg, "corners", no_dummy)
    got, _ = ask(user, layout, cts, secret, pub, box, 2)
    assert got != truth(cells, tpl, box)


def test_every_query_sends_the_same_keys(bfv):
    """A box touching the cube's edge (dummy corners) and an interior box send
    the same number of keys, of the same sizes, and get same-size responses."""
    dims = (12, 9)
    user, layout, cts, secret, cells, tpl, pub = setup(bfv, dims, 2, "per_corner")
    shapes, sizes = set(), set()
    for box in (((0, 3), (0, 2)), ((4, 8), (3, 7)), ((0, 11), (0, 8))):
        keys, meta = rangeagg.range_token(layout, box, 2)
        shapes.add(tuple(k.size_bytes() for k in keys[0]))
        _, resp = ask(user, layout, cts, secret, pub, box, 2)
        sizes.add(he.size_bytes(resp[0]))
    assert len(shapes) == 1 and len(next(iter(shapes))) == 4
    assert len(sizes) == 1


def test_per_corner_mac_catches_substitution_combined_does_not(bfv):
    dims = (12, 9)
    rng = np.random.default_rng(4)
    box = ((3, 8), (2, 6))
    for mode, caught in (("per_corner", True), ("combined", False)):
        user, layout, cts, secret, cells, tpl, pub = setup(bfv, dims, 2, mode)
        keys, meta = rangeagg.range_token(layout, box, 2)

        class Bent:                      # provider 1 contracts e_r + d for corner 0
            def __init__(self, k, d):
                self.k, self.d, self.N = k, d, k.N

            def eval_full(self):
                return field.add(self.k.eval_full(), self.d)
        d = rng.integers(0, field.P, layout.M, dtype=np.uint64)
        bent = [Bent(keys[1][0], d)] + keys[1][1:]
        resp = [rangeagg.range_answer(pub, layout, cts, keys[0]),
                rangeagg.range_answer(pub, layout, cts, bent)]
        if caught:
            with pytest.raises(VerificationError):
                rangeagg.finish_range(user, layout, secret, meta, resp)
        else:
            assert rangeagg.finish_range(user, layout, secret, meta, resp) != truth(cells, tpl, box)


def test_cube_total_must_fit_below_p(bfv):
    owner = Owner(["t0"], [np.arange(2)], np.array([1, 2]), {"s": np.array([1, 2])}, n=2, bfv=bfv)
    co = rangeagg.CubeOwner(owner)
    big = np.full(4, field.P // 3, dtype=np.int64)
    with pytest.raises(ValueError):
        co.register("c", (4,), np.arange(4)[:, None], {"big": big})


def test_corner_enumeration_is_inclusion_exclusion():
    dims = (5, 4, 3)
    rng = np.random.default_rng(2)
    cube = rng.integers(0, 10, dims)
    cells = np.array(list(itertools.product(*map(range, dims))))
    sat = rangeagg.summed_area(cells, dims, cube.reshape(-1))
    for box in boxes(dims, rng, 30):
        total = sum(beta * int(sat[x]) for _, x, beta in rangeagg.corners(box, dims) if x is not None) % field.P
        sl = tuple(slice(lo, hi + 1) for lo, hi in box)
        assert total == int(cube[sl].sum())


def test_tampered_dummy_corner_is_caught(bfv):
    """A box with lo = 0 has dummy corners whose contribution must be zero. A
    provider that perturbs a dummy corner's share is caught by the zero check."""
    dims = (12, 9)
    user, layout, cts, secret, cells, tpl, pub = setup(bfv, dims, 2, "per_corner")
    box = ((0, 8), (2, 6))
    keys, meta = rangeagg.range_token(layout, box, 2)
    r = next(i for i, m in enumerate(meta) if m[1] is None)

    class Bent:
        def __init__(self, k):
            self.k, self.N = k, k.N

        def eval_full(self):
            e = self.k.eval_full().copy()
            e[5] = (int(e[5]) + 1) % field.P
            return e
    bent = list(keys[1])
    bent[r] = Bent(keys[1][r])
    resp = [rangeagg.range_answer(pub, layout, cts, keys[0]),
            rangeagg.range_answer(pub, layout, cts, bent)]
    with pytest.raises(VerificationError):
        rangeagg.finish_range(user, layout, secret, meta, resp)
