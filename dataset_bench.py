"""CR-SHE evaluation on the real Reuters-21578 corpus (NLTK).
Builds a real keyword index + posting lists + real per-document numeric fields,
then measures: (1) search latency vs N, (2) HE-compute latency vs |S|,
(3) communication vs N, (4) real posting-list size distribution. Emits 4 PDFs.
"""
import re, json, time, math, statistics, os
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nltk
nltk.download("reuters", quiet=True)   # auto-fetch corpus on first run
from nltk.corpus import reuters
import dpf, crshe
from phe import paillier

TOK = re.compile(r"[a-z]{3,}")

# ---------- build real index from Reuters ----------
docs = reuters.fileids()
postings = {}                 # keyword -> set(doc_index)
doc_len = []                  # real numeric field per doc: token count
for i, d in enumerate(docs):
    toks = TOK.findall(reuters.raw(d).lower())
    doc_len.append(len(toks))
    for w in set(toks):
        postings.setdefault(w, set()).add(i)
# keep keywords appearing in >=2 docs (meaningful vocabulary)
vocab = sorted(w for w, s in postings.items() if len(s) >= 2)
N_total = len(vocab)
print(f"corpus: {len(docs)} docs, vocabulary (>=2 docs): {N_total} keywords")

K = b"\x02" * 16
res = {"corpus_docs": len(docs), "vocab": N_total}

# ---------- calibrate one Paillier op (FHE proxy) ----------
pub, priv = paillier.generate_paillier_keypair(n_length=2048)
c = pub.encrypt(7)
t_he = statistics.median(_t for _t in (
    (lambda: (lambda s=time.perf_counter(): (c + c, time.perf_counter() - s)[1])())()
    for _ in range(40)))
print(f"Paillier op: {t_he*1e3:.3f} ms")

# ---------- (1) search latency vs N ----------
def median_time(fn, reps):
    ts = []
    for _ in range(reps):
        s = time.perf_counter(); fn(); ts.append(time.perf_counter() - s)
    return statistics.median(ts)

search_rows = []
N_list = [(1000, 5), (10000, 3), (N_total, 1)]
for N, reps in N_list:
    n = max(1, math.ceil(math.log2(N)))
    kws = vocab[:N]
    # pseudonymous index: address -> 64-bucket membership of its posting list
    M = [0] * (1 << n)
    for w in kws:
        a = crshe.prf_addr(K, w, n)
        mask = 0
        for r in postings[w]:
            mask |= (1 << (r % 64))
        M[a] |= mask
    alpha = crshe.prf_addr(K, kws[7], n)
    k0, _ = dpf.gen(alpha, 1, n)
    def crshe_search():
        acc = 0
        for x in range(N):
            e = dpf.eval_point(k0, x)
            if e: acc = (acc + e * M[x]) & dpf.OUTMASK
        return acc
    t_crshe = median_time(crshe_search, reps)
    tgt = M[alpha]
    t_plain = median_time(lambda: sum(1 for x in range(N) if M[x] == tgt), reps)
    search_rows.append({"N": N, "crshe_ms": t_crshe*1e3, "plain_ms": t_plain*1e3,
                        "fhe_proxy_ms": N*t_he*1e3, "dpf_key_bytes": dpf.key_size_bytes(k0)})
    print(f"[search] N={N:>6} CR-SHE={t_crshe*1e3:9.1f}ms plain={t_plain*1e3:7.2f}ms "
          f"FHE~{N*t_he*1e3:9.1f}ms key={dpf.key_size_bytes(k0)}B")
res["search_vs_N"] = search_rows

# ---------- (2) HE compute latency vs real |S| ----------
sizes = sorted(len(s) for s in postings.values())
def kw_with_postings(target):
    best = min(vocab, key=lambda w: abs(len(postings[w]) - target))
    return best, sorted(postings[best])
comp_rows = []
for target in (10, 100, 1000):
    w, recs = kw_with_postings(target)
    S = len(recs)
    vals = [doc_len[r] for r in recs]                  # real numeric field
    cts = [pub.encrypt(int(v)) for v in vals]
    wts = [(r % 5) + 1 for r in recs]
    t_sum = median_time(lambda: crshe.he_aggregate(pub, cts), 5 if S < 500 else 2)
    def mean_op():
        cc = crshe.he_aggregate(pub, cts); _ = priv.decrypt(cc) / S
    t_mean = median_time(mean_op, 5 if S < 500 else 2)
    t_ip = median_time(lambda: crshe.he_aggregate(pub, cts, weights=wts), 5 if S < 500 else 2)
    comp_rows.append({"keyword": w, "S": S, "sum_ms": t_sum*1e3,
                      "mean_ms": t_mean*1e3, "ip_ms": t_ip*1e3})
    print(f"[compute] kw='{w}' |S|={S:>4} sum={t_sum*1e3:7.2f} mean={t_mean*1e3:7.2f} ip={t_ip*1e3:7.2f}")
res["compute_vs_S"] = comp_rows

with open("results_real.json", "w") as f:
    json.dump({"paillier_op_ms": t_he*1e3, **res}, f, indent=2)

# ================= FIGURES =================
plt.rcParams.update({"font.size": 9, "figure.figsize": (4.2, 3.0)})

# --- NEW: Ensure the Figures folder exists ---
import os
os.makedirs("Figures", exist_ok=True)

# Fig 1: search latency vs N
Ns = [r["N"] for r in search_rows]
plt.figure()
plt.loglog(Ns, [r["crshe_ms"] for r in search_rows], "o-", label="CR-SHE (measured)")
plt.loglog(Ns, [r["fhe_proxy_ms"] for r in search_rows], "s--", label="Pure-FHE proxy")
plt.loglog(Ns, [r["plain_ms"] for r in search_rows], "^:", label="Plaintext scan")
plt.xlabel("Index domain size $N$ (Reuters vocabulary)"); plt.ylabel("Search latency (ms)")
plt.legend(); plt.grid(True, which="both", alpha=.3); plt.tight_layout()
plt.savefig(os.path.join("Figures", "fig_search_latency.pdf")); plt.close()

# Fig 2: HE compute latency vs |S|
Ss = [r["S"] for r in comp_rows]
plt.figure()
plt.loglog(Ss, [r["sum_ms"] for r in comp_rows], "o-", label="Sum")
plt.loglog(Ss, [r["mean_ms"] for r in comp_rows], "s--", label="Mean")
plt.loglog(Ss, [r["ip_ms"] for r in comp_rows], "^-.", label="Inner product")
plt.xlabel("Result-set size $|S|$"); plt.ylabel("Compute latency (ms)")
plt.legend(); plt.grid(True, which="both", alpha=.3); plt.tight_layout()
plt.savefig(os.path.join("Figures", "fig_compute_latency.pdf")); plt.close()

# Fig 3: communication (DPF key size) vs N
plt.figure()
plt.semilogx(Ns, [r["dpf_key_bytes"] for r in search_rows], "D-", color="purple")
plt.xlabel("Index domain size $N$"); plt.ylabel("DPF key size / provider (bytes)")
plt.grid(True, which="both", alpha=.3); plt.tight_layout()
plt.savefig(os.path.join("Figures", "fig_communication.pdf")); plt.close()

# Fig 4: real posting-list size distribution (CDF)
arr = np.array(sizes)
xs = np.sort(arr); ys = np.arange(1, len(xs)+1)/len(xs)
plt.figure()
plt.semilogx(xs, ys, "-", color="teal")
plt.xlabel("Keyword posting-list size $|S|$ (Reuters)"); plt.ylabel("CDF")
plt.grid(True, which="both", alpha=.3); plt.tight_layout()
plt.savefig(os.path.join("Figures", "fig_posting_cdf.pdf")); plt.close()

res["posting_stats"] = {"min": int(arr.min()), "median": int(np.median(arr)),
                        "mean": float(arr.mean()), "max": int(arr.max())}
print("posting-list sizes: median=%d mean=%.1f max=%d" %
      (np.median(arr), arr.mean(), arr.max()))

with open("results_real.json", "w") as f:
    json.dump({"paillier_op_ms": t_he*1e3, **res}, f, indent=2)

print("\nWrote results_real.json and 4 figures inside Figures/")