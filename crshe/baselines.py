"""Baselines that the submitted manuscript did not evaluate.

single_server_*   The natural non-colluding-free alternative to the fast path:
                  ONE server holds the same encrypted precomputed columns A_f,
                  the user sends an encrypted one-hot selection vector, and
                  the server contracts ciphertext-by-ciphertext. It needs no
                  non-collusion assumption, so it is the comparison that says
                  what the multi-cloud trust split actually buys.
nn_shared_*       The (n,n)-secret-shared store the submitted Section 6.2
                  claimed could answer DPF queries locally "in the clear".
                  It cannot: the answer is bilinear in the query and the
                  data, and the cross terms <e_j, S_k>, j != k, are held by
                  no single provider. This function computes what the local
                  answers actually sum to, so a test can show the error.
"""
import numpy as np

from . import dpf, field, he


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
