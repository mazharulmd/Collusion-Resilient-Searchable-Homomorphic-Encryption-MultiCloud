import numpy as np
import pytest

from crshe import dpf, field, prg
from crshe.baselines import nn_shared_local_answers


def test_mul_is_exact():
    rng = np.random.default_rng(0)
    a = rng.integers(0, field.P, 5000, dtype=np.uint64)
    b = rng.integers(0, field.P, 5000, dtype=np.uint64)
    got = field.mul(a, b)
    assert all(int(g) == int(x) * int(y) % field.P for g, x, y in zip(got, a, b))


def test_magnitude_guard():
    field.check_magnitude([field.P - 1])
    with pytest.raises(ValueError):
        field.check_magnitude([field.P // 2, field.P // 2 + 1])


@pytest.mark.parametrize("N", [1, 2, 3, 5, 8, 31, 64, 100, 257, 4096])
def test_two_party_dpf_full_domain(N):
    for alpha in sorted({0, N // 3, N - 1}):
        k0, k1 = dpf.gen2(alpha, N, beta=12345)
        tot = field.add(k0.eval_full(), k1.eval_full())
        expect = np.zeros(N, dtype=np.uint64)
        expect[alpha] = 12345
        assert (tot == expect).all()


def test_two_party_dpf_pointwise_matches_full_domain():
    for depth in range(1, 9):          # exhaustive over every point and alpha
        N = 1 << depth
        for alpha in range(0, N, max(1, N // 8)):
            k0, k1 = dpf.gen2(alpha, N)
            f0, f1 = k0.eval_full(), k1.eval_full()
            for x in range(N):
                assert dpf.eval_point(k0, x) == int(f0[x])
                assert dpf.eval_point(k1, x) == int(f1[x])
                assert (int(f0[x]) + int(f1[x])) % field.P == (1 if x == alpha else 0)


@pytest.mark.parametrize("n", [3, 4, 5])
def test_n_party_sharing(n):
    N = 777
    keys = dpf.gen(400, N, n)
    acc = np.zeros(N, dtype=np.uint64)
    for k in keys:
        acc = field.add(acc, k.eval_full())
    expect = np.zeros(N, dtype=np.uint64)
    expect[400] = 1
    assert (acc == expect).all()
    assert [k.size_bytes() for k in keys] == [16] * (n - 1) + [8 * N]


def test_key_size_logarithmic():
    sizes = [dpf.gen2(0, N)[0].size_bytes() for N in (1000, 11_580, 10**6)]
    assert sizes == [16 + d * 17 + 5 + 1 for d in (10, 14, 20)]


def test_uniform_zp_rejection():
    key = bytes(16)
    v = prg.uniform_zp(key, prg.DOMAIN_MASK, 3, 200_000)
    assert v.dtype == np.uint64 and int(v.max()) < field.P
    assert (v == prg.uniform_zp(key, prg.DOMAIN_MASK, 3, 200_000)).all()
    assert not (v[:1000] == prg.uniform_zp(key, prg.DOMAIN_MASK, 4, 1000)).all()
    counts = np.bincount((v * np.uint64(64) // np.uint64(field.P)).astype(np.int64), minlength=64)
    chi2 = float(((counts - len(v) / 64) ** 2 / (len(v) / 64)).sum())
    assert chi2 < 120            # 63 dof; p < 1e-5 above this


def test_nn_shared_store_cannot_answer_locally():
    """The submitted Section 6.2 claimed an (n,n)-shared store answers DPF
    queries locally. The local answers miss the cross terms."""
    rng = np.random.default_rng(5)
    col = rng.integers(0, 10**6, 500, dtype=np.uint64)
    wrong = 0
    for n in (2, 3):
        for alpha in (0, 17, 499):
            got, true = nn_shared_local_answers(col, alpha, n, rng)
            wrong += got != true
    assert wrong == 6
