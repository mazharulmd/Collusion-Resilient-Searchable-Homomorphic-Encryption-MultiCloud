"""Arithmetic in Z_p, the single ring shared by the DPF, the index mask and BFV.

Lemma 1 of the manuscript requires the DPF output group and the homomorphic
plaintext ring to be the same Z_p. This module is the only place the modulus
is defined, and every other module imports it from here, so a DPF over
Z_{2^k} composed with an unrelated plaintext modulus cannot be written.

Values are numpy uint64 arrays holding canonical representatives in [0, p).
p is a 37-bit prime, so a product of two residues does not fit in 64 bits;
`mul` splits one operand into limbs to stay exact.
"""
import numpy as np

# 37-bit prime, p = 1 mod 2^17, so BFV batching works for every ring
# dimension up to 65,536. Same value as the manuscript (Section 9).
P = 68_724_326_401
P_BITS = P.bit_length()          # 37
WORD_BYTES = 8                   # a residue is stored in one 64-bit word

_P = np.uint64(P)
_LIMB = 19
_LIMB_MASK = np.uint64((1 << _LIMB) - 1)
_SHIFT = np.uint64(_LIMB)


def add(a, b):
    s = a + b                    # < 2^38, no overflow
    return np.where(s >= _P, s - _P, s)


def sub(a, b):
    return np.where(a >= b, a - b, a + _P - b)


def neg(a):
    return np.where(a == 0, a, _P - a)


def mul(a, b):
    """Exact a*b mod p for residues a, b < p (arrays or broadcastable scalars)."""
    a = np.asarray(a, dtype=np.uint64)
    b = np.asarray(b, dtype=np.uint64)
    b0 = b & _LIMB_MASK          # < 2^19
    b1 = b >> _SHIFT             # < 2^18
    lo = (a * b0) % _P           # a*b0 < 2^56
    hi = (a * b1) % _P           # a*b1 < 2^55
    hi = (hi << _SHIFT) % _P     # < 2^56
    return add(lo, hi)


def reduce_u64(x):
    return np.asarray(x, dtype=np.uint64) % _P


def from_bytes128(blocks):
    """Map 16-byte blocks (shape (m,16) uint8) to Z_p by reducing the 128-bit
    integer mod p. Statistical distance from uniform is below p / 2^128."""
    words = blocks.reshape(-1, 2, 8)
    hi = words[:, 0, :].copy().view(">u8").reshape(-1).astype(np.uint64)
    lo = words[:, 1, :].copy().view(">u8").reshape(-1).astype(np.uint64)
    two64 = np.uint64((1 << 64) % P)
    return add(mul(hi % _P, two64), lo % _P)


def to_signed(a):
    """Centred representatives in (-p/2, p/2], as BFV encoders expect."""
    a = np.asarray(a, dtype=np.int64)
    return np.where(a > P // 2, a - P, a)


def check_magnitude(values, weights=None):
    """Lemma 1 magnitude bound: sum |w_i m_i| < p. Raises instead of wrapping."""
    v = np.abs(np.asarray(values, dtype=object))
    if weights is not None:
        v = v * np.abs(np.asarray(weights, dtype=object))
    total = int(v.sum())
    if total >= P:
        raise ValueError(f"aggregate bound {total} >= p = {P}: would wrap mod p")
    return total
