import numpy as np
import pytest

from crshe import Owner, Provider, VerificationError, field
from crshe.protocol import PACK_BITS, pack_row, unpack_row


def deploy(bfv, nd, pack_bits, seed=3):
    rng = np.random.default_rng(seed)
    ntags = 150
    postings = [np.sort(rng.choice(nd, size=int(rng.integers(0, 60)), replace=False)) for _ in range(ntags)]
    postings[0] = np.arange(nd)                  # every record, incl. the last partial word
    postings[1] = np.array([], dtype=np.int64)
    values = rng.integers(1, 100, nd)
    o = Owner([f"k{i:03d}" for i in range(ntags)], postings, values, {"sum": values}, n=2,
              bfv=bfv, seed=seed, build_masked_index=True, pack_bits=pack_bits)
    b = o.bundle(flexible=True)
    return o, [Provider(j, b) for j in range(2)], o.user(), postings


@pytest.mark.parametrize("nd", [1, 31, 32, 33, 1000, 4099])
def test_pack_unpack_roundtrip(nd):
    rng = np.random.default_rng(nd)
    post = np.sort(rng.choice(nd, size=min(nd, 17), replace=False))
    words = -(-nd // PACK_BITS)
    bits = unpack_row(pack_row(post, words), nd)
    assert np.array_equal(np.flatnonzero(bits), post)


@pytest.mark.parametrize("pack_bits", [1, PACK_BITS])
def test_packed_retrieval_exact(bfv, pack_bits):
    o, P, u, postings = deploy(bfv, 1037, pack_bits)
    assert o.masked_index.shape[1] == -(-1037 // pack_bits)
    for x in (0, 1, 2, 77, 149):
        tag = f"k{x:03d}"
        S = u.finish_retrieve(tag, [p.retrieve(k) for p, k in zip(P, u.token(tag))])
        assert np.array_equal(S, postings[x])


def test_packed_index_is_smaller(bfv):
    o1, *_ = deploy(bfv, 2048, 1)        # a multiple of the word width
    o32, *_ = deploy(bfv, 2048, PACK_BITS)
    assert o1.masked_index.nbytes == PACK_BITS * o32.masked_index.nbytes


def test_corrupted_share_is_usually_rejected(bfv):
    """Failure control for the width check: random corruption of a retrieval
    share leaves a word >= 2^32 with probability 15/16 per corrupted word."""
    o, P, u, postings = deploy(bfv, 3200, PACK_BITS)
    rng = np.random.default_rng(0)
    rejected = 0
    for _ in range(40):
        keys = u.token("k002")
        s0, s1 = P[0].retrieve(keys[0]), P[1].retrieve(keys[1])
        s1 = s1.copy()
        idx = rng.integers(0, len(s1), 8)
        s1[idx] = rng.integers(0, field.P, 8, dtype=np.uint64)
        try:
            u.finish_retrieve("k002", [s0, s1])
        except VerificationError:
            rejected += 1
    assert rejected >= 36          # expected 40 * (1 - 16^-8) ~ 40


def test_stray_bit_beyond_last_record_is_rejected(bfv):
    nd = 1000                       # 1000 = 31*32 + 8: the last word has 24 padding bits
    o, P, u, postings = deploy(bfv, nd, PACK_BITS)
    keys = u.token("k003")
    s0, s1 = P[0].retrieve(keys[0]), P[1].retrieve(keys[1]).copy()
    s1[-1] = (int(s1[-1]) + (1 << 30)) % field.P   # sets a padding bit after unmasking
    with pytest.raises(VerificationError):
        u.finish_retrieve("k003", [s0, s1])


def test_repeated_record_id_sets_one_bit():
    """Regression: packing added 2^b per occurrence, so a repeated id carried
    into the next bit. Bits must have set semantics."""
    post = np.array([3, 3, 7])
    bits = unpack_row(pack_row(post, 1), 32)
    assert np.array_equal(np.flatnonzero(bits), [3, 7])


def test_failure_control_additive_packing_carries():
    """The regression test must be able to fail: the old additive packing
    turns 3,3 into bit 4, which is the bug the test above guards."""
    row = np.zeros(1, dtype=np.uint64)
    post = np.array([3, 3, 7])
    np.add.at(row, post // 32, np.left_shift(np.uint64(1), (post % 32).astype(np.uint64)))
    assert not np.array_equal(np.flatnonzero(unpack_row(row, 32)), [3, 7])


@pytest.mark.parametrize("bad", [np.array([0, 5, 5]), np.array([-1, 2]), np.array([0, 40])])
def test_owner_rejects_bad_posting_lists(bfv, bad):
    values = np.ones(40, dtype=np.int64)
    with pytest.raises(ValueError):
        Owner(["a"], [bad], values, {"sum": values}, n=2, bfv=bfv, seed=1)
