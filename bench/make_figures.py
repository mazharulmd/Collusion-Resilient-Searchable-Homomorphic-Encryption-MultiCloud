"""Draw the figures of the condensed manuscript from results/*.json, so no point
is transcribed by hand. Writes vector PDFs to paper/<--paper>/figures/ (default
paper/jisa; paper/jnca holds the earlier package).

Palette: categorical slots 1-4 of the validated default palette, in fixed order;
every series also has its own marker or fill, so identity never rests on colour.
"""
import argparse
import csv
import gzip
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
_ap = argparse.ArgumentParser()
_ap.add_argument("--paper", default="jisa", help="folder under paper/ that receives figures/")
OUT = os.path.join(ROOT, "paper", _ap.parse_args().paper, "figures")
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


# 0. schematic: a box as signed corners of the summed-area table --------------------
def _grid(ax, nx, ny):
    for i in range(nx + 1):
        ax.plot([i, i], [0, ny], color=GRID, lw=0.6, zorder=1)
    for j in range(ny + 1):
        ax.plot([0, nx], [j, j], color=GRID, lw=0.6, zorder=1)
    ax.set_xlim(-0.15, nx + 0.15)
    ax.set_ylim(-0.15, ny + 0.15)
    ax.set_aspect("equal")
    ax.set_xticks(np.arange(nx) + 0.5, [str(i) for i in range(nx)], fontsize=6)
    ax.set_yticks(np.arange(ny) + 0.5, [str(j) for j in range(ny)], fontsize=6)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)


def _box(ax, lo1, hi1, lo2, hi2):
    ax.add_patch(plt.Rectangle((lo1, lo2), hi1 - lo1 + 1, hi2 - lo2 + 1, facecolor=BLUE_LIGHT, alpha=0.55,
                               edgecolor=BLUE, lw=1.2, zorder=2))
    ax.text((lo1 + hi1 + 1) / 2, (lo2 + hi2 + 1) / 2, "box $B$", ha="center", va="center", fontsize=8,
            color="#184f95", zorder=3)


def _corner(ax, x, y, sign):
    colour, marker = (BLUE, "o") if sign > 0 else (ORANGE, "s")
    ax.plot(x + 0.5, y + 0.5, marker=marker, ms=9, color=colour, mec="white", mew=0.8, zorder=4)
    ax.text(x + 0.5, y + 0.5, "+" if sign > 0 else "−", ha="center", va="center", fontsize=7, color="white",
            fontweight="bold", zorder=5)


def _dummy(ax, x, y):
    ax.plot(x + 0.5, y + 0.5, marker="D", ms=8, mfc="white", mec=MUTED, mew=1.2, zorder=4)
    ax.text(x + 0.5, y + 0.5, "0", ha="center", va="center", fontsize=6, color=MUTED, zorder=5)


NX, NY = 10, 6
fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.6, 2.75))
_grid(a1, NX, NY)
_box(a1, 3, 7, 2, 4)
for x, y, sg in ((7, 4, 1), (2, 4, -1), (7, 1, -1), (2, 1, 1)):
    _corner(a1, x, y, sg)
a1.set_title("(a) Interior box: four signed corner keys", fontsize=8, color=INK)
_grid(a2, NX, NY)
_box(a2, 0, 4, 2, 4)
_corner(a2, 4, 4, 1)
_corner(a2, 4, 1, -1)
_dummy(a2, 8, 0)
_dummy(a2, 6, 5)
a2.set_title("(b) Box at the edge: two corners become dummy keys", fontsize=8, color=INK)
for ax in (a1, a2):
    ax.set_xlabel("Dimension 1 (for example, time window)")
a1.set_ylabel("Dimension 2 (for example, value band)")
handles = [plt.Line2D([], [], marker="o", ls="", ms=8, color=BLUE, label="Key with output $+1$"),
           plt.Line2D([], [], marker="s", ls="", ms=8, color=ORANGE, label="Key with output $-1$"),
           plt.Line2D([], [], marker="D", ls="", ms=7, mfc="white", mec=MUTED, mew=1.2,
                      label="Dummy key, output $0$, random cell")]
fig.legend(handles=handles, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.0), fontsize=7)
fig.tight_layout(rect=(0, 0, 1, 0.9))
save(fig, "fig_range_idea")

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

# 8. the same range query answered three ways, on one machine --------------------------
rb = load("range_baselines.json")
rows = rb["rows"]
wk = rb["workers"]
L = [r["window_minutes"] for r in rows]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.6, 2.7))
a1.plot(L, [ms(r["crshe_session_serial"]["provider"]) / 1000 for r in rows], color=ORANGE, marker="D", lw=2, ms=6,
        label="CR-SHE verified, 1 thread")
a1.plot(L, [ms(r[f"crshe_session_pool{wk}"]["provider"]) / 1000 for r in rows], color=BLUE, marker="o", lw=2, ms=6,
        ls="--", label=f"CR-SHE verified, {wk} workers")
ss = [r for r in rows if "single_server" in r]
a1.plot([r["window_minutes"] for r in ss], [ms(r["single_server"]["server"]) / 1000 for r in ss], color=AQUA,
        marker="s", lw=2, ms=6, ls="-.", label="Single server")
meas = [r for r in rows if r["percell"]["measured"]]
comp = [r for r in rows if not r["percell"]["measured"]]
a1.plot([r["window_minutes"] for r in meas], [ms(r["percell"]["provider"]) / 1000 for r in meas], color=MAGENTA,
        marker="^", lw=2, ms=7, label="Per-cell keys (measured)")
a1.plot([meas[-1]["window_minutes"]] + [r["window_minutes"] for r in comp],
        [ms(meas[-1]["percell"]["provider"]) / 1000] + [ms(r["percell"]["provider"]) / 1000 for r in comp],
        color=MAGENTA, lw=1.5, ls=":", zorder=1)
a1.plot([r["window_minutes"] for r in comp], [ms(r["percell"]["provider"]) / 1000 for r in comp], color=MAGENTA,
        marker="^", ls="", ms=7, mfc="white", mew=1.4, label="Per-cell keys (computed)")
a1.set_ylabel("Time per provider or server (s)")
a1.set_title("Server-side time", fontsize=8, color=INK)
a1.set_ylim(0.2, 3e4)
a2.plot(L, [r["crshe_session_serial"]["uplink_bytes_per_provider"] for r in rows], color=ORANGE, marker="D", lw=2,
        ms=6, label="CR-SHE verified")
a2.plot(L, [r["percell"]["uplink_bytes_per_provider"] for r in rows], color=MAGENTA, marker="^", lw=2, ms=7,
        label="Per-cell keys")
a2.plot([r["window_minutes"] for r in ss], [r["single_server"]["uplink_bytes"] for r in ss], color=AQUA, marker="s",
        lw=2, ms=6, ls="-.", label="Single server")
a2.set_ylabel("Query upload per provider or server (bytes)")
a2.set_title("Query upload", fontsize=8, color=INK)
a2.set_ylim(500, 5e9)
for ax in (a1, a2):
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Window length L (minutes)")
    style(ax, "both")
a1.legend(loc="upper left", fontsize=6.3)
a2.legend(loc="upper left", fontsize=6.3, ncol=3, columnspacing=0.9, handletextpad=0.4)
fig.tight_layout()
save(fig, "fig_range_baselines")
