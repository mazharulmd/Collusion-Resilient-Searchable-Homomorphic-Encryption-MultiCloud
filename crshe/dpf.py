"""Distributed point functions over Z_p.

Two parties: the Boyle-Gilboa-Ishai GGM-tree construction (CCS 2016), with
output in the additive group Z_p, keys of O(lambda log N) bytes, and a
full-domain evaluation that walks the tree once, level by level.

More than two parties: the non-succinct additive sharing of a unit vector used
by the manuscript for n > 2. Parties 0..n-2 each hold a 16-byte seed whose PRF
expansion is their share; party n-1 holds the explicit difference vector.
Any n-1 parties miss at least one expansion, so the point is hidden under the
PRF assumption. This is multi-server PIR-style sharing, not succinct FSS.

For every x in [N]:  sum_j Eval(j, k_j, x) = beta if x == alpha else 0 (mod p).
"""
import os
from dataclasses import dataclass

import numpy as np

from . import field, prg

LAMBDA = prg.LAMBDA


def depth_for(N):
    return max(1, (N - 1).bit_length())


def _split(blocks):
    """Control bit = LSB of the first byte; clear it in the seed."""
    t = (blocks[:, 0] & 1).astype(np.uint8)
    s = blocks.copy()
    s[:, 0] &= 0xFE
    return s, t


def _expand(seeds):
    sL, tL = _split(prg.mmo("left", seeds))
    sR, tR = _split(prg.mmo("right", seeds))
    return sL, tL, sR, tR


def _convert(seeds):
    return field.from_bytes128(prg.mmo("conv", seeds))


@dataclass
class TreeKey:
    party: int
    seed: np.ndarray        # (1,16) uint8
    cw_seed: np.ndarray     # (depth,16) uint8
    cw_tl: np.ndarray       # (depth,) uint8
    cw_tr: np.ndarray       # (depth,) uint8
    cw_out: int             # element of Z_p
    depth: int
    N: int

    def size_bytes(self):
        # root seed + per level (seed CW + two control bits in one byte)
        # + output CW (ceil(37/8) = 5 bytes) + domain depth (1 byte)
        return LAMBDA + self.depth * (LAMBDA + 1) + (field.P_BITS + 7) // 8 + 1

    def eval_full(self):
        return _tree_eval_full(self)


def _bits_msb(x, depth):
    return [(x >> (depth - 1 - i)) & 1 for i in range(depth)]


def gen2(alpha, N, beta=1):
    """Two-party DPF keys for f_{alpha,beta} on domain [N]."""
    if not 0 <= alpha < N:
        raise ValueError("alpha outside the domain")
    depth = depth_for(N)
    s = [np.frombuffer(os.urandom(LAMBDA), dtype=np.uint8).reshape(1, LAMBDA).copy()
         for _ in range(2)]
    for b in range(2):
        s[b][0, 0] &= 0xFE
    roots = [x.copy() for x in s]
    t = [0, 1]
    cw_seed = np.zeros((depth, LAMBDA), dtype=np.uint8)
    cw_tl = np.zeros(depth, dtype=np.uint8)
    cw_tr = np.zeros(depth, dtype=np.uint8)
    for i, a in enumerate(_bits_msb(alpha, depth)):
        ex = [_expand(s[b]) for b in range(2)]
        (sL0, tL0, sR0, tR0), (sL1, tL1, sR1, tR1) = ex
        lose0, lose1 = (sR0, sR1) if a == 0 else (sL0, sL1)
        scw = lose0 ^ lose1
        tlcw = int(tL0[0] ^ tL1[0] ^ a ^ 1)
        trcw = int(tR0[0] ^ tR1[0] ^ a)
        cw_seed[i], cw_tl[i], cw_tr[i] = scw[0], tlcw, trcw
        for b in range(2):
            sL, tL, sR, tR = ex[b]
            keep_s, keep_t, keep_cw = (sL, int(tL[0]), tlcw) if a == 0 else (sR, int(tR[0]), trcw)
            if t[b]:
                keep_s = keep_s ^ scw
                keep_t ^= keep_cw
            s[b], t[b] = keep_s, keep_t
    c0 = int(_convert(s[0])[0])
    c1 = int(_convert(s[1])[0])
    out = (beta - c0 + c1) % field.P
    if t[1]:
        out = (-out) % field.P
    return tuple(TreeKey(b, roots[b], cw_seed, cw_tl, cw_tr, out, depth, N) for b in range(2))


def _tree_eval_full(key):
    depth, N = key.depth, key.N
    s = key.seed.copy()
    t = np.array([key.party], dtype=np.uint8)
    for i in range(depth):
        sL, tL, sR, tR = _expand(s)
        corr = t.astype(bool)
        sL[corr] ^= key.cw_seed[i]
        sR[corr] ^= key.cw_seed[i]
        tL = tL ^ (t & key.cw_tl[i])
        tR = tR ^ (t & key.cw_tr[i])
        m = s.shape[0]
        s = np.empty((2 * m, LAMBDA), dtype=np.uint8)
        s[0::2], s[1::2] = sL, sR
        t = np.empty(2 * m, dtype=np.uint8)
        t[0::2], t[1::2] = tL, tR
        # keep only the subtrees that cover [0, N)
        keep = -(-N // (1 << (depth - 1 - i)))
        s, t = s[:keep], t[:keep]
    vals = field.add(_convert(s), field.mul(t.astype(np.uint64), np.uint64(key.cw_out)))
    return field.neg(vals) if key.party == 1 else vals


def eval_point(key, x):
    """Single-point evaluation, used by the exhaustive tests."""
    s = key.seed.copy()
    t = key.party
    for i, bit in enumerate(_bits_msb(x, key.depth)):
        sL, tL, sR, tR = _expand(s)
        if t:
            sL = sL ^ key.cw_seed[i]
            sR = sR ^ key.cw_seed[i]
            tL = tL ^ key.cw_tl[i]
            tR = tR ^ key.cw_tr[i]
        s, t = (sL, int(tL[0])) if bit == 0 else (sR, int(tR[0]))
    v = (int(_convert(s)[0]) + t * key.cw_out) % field.P
    return (-v) % field.P if key.party == 1 else v


@dataclass
class SeedKey:
    """Light key of the n-party sharing: a PRF seed."""
    party: int
    seed: bytes
    N: int

    def size_bytes(self):
        return LAMBDA

    def eval_full(self):
        return prg.uniform_zp(self.seed, prg.DOMAIN_SHARE, 0, self.N)


@dataclass
class VectorKey:
    """Heavy key of the n-party sharing: the explicit difference vector."""
    party: int
    vec: np.ndarray
    N: int

    def size_bytes(self):
        return field.WORD_BYTES * self.N

    def eval_full(self):
        return self.vec


def gen_additive(alpha, N, n, beta=1):
    """n-party additive sharing of beta * e_alpha over Z_p, n >= 2."""
    if not 0 <= alpha < N:
        raise ValueError("alpha outside the domain")
    light = [SeedKey(j, os.urandom(LAMBDA), N) for j in range(n - 1)]
    acc = np.zeros(N, dtype=np.uint64)
    for k in light:
        acc = field.add(acc, k.eval_full())
    target = np.zeros(N, dtype=np.uint64)
    target[alpha] = beta % field.P
    return light + [VectorKey(n - 1, field.sub(target, acc), N)]


def gen(alpha, N, n, beta=1):
    """Succinct tree keys for n == 2, the non-succinct sharing for n > 2."""
    return list(gen2(alpha, N, beta)) if n == 2 else gen_additive(alpha, N, n, beta)


def share_vector(v, n):
    """Additive n-sharing of an arbitrary vector over Z_p, compressed the same
    way: n-1 seeds and one explicit vector. Used by the flexible path."""
    keys = gen_additive(0, len(v), n, beta=0)
    acc = np.zeros(len(v), dtype=np.uint64)
    for k in keys[:-1]:
        acc = field.add(acc, k.eval_full())
    keys[-1] = VectorKey(n - 1, field.sub(np.asarray(v, dtype=np.uint64) % np.uint64(field.P), acc), len(v))
    return keys
