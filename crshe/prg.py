"""Pseudorandomness: the DPF's fixed-key AES generator and the PRF streams.

The DPF generator is Matyas-Meyer-Oseas over fixed-key AES-128,
G_k(s) = AES_k(s) XOR s, under three independent public keys (left child,
right child, output conversion), as in the manuscript (Section 9). All calls
are batched: one AES-ECB call per tree level, so the work runs in OpenSSL's
AES-NI code rather than in Python.

PRF streams (index mask, per-row MAC keys, n-party share expansion) are
AES-CTR under a secret key, with a 64-bit domain label and a 64-bit index in
the nonce. `uniform_zp` turns a stream into exactly uniform Z_p elements by
rejection sampling, which removes the N*N_d*2^-omega statistical term that
Theorem 2 of the submitted manuscript carried.
"""
import hashlib
import numpy as np
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from . import field

LAMBDA = 16  # bytes, 128-bit seeds


def _fixed_key(label):
    return hashlib.sha256(b"CR-SHE fixed AES key/" + label).digest()[:16]


_KEYS = {name: _fixed_key(name.encode()) for name in ("left", "right", "conv")}


def mmo(which, seeds):
    """G(s) = AES_k(s) XOR s for every row of `seeds` (shape (m,16) uint8)."""
    enc = Cipher(algorithms.AES(_KEYS[which]), modes.ECB()).encryptor()
    out = np.frombuffer(enc.update(seeds.tobytes()), dtype=np.uint8)
    return out.reshape(-1, LAMBDA) ^ seeds


# Domain labels keep the PRF streams for different purposes independent.
DOMAIN_MASK = 1
DOMAIN_ROWMAC = 2
DOMAIN_SHARE = 3


def stream_words(key, domain, index, count):
    """`count` pseudorandom 64-bit words from AES-CTR(key, domain || index)."""
    nonce = int(domain).to_bytes(8, "big") + int(index).to_bytes(8, "big")
    enc = Cipher(algorithms.AES(key), modes.CTR(nonce)).encryptor()
    raw = enc.update(bytes(8 * count))
    return np.frombuffer(raw, dtype="<u8").astype(np.uint64)


_CAND_MASK = np.uint64((1 << field.P_BITS) - 1)


def uniform_zp(key, domain, index, count):
    """`count` exactly uniform elements of Z_p (under the PRF assumption).

    Each 64-bit word is cut to P_BITS bits and kept only if below p, so every
    accepted value is uniform on [0, p). p is just above 2^36, so about half
    of the candidates survive; the stream is extended until enough have.
    """
    out = np.empty(0, dtype=np.uint64)
    drawn = 0
    while out.size < count:
        need = count - out.size
        batch = 2 * need + 64
        words = stream_words(key, domain, index, drawn + batch)[drawn:]
        drawn += batch
        cand = words & _CAND_MASK
        out = np.concatenate([out, cand[cand < np.uint64(field.P)]])
    return out[:count]
