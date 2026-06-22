"""CR-SHE prototype: distributed private keyword search (2-party DPF over a
replicated, PRF-pseudonymous membership index) + homomorphic aggregates
(Paillier) over the matched records' encrypted fields.

Design (the composable, correct variant):
- Keyword w -> address alpha_w = PRF_K(w) mod N. The two providers hold the SAME
  plaintext membership index M (row alpha = bitmask of records containing that
  keyword). Pseudonymous addresses hide the keyword<->address map; the DPF hides
  WHICH address is queried (query privacy + access-pattern privacy).
- Record numeric fields are Paillier-encrypted; both providers hold them.
  Homomorphic aggregates run over the matched ciphertexts; only the DU decrypts.
"""
import hashlib, time
import dpf
from phe import paillier


# ---------- PRF-pseudonymous address ----------
def prf_addr(K: bytes, w: str, n: int) -> int:
    h = hashlib.sha256(K + w.encode()).digest()
    return int.from_bytes(h[:8], "big") % (1 << n)


# ---------- build a replicated membership index ----------
def build_index(K: bytes, keywords, n: int, n_records: int):
    """M[addr] = integer bitmask over records (bit r set if record r has the kw)."""
    M = [0] * (1 << n)
    addr_of = {}
    for w, recs in keywords.items():
        a = prf_addr(K, w, n)
        addr_of[w] = a
        mask = 0
        for r in recs:
            mask |= (1 << r)
        M[a] |= mask
    return M, addr_of


# ---------- distributed private search ----------
def search(K: bytes, w: str, M, n: int):
    """Returns (matched_record_ids, per_provider_time_s, key_bytes, answer_bytes)."""
    alpha = prf_addr(K, w, n)
    k0, k1 = dpf.gen(alpha, 1, n)            # DU side: one key per provider
    key_bytes = dpf.key_size_bytes(k0)
    N = 1 << n

    def provider(key):
        acc = 0
        for x in range(N):
            e = dpf.eval_point(key, x)
            if e:                              # weighted sum over the bitmask column
                acc = (acc + e * M[x]) & dpf.OUTMASK
        return acc

    t0 = time.perf_counter()
    s0 = provider(k0)
    t_prov = time.perf_counter() - t0          # one provider's wall time (they run in parallel)
    s1 = provider(k1)
    combined = (s0 + s1) & dpf.OUTMASK         # = M[alpha] = membership bitmask
    matched = [r for r in range(64) if (combined >> r) & 1]
    answer_bytes = 8                           # one OUTBITS word per provider
    return matched, t_prov, key_bytes, answer_bytes


# ---------- homomorphic aggregates over matched records ----------
def he_setup():
    return paillier.generate_paillier_keypair(n_length=2048)


def he_encrypt_fields(pub, values):
    return [pub.encrypt(int(v)) for v in values]


def he_aggregate(pub, cts, weights=None):
    """sum / weighted-sum (inner product) over Paillier ciphertexts. count is |cts|."""
    if weights is None:
        acc = cts[0]
        for c in cts[1:]:
            acc = acc + c
        return acc
    acc = cts[0] * int(weights[0])
    for c, wgt in zip(cts[1:], weights[1:]):
        acc = acc + c * int(wgt)
    return acc


if __name__ == "__main__":
    # end-to-end correctness check
    K = b"\x00" * 16
    n = 8
    kws = {"fever": [1, 5, 9], "cough": [2, 5], "asthma": [9]}
    M, addr = build_index(K, kws, n, n_records=16)
    matched, _, kb, ab = search(K, "fever", M, n)
    assert matched == [1, 5, 9], matched
    matched2, _, _, _ = search(K, "cough", M, n)
    assert matched2 == [2, 5], matched2
    print("search correctness: PASS", "key_bytes=", kb)

    pub, priv = he_setup()
    vals = [10, 20, 30]
    cts = he_encrypt_fields(pub, vals)
    s = priv.decrypt(he_aggregate(pub, cts))
    ip = priv.decrypt(he_aggregate(pub, cts, weights=[1, 2, 3]))
    assert s == 60 and ip == 10 + 40 + 90, (s, ip)
    print("HE aggregate correctness: PASS  (sum=%d, inner_product=%d)" % (s, ip))
