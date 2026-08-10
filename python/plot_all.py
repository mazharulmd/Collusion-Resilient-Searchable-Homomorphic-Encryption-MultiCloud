#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Turn one corpus's results CSVs into the paper's figures.

One function per figure, each reading exactly one CSV.  When a reviewer asks
how a figure was produced, the answer is a single file and a single command.

  python3 python/plot_all.py --results bench/results/telemetry \\
      --figs Figures/telemetry
"""

import argparse
import csv
import os
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({
    "font.size": 8,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "figure.figsize": (3.5, 2.5),   # IEEE single column
    "savefig.bbox": "tight",
    "savefig.dpi": 300,
})


def read(path):
    if not os.path.exists(path):
        return None
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def save(fig, figs, name):
    os.makedirs(figs, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(figs, f"{name}.{ext}"))
    plt.close(fig)
    print(f"  wrote {figs}/{name}.pdf")


def fig_selection_latency(rows, figs):
    """Fig. 2 / E1: selection latency vs N, per thread count."""
    fig, ax = plt.subplots()
    series = defaultdict(list)
    for r in rows:
        if r["construction"] != "bgi16-tree":
            continue
        series[int(r["threads"])].append(
            (int(r["N"]), float(r["eval_ms_median"]),
             float(r["eval_ms_p25"]), float(r["eval_ms_p75"])))
    for t in sorted(series):
        pts = sorted(series[t])
        x = [p[0] for p in pts]
        y = [p[1] for p in pts]
        lo = [p[1] - p[2] for p in pts]
        hi = [p[3] - p[1] for p in pts]
        ax.errorbar(x, y, yerr=[lo, hi], marker="o", ms=3, capsize=2,
                    label=f"{t} core" + ("s" if t > 1 else ""))
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("index domain size $N$")
    ax.set_ylabel("selection latency (ms)")
    ax.legend(fontsize=6)
    save(fig, figs, "fig_selection_latency")


def fig_keysize(rows, figs):
    """Fig. 4 / E4: per-provider DPF key size vs N, for n in {2,3,4}."""
    fig, ax = plt.subplots()
    series = defaultdict(list)
    for r in rows:
        label = f"n={r['n_parties']} ({r['construction']})"
        series[label].append((int(r["N"]), int(r["key_bytes_max"])))
    for label in sorted(series):
        pts = sorted(set(series[label]))
        ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", ms=3,
                label=label)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("index domain size $N$")
    ax.set_ylabel("largest per-provider key (bytes)")
    ax.legend(fontsize=5)
    save(fig, figs, "fig_key_size")


def fig_aggregate(rows, figs):
    """Fig. 3 / E2: fast path vs general path, against N_d.

    The x-axis is N_d, not |S|: the whole point is that the cost no longer
    depends on the matched-set size.
    """
    fig, ax = plt.subplots()
    for path, style in (("fast", "o-"), ("general", "s--")):
        pts = sorted((int(r["Nd"]), float(r["provider_ms_median"]))
                     for r in rows
                     if r["path"] == path and float(r["provider_ms_median"]) > 0)
        if not pts:
            continue
        ax.plot([p[0] for p in pts], [p[1] for p in pts], style, ms=3,
                label={"fast": "fast path (precomputed $A_f$)",
                       "general": r"general path ($\Theta(N N_d)$)"}[path])
    skipped = [r for r in rows if r["path"] == "general"
               and r["note"].startswith("SKIPPED")]
    if skipped:
        ax.text(0.02, 0.95, f"general path skipped at $N_d\\geq${skipped[0]['Nd']}\n"
                            "(masked index exceeds RAM)",
                transform=ax.transAxes, fontsize=5, va="top")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("record count $N_d$")
    ax.set_ylabel("provider aggregate latency (ms)")
    ax.legend(fontsize=6)
    save(fig, figs, "fig_aggregate_latency")


def fig_baselines(rows, figs):
    """E5: CR-SHE against the five baselines, on the same corpus."""
    fig, ax = plt.subplots(figsize=(3.5, 2.2))
    items = [(r["baseline"], float(r["server_ms_median"]),
              r["extrapolated"] == "yes")
             for r in rows if float(r["server_ms_median"]) > 0]
    items.sort(key=lambda t: t[1])
    names = [i[0] for i in items]
    vals = [i[1] for i in items]
    colors = ["0.75" if i[2] else "0.35" for i in items]
    ax.barh(range(len(names)), vals, color=colors)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=6)
    ax.set_xscale("log")
    ax.set_xlabel("server-side latency per query (ms)")
    ax.text(0.98, 0.05, "light bars are extrapolated", transform=ax.transAxes,
            ha="right", fontsize=5)
    save(fig, figs, "fig_baselines")


def fig_scaling(rows, figs):
    """E8/E10: core scaling and sustained throughput."""
    e8 = [r for r in rows if r["experiment"] == "e8-core-scaling"]
    e10 = [r for r in rows if r["experiment"] == "e10-throughput"]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.4))
    if e8:
        pts = sorted((int(r["threads"]), float(r["latency_ms_median"])) for r in e8)
        base = pts[0][1] if pts else 1.0
        axes[0].plot([p[0] for p in pts], [base / p[1] for p in pts], "o-", ms=3,
                     label="measured")
        axes[0].plot([p[0] for p in pts], [p[0] / pts[0][0] for p in pts], "k:",
                     lw=0.8, label="linear")
        axes[0].set_xlabel("threads")
        axes[0].set_ylabel("speed-up over 1 thread")
        axes[0].legend(fontsize=6)
    if e10:
        pts = sorted((int(r["clients"]), float(r["queries_per_sec"])) for r in e10)
        axes[1].plot([p[0] for p in pts], [p[1] for p in pts], "s-", ms=3)
        axes[1].set_xlabel("concurrent clients")
        axes[1].set_ylabel("queries / s")
    save(fig, figs, "fig_scaling")


def fig_posting_cdf(rows, figs):
    """Fig. 5: CDF of posting-list sizes; characterises the corpus and sets
    the retrieval padding bound k_max."""
    lens = sorted(int(r["unmasked_weight"]) for r in rows)
    if not lens:
        return
    fig, ax = plt.subplots()
    n = len(lens)
    ax.step(lens, [(i + 1) / n for i in range(n)], where="post")
    ax.set_xscale("log")
    ax.set_xlabel("posting-list size")
    ax.set_ylabel("empirical CDF")
    med = lens[n // 2]
    ax.axvline(med, color="0.5", ls=":", lw=0.8)
    ax.text(med, 0.5, f" median {med}", fontsize=6)
    save(fig, figs, "fig_posting_cdf")


def fig_leakage(rows, figs):
    """E6: what index masking removes, as a function of how much the adversary
    already knows."""
    fig, ax = plt.subplots()
    series = defaultdict(list)
    for r in rows:
        series[r["index_variant"]].append(
            (float(r["aux_fraction"]),
             float(r["reidentification_pct_median"]),
             float(r["reidentification_pct_min"]),
             float(r["reidentification_pct_max"])))
    for label, style in (("unmasked", "o-"), ("masked (CR-SHE)", "s--")):
        pts = sorted(series.get(label, []))
        if not pts:
            continue
        x = [p[0] * 100 for p in pts]
        y = [max(p[1], 1e-3) for p in pts]
        lo = [max(p[1] - p[2], 0) for p in pts]
        hi = [max(p[3] - p[1], 0) for p in pts]
        ax.errorbar(x, y, yerr=[lo, hi], fmt=style, ms=3, capsize=2, label=label)
    if rows:
        ax.axhline(float(rows[0]["chance_pct"]), color="k", ls=":", lw=0.8)
        ax.text(0.02, float(rows[0]["chance_pct"]), " random guessing", fontsize=5,
                va="bottom", transform=ax.get_yaxis_transform())
    ax.set_yscale("log")
    ax.set_xlabel("adversary auxiliary knowledge (% of records seen)")
    ax.set_ylabel("tags re-identified (%)")
    ax.legend(fontsize=6)
    save(fig, figs, "fig_leakage_attack")


def fig_wan(rows, figs):
    """E3: end-to-end latency decomposition across the deployment."""
    if not rows:
        return
    import statistics
    comp = statistics.median(float(r["provider_compute_ms_max"]) for r in rows)
    tran = statistics.median(float(r["transport_ms"]) for r in rows)
    comb = statistics.median(float(r["client_combine_decrypt_ms"]) for r in rows)
    fig, ax = plt.subplots(figsize=(3.5, 1.6))
    left = 0
    for val, label, c in ((comp, "provider compute", "0.35"),
                          (tran, "wide-area transport", "0.6"),
                          (comb, "client combine+decrypt", "0.8")):
        ax.barh([0], [val], left=[left], color=c, label=f"{label} ({val:.1f} ms)")
        left += val
    ax.set_yticks([])
    ax.set_xlabel("end-to-end query latency (ms)")
    ax.legend(fontsize=5, loc="upper center", bbox_to_anchor=(0.5, -0.5), ncol=1)
    save(fig, figs, "fig_wan_breakdown")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="bench/results/telemetry")
    ap.add_argument("--figs", default="Figures/telemetry")
    a = ap.parse_args()

    jobs = [
        ("e1_dpf.csv", fig_selection_latency),
        ("e4_comm.csv", fig_keysize),
        ("e2_agg.csv", fig_aggregate),
        ("e5_baselines.csv", fig_baselines),
        ("e8_e10_scale.csv", fig_scaling),
        ("e6_index_stats.csv", fig_posting_cdf),
        ("e6_leakage.csv", fig_leakage),
        ("e3_wan.csv", fig_wan),
    ]
    # The homomorphic-scan baseline runs as its own binary (it is slow by
    # construction), so its row is merged in here rather than being a
    # separate figure.
    extra = {"e5_baselines.csv": "e5_fhe_scan.csv"}

    made = 0
    for name, fn in jobs:
        rows = read(os.path.join(a.results, name))
        if rows is not None and name in extra:
            more = read(os.path.join(a.results, extra[name]))
            if more:
                rows = rows + more
        if rows is None:
            print(f"  skip {name} (not found -- run the matching benchmark)")
            continue
        try:
            fn(rows, a.figs)
            made += 1
        except Exception as ex:               # a bad CSV should not kill the rest
            print(f"  FAILED on {name}: {ex}", file=sys.stderr)
    print(f"\n{made} figure(s) written to {a.figs}/")


if __name__ == "__main__":
    main()
