"""Draw the result figures of the JNCA manuscript from results/*.json, so no point
is transcribed by hand. Writes vector PDFs to paper/jnca/figures/.

Palette: categorical slots 1-4 of the validated default palette, in fixed order;
every series also has its own marker or fill, so identity never rests on colour.
"""
import csv
import gzip
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "paper", "jnca", "figures")
os.makedirs(OUT, exist_ok=True)
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
BLUE_LIGHT, ORANGE_LIGHT = "#9ec5f4", "#f6b89c"
INK, MUTED, GRID = "#1f1f1d", "#4a4a46", "#e6e5e0"
RAMP = ["#ffffff", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({"font.size": 8, "axes.edgecolor": "#8a8a85", "axes.linewidth": 0.6,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.labelcolor": INK,
                     "legend.frameon": False, "legend.fontsize": 7})


def load(name):
    with open(os.path.join(ROOT, "results", name)) as f:
        return json.load(f)


def style(ax, grid_axis="y"):
    ax.grid(True, axis=grid_axis, color=GRID, lw=0.5)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def save(fig, name):
    fig.savefig(os.path.join(OUT, name + ".pdf"))
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=160)
    plt.close(fig)
    print("wrote", name)


def ms(t):
    return t["median_ms"]


# 1. posting-list length distribution of both datasets --------------------------
fig, ax = plt.subplots(figsize=(3.4, 2.3))
for corpus, label, colour, ls in (("telemetry", "Telemetry", BLUE, "-"), ("beijing", "Beijing", ORANGE, "--")):
    with gzip.open(os.path.join(ROOT, "results", f"lengths_{corpus}.csv.gz"), "rt") as f:
        L = np.sort(np.array([int(r["length"]) for r in csv.DictReader(f)]))
    ccdf = 1.0 - np.arange(len(L)) / len(L)
    ax.step(L, ccdf, where="post", color=colour, lw=2, ls=ls, label=f"{label} ({len(L):,} tags)")
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlabel("Posting-list length (records per tag)")
ax.set_ylabel("Fraction of tags with length ≥ x")
ax.legend(loc="lower left")
style(ax, "both")
fig.tight_layout()
save(fig, "fig_postings")

# 2. range aggregation on the real cubes, per provider ------------------------------
fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.5), sharey=True)
for ax, (fname, title, unit) in zip(axes, (("range_real_telemetry.json", "Telemetry cube (345,690 cells)", "min"),
                                           ("range_real_beijing_day.json", "Beijing cube (192,852 cells)", "d"))):
    d = load(fname)
    cb, se = d["modes"]["combined"]["by_window"], d["modes"]["session"]["by_window"]
    x = np.arange(len(cb))
    w = 0.38
    for off, rows, dark, light, name in ((-w / 2, cb, BLUE, BLUE_LIGHT, "Combined"),
                                         (w / 2, se, ORANGE, ORANGE_LIGHT, "Verified")):
        dpf = np.array([ms(r["dpf_eval_all_keys"]) for r in rows])
        tot = np.array([ms(r["provider_total"]) for r in rows])
        ax.bar(x + off, dpf, w * 0.92, color=dark, label=f"{name}: DPF evaluation")
        ax.bar(x + off, tot - dpf, w * 0.92, bottom=dpf, color=light, edgecolor=dark, lw=0.6, hatch="///",
               label=f"{name}: homomorphic part")
    ax.set_xticks(x, [f"{r['window']:,}" for r in cb])
    ax.set_title(title, fontsize=8, color=INK)
    ax.set_xlabel("Window length L (minutes)" if unit == "min" else "Window length L (days)")
    style(ax)
axes[0].set_ylabel("Per-provider time (ms)")
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.0))
fig.tight_layout(rect=(0, 0, 1, 0.84))
save(fig, "fig_range_real")

# 3. layouts on the synthetic cube, and cube size ---------------------------------
ra, rs = load("range_aggregation.json"), load("range_session.json")
fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.6, 2.4))
wins = [r["window_minutes"] for r in ra["modes"]["combined"]["by_window"]]
x = np.arange(len(wins))
for k, (rows, colour, marker, name) in enumerate(((ra["modes"]["per_corner"]["by_window"], AQUA, "s", "Per-corner keys"),
                                                  (rs["modes"]["session"]["by_window"], ORANGE, "D", "Verified (session)"),
                                                  (ra["modes"]["combined"]["by_window"], BLUE, "o", "Combined"))):
    a1.plot(x, [ms(r["provider_total"]) / 1000 for r in rows], color=colour, marker=marker, lw=2, ms=6, label=name)
a1.set_xticks(x, [f"{w:,}" for w in wins])
a1.set_xlabel("Window length L (min)")
a1.set_ylabel("Per-provider time (s)")
a1.set_ylim(0, 4.6)
a1.set_title("Layouts, synthetic cube (345,690 cells)", fontsize=8, color=INK)
a1.legend(loc="upper center", ncol=3, fontsize=6.5)
style(a1)
sc = ra["cube_scaling"]
M = [r["M"] for r in sc]
a2.plot(M, [ms(r["provider_total"]) for r in sc], color=BLUE, marker="o", lw=2, ms=6, label="Provider total")
a2.plot(M, [ms(r["dpf_eval_all_corners"]) for r in sc], color=ORANGE, marker="s", lw=2, ms=6, ls="--",
        label="DPF evaluation")
a2.set_xscale("log")
a2.set_yscale("log")
a2.set_xlabel("Cube size M (cells)")
a2.set_ylabel("Per-provider time (ms)")
a2.set_title("Cube size, combined layout, d = 2", fontsize=8, color=INK)
a2.legend(loc="upper left")
style(a2, "both")
fig.tight_layout()
save(fig, "fig_range_layouts")

# 4. tamper detection: wrong answers accepted, by path, check and deviation --------
v = load("verification_modes.json")["results"]
ROWS = [("fast", "global", "Keyword: one key"), ("fast", "row", "Keyword: per-row keys"),
        ("fast", "session", "Keyword: session"), ("range", "combined", "Range: one key"),
        ("range", "per_corner", "Range: per-cell keys"), ("range", "session", "Range: session"),
        ("flexible", "global", "Flexible: one key"), ("flexible", "session", "Flexible: session"),
        ("retrieval", "width_only", "Retrieval: width check"), ("retrieval", "session", "Retrieval: session")]
KINDS = [("inconsistent", "Constant"), ("dense", "Uniform"), ("scale", "Scale"),
         ("random_point", "Random\npoint"), ("hidden_point", "Queried\npoint")]
A = np.array([[v[p][m][k]["undetected_wrong"] / 200 for k, _ in KINDS] for p, m, _ in ROWS])
fig, ax = plt.subplots(figsize=(4.6, 3.1))
cmap = matplotlib.colors.LinearSegmentedColormap.from_list("blue", RAMP)
im = ax.imshow(A, cmap=cmap, vmin=0, vmax=1, aspect="auto")
for i, (p, m, _) in enumerate(ROWS):
    for j, (k, _) in enumerate(KINDS):
        c = v[p][m][k]
        ax.text(j, i, f"{c['detected']}/{c['undetected_wrong']}", ha="center", va="center", fontsize=6.5,
                color="white" if A[i, j] > 0.5 else INK)
ax.set_xticks(range(len(KINDS)), [n for _, n in KINDS])
ax.set_yticks(range(len(ROWS)), [n for _, _, n in ROWS])
ax.tick_params(length=0)
for s in ax.spines.values():
    s.set_visible(False)
for y in (2.5, 5.5, 7.5):
    ax.axhline(y, color="white", lw=2)
cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
cb.set_label("Share of trials accepted with a wrong answer", fontsize=7)
cb.outline.set_visible(False)
ax.set_xlabel("Injected deviation (cells: detected / accepted wrong, of 200)")
fig.tight_layout()
save(fig, "fig_tamper")

# 5. single-keyword aggregate in the C++ prototype -----------------------------------
c = load("cpp_fastpath_revision.json")
fig, ax = plt.subplots(figsize=(3.4, 2.3))
ax.plot(c["Nd"], c["general_ms"], color=ORANGE, marker="s", lw=2, ms=6, ls="--", label="Single-round general path")
ax.plot(c["Nd"], c["fast_ms"], color=BLUE, marker="o", lw=2, ms=6, label="Precomputed keyword column")
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlabel("Number of records $N_d$")
ax.set_ylabel("Per-provider time (ms)")
ax.legend(loc="upper left")
style(ax, "both")
fig.tight_layout()
save(fig, "fig_cpp_keyword")

# 6. response packing and the single-server alternative ------------------------------
rss = load("response_and_single_server.json")["rows"]
CONF = [("submitted_2ct_1tpl", "Unpacked, 1 template"), ("packed_1ct_1tpl_compressed", "Packed, 1 template"),
        ("submitted_2ct_x4_4tpl", "Unpacked, 4 templates"), ("packed_1ct_4tpl_compressed", "Packed, 4 templates")]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.6, 2.5))
w = 0.16
x = np.arange(len(rss))
colours = [BLUE_LIGHT, BLUE, ORANGE_LIGHT, ORANGE]
hatches = ["///", "", "///", ""]
for k, ((key, name), col, hat) in enumerate(zip(CONF, colours, hatches)):
    a1.bar(x + (k - 2) * w, [ms(r["configs"][key]["provider"]) for r in rss], w * 0.92, color=col,
           edgecolor=BLUE if k < 2 else ORANGE, lw=0.6, hatch=hat, label=name)
a1.bar(x + 2 * w, [ms(r["single_server"]["server"]) for r in rss], w * 0.92, color=AQUA, label="Single server")
a1.set_xticks(x, [f"N = {r['N']:,} tags" for r in rss])
a1.set_ylabel("Per-provider time (ms)")
a1.set_title("Keyword aggregate: layouts and single server", fontsize=8, color=INK)
a1.set_ylim(0, 340)
a1.legend(loc="upper left", fontsize=6.5, ncol=2)
style(a1)
rt, rb = load("range_real_telemetry.json"), load("range_real_beijing_day.json")
groups = [("Keyword\n(11,580)", rss[0]["dpf_key_bytes"], rss[0]["single_server"]["uplink_bytes"]),
          ("Keyword\n(35,162)", rss[1]["dpf_key_bytes"], rss[1]["single_server"]["uplink_bytes"]),
          ("Range\n(telemetry)", rt["modes"]["session"]["by_window"][0]["uplink_bytes_per_provider"],
           rt["single_server_uplink_bytes_computed"]),
          ("Range\n(Beijing)", rb["modes"]["session"]["by_window"][0]["uplink_bytes_per_provider"],
           rb["single_server_uplink_bytes_computed"])]
x = np.arange(len(groups))
a2.bar(x - 0.19, [g[1] for g in groups], 0.36, color=BLUE, label="CR-SHE keys")
a2.bar(x + 0.19, [g[2] for g in groups], 0.36, color=AQUA, hatch="///", edgecolor="#127a55", lw=0.6,
       label="Single-server query")
a2.set_yscale("log")
a2.set_xticks(x, [g[0] for g in groups], fontsize=6.5)
a2.set_ylim(100, 1e10)
a2.set_ylabel("Query upload (bytes)")
a2.set_title("Query upload", fontsize=8, color=INK)
a2.legend(loc="upper left", fontsize=6.5, ncol=2)
style(a2)
fig.tight_layout()
save(fig, "fig_trust_split")

# 7. masked index: packed against unpacked ---------------------------------------------
pk = load("packed_index.json")
fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.6, 2.3))
for bits, colour, marker, name, ls in ((1, ORANGE, "s", "1 bit per word", "--"), (32, BLUE, "o", "32 bits per word", "-")):
    rows = [r for r in pk["rows"] if r["pack_bits"] == bits]
    nd = [r["Nd"] for r in rows]
    a1.plot(nd, [r["index_bytes"] / 1e9 for r in rows], color=colour, marker=marker, lw=2, ms=6, ls=ls, label=name)
    a2.plot(nd, [ms(r["retrieve"]) for r in rows], color=colour, marker=marker, lw=2, ms=6, ls=ls, label=name)
for ax, ylab, title in ((a1, "Masked index per provider (GB)", "Index size"),
                        (a2, "Retrieval per provider (ms)", "Retrieval time")):
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Number of records $N_d$")
    ax.set_ylabel(ylab)
    ax.set_title(title + f", N = {pk['N']:,} tags", fontsize=8, color=INK)
    ax.legend(loc="lower right")
    style(ax, "both")
fig.tight_layout()
save(fig, "fig_packed_index")
