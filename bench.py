import json, time, math, statistics, os
import dpf, crshe
from phe import paillier
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = {}
K = b"\x01" * 16


def bits_for(N):
    return max(1, math.ceil(math.log2(N)))


def median_time(fn, reps):
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter(); fn(); ts.append(time.perf_counter() - t0)
    return statistics.median(ts)


# ---- per-Paillier-op cost (for the pure-FHE proxy, extrapolated) ----
pub, priv = paillier.generate_paillier_keypair(n_length=2048)
_c = pub.encrypt(7)
t_he_op = median_time(lambda: _c + _c, 50)   # one homomorphic add
print(f"[calib] Paillier homomorphic op: {t_he_op*1e3:.3f} ms")

# ---- Table: search latency vs N (CR-SHE measured; plaintext scan measured;
#      pure-FHE proxy = N * t_he_op, EXTRAPOLATED) ----
search_rows = []
for N, reps in [(10**3, 5), (10**4, 3), (10**5, 1)]:
    n = bits_for(N)
    # build an index with N pseudonymous keywords, 64 records
    kws = {f"kw{i}": [i % 64] for i in range(N)}
    M, addr = crshe.build_index(K, kws, n, n_records=64)
    # CR-SHE: time ONE provider's full-domain eval (providers run in parallel)
    alpha = crshe.prf_addr(K, "kw7", n)
    k0, k1 = dpf.gen(alpha, 1, n)
    def crshe_search():
        acc = 0
        for x in range(N):
            e = dpf.eval_point(k0, x)
            if e: acc = (acc + e * M[x]) & dpf.OUTMASK
        return acc
    t_crshe = median_time(crshe_search, reps)
    # plaintext linear scan (no privacy) -- lower bound
    target = M[alpha]
    def plain_scan():
        hit = 0
        for x in range(N):
            if M[x] == target: hit ^= 1
        return hit
    t_plain = median_time(plain_scan, reps)
    t_fhe = N * t_he_op   # extrapolated pure-FHE-per-item proxy
    search_rows.append({"N": N, "crshe_ms": t_crshe*1e3,
                        "plain_ms": t_plain*1e3, "fhe_proxy_ms": t_fhe*1e3,
                        "dpf_key_bytes": dpf.key_size_bytes(k0)})
    print(f"[search] N={N:>6}  CR-SHE={t_crshe*1e3:9.2f} ms  "
          f"plain={t_plain*1e3:8.2f} ms  FHE-proxy(extrap)={t_fhe*1e3:11.1f} ms  "
          f"key={dpf.key_size_bytes(k0)}B")
OUT["search_vs_N"] = search_rows

# ---- Table: homomorphic-compute latency vs |S| ----
comp_rows = []
for S, reps in [(10, 10), (100, 5), (1000, 2)]:
    vals = list(range(1, S + 1))
    cts = crshe.he_encrypt_fields(pub, vals)
    w = [((i % 5) + 1) for i in range(S)]
    t_sum = median_time(lambda: crshe.he_aggregate(pub, cts), reps)
    # mean = sum then one decrypt + divide (client side); time = sum + decrypt
    def mean_op():
        c = crshe.he_aggregate(pub, cts); _ = priv.decrypt(c) / S
    t_mean = median_time(mean_op, reps)
    t_ip = median_time(lambda: crshe.he_aggregate(pub, cts, weights=w), reps)
    comp_rows.append({"S": S, "sum_ms": t_sum*1e3, "mean_ms": t_mean*1e3, "ip_ms": t_ip*1e3})
    print(f"[compute] |S|={S:>4}  sum={t_sum*1e3:8.2f} ms  mean={t_mean*1e3:8.2f} ms  "
          f"inner_prod={t_ip*1e3:8.2f} ms")
OUT["compute_vs_S"] = comp_rows

# ---- Communication vs n (2-party DPF measured; >2 needs multiparty DPF: future) ----
N0 = 10**4; n0 = bits_for(N0)
k0, _ = dpf.gen(123, 1, n0)
OUT["comm"] = {"N": N0, "n_providers": 2,
               "dpf_key_bytes_per_provider": dpf.key_size_bytes(k0),
               "answer_bytes_per_provider": 8,
               "note": "2-party DPF; n>2 requires a multiparty DPF (future work)."}
print(f"[comm] N={N0} n=2  key/provider={dpf.key_size_bytes(k0)}B  answer/provider=8B")

with open("results.json", "w") as f:
    json.dump({"paillier_op_ms": t_he_op*1e3, **OUT}, f, indent=2)

# ---- Figure: search latency vs N (log-log), CR-SHE vs FHE proxy ----
Ns = [r["N"] for r in search_rows]
plt.figure(figsize=(5, 3.4))
plt.loglog(Ns, [r["crshe_ms"] for r in search_rows], "o-", label="CR-SHE (measured)")
plt.loglog(Ns, [r["fhe_proxy_ms"] for r in search_rows], "s--", label="Pure-FHE proxy (extrap.)")
plt.loglog(Ns, [r["plain_ms"] for r in search_rows], "^:", label="Plaintext scan")
plt.xlabel("Index domain size N"); plt.ylabel("Search latency (ms)")
plt.legend(fontsize=8); plt.grid(True, which="both", alpha=0.3); plt.tight_layout()
os.makedirs("Figures", exist_ok=True)
plt.savefig(os.path.join("Figures", "search_latency.pdf"))
plt.savefig(os.path.join("Figures", "search_latency.png"), dpi=130)

print("\nWrote results.json, and saved figures to Figures/")