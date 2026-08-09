#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Figure 1: CR-SHE architecture and query workflow.

Drawn to match the construction as implemented, which is why it exists as a
script rather than as a hand-drawn asset: the two things that were wrong in the
earlier draft were the return arrow (one ciphertext per provider, not a
selection vector) and the second round (the client never sends S back). Both
are structural claims of Theorem 2, so the figure is generated from the same
description the text uses.

  python3 python/fig_architecture.py --out Figures/fig_architecture.pdf
"""

import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

plt.rcParams.update({"font.size": 7, "savefig.bbox": "tight", "savefig.dpi": 300})


def box(ax, x, y, w, h, text, fc="white", ec="0.25", lw=0.9, fs=7):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=0.012,rounding_size=0.02",
                                fc=fc, ec=ec, lw=lw, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, zorder=3)


def arrow(ax, p, q, text="", style="-|>", color="0.25", ls="-", rad=0.0,
          fs=6, dy=0.018, lw=0.9):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=8,
                                 color=color, lw=lw, linestyle=ls,
                                 connectionstyle=f"arc3,rad={rad}", zorder=1))
    if text:
        ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2 + dy, text,
                ha="center", va="bottom", fontsize=fs, color=color, zorder=3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="Figures/fig_architecture.pdf")
    a = ap.parse_args()

    fig, ax = plt.subplots(figsize=(7.1, 3.3))
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.04, 1.06)
    ax.axis("off")

    # ---- IoT trust domain -------------------------------------------------
    ax.add_patch(FancyBboxPatch((0.005, 0.20), 0.215, 0.72,
                                boxstyle="round,pad=0.008,rounding_size=0.02",
                                fc="0.96", ec="0.6", lw=0.8, ls="--", zorder=0))
    ax.text(0.112, 0.945, "IoT trust domain", ha="center", fontsize=6.5,
            color="0.35")

    box(ax, 0.022, 0.735, 0.180, 0.135, "Data Producers\n(sensors)")
    box(ax, 0.022, 0.545, 0.180, 0.125, "Edge relays\n(no secrets)")
    box(ax, 0.022, 0.255, 0.180, 0.215,
        "Data Owner\n$K,\\ K',\\ \\delta,\\ sk$", fc="0.90")
    arrow(ax, (0.112, 0.735), (0.112, 0.678), "")
    arrow(ax, (0.112, 0.545), (0.112, 0.478), "")

    # ---- providers --------------------------------------------------------
    ax.add_patch(FancyBboxPatch((0.335, 0.20), 0.315, 0.72,
                                boxstyle="round,pad=0.008,rounding_size=0.02",
                                fc="0.985", ec="0.6", lw=0.8, ls="--", zorder=0))
    ax.text(0.4925, 0.985, "untrusted multi-cloud back-end", ha="center",
            fontsize=6.5, color="0.35")
    ax.text(0.4925, 0.945,
            "up to $t=n-1$ collude; no server--server channel",
            ha="center", fontsize=6.2, color="0.45")

    ys = [0.700, 0.505, 0.270]
    labels = ["$\\mathrm{CP}_1$", "$\\mathrm{CP}_2$", "$\\mathrm{CP}_n$"]
    for y, lab in zip(ys, labels):
        box(ax, 0.352, y, 0.281, 0.135,
            lab + ":  $I'$, CT, $\\widehat{\\mathrm{CT}}$, "
                  "$A_f,\\widehat{A}_f,U_f,G_f$, $pk$", fs=6.2)
    ax.text(0.4925, 0.432, "$\\vdots$", ha="center", fontsize=10)

    # setup replication: routed under the domains so it crosses nothing
    arrow(ax, (0.112, 0.245), (0.352, 0.135), "", ls=":", color="0.45",
          rad=0.0)
    arrow(ax, (0.352, 0.135), (0.633, 0.135), "", ls=":", color="0.45")
    ax.text(0.4925, 0.088,
            "setup: replicate masked index $I'$ and encrypted columns",
            ha="center", fontsize=6.2, color="0.45")

    # ---- data user --------------------------------------------------------
    # Authorisation and key delegation are stated inside the box rather than
    # drawn as a long arc: they are a side channel from the owner, not part of
    # the query path, and drawing them only obscured the round structure that
    # this figure exists to show.
    box(ax, 0.775, 0.435, 0.212, 0.245,
        "Data User\nauthorised by DO;\nholds $K$, $K'$, delegated $sk$",
        fc="0.90", fs=6.6)

    # ---- query round: one DPF key out, one ciphertext pair back -----------
    for y in ys:
        arrow(ax, (0.775, 0.610), (0.636, y + 0.100), "", color="0.15",
              rad=0.10)
        arrow(ax, (0.636, y + 0.032), (0.775, 0.478), "", color="0.15",
              rad=0.10)

    ax.text(0.845, 0.870, "$\\kappa_j,\\ f$", ha="center", fontsize=7,
            color="0.15")
    ax.text(0.845, 0.775, "one DPF key\nper provider", ha="center",
            fontsize=6.1, color="0.35")
    ax.text(0.845, 0.310,
            "$\\mathrm{ct}_j,\\ \\widehat{\\mathrm{ct}}_j$",
            ha="center", fontsize=7, color="0.15")
    ax.text(0.845, 0.205,
            "one ciphertext pair,\nsize independent of $|S|$",
            ha="center", fontsize=6.1, color="0.35")

    # The two things the earlier draft's figure got wrong.
    ax.text(0.4925, 0.020,
            "single round: $S$ is never assembled at a provider, and never "
            "sent back to one",
            ha="center", fontsize=6.4, color="0.15", style="italic")

    fig.savefig(a.out)
    fig.savefig(a.out.replace(".pdf", ".png"))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
