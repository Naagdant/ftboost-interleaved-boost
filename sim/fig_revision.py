"""Figures redrawn or added in revision 2 of the manuscript.

  python3 -I sim/fig_revision.py [flow] [bench] [comparison] [all]

fig04  fault-management flowchart: real flowchart symbols (terminator, process, decision),
       Yes/No branches and the loop back to sampling; text sized to fit every box.
fig12  detector benchmark: legend moved outside the bars; the all-zero false-trip panel is
       replaced by a note, because every detector gave 0 false trips.
fig11  proposed vs conventional, now with the fuse-protected conventional converter.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
from matplotlib import font_manager  # noqa: E402

for f in ("texgyretermes-regular.otf", "texgyretermes-italic.otf", "texgyretermes-bold.otf",
          "texgyretermes-bolditalic.otf"):
    p = os.path.join("/usr/share/texmf/fonts/opentype/public/tex-gyre", f)
    if os.path.exists(p):
        font_manager.fontManager.addfont(p)

import numpy as np  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
OUT = os.path.join(ROOT, "paper", "elsevier", "figures")
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#222222", "#6b6b6b", "#d9d9d6"
FILL, FILL_ISO, FILL_REC = "#f4f6fa", "#fff4ec", "#f2faf6"
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "TeX Gyre Termes", "Liberation Serif"],
    "mathtext.fontset": "stix", "font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9,
    "legend.fontsize": 7.5, "xtick.labelsize": 8, "ytick.labelsize": 8, "axes.edgecolor": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5, "axes.spines.top": False,
    "axes.spines.right": False, "savefig.dpi": 300, "savefig.bbox": "tight", "savefig.pad_inches": 0.03,
})
W1 = 6.3


def save(fig, stem):
    os.makedirs(OUT, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT, f"{stem}.{ext}"))
    plt.close(fig)
    print("wrote", stem)


# ------------------------------------------------------------------ flowchart primitives
def _proc(ax, cx, cy, w, h, text, fc=FILL, fs=8, rounding=0.06):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                                boxstyle=f"round,pad=0,rounding_size={rounding}", fc=fc, ec=INK, lw=0.8))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, color=INK, linespacing=1.25)


def _term(ax, cx, cy, w, h, text, fs=8):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                                boxstyle=f"round,pad=0,rounding_size={h / 2}", fc="#e9eef7", ec=INK, lw=0.8))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, color=INK, linespacing=1.25)


def _dec(ax, cx, cy, w, h, text, fs=7.6):
    ax.add_patch(Polygon([(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)],
                         closed=True, fc="#fffbe8", ec=INK, lw=0.8))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, color=INK, linespacing=1.2)


def _arr(ax, pts, label=None, lpos=0, loff=(0.12, 0.0), ha="left"):
    """Polyline with an arrow head on the last segment; label at vertex lpos."""
    for a, b in zip(pts[:-2], pts[1:-1]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=INK, lw=0.8, solid_capstyle="butt")
    ax.add_patch(FancyArrowPatch(pts[-2], pts[-1], arrowstyle="-|>", mutation_scale=8, lw=0.8, color=INK,
                                 shrinkA=0, shrinkB=0))
    if label:
        x, y = pts[lpos]
        ax.text(x + loff[0], y + loff[1], label, fontsize=7.5, ha=ha, va="center", color=INK, style="italic")


def fig_flow():
    fig, ax = plt.subplots(figsize=(W1, 7.6))
    ax.set_xlim(0, 12.4)
    ax.set_ylim(0, 14.2)
    ax.axis("off")
    ax.grid(False)
    X, XL, XR, XRET = 6.2, 3.0, 8.6, 11.95
    fs = 7.8

    _term(ax, X, 13.6, 7.4, 0.7, "Start: soft-start complete ($t \\geq$ 30 ms), detectors armed", fs=fs)
    _proc(ax, X, 12.5, 7.8, 0.8, "Learn the healthy off-time template $y_k$ of each phase\n"
          "(average of 250 periods, 40–45 ms)", fs=fs)
    _proc(ax, X, 11.2, 8.8, 0.9, "Sample $i_{L1}$, $i_{L2}$, $V_{out}$, $V_{in}$ at 5 MS/s (isolated sensing);\n"
          "update the ACM loops once per period, Eqs. (20)–(23)", fs=fs)
    _arr(ax, [(X, 13.25), (X, 12.9)])
    _arr(ax, [(X, 12.1), (X, 11.65)])

    _arr(ax, [(X - 2.0, 10.75), (X - 2.0, 10.45), (XL, 10.45), (XL, 10.15)])
    _arr(ax, [(X + 2.0, 10.75), (X + 2.0, 10.45), (XR, 10.45), (XR, 10.15)])
    _proc(ax, XL, 9.65, 4.9, 1.0, "Level detectors (every sample)\n$i_k < I_{open}$ for 100 µs, or\n"
          "$i_k > I_{short}(N_{active})$ for 60 µs", fs=7.5)
    _proc(ax, XR, 9.65, 5.0, 1.0, "Template detector (end of each off-time)\n"
          "$N_w = \\lfloor(1-D)Tf_s\\rfloor-2$, skip if $N_w < 6$\ncompute $r$, Eq. (13), and $\\beta$, Eq. (15)", fs=7.5)
    _arr(ax, [(XL, 9.15), (XL, 8.85)])
    _arr(ax, [(XR, 9.15), (XR, 8.85)])
    _dec(ax, XL, 8.05, 3.8, 1.6, "Level limit\nexceeded?", fs=7.5)
    _dec(ax, XR, 8.05, 3.8, 1.6, "$r < 0.80$ or\n$\\beta \\notin [0.5,\\,2.0]$ ?", fs=7.5)

    # template branch
    _arr(ax, [(XR, 7.25), (XR, 6.95)], "Yes", 0, (0.15, -0.02))
    _proc(ax, XR, 6.6, 2.6, 0.7, "$v_k \\leftarrow v_k + 1$", fs=fs)
    _arr(ax, [(XR, 6.25), (XR, 5.95)])
    _dec(ax, XR, 5.3, 2.8, 1.3, "$v_k = 3$ ?", fs=fs)
    # return paths to sampling
    ax.plot([XR + 1.9, XRET], [8.05, 8.05], color=INK, lw=0.8)
    ax.plot([XRET], [8.05], marker="o", ms=2.6, color=INK)
    ax.text(XR + 2.0, 8.25, "No: $v_k \\leftarrow 0$", fontsize=7.2, style="italic", va="bottom")
    _arr(ax, [(XR + 1.4, 5.3), (XRET, 5.3), (XRET, 11.2), (X + 4.4, 11.2)], "No", 0, (0.1, 0.2))
    _arr(ax, [(XL - 1.9, 8.05), (0.35, 8.05), (0.35, 11.2), (X - 4.4, 11.2)], "No", 0, (-0.1, 0.22), ha="right")

    # merge -> classify
    _arr(ax, [(XL, 7.25), (XL, 4.45), (X - 1.4, 4.45), (X - 1.4, 4.05)], "Yes", 0, (0.15, -0.2))
    _arr(ax, [(XR, 4.65), (XR, 4.45), (X + 1.4, 4.45), (X + 1.4, 4.05)], "Yes", 0, (0.15, 0.0))
    _proc(ax, X, 3.6, 9.6, 0.9, "Classify from the tripping window:  max $x < I_{open}$ → open inductor;\n"
          "$\\beta < 0$ → shorted switch;  otherwise → open diode", fs=fs)
    _arr(ax, [(X, 3.15), (X, 2.85)])
    _proc(ax, X, 2.4, 9.6, 0.9, "Isolate phase $k$:  gate inhibit  →  SSD off after 1 µs\n"
          "→  relay opens (≤ 5 ms, with the current already zero)", fc=FILL_ISO, fs=fs)
    _arr(ax, [(X, 1.95), (X, 1.65)])
    _proc(ax, X, 1.2, 9.6, 0.9, "Reconfigure: $N_{active} \\leftarrow N_{active}-1$;  $I_{lim}$ = 5.0 A,  $I_{short}$ = 6.76 A;\n"
          "same control law, $I_{ref,k} = I_{ref,tot}/N_{active}$; the voltage loop trims $D$", fc=FILL_REC, fs=fs)
    _arr(ax, [(X, 0.75), (X, 0.5)])
    _term(ax, X, 0.18, 8.4, 0.62, "Degraded mode: regulate on the surviving phase and report the fault", fs=fs)
    ax.set_ylim(-0.2, 14.0)
    save(fig, "fig04_fault_management_flow")


# ------------------------------------------------------------------ Fig. 12
def fig_bench():
    b = json.load(open(os.path.join(RES, "detector_benchmark.json")))
    dets = [("level", "L: level thresholds"), ("r_fixed", "rF: correlation, fixed window"),
            ("r_adaptive", "rA: correlation, adaptive window"), ("beta_only", "$\\beta$: slope ratio only"),
            ("proposed", "P: proposed ($r$ + $\\beta$)")]
    cols = [INK, C2, "#9a9a9a", C3, C1]
    faults = ["open_inductor", "shorted_switch", "open_diode"]
    fig, ax = plt.subplots(figsize=(W1, 2.7))
    w = 0.15
    for i, (dk, dl) in enumerate(dets):
        e = b[f"{dk}@1x"]
        assert e["healthy"]["false_trips"] == 0
        for j, fk in enumerate(faults):
            v = e["faults"][fk]
            x = j + (i - 2) * w
            if v["latency_us"]:
                ax.bar(x, v["latency_us"][1], w * 0.92, color=cols[i], label=dl if j == 0 else None, zorder=3)
            else:
                ax.text(x, 4, "×", ha="center", va="bottom", fontsize=11, color=cols[i], zorder=3)
                if j == 0 or True:
                    ax.text(x, 13, "missed", ha="center", va="bottom", fontsize=6.3, color=cols[i],
                            rotation=90)
    ax.axhline(62.7, color=MUTED, ls="--", lw=0.7, zorder=2, label="Eq. (18), $m$ = 0: 62.7 µs")
    ax.set_xticks(range(3))
    ax.set_xticklabels(["open inductor", "shorted switch", "open diode"])
    ax.set_ylabel("detection time (µs)")
    ax.set_ylim(0, 115)
    ax.set_xlim(-0.5, 2.5)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False, prop={"family": "serif", "size": 7.6})
    ax.text(1.03, 0.08, "False trips on the six healthy\nruns: 0 for every detector\n(1× and 3× nominal noise)",
            transform=ax.transAxes, fontsize=7.3, color=MUTED, va="bottom")
    save(fig, "fig12_detector_benchmark")


# ------------------------------------------------------------------ Fig. 5
def fig_validation():
    a = np.load(os.path.join(RES, "validation", "openloop_c150u.npy"))
    b = np.load(os.path.join(RES, "validation", "openloop_c14u.npy"))
    fig, ax = plt.subplots(1, 2, figsize=(W1, 2.6))
    for d, lab, c, ls in ((b, "$C_{out}$ = 14 µF (stress case)", C2, "--"), (a, "$C_{out}$ = 150 µF", C1, "-")):
        m = d[:, 0] <= 40e-3
        ax[0].plot(d[m, 0] * 1e3, d[m, 1], color=c, ls=ls, lw=0.8, label=lab)
    vf = a[a[:, 0] > 50e-3, 1].mean()
    ax[0].axhspan(vf * 0.98, vf * 1.02, color=C3, alpha=0.18, lw=0, label="±2 % of final value")
    ax[0].set_xlabel("$t$ (ms)")
    ax[0].set_ylabel("$V_{out}$ (V)")
    ax[0].set_title("(a) Open-loop start-up, $D$ = 0.76")
    ax[0].legend(loc="upper right", frameon=False, fontsize=7)
    m = (b[:, 0] >= 79.94e-3) & (b[:, 0] <= 80e-3)
    t = b[m, 0] * 1e6 - 79940
    ax[1].plot(t, b[m, 2], color=C1, ls="-", lw=0.9, label="$i_{L1}$")
    ax[1].plot(t, b[m, 3], color=C2, ls="--", lw=0.9, label="$i_{L2}$")
    ss = b[b[:, 0] > 78e-3]
    iav = ss[:, 2].mean()
    for y in (iav - 0.365, iav + 0.365):
        ax[1].axhline(y, color=MUTED, lw=0.7, ls=":")
    ax[1].text(30, iav + 0.395, "mean ± $\\Delta i_L/2$, Eq. (3)", fontsize=7, color=MUTED, ha="center")
    ax[1].set_ylim(1.6, 2.62)
    ax[1].set_xlabel("$t$ (µs, steady state, $C_{out}$ = 14 µF)")
    ax[1].set_ylabel("phase current (A)")
    ax[1].set_title("(b) 180°-interleaved phase currents")
    ax[1].legend(loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.02), fontsize=7.5)
    fig.tight_layout()
    save(fig, "fig05_openloop_validation")


def _rec(name):
    return np.load(os.path.join(RES, name + ".npz"))["rec"]


# ------------------------------------------------------------------ Fig. 11
def fig_comparison():
    faults = [("open_inductor", "Open inductor"), ("shorted_switch", "Shorted switch"), ("open_diode", "Open diode")]
    fig, ax = plt.subplots(2, 3, figsize=(W1, 3.9), sharex=True)
    for j, (case, title) in enumerate(faults):
        runs = [(_rec(f"{case}_baseline"), "conventional", C2, "--"),
                (_rec(f"{case}_final"), "proposed", C1, "-")]
        if case == "shorted_switch":
            runs.insert(1, (_rec("shorted_switch_baseline_fuse"), "conventional + input fuse", INK, ":"))
        for r, lab, c, ls in runs:
            m = r[:, 0] >= 48e-3
            ax[0, j].plot(r[m, 0] * 1e3, r[m, 1], color=c, ls=ls, lw=0.9, label=lab)
            ax[1, j].plot(r[m, 0] * 1e3, np.abs(r[m, 2]), color=c, ls=ls, lw=0.7, label=lab)
        ax[0, j].axhspan(190, 210, color=C3, alpha=0.15, lw=0)
        ax[0, j].set_ylim(-5, 225)
        ax[0, j].set_title(f"({'abc'[j]}) {title}")
        ax[1, j].set_yscale("symlog", linthresh=5)
        ax[1, j].set_ylim(0, 400)
        ax[1, j].set_xlabel("$t$ (ms)")
        ax[1, j].set_xlim(48, 80)
        for k in range(2):
            ax[k, j].axvline(50, color=MUTED, lw=0.6, ls=":")
    ax[0, 0].set_ylabel("$V_{out}$ (V)")
    ax[1, 0].set_ylabel("$|i_{L1}|$, faulted phase (A)")
    h, l = ax[0, 1].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.03), fontsize=7.8)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "fig11_proposed_vs_conventional")


# ------------------------------------------------------------------ Fig. 13
def fig_isolation():
    a = _rec("shorted_switch_relayonly_final")
    b = _rec("shorted_switch_final")
    fig, ax = plt.subplots(figsize=(4.4, 2.7))
    for r, lab, c, ls in ((a, "relay only (5 ms release)", C2, "--"),
                          (b, "SSD (1 µs) + relay (5 ms release)", C1, "-")):
        m = (r[:, 0] >= 49.5e-3) & (r[:, 0] <= 58e-3)
        ax.plot(r[m, 0] * 1e3, np.maximum(r[m, 2], 1e-2), color=c, ls=ls, lw=0.9, label=lab)
    ax.axhline(3.59, color=MUTED, ls=":", lw=0.8)
    ax.text(57.9, 4.3, "3.59 A", fontsize=7, color=MUTED, ha="right")
    ax.set_yscale("log")
    ax.set_ylim(1e-2, 400)
    ax.set_xlabel("$t$ (ms)")
    ax.set_ylabel("$i_{L1}$ (A), log scale")
    ax.text(55.2, 185, f"peak {a[a[:, 0] > 50e-3, 2].max():.0f} A", fontsize=7.5)
    ax.text(50.3, 7.5, f"peak {b[b[:, 0] > 50e-3, 2].max():.2f} A", fontsize=7.5, color=C1)
    ax.legend(loc="lower right", frameon=False, fontsize=7.3)
    save(fig, "fig13_isolation_timing")


# ------------------------------------------------------------------ Fig. 1
def fig_architecture():
    """Architecture: power path left to right, controller underneath, sensing up/down, commands up."""
    fig, ax = plt.subplots(figsize=(W1, 4.0))
    ax.set_xlim(0, 16)
    ax.set_ylim(-0.1, 9.4)
    ax.axis("off")
    ax.grid(False)
    PW, SNS, CMD = INK, C1, C2
    DISC, CELL, CTRL = "#fdeee3", "#e8eef8", "#e9f6ef"

    def blk(x0, x1, yc, txt, fc=FILL, h=1.15, fs=7.3, bold=False):
        ax.add_patch(FancyBboxPatch((x0, yc - h / 2), x1 - x0, h, boxstyle="round,pad=0,rounding_size=0.12",
                                    fc=fc, ec=INK, lw=0.8, zorder=3))
        ax.text((x0 + x1) / 2, yc, txt, ha="center", va="center", fontsize=fs, color=INK, zorder=4,
                linespacing=1.2, fontweight="bold" if bold else "normal")

    def line(pts, color=PW, ls="-", lw=1.1, arrow=True, z=2):
        for a, b in zip(pts[:-2], pts[1:-1]):
            ax.plot([a[0], b[0]], [a[1], b[1]], color=color, ls=ls, lw=lw, zorder=z, solid_capstyle="butt")
        if arrow:
            ax.add_patch(FancyArrowPatch(pts[-2], pts[-1], arrowstyle="-|>", mutation_scale=8, lw=lw, color=color,
                                         ls=ls, shrinkA=0, shrinkB=0, zorder=z))
        else:
            ax.plot([pts[-2][0], pts[-1][0]], [pts[-2][1], pts[-1][1]], color=color, ls=ls, lw=lw, zorder=z)

    Y1, Y2 = 4.75, 7.55          # phase 1 (detailed) and phase 2 (compact) rows
    # source and input bus
    blk(0.15, 1.55, 6.15, "48 V\nbattery", fs=7.8)
    xb = 2.0
    line([(1.55, 6.15), (xb, 6.15)], arrow=False)
    line([(xb, Y1), (xb, Y2)], arrow=False)
    ax.plot([xb], [6.15], "o", ms=3, color=PW, zorder=3)
    # phase 1, detailed
    ax.add_patch(FancyBboxPatch((2.35, Y1 - 0.85), 3.5, 1.7, boxstyle="round,pad=0,rounding_size=0.15",
                                fc=DISC, ec="none", zorder=1))
    ax.text(4.1, Y1 + 0.95, "hybrid input-side disconnect", ha="center", fontsize=6.8, color="#a0522d",
            style="italic")
    blk(2.5, 4.0, Y1, "Relay $K_1$\nG2RL-1A", fc="#fff7f1", fs=6.9)
    blk(4.3, 5.65, Y1, "SSD$_1$\n1 µs off", fc="#fff7f1", fs=6.9)
    blk(6.05, 7.35, Y1, "Shunt\n10 mΩ")
    blk(7.75, 8.95, Y1, "$L_1$\n1 mH")
    blk(9.35, 10.95, Y1, "Boost cell\n$S_1$ / $D_1$", fc=CELL)
    ax.text(6.05, Y1 + 0.78, "Phase 1  (0° carrier)", fontsize=7.0, color=MUTED, style="italic")
    for a, b in ((xb, 2.5), (4.0, 4.3), (5.65, 6.05), (7.35, 7.75), (8.95, 9.35)):
        line([(a, Y1), (b, Y1)])
    # phase 2, compact
    blk(2.35, 11.2, Y2, "Phase 2 (180° carrier): $K_2$, SSD$_2$, shunt + AMC1300, $L_2$, $S_2$ / $D_2$\n"
        "identical to phase 1, with its own sensing and commands", fc="#f6f6f4", h=1.1, fs=6.9)
    line([(xb, Y2), (2.35, Y2)])
    # output bus and load
    xo = 11.55
    line([(10.95, Y1), (xo, Y1)], arrow=False)
    line([(11.2, Y2), (xo, Y2)], arrow=False)
    line([(xo, Y1), (xo, Y2)], arrow=False)
    yo = (Y1 + Y2) / 2
    ax.plot([xo], [yo], "o", ms=3, color=PW, zorder=3)
    line([(xo, yo), (12.1, yo)])
    blk(12.1, 14.3, yo, "$C_{out}$, load\n200 V bus", fc=CELL, h=1.2, fs=7.6)
    # isolated current sensor
    blk(5.85, 7.55, 3.05, "AMC1300\nisolated amp", fs=6.9, h=0.9)
    line([(6.7, Y1 - 0.575), (6.7, 3.5)], color=SNS, lw=1.0)

    # controller
    ax.add_patch(FancyBboxPatch((2.3, 0.0), 12.2, 2.15, boxstyle="round,pad=0,rounding_size=0.15",
                                fc=CTRL, ec=INK, lw=0.9, zorder=1))
    ax.text(7.05, 1.97, "Controller (firmware)", fontsize=7.2, fontweight="bold", va="top", color=INK)
    yc = 0.85
    blk(2.55, 5.45, yc, "Isolation logic:\ngate → SSD → relay", fc="white", h=1.05, fs=6.9)
    blk(5.85, 9.25, yc, "5 MS/s ADC, level and\ntemplate detectors ($r$, $\\beta$),\ndebounce, classify",
        fc="white", h=1.25, fs=6.9)
    blk(9.65, 14.3, yc, "ACM loops (outer $V$, inner $I$)\n"
        "$I_{ref,k} = I_{ref,tot}/N_{active}$; PWM $d_1$, $d_2$", fc="white", h=1.05, fs=6.9)
    line([(5.85, yc), (5.45, yc)], color=INK, lw=0.9)
    line([(9.25, yc), (9.65, yc)], color=INK, lw=0.9)

    # sensing (dashed blue, downwards) and commands (dotted orange, upwards)
    line([(6.7, 2.575), (6.7, yc + 0.625)], color=SNS, ls="--", lw=1.0)
    ax.text(6.8, 2.3, "$i_{L1}$", fontsize=7.0, color=SNS)
    line([(13.2, yo - 0.65), (13.2, yc + 0.525)], color=SNS, ls="--", lw=1.0)
    ax.text(13.3, 2.6, "$V_{out}$", fontsize=7.0, color=SNS)
    for x, lab in ((3.25, "relay $K_1$"), (4.95, "SSD$_1$ gate")):
        line([(x, yc + 0.525), (x, Y1 - 0.575)], color=CMD, ls=":", lw=1.2)
        ax.text(x + 0.1, 2.85, lab, fontsize=6.6, color=CMD, rotation=90, va="center")
    line([(10.15, yc + 0.525), (10.15, Y1 - 0.575)], color=CMD, ls=":", lw=1.2)
    ax.text(10.25, 3.0, "gate $S_1$, PWM $d_1$", fontsize=6.6, color=CMD, rotation=90, va="center")

    # legend
    lx, ly = 12.0, 9.05
    for i, (c, ls, lab) in enumerate(((PW, "-", "power path"), (SNS, "--", "measured signals"),
                                      (CMD, ":", "commands from the controller"))):
        y = ly - i * 0.42
        ax.plot([lx, lx + 0.6], [y, y], color=c, ls=ls, lw=1.2)
        ax.text(lx + 0.75, y, lab, fontsize=6.8, va="center", color=INK)
    save(fig, "fig01_architecture")


# ------------------------------------------------------------------ Fig. 16 (revision 3)
def fig_rev3():
    fig, ax = plt.subplots(1, 3, figsize=(W1, 2.55), gridspec_kw={"width_ratios": [1, 1.2, 1.2]})
    i = np.linspace(0, 8, 400)
    for ik, lab, c, ls in ((None, "linear", INK, "-"),
                           (13.5, "$I_k$ = 13.5 A (rated 6.76 A)", C1, "--"),
                           (7.2, "$I_k$ = 7.2 A (rated 3.59 A)", C2, ":")):
        ax[0].plot(i, np.ones_like(i) if ik is None else 1 / (1 + (i / ik) ** 2), color=c, ls=ls, lw=1.0, label=lab)
    ax[0].set_xticks([0, 2.47, 4.63, 6.76])
    ax[0].set_xticklabels(["0", "2.5\nhealthy", "4.6\n1-phase", "6.8\ntrip"], fontsize=6.6)
    ax[0].set_ylim(0.4, 1.05)
    ax[0].set_xlabel("$i_L$ (A)", labelpad=1)
    ax[0].set_ylabel("$L(i)/L_0$")
    ax[0].set_title("(a) inductance roll-off", fontsize=8.5)
    ax[0].legend(fontsize=5.9, loc="lower left", frameon=False)
    for name, lab, c, ls in (("open_inductor_final", "linear", INK, "-"),
                             ("rev3_sat135_open_inductor", "$I_k$ = 13.5 A", C1, "--"),
                             ("rev3_sat72_open_inductor", "$I_k$ = 7.2 A", C2, ":")):
        r = _rec(name)
        m = (r[:, 0] >= 75e-3) & (r[:, 0] <= 75.06e-3)
        ax[1].plot((r[m, 0] - 75e-3) * 1e6, r[m, 3], color=c, ls=ls, lw=1.0, label=lab)
    ax[1].axhline(6.76, color=MUTED, ls=":", lw=0.7)
    ax[1].text(1, 6.82, "6.76 A trip level (single phase)", fontsize=6.4, color=MUTED, ha="left", va="bottom")
    ax[1].set_ylim(3.4, 7.4)
    ax[1].set_xlabel("$t$ (µs, degraded steady state)")
    ax[1].set_ylabel("$i_{L2}$, surviving phase (A)")
    ax[1].set_title("(b) surviving phase, open inductor", fontsize=8.5)
    ax[1].legend(fontsize=6.2, loc="upper left", frameon=False, ncol=3, bbox_to_anchor=(0.0, 0.76),
                 handlelength=1.6, columnspacing=0.8)
    for name, lab, c, ls in (("rev3_su_orig_shorted_switch", "detectors armed at 30 ms", C2, "--"),
                             ("rev3_su_early_shorted_switch", "start-up protection", C1, "-")):
        r = _rec(name)
        m = (r[:, 0] > 5.0e-3 + 2e-6) & (r[:, 0] <= 45e-3)
        ax[2].plot((r[m, 0] - 5e-3) * 1e3, np.maximum(np.abs(r[m, 2]), 1e-2), color=c, ls=ls, lw=1.0, label=lab)
    ax[2].set_xscale("log")
    ax[2].set_yscale("log")
    ax[2].set_xlim(2e-3, 40)
    ax[2].set_ylim(5e-2, 700)
    ax[2].plot([0.134], [6.6], "o", ms=3.5, color=C1)
    ax[2].plot([25.06], [276.5], "o", ms=3.5, color=C2)
    ax[2].set_xlabel("time after the fault (ms)")
    ax[2].set_ylabel("$|i_{L1}|$, faulted phase (A)")
    ax[2].set_title("(c) stuck-on switch at 5 ms", fontsize=8.5)
    ax[2].legend(fontsize=6.0, loc="lower right", frameon=False)
    fig.tight_layout(w_pad=0.6)
    save(fig, "fig16_saturation_startup")


# ------------------------------------------------------------------ Fig. 10
def fig_random():
    import glob
    T, TSNS, TS = 20e-6, 2.3e-6, 0.2e-6
    fig, ax = plt.subplots(1, 2, figsize=(W1, 2.6))
    marks = {"open_inductor": ("s", INK), "shorted_switch": ("^", C2), "open_diode": ("o", C3)}
    rows = []
    for f in sorted(glob.glob(os.path.join(RES, "*_rand??.json"))):
        m = json.load(open(f))
        ev = [e for e in m["events"] if e["event"].startswith("FAULT_")]
        tf = m["t_fault_s"]
        r = _rec(os.path.basename(f)[:-5])
        post = r[r[:, 0] >= tf]
        rows.append((m["case"], (tf % T) / T, (ev[0]["t"] - tf) * 1e6, 200 - post[:, 1].min()))
    for case, (mk, c) in marks.items():
        x = [p for (cs, p, l, dv) in rows if cs == case]
        ax[0].scatter(x, [l for (cs, p, l, dv) in rows if cs == case], marker=mk, facecolor="none", edgecolor=c,
                      s=22, lw=0.9, label=case.replace("_", " "), zorder=3)
        ax[1].scatter(x, [v for (cs, p, l, v) in rows if cs == case], marker=mk, facecolor="none", edgecolor=c,
                      s=22, lw=0.9, zorder=3)
    b0 = (3 * T + TSNS + 2 * TS) * 1e6
    for m_, lab in ((0, "Eq. (18), $m$ = 0: %.1f µs"), (2, "Eq. (18), $m$ = 2: %.1f µs")):
        ax[0].axhline(b0 + m_ * 20, color=MUTED, ls="--" if m_ == 0 else ":", lw=0.8)
        ax[0].text(0.01, b0 + m_ * 20 + 1.2, lab % (b0 + m_ * 20), fontsize=6.8, color=MUTED)
    out = [r for r in rows if r[2] > 70][0]
    ax[0].annotate("second window accepted ($m$ = 2)", xy=(out[1], out[2]), xytext=(0.22, 76),
                   fontsize=6.8, color=INK, arrowprops=dict(arrowstyle="-", lw=0.5, color=MUTED))
    ax[0].set_ylim(40, 108)
    ax[0].set_xlabel("fault instant within the period (0–1)")
    ax[0].set_ylabel("detection time (µs)")
    ax[0].legend(fontsize=6.8, loc="upper left", frameon=False, bbox_to_anchor=(0.0, 0.9), ncol=1)
    ax[1].axhline(10, color=MUTED, ls=":", lw=0.8)
    ax[1].text(0.02, 9.8, "±5 % limit (10 V)", fontsize=6.8, color=MUTED, va="top")
    ax[1].set_ylim(6.8, 10.4)
    ax[1].set_xlabel("fault instant within the period (0–1)")
    ax[1].set_ylabel("output dip (V)")
    fig.tight_layout(w_pad=2.0)
    save(fig, "fig10_random_fault_instants")


if __name__ == "__main__":
    what = set(sys.argv[1:]) or {"all"}
    if what & {"flow", "all"}:
        fig_flow()
    if what & {"bench", "all"}:
        fig_bench()
    if what & {"valid", "all"}:
        fig_validation()
    if what & {"comparison", "all"}:
        fig_comparison()
    if what & {"isolation", "all"}:
        fig_isolation()
    if what & {"random", "all"}:
        fig_random()
    if what & {"arch", "all"}:
        fig_architecture()
    if what & {"rev3"}:
        fig_rev3()
