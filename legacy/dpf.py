"""Two-party Distributed Point Function (BGI16 GGM-tree construction).

Gen(alpha, beta, domain_bits) -> (k0, k1)
Eval(party, k, x) -> share in Z_{2^OUTBITS}
For all x:  Eval(0,k0,x) + Eval(1,k1,x)  ==  beta if x==alpha else 0  (mod 2^OUTBITS)

PRG is SHA256-based (portable, no native deps). Seeds are LAMBDA bytes.
Key size is O(domain_bits) correction words => O(lambda * log N), the succinct
property we want to measure for communication.
"""
import hashlib, os

LAMBDA = 16            # 128-bit seeds
OUTBITS = 64
OUTMASK = (1 << OUTBITS) - 1


def _prg(seed: bytes):
    """Expand a seed into (sL, tL, sR, tR): two child seeds + two control bits."""
    h = hashlib.sha512(seed).digest()      # 64 bytes
    sL = h[0:LAMBDA]
    sR = h[LAMBDA:2 * LAMBDA]
    tL = h[2 * LAMBDA] & 1
    tR = h[2 * LAMBDA + 1] & 1
    return sL, tL, sR, tR


def _xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def _convert(seed: bytes) -> int:
    """Map a seed to a group element in Z_{2^OUTBITS}."""
    return int.from_bytes(hashlib.sha256(seed).digest()[:8], "big") & OUTMASK


def _bit(x: int, i: int, n: int) -> int:
    """i-th bit from the MSB (i in 1..n)."""
    return (x >> (n - i)) & 1


def gen(alpha: int, beta: int, n: int):
    s0 = os.urandom(LAMBDA)
    s1 = os.urandom(LAMBDA)
    t0, t1 = 0, 1
    s = [s0, s1]
    t = [t0, t1]
    CW = []
    for i in range(1, n + 1):
        sL0, tL0, sR0, tR0 = _prg(s[0])
        sL1, tL1, sR1, tR1 = _prg(s[1])
        ai = _bit(alpha, i, n)
        if ai == 0:          # keep = Left, lose = Right
            sCW = _xor(sR0, sR1)
        else:                # keep = Right, lose = Left
            sCW = _xor(sL0, sL1)
        tLCW = tL0 ^ tL1 ^ ai ^ 1
        tRCW = tR0 ^ tR1 ^ ai
        CW.append((sCW, tLCW, tRCW))
        for b in (0, 1):
            sLb, tLb, sRb, tRb = (sL0, tL0, sR0, tR0) if b == 0 else (sL1, tL1, sR1, tR1)
            if ai == 0:
                sKeep, tKeep, tKeepCW = sLb, tLb, tLCW
            else:
                sKeep, tKeep, tKeepCW = sRb, tRb, tRCW
            if t[b]:
                sKeep = _xor(sKeep, sCW)
                tKeep = tKeep ^ tKeepCW
            s[b] = sKeep
            t[b] = tKeep
    # final correction so shares differ by beta at alpha
    conv0 = _convert(s[0])
    conv1 = _convert(s[1])
    sign = -1 if t[1] == 1 else 1
    CW_final = (sign * (beta - conv0 + conv1)) & OUTMASK
    k0 = (0, s0, CW, CW_final, n)
    k1 = (1, s1, CW, CW_final, n)
    return k0, k1


def eval_point(key, x: int) -> int:
    b, seed, CW, CW_final, n = key
    s = seed
    t = b
    for i in range(1, n + 1):
        sL, tL, sR, tR = _prg(s)
        sCW, tLCW, tRCW = CW[i - 1]
        if t:
            sL = _xor(sL, sCW); tL = tL ^ tLCW
            sR = _xor(sR, sCW); tR = tR ^ tRCW
        if _bit(x, i, n) == 0:
            s, t = sL, tL
        else:
            s, t = sR, tR
    val = (_convert(s) + (t * CW_final)) & OUTMASK
    return val if b == 0 else (-val) & OUTMASK


def key_size_bytes(key) -> int:
    _, seed, CW, _, _ = key
    return len(seed) + len(CW) * (LAMBDA + 1) + 8   # seed + CWs(sCW+bits) + final


if __name__ == "__main__":
    # exhaustive correctness test on small domains
    for n in (3, 6, 10):
        N = 1 << n
        alpha = (N // 3) + 1
        beta = 12345
        k0, k1 = gen(alpha, beta, n)
        ok = True
        for x in range(N):
            tot = (eval_point(k0, x) + eval_point(k1, x)) & OUTMASK
            expect = beta if x == alpha else 0
            if tot != expect:
                ok = False
                print(f"  MISMATCH n={n} x={x} got={tot} expect={expect}")
                break
        print(f"n={n} (N={N}): correctness={'PASS' if ok else 'FAIL'}, "
              f"key_size={key_size_bytes(k0)} bytes")
