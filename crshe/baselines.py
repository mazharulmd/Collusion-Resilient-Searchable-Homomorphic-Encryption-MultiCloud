"""Baselines that the submitted manuscript did not evaluate.

single_server_*   The natural non-colluding-free alternative to the fast path:
                  ONE server holds the same encrypted precomputed columns A_f,
                  the user sends an encrypted one-hot selection vector, and
                  the server contracts ciphertext-by-ciphertext. It needs no
                  non-collusion assumption, so it is the comparison that says
                  what the multi-cloud trust split actually buys.
percell_*         A box without prefix sums: the table holds the cell
                  aggregates themselves and the user sends one point key per
                  cell of the box. One round and the same contraction, but
                  the number of keys is the volume of the box.
single_server_range_*
                  ONE server holds the same encrypted summed-area table and
                  the user sends the signed corner vector encrypted, laid out
                  like the table. No non-collusion assumption; the query is as
                  long as the cube.
nn_shared_*       The (n,n)-secret-shared store the submitted Section 6.2
                  claimed could answer DPF queries locally "in the clear".
                  It cannot: the answer is bilinear in the query and the
                  data, and the cross terms <e_j, S_k>, j != k, are held by
                  no single provider. This function computes what the local
                  answers actually sum to, so a test can show the error.
"""
import numpy as np

from . import dpf, field, he, rangeagg


def single_server_query(user, layout, tag):
    """User side: encrypt the one-hot selection, chunked like the columns."""
    alpha = user.D[tag]
    e = np.zeros(user.N, dtype=np.uint64)
    e[alpha] = 1
    H, seg = user.bfv.half, layout.seg
    cts = []
    for c in range(layout.chunks):
        lo, hi = c * seg, min((c + 1) * seg, user.N)
        v = np.zeros(user.bfv.slots, dtype=np.uint64)
        for r in range(len(layout.templates)):
            v[r * seg: r * seg + hi - lo] = e[lo:hi]
            v[H + r * seg: H + r * seg + hi - lo] = e[lo:hi]
        cts.append(user.bfv.encrypt(v))
    return cts


def single_server_answer(bundle, name, query, compress=False):
    """Server side: ciphertext-ciphertext contraction, then segment sum."""
    cc = bundle.he.cc
    layout, cols = bundle.fast[name]
    acc = None
    for ct, q in zip(cols, query):
        acc = he.add(cc, acc, cc.EvalMult(ct, q))
    acc = he.segment_sum(cc, acc, layout.seg)
    return he.compress(cc, acc) if compress else acc


def nn_shared_local_answers(column, alpha, n, rng):
    """Deal `column` as an (n,n) additive sharing, query alpha with an
    n-party DPF, and let each provider answer <e_j, S_j> locally.
    Returns (sum of the local answers, true value)."""
    N = len(column)
    shares = [rng.integers(0, field.P, N, dtype=np.uint64) for _ in range(n - 1)]
    last = np.asarray(column, dtype=np.uint64)
    for s in shares:
        last = field.sub(last, s)
    shares.append(last)
    keys = dpf.gen(alpha, N, n)
    total = 0
    for k, s in zip(keys, shares):
        total = (total + int(field.mul(k.eval_full(), s).sum(dtype=object))) % field.P
    return total, int(column[alpha]) % field.P


def cell_table(cells, dims, coeff):
    """Per-cell sums of `coeff`, flattened: the table before prefix sums."""
    flat = np.ravel_multi_index(tuple(np.asarray(cells).T), dims)
    cube = np.zeros(int(np.prod(dims)), dtype=np.int64)
    np.add.at(cube, flat, np.asarray(coeff, dtype=np.int64))
    return cube.astype(np.uint64)


def percell_token(layout, box, n):
    """One point key with output 1 for every cell of the box."""
    axes = [np.arange(lo, hi + 1) for lo, hi in box]
    grid = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, len(box))
    keys = [[] for _ in range(n)]
    for x in np.ravel_multi_index(tuple(grid.T), layout.dims):
        for j, k in enumerate(dpf.gen(int(x), layout.M, n)):
            keys[j].append(k)
    return keys


def percell_answer(public_he, layout, cts, keys, compress=False, pool=None):
    e = rangeagg._total(rangeagg.eval_keys(keys, pool))
    return rangeagg.contract(public_he, layout, cts, [(e, e)], compress)


def single_server_range_query(bfv, layout, box, delta_s=None):
    """User side: the signed corner vector, encrypted chunk by chunk in the
    table's own slot layout. With delta_s, row 1 carries delta_s times the
    vector, the single-server analogue of the per-query check (which a single
    server can defeat, see tests/test_rangeagg.py)."""
    e = np.zeros(layout.M, dtype=np.uint64)
    for _, x, beta in rangeagg.corners(box, layout.dims):
        if x is not None:
            e[x] = (int(e[x]) + beta) % field.P
    eh = e if delta_s is None else field.mul(e, np.uint64(delta_s))
    H, seg = bfv.half, layout.seg
    query = []
    for c in range(layout.chunks):
        lo, hi = c * seg, min((c + 1) * seg, layout.M)
        v = np.zeros(bfv.slots, dtype=np.uint64)
        for ti in range(len(layout.templates)):
            g = ti * seg
            v[g:g + hi - lo] = e[lo:hi]
            v[H + g:H + g + hi - lo] = eh[lo:hi]
        query.append(bfv.encrypt(v))
    return query


def single_server_range_answer(public_he, layout, cts, query, compress=False):
    """Server side: ciphertext-ciphertext contraction, then the segment sum."""
    cc = public_he.cc
    acc = None
    for ct, q in zip(cts, query):
        acc = he.add(cc, acc, cc.EvalMult(ct, q))
    acc = he.segment_sum(cc, acc, layout.seg)
    return he.compress(cc, acc) if compress else acc
