"""Frequency (volume) leakage-abuse attack against a replicated index.

The adversary sees one statistic per index row and holds auxiliary tag
frequencies from a similar deployment. It assigns each row to the tag whose
auxiliary frequency is nearest; a row counts as re-identified with weight
1/k when the true tag is among k equally near candidates, which is the
expected success of breaking ties at random.

Row statistics compared:
  unmasked      Hamming weight of the row: the posting-list length.
  padded(base)  length rounded up to the next power of `base`, the usual
                padding defence (base=2 gives next power of two).
  volume_hiding every row padded to the maximum length.
  masked        the CR-SHE index: the row is I[x] + P[x] over Z_p with P a
                one-time pad, so its sum is uniform on Z_p.

Auxiliary knowledge: true lengths binomially thinned to a sampled fraction f
of the records and rescaled by 1/f, so the attack is not handed the answer
unless f = 1 ("perfect auxiliary knowledge").
"""
import numpy as np

from . import field, prg


def pad_pow(lengths, base):
    L = np.maximum(np.asarray(lengths, dtype=np.float64), 1)
    return np.power(float(base), np.ceil(np.log(L) / np.log(base) - 1e-12)).astype(np.int64)


def observed(lengths, scheme, key=None, n_records=None, base=2):
    L = np.asarray(lengths, dtype=np.int64)
    if scheme == "unmasked":
        return L
    if scheme == "padded":
        return pad_pow(L, base)
    if scheme == "volume_hiding":
        return np.full_like(L, L.max())
    if scheme == "masked":
        # row sum of I'[x] = |row| + sum_i P[x][i] mod p, with the real PRF
        out = np.empty(len(L), dtype=np.int64)
        for x in range(len(L)):
            pad = prg.uniform_zp(key, prg.DOMAIN_MASK, x, n_records)
            s = int(pad.sum()) + int(L[x])     # < N_d * 2^37, fits in 64 bits
            out[x] = s % field.P
        return out
    raise ValueError(scheme)


def auxiliary(lengths, fraction, rng):
    L = np.asarray(lengths, dtype=np.int64)
    if fraction >= 1:
        return L.astype(np.float64)
    return rng.binomial(L, fraction) / fraction


def reidentify(obs, aux_view):
    """Per-row expected success of nearest-frequency assignment."""
    order = np.argsort(aux_view, kind="stable")
    sorted_aux = aux_view[order]
    succ = np.zeros(len(obs))
    for x, o in enumerate(obs):
        pos = np.searchsorted(sorted_aux, o)
        best = None
        for q in (pos - 1, pos):
            if 0 <= q < len(sorted_aux):
                d = abs(sorted_aux[q] - o)
                best = d if best is None else min(best, d)
        if best is None:
            continue
        lo = np.searchsorted(sorted_aux, o - best, side="left")
        hi = np.searchsorted(sorted_aux, o + best, side="right")
        cands = order[lo:hi]
        cands = cands[np.abs(aux_view[cands] - o) == best]
        if x in cands:
            succ[x] = 1.0 / len(cands)
    return succ


def run(lengths, classes, scheme, fraction=1.0, seed=0, key=None, n_records=None, base=2):
    """Re-identification rate overall and per tag class."""
    rng = np.random.default_rng(seed)
    aux = auxiliary(lengths, fraction, rng)
    obs = observed(lengths, scheme, key=key, n_records=n_records, base=base)
    # the adversary applies the same public transformation to its auxiliary data
    if scheme == "padded":
        aux_view = pad_pow(np.round(aux), base).astype(np.float64)
    elif scheme == "volume_hiding":
        aux_view = np.full(len(aux), float(np.max(aux)))
    else:
        aux_view = aux
    succ = reidentify(obs.astype(np.float64), aux_view)
    classes = np.asarray(classes)
    per = {c: float(succ[classes == c].mean()) for c in sorted(set(classes.tolist()))}
    return {"scheme": scheme, "fraction": fraction, "overall": float(succ.mean()),
            "per_class": per, "random_guess": 1.0 / len(lengths)}
