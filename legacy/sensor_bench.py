"""CR-SHE homomorphic-aggregate benchmark on REAL sensor telemetry.
Uses the Mauna Loa weekly atmospheric CO2 series (bundled with statsmodels),
runs Paillier aggregates (sum / mean / inner product) over windows of |S|
matched telemetry records, and regenerates fig_compute_latency.pdf.

Run:  python3 sensor_bench.py
"""
import time, json, statistics, os
import numpy as np
import statsmodels.api as sm
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import crshe
from phe import paillier

# real environmental sensor stream (atmospheric CO2, ppm), as integer fixed-point (0.1 ppm)
vals_all = sm.datasets.co2.load_pandas().data["co2"].dropna().values
vals_all = np.round(vals_all * 10).astype(int)
print(f"CO2 sensor readings: {len(vals_all)}")

pub, priv = paillier.generate_paillier_keypair(n_length=2048)


def med(fn, reps):
    ts = []
    for _ in range(reps):
        s = time.perf_counter(); fn(); ts.append(time.perf_counter() - s)
    return statistics.median(ts)


rows = []
for S, reps in [(10, 5), (100, 5), (1000, 2)]:
    vals = vals_all[:S]
    cts = [pub.encrypt(int(v)) for v in vals]
    wts = [(i % 5) + 1 for i in range(S)]
    t_sum = med(lambda: crshe.he_aggregate(pub, cts), reps)

    def mean_op():
        c = crshe.he_aggregate(pub, cts); _ = priv.decrypt(c) / S
    t_mean = med(mean_op, reps)
    t_ip = med(lambda: crshe.he_aggregate(pub, cts, weights=wts), reps)
    rows.append({"S": S, "sum_ms": t_sum*1e3, "mean_ms": t_mean*1e3, "ip_ms": t_ip*1e3})
    print(f"[CO2 compute] |S|={S:>4} sum={t_sum*1e3:7.2f} mean={t_mean*1e3:7.2f} ip={t_ip*1e3:7.2f}")

json.dump({"sensor": "MaunaLoa_CO2_weekly", "readings": int(len(vals_all)),
           "compute_vs_S": rows}, open("results_sensor.json", "w"), indent=2)

Ss = [r["S"] for r in rows]
plt.rcParams.update({"font.size": 9, "figure.figsize": (4.2, 3.0)})
plt.figure()
plt.loglog(Ss, [r["sum_ms"] for r in rows], "o-", label="Sum")
plt.loglog(Ss, [r["mean_ms"] for r in rows], "s--", label="Mean")
plt.loglog(Ss, [r["ip_ms"] for r in rows], "^-.", label="Inner product")
plt.xlabel("Telemetry window $|S|$ (CO$_2$ sensor records)")
plt.ylabel("Compute latency (ms)")
plt.legend(); plt.grid(True, which="both", alpha=.3); plt.tight_layout()
os.makedirs("Figures", exist_ok=True)
plt.savefig(os.path.join("Figures", "fig_compute_latency.pdf"))
print("wrote results_sensor.json and saved figure to Figures/fig_compute_latency.pdf")