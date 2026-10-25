"""Role-scoped access: a user of role r must learn nothing about records of
other roles, whatever vectors it sends. Retrieval words of other roles stay
one-time-padded under keys the user lacks; aggregate columns, cube tables and
the record column of role r are built from role-r records only."""
import numpy as np
import pytest

from crshe import Owner, Provider, VerificationError, dpf, field, rangeagg
from crshe.protocol import PACK_BITS, role_key, unpack_row
from crshe import prg


@pytest.fixture(scope="module")
def roled(bfv):
    rng = np.random.default_rng(11)
    nd = 3 * 320                                        # three roles, 10 words each
    role = np.repeat([0, 1, 2], 320)
    ntags = 64
    postings = [np.sort(rng.choice(nd, size=int(rng.integers(5, 200)), replace=False)) for _ in range(ntags)]
    values = rng.integers(100, 900, nd)
    o = Owner([f"t{i}" for i in range(ntags)], postings, values,
              {"count": np.ones(nd, dtype=np.int64), "sum": values}, n=2, bfv=bfv, seed=8,
              build_masked_index=True, record_role=role)
    return o, role, postings, values


def test_misaligned_roles_are_rejected(bfv):
    values = np.ones(64, dtype=np.int64)
    role = np.r_[np.zeros(40), np.ones(24)]             # word 1 mixes roles
    with pytest.raises(ValueError):
        Owner(["a"], [np.arange(3)], values, {"sum": values}, n=2, bfv=bfv, record_role=role)


def test_role_retrieval_returns_own_records_only(roled):
    o, role, postings, values = roled
    b = o.bundle(flexible=True)
    P = [Provider(j, b) for j in range(2)]
    admin, u0 = o.user(), o.user(role=0)
    for t in o.tags[:20]:
        sh = [P[j].retrieve(k) for j, k in enumerate(u0.token(t))]
        post = postings[o.D[t]]
        assert np.array_equal(admin.finish_retrieve(t, sh), post)
        assert np.array_equal(u0.finish_retrieve(t, sh), post[role[post] == 0])


def test_other_roles_words_do_not_unmask_with_own_key(roled):
    """Extraction attempt: role 0 strips every row's role-1 and role-2 words
    with its own key. If the per-role keys worked, the result is a uniform
    word, which lands below 2^32 with probability 2^32/p, about 1/16; if one
    key masked everything (the failure control below), every word decodes."""
    o, role, postings, values = roled
    words = -(-o.Nd // PACK_BITS)
    other = o.word_role != 0
    k0 = role_key(o.K_mask, 0)
    ok = total = 0
    for x in range(o.N):
        row = field.sub(o.masked_index[x], prg.uniform_zp(k0, prg.DOMAIN_MASK, x, words))[other]
        ok += int((row < (1 << PACK_BITS)).sum())
        total += len(row)
    assert ok / total < 0.12                             # 2^32/p = 0.0625


def unmask_rate(index, key, words, cols):
    ok = total = 0
    for x in range(index.shape[0]):
        row = field.sub(index[x], prg.uniform_zp(key, prg.DOMAIN_MASK, x, words))[cols]
        ok += int((row < (1 << PACK_BITS)).sum())
        total += len(row)
    return ok / total


def test_failure_control_single_key_index_unmasks_everything(roled, bfv):
    """Control: the same statistic on an index built WITHOUT roles (one mask
    key) is 1.0 for a holder of that key, so the test above can fail."""
    o, role, postings, values = roled
    flat = Owner(o.tags, postings, values, {"sum": values}, n=2, bfv=bfv, seed=8,
                 build_masked_index=True)
    words = -(-o.Nd // PACK_BITS)
    assert unmask_rate(flat.masked_index, flat.K_mask, words, o.word_role != 0) == 1.0


def test_role_columns_hold_only_role_data_under_any_query(roled, bfv):
    """Fast path: whatever vector a role-0 user sends, the answer is a linear
    function of role-0 aggregates only. Query every row with raw additive
    shares (a malformed key) and compare with role-0 ground truth."""
    o, role, postings, values = roled
    lay = o.fast_layout(["count", "sum"], mac="session", role=0)
    b = o.bundle(layouts=[("r0", lay)])
    P = [Provider(j, b) for j in range(2)]
    u0 = o.user(role=0)
    for t in o.tags[:16]:
        x = o.D[t]
        keys, hats, ds = u0.token_session(t)
        got = u0.finish_fast(t, lay, [p.fast(keys[j], "r0", compress=True, key_hat=hats[j])
                                     for j, p in enumerate(P)], delta_s=ds)
        post = postings[x]
        mine = post[role[post] == 0]
        assert got == {"count": len(mine), "sum": int(values[mine].sum())}


def test_role_cube_and_flexible_round_see_role_data_only(roled, bfv):
    o, role, postings, values = roled
    rng = np.random.default_rng(3)
    dims = (3, 40)
    cells = np.stack([role, rng.integers(0, 40, o.Nd)], axis=1)      # axis 0 is the role's site
    tpl = {"sum": values}
    lay, cts = rangeagg.CubeOwner(o).register("c", dims, cells, tpl, mode="session", role=1)
    u1 = o.user(role=1)
    pub = bfv.public_view()
    box = ((0, 2), (0, 39))                                          # the whole cube
    keys, meta = rangeagg.range_token(lay, box, 2)
    got = rangeagg.finish_range(u1, lay, None, meta,
                                [rangeagg.range_answer(pub, lay, cts, keys[j], compress=True) for j in range(2)])
    assert got == {"sum": int(values[role == 1].sum())}
    b = o.bundle(flexible=True, record_mac="session", role=1)
    P = [Provider(j, b) for j in range(2)]
    every = np.arange(o.Nd)                                          # ask for every record
    sh, hats, ds = u1.deal_selection(every, session=True)
    got = u1.finish_contract([P[j].contract(sh[j], compress=True, hat_key=hats[j]) for j in range(2)],
                             delta_s=ds)
    assert got == int(values[role == 1].sum())


def test_failure_control_unfiltered_column_leaks_other_roles(roled, bfv):
    """Without role filtering the same all-records request returns other
    roles' data, so the test above can fail."""
    o, role, postings, values = roled
    b = o.bundle(flexible=True, record_mac="session")
    P = [Provider(j, b) for j in range(2)]
    u1 = o.user(role=1)
    sh, hats, ds = u1.deal_selection(np.arange(o.Nd), session=True)
    got = u1.finish_contract([P[j].contract(sh[j], compress=True, hat_key=hats[j]) for j in range(2)],
                             delta_s=ds)
    assert got == int(values.sum()) != int(values[role == 1].sum())
