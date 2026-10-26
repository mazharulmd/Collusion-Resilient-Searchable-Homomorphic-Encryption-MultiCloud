"""Draw the leakage figure of the v5 manuscript from results/leakage_{telemetry,beijing}.json,
so no point is transcribed by hand. Overall re-identification rate against the adversary's
auxiliary knowledge, one panel per corpus, four index representations."""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "paper", "v5", "Figures", "fig_leakage_reference.pdf")

# categorical slots 1-4 of the validated default palette, fixed order; each series also
# has its own marker so identity never rests on colour alone
SERIES = [("unmasked", "Unmasked", "#2a78d6", "o", "full"),
          ("padded", "Power-of-two padding", "#eb6834", "s", "full"),
          ("volume_hiding", "Volume-hiding padding", "#1baf7a", "^", "full"),
          ("masked", "CR-SHE masked index", "#eda100", "D", "none")]
CORPORA = [("telemetry", "Primary corpus (telemetry)"), ("beijing", "Second corpus (Beijing)")]

plt.rcParams.update({"font.size": 8, "axes.edgecolor": "#8a8a85", "axes.linewidth": 0.6,
                     "xtick.color": "#4a4a46", "ytick.color": "#4a4a46"})
fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.5), sharey=True)
for ax, (corpus, title) in zip(axes, CORPORA):
    with open(os.path.join(ROOT, "results", f"leakage_{corpus}.json")) as f:
        runs = json.load(f)["runs"]
    rand = runs[0]["random_guess"]
    ax.axhline(100 * rand, color="#8a8a85", lw=1, ls=(0, (4, 3)), zorder=1)
    ax.text(0.0105, 100 * rand * 1.25, "random guessing", color="#4a4a46", fontsize=7)
    for key, label, colour, marker, fill in SERIES:
        pts = sorted((r["fraction"], 100 * r["overall"]) for r in runs if r["scheme"] == key)
        xs, ys = zip(*pts)
        # the masked and volume-hiding lines coincide at random guessing; draw masked
        # thinner and hollow on top so both stay visible
        ax.plot(xs, ys, color=colour, lw=2 if key != "masked" else 1, marker=marker,
                ms=6 if key != "masked" else 7, fillstyle=fill,
                markeredgewidth=1.4, label=label, zorder=3 if key != "masked" else 4)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_title(title, fontsize=8, color="#1f1f1d")
    ax.set_xlabel("Auxiliary knowledge: sampled fraction $f$ of records")
    ax.grid(True, which="major", color="#e6e5e0", lw=0.5)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
axes[0].set_ylabel("Tags re-identified (%)")
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, fontsize=7,
           bbox_to_anchor=(0.5, 1.04))
fig.tight_layout(rect=(0, 0, 1, 0.92))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
fig.savefig(OUT)
fig.savefig(OUT.replace(".pdf", ".png"), dpi=160)
print("wrote", os.path.relpath(OUT, ROOT))
