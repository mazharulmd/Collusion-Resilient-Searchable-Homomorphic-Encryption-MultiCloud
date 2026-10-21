"""Leveled BFV through OpenFHE, at the manuscript's parameters.

Plaintext modulus p (crshe.field.P), ring dimension 8,192, multiplicative
depth 1, 128-bit classical security. The 8,192 slots form two rows of
H = 4,096; OpenFHE's rotations act within each row. CR-SHE uses that shape:
row 0 carries a value column and row 1 its MAC column, so one ciphertext
returns both (Section 6.6 of the revised manuscript).
"""
import numpy as np
import openfhe as fhe

from . import field

RING_DIM = 8192


class BFV:
    def __init__(self, ring_dim=RING_DIM, depth=1, rotations=True, mult_keys=True):
        params = fhe.CCParamsBFVRNS()
        params.SetPlaintextModulus(field.P)
        params.SetMultiplicativeDepth(depth)
        params.SetRingDim(ring_dim)
        params.SetSecurityLevel(fhe.SecurityLevel.HEStd_128_classic)
        cc = fhe.GenCryptoContext(params)
        for feat in (fhe.PKESchemeFeature.PKE, fhe.PKESchemeFeature.KEYSWITCH,
                     fhe.PKESchemeFeature.LEVELEDSHE, fhe.PKESchemeFeature.ADVANCEDSHE):
            cc.Enable(feat)
        self.cc = cc
        self.slots = cc.GetRingDimension()
        self.half = self.slots // 2
        kp = cc.KeyGen()
        self.pk, self._sk = kp.publicKey, kp.secretKey
        if mult_keys:
            cc.EvalMultKeyGen(self._sk)
        if rotations:
            cc.EvalRotateKeyGen(self._sk, [1 << i for i in range(self.half.bit_length() - 1)])
            cc.EvalSumKeyGen(self._sk)

    # -- the secret key never leaves the owner / data user -----------------
    def secret_key(self):
        return self._sk

    def public_view(self):
        """What a provider receives: context, pk and evaluation keys, no sk."""
        return PublicBFV(self)

    # -- encoding -----------------------------------------------------------
    def encode(self, vec):
        v = np.zeros(self.slots, dtype=np.uint64)
        v[:len(vec)] = vec
        return self.cc.MakePackedPlaintext(field.to_signed(v).tolist())

    def encrypt(self, vec):
        return self.cc.Encrypt(self.pk, self.encode(vec))

    def decrypt(self, sk, ct, length=None):
        pt = self.cc.Decrypt(sk, ct)
        pt.SetLength(length or self.slots)
        return np.array(pt.GetPackedValue(), dtype=np.int64) % field.P


class PublicBFV:
    """Evaluation-side handle: everything a provider may hold."""

    def __init__(self, bfv):
        self.cc, self.pk = bfv.cc, bfv.pk
        self.slots, self.half = bfv.slots, bfv.half
        self.encode = bfv.encode
        self.encrypt = bfv.encrypt

    def decrypt(self, *_):
        raise PermissionError("providers hold no secret key")


def mul_plain(cc, ct, pt):
    return cc.EvalMult(ct, pt)


def add(cc, a, b):
    return b if a is None else cc.EvalAdd(a, b)


def segment_sum(cc, ct, seg):
    """After this, slot r*seg of each row holds the sum of slots
    [r*seg, (r+1)*seg) of that row. log2(seg) rotations."""
    step = 1
    while step < seg:
        ct = cc.EvalAdd(ct, cc.EvalRotate(ct, step))
        step <<= 1
    return ct


def full_sum(cc, ct, slots):
    """Sum over all slots of both rows (the submitted layout)."""
    return cc.EvalSum(ct, slots)


def compress(cc, ct):
    """Drop to a single RNS tower before sending; decryption is unchanged."""
    return cc.Compress(ct, 1)


def size_bytes(ct):
    return len(fhe.Serialize(ct, fhe.BINARY))
