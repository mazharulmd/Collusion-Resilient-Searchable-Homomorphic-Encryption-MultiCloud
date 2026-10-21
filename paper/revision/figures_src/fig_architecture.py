#!/usr/bin/env python3
"""
CR-SHE architecture overview (Fig. 1).

A deliberately high-level, icon-based overview across the three trust zones:
the IoT trust domain, the n semi-honest cloud providers, and the authorised
data user. Five numbered steps trace one query end to end. The detail belongs
in Section 6 and in Algorithms 1 and 2, not here.

Renders at the cas-dc full text width (figure* float).
Output: Figures/fig_architecture.pdf and .png.

Usage:  python fig_architecture.py [outdir]
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import (FancyBboxPatch, FancyArrowPatch, Ellipse,
                                Rectangle, Polygon, Arc, PathPatch)
from matplotlib.path import Path

# --------------------------------------------------------------------------
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "mathtext.fontset": "dejavusans",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})

INK       = "#1b1b1b"
TRUSTED   = "#2b6a4d"
UNTRUSTED = "#9c2a24"
USER      = "#1d4e7d"
ACCENT    = "#a8620a"
GREY      = "#707070"

FILL_TRUST = "#eef5f0"
FILL_UNTR  = "#fceff0"
FILL_USER  = "#ecf1f7"

FIGW, FIGH = 7.16, 3.05
ASPECT = FIGW / FIGH          # x-units per y-unit; round icons need this

AX, AW = 0.004, 0.214         # IoT trust domain
BX, BW = 0.274, 0.344         # multi-cloud back-end
CX, CW = 0.742, 0.254         # authorised data user
ZY, ZH = 0.085, 0.780

CLOUD_Y = [0.690, 0.450, 0.210]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def ry(v):
    """The y-length that looks the same on paper as the x-length v."""
    return v * ASPECT


def ell(cx, cy, r, **kw):
    """A circle that stays circular under the figure's unequal axis scaling."""
    return Ellipse((cx, cy), 2 * r, ry(2 * r), **kw)


def zone(ax, x, y, w, h, title, subtitle, ec, fc):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.010",
        linewidth=1.0, edgecolor=ec, facecolor=fc,
        linestyle=(0, (4, 2.4)), zorder=1))
    ax.text(x + w / 2, y + h + 0.086, title, ha="center", va="center",
            fontsize=7.6, weight="bold", color=ec, zorder=3)
    ax.text(x + w / 2, y + h + 0.040, subtitle, ha="center", va="center",
            fontsize=5.6, color=ec, zorder=3)


def txt(ax, x, y, s, *, fs=5.2, color=INK, ha="left", va="center",
        weight="normal", style="normal", z=6, ls_=1.45):
    ax.text(x, y, s, ha=ha, va=va, fontsize=fs, color=color, weight=weight,
            style=style, zorder=z, linespacing=ls_)


def arrow(ax, p0, p1, *, color=INK, lw=1.1, ls="solid", rad=0.0, head=6.0,
          z=7, double=False):
    style = "<|-|>" if double else "-|>"
    ax.add_patch(FancyArrowPatch(
        p0, p1, arrowstyle=f"{style},head_width=0.25,head_length=0.42",
        connectionstyle=f"arc3,rad={rad}", mutation_scale=head,
        linewidth=lw, color=color, linestyle=ls, zorder=z,
        shrinkA=1.0, shrinkB=1.0))


def step(ax, x, y, k, *, r=0.0125):
    ax.add_patch(ell(x, y, r, facecolor=ACCENT, edgecolor="white",
                     linewidth=0.9, zorder=10))
    ax.text(x, y - 0.0005, str(k), ha="center", va="center", fontsize=5.0,
            color="white", weight="bold", zorder=11)


def blob(ax, pieces, fc, ec, lw):
    """Union of shapes with one clean outline, by stroking underneath."""
    for under in (True, False):
        col = ec if under else fc
        for kind, args in pieces:
            if kind == "e":
                cx, cy, r = args
                p = ell(cx, cy, r)
            else:
                x, y, w, h = args
                p = Rectangle((x, y), w, h)
            p.set_facecolor(col)
            p.set_edgecolor(col)
            p.set_linewidth(lw * 2 if under else 0)
            p.set_zorder(3 if under else 4)
            ax.add_patch(p)


# --------------------------------------------------------------------------
# icons: cx, cy is the centre and s the nominal x-size
# --------------------------------------------------------------------------
def icon_sensor(ax, cx, cy, s, color=TRUSTED):
    w, h = s * 0.58, ry(s * 0.34)
    by = cy - ry(s * 0.16)
    ax.add_patch(FancyBboxPatch(
        (cx - w / 2, by - h / 2), w, h,
        boxstyle="round,pad=0,rounding_size=0.004",
        linewidth=1.0, edgecolor=color, facecolor="white", zorder=5))
    for k in range(3):
        px = cx - w / 2 + w * (k + 1) / 4
        ax.plot([px, px], [by - h / 2, by - h / 2 - ry(s * 0.11)],
                color=color, lw=0.9, zorder=4)
    for rr in (0.26, 0.40):
        ax.add_patch(Arc((cx, cy + ry(s * 0.06)), s * rr * 2, ry(s * rr * 2),
                         theta1=30, theta2=150, edgecolor=color,
                         linewidth=0.9, zorder=5))
    ax.add_patch(ell(cx, cy + ry(s * 0.06), s * 0.042, facecolor=color,
                     edgecolor="none", zorder=5))


def icon_relay(ax, cx, cy, s, color=TRUSTED):
    w, h = s * 0.74, ry(s * 0.28)
    ax.add_patch(FancyBboxPatch(
        (cx - w / 2, cy - h / 2 - ry(s * 0.08)), w, h,
        boxstyle="round,pad=0,rounding_size=0.005",
        linewidth=1.0, edgecolor=color, facecolor="white", zorder=5))
    ax.add_patch(ell(cx - w * 0.30, cy - ry(s * 0.08), s * 0.040,
                     facecolor=color, edgecolor="none", zorder=6))
    ax.plot([cx - w * 0.14, cx + w * 0.32], [cy - ry(s * 0.08)] * 2,
            color=color, lw=0.8, zorder=6)
    for dx in (-0.17, 0.17):
        ax.plot([cx + s * dx, cx + s * dx],
                [cy + h / 2 - ry(s * 0.08), cy + ry(s * 0.30)],
                color=color, lw=0.9, zorder=4)
        ax.add_patch(ell(cx + s * dx, cy + ry(s * 0.33), s * 0.035,
                         facecolor=color, edgecolor="none", zorder=4))


def icon_shield(ax, cx, cy, s, color=TRUSTED):
    w, h = s * 0.56, ry(s * 0.72)
    pts = [(cx - w / 2, cy + h / 2), (cx + w / 2, cy + h / 2),
           (cx + w / 2, cy - h * 0.08), (cx, cy - h / 2),
           (cx - w / 2, cy - h * 0.08)]
    ax.add_patch(Polygon(pts, closed=True, linewidth=1.1, edgecolor=color,
                         facecolor="white", zorder=5))
    ax.add_patch(ell(cx, cy + h * 0.12, s * 0.070, facecolor=color,
                     edgecolor="none", zorder=6))
    ax.add_patch(Polygon([(cx - s * 0.032, cy + h * 0.08),
                          (cx + s * 0.032, cy + h * 0.08),
                          (cx + s * 0.020, cy - h * 0.18),
                          (cx - s * 0.020, cy - h * 0.18)],
                         closed=True, facecolor=color, edgecolor="none",
                         zorder=6))


def icon_cloud(ax, cx, cy, s, color=UNTRUSTED, fc="white"):
    pieces = [
        ("e", (cx - s * 0.26, cy + ry(s * 0.02), s * 0.23)),
        ("e", (cx + s * 0.02, cy + ry(s * 0.14), s * 0.31)),
        ("e", (cx + s * 0.32, cy + ry(s * 0.01), s * 0.25)),
        ("r", (cx - s * 0.49, cy - ry(s * 0.22), s * 0.97, ry(s * 0.24))),
    ]
    blob(ax, pieces, fc, color, 1.0)


def icon_lock(ax, cx, cy, s, color=UNTRUSTED):
    w, h = s * 0.72, ry(s * 0.52)
    ax.add_patch(Arc((cx, cy + h * 0.42), w * 0.58, ry(s * 0.46),
                     theta1=0, theta2=180, edgecolor=color, linewidth=1.3,
                     zorder=5))
    ax.add_patch(FancyBboxPatch(
        (cx - w / 2, cy - h / 2), w, h,
        boxstyle="round,pad=0,rounding_size=0.004",
        linewidth=0.0, edgecolor="none", facecolor=color, zorder=6))
    ax.add_patch(ell(cx, cy + h * 0.04, s * 0.055, facecolor="white",
                     edgecolor="none", zorder=7))


def icon_user(ax, cx, cy, s, color=USER):
    ax.add_patch(ell(cx, cy + ry(s * 0.20), s * 0.150, facecolor="white",
                     edgecolor=color, linewidth=1.1, zorder=6))
    w, h = s * 0.46, ry(s * 0.15)
    verts = [(cx - w, cy - h), (cx - w, cy + h * 2.6),
             (cx + w, cy + h * 2.6), (cx + w, cy - h), (cx - w, cy - h)]
    codes = [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4,
             Path.CLOSEPOLY]
    ax.add_patch(PathPatch(Path(verts, codes), facecolor="white",
                           edgecolor=color, linewidth=1.1, zorder=5))


def icon_key(ax, cx, cy, s, color=USER):
    ax.add_patch(ell(cx - s * 0.30, cy, s * 0.15, facecolor="none",
                     edgecolor=color, linewidth=1.2, zorder=8))
    ax.plot([cx - s * 0.16, cx + s * 0.38], [cy, cy], color=color, lw=1.2,
            zorder=8)
    for dx in (0.14, 0.28):
        ax.plot([cx + s * dx, cx + s * dx], [cy, cy - ry(s * 0.15)],
                color=color, lw=1.2, zorder=8)


def icon_ct(ax, cx, cy, s, color=UNTRUSTED):
    w, h = s * 0.62, ry(s * 0.42)
    ax.add_patch(Rectangle((cx - w / 2, cy - h / 2), w, h, facecolor="white",
                           edgecolor=color, linewidth=1.1, zorder=8))
    ax.add_patch(PathPatch(
        Path([(cx - w / 2, cy + h / 2), (cx, cy - h * 0.10),
              (cx + w / 2, cy + h / 2)],
             [Path.MOVETO, Path.LINETO, Path.LINETO]),
        facecolor="none", edgecolor=color, linewidth=1.0, zorder=9))


def cross(ax, x, y, s=0.008, color=UNTRUSTED, lw=1.3, z=9):
    ax.plot([x - s, x + s], [y - ry(s), y + ry(s)], color=color, lw=lw,
            zorder=z)
    ax.plot([x - s, x + s], [y + ry(s), y - ry(s)], color=color, lw=lw,
            zorder=z)


# --------------------------------------------------------------------------
def render(outdir):
    fig, ax = plt.subplots(figsize=(FIGW, FIGH))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # ---------------- zone A: the IoT trust domain ------------------------
    zone(ax, AX, ZY, AW, ZH, "IoT trust domain", "trusted; holds every key",
         TRUSTED, FILL_TRUST)
    icx = AX + 0.044
    tx = icx + 0.046

    icon_sensor(ax, icx, 0.750, 0.072)
    txt(ax, tx, 0.762, "Sensor nodes", fs=6.0, weight="bold", color=TRUSTED)
    txt(ax, tx, 0.728, "IoT telemetry", fs=5.0, color=GREY)
    arrow(ax, (icx, 0.696), (icx, 0.648), color=TRUSTED, lw=0.9, head=4.8)

    icon_relay(ax, icx, 0.596, 0.072)
    txt(ax, tx, 0.608, "Edge relays", fs=6.0, weight="bold", color=TRUSTED)
    txt(ax, tx, 0.574, "no key material", fs=5.0, color=GREY)
    arrow(ax, (icx, 0.548), (icx, 0.492), color=TRUSTED, lw=0.9, head=4.8)

    icon_shield(ax, icx, 0.402, 0.084)
    txt(ax, tx, 0.442, "Data owner", fs=6.0, weight="bold", color=TRUSTED)
    txt(ax, tx, 0.408, r"holds $D$, $K'$, $\delta$, $sk$", fs=5.0,
        color=ACCENT)
    txt(ax, tx, 0.374, "builds the store", fs=5.0, color=GREY)

    ax.plot([AX + 0.018, AX + AW - 0.018], [0.292] * 2, color=TRUSTED,
            lw=0.5, alpha=0.4, zorder=4)
    txt(ax, AX + AW / 2, 0.232,
        r"index $\rightarrow$ mask $\rightarrow$ encrypt", fs=5.2,
        ha="center")
    txt(ax, AX + AW / 2, 0.180, r"$\rightarrow$ precompute columns", fs=5.2,
        ha="center")

    # ---------------- zone B: the multi-cloud back-end --------------------
    zone(ax, BX, ZY, BW, ZH, "Multi-cloud back-end",
         r"semi-honest; any $t = n-1$ may collude", UNTRUSTED, FILL_UNTR)

    ccx = BX + 0.058
    for nm, cy in zip([r"$\mathrm{CP}_1$", r"$\mathrm{CP}_2$",
                       r"$\mathrm{CP}_n$"], CLOUD_Y):
        icon_cloud(ax, ccx, cy, 0.092)
        txt(ax, ccx, cy - ry(0.002), nm, fs=6.2, weight="bold",
            color=UNTRUSTED, ha="center", z=6)
        icon_lock(ax, ccx + 0.076, cy + 0.012, 0.038)
        txt(ax, ccx + 0.100, cy + 0.016, "masked index and", fs=5.0)
        txt(ax, ccx + 0.100, cy - 0.018, "encrypted columns", fs=5.0)

    mid = 0.595
    arrow(ax, (ccx, mid + 0.022), (ccx, mid - 0.022), color=UNTRUSTED,
          lw=0.8, head=4.0, double=True)
    cross(ax, ccx, mid, s=0.0065)
    txt(ax, ccx + 0.024, mid, "no channel between providers", fs=4.9,
        color=UNTRUSTED, style="italic")

    txt(ax, ccx, (CLOUD_Y[1] + CLOUD_Y[2]) / 2, r"$\vdots$", fs=9,
        ha="center")

    ax.add_patch(FancyBboxPatch(
        (BX + 0.024, 0.098), BW - 0.048, 0.056,
        boxstyle="round,pad=0,rounding_size=0.007",
        linewidth=0.9, edgecolor=ACCENT, facecolor="#fdf8f0", zorder=7))
    txt(ax, BX + BW / 2 + 0.012, 0.126, "oblivious homomorphic aggregation",
        fs=5.4, weight="bold", color=ACCENT, ha="center", z=8)
    step(ax, BX + 0.042, 0.126, 3)

    # ---------------- zone C: the authorised data user --------------------
    zone(ax, CX, ZY, CW, ZH, "Authorised data user",
         r"holds $D$, $K'$ and a delegated $sk$", USER, FILL_USER)

    icon_user(ax, CX + 0.046, 0.678, 0.098)
    txt(ax, CX + 0.098, 0.700, "Data user", fs=6.2, weight="bold",
        color=USER)
    txt(ax, CX + 0.098, 0.664, "thin client", fs=5.0, color=GREY)

    ax.add_patch(FancyBboxPatch(
        (CX + 0.014, 0.148), CW - 0.028, 0.376,
        boxstyle="round,pad=0,rounding_size=0.008",
        linewidth=0.9, edgecolor=USER, facecolor="white", zorder=4))
    txt(ax, CX + 0.030, 0.478,
        r"$\alpha_w \leftarrow D(w)$, split into $n$ keys", fs=5.2)
    txt(ax, CX + 0.030, 0.414, r"add the $n$ ciphertexts", fs=5.2)
    txt(ax, CX + 0.030, 0.350, r"verify the MAC, $\hat{y} = \delta_\alpha y$",
        fs=5.2)
    txt(ax, CX + 0.030, 0.286, "decrypt once", fs=5.2)
    ax.plot([CX + 0.030, CX + CW - 0.030], [0.238] * 2, color=USER, lw=0.5,
            alpha=0.4, zorder=5)
    txt(ax, CX + CW / 2 - 0.014, 0.194,
        r"the coalition learns only $\mathrm{class}(q)$", fs=4.9,
        color=UNTRUSTED, ha="center", style="italic")
    step(ax, CX + 0.014, 0.524, 5)

    # ---------------- flows -----------------------------------------------
    mx = (AX + AW + BX) / 2
    arrow(ax, (AX + AW + 0.003, 0.440), (BX - 0.003, 0.440), color=TRUSTED,
          lw=1.2, ls=(0, (3.0, 1.8)), head=6.2)
    txt(ax, mx, 0.492, "replicate", fs=4.9, color=TRUSTED, weight="bold",
        ha="center")
    txt(ax, mx, 0.390, r"to all $n$", fs=4.9, color=TRUSTED, ha="center")
    step(ax, mx, 0.566, 1)

    gx0, gx1 = CX - 0.003, BX + BW + 0.003
    for k, cy in enumerate(CLOUD_Y):
        rad = (0.13, 0.0, -0.13)[k]
        arrow(ax, (gx0, cy + 0.028), (gx1, cy + 0.028), color=USER, lw=1.0,
              rad=rad, head=5.4)
        arrow(ax, (gx1, cy - 0.028), (gx0, cy - 0.028), color=UNTRUSTED,
              lw=1.0, rad=rad, head=5.4)

    kx = (BX + BW + CX) / 2
    icon_key(ax, kx, 0.836, 0.050)
    txt(ax, kx, 0.786, "one DPF key", fs=5.0, color=USER, weight="bold",
        ha="center")
    txt(ax, kx, 0.754, "per provider", fs=5.0, color=USER, ha="center")
    step(ax, kx - 0.040, 0.836, 2)

    icon_ct(ax, kx, 0.152, 0.062)
    txt(ax, kx, 0.106, "one ciphertext", fs=5.0, color=UNTRUSTED,
        weight="bold", ha="center")
    txt(ax, kx, 0.074, "value + MAC, fixed size", fs=5.0,
        color=UNTRUSTED, ha="center")
    step(ax, kx - 0.040, 0.152, 4)

    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    os.makedirs(outdir, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(outdir, f"fig_architecture.{ext}"),
                    dpi=400, bbox_inches="tight", pad_inches=0.012)
    plt.close(fig)
    print("wrote", os.path.join(outdir, "fig_architecture.pdf"))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "Figures")
    render(os.path.abspath(out))
