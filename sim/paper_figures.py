"""Publication figures for paper/paper.md, drawn only from real simulation data.

  python -I sim/paper_figures.py     (needs numpy + matplotlib)

Inputs: results/*_noisy.npz, results/*_c150u_noisy.npz, results/shorted_switch*.npz,
results/validation/openloop_*.npy, results/*.json. Output: paper/figures/figNN_*.png
"""
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
OUT = os.path.join(ROOT, "paper", "figures")
sys.path.insert(0, os.path.join(ROOT, "sim"))
from controller import I_SHORT_TH_1PH, I_SHORT_TH_2PH  # noqa: E402

# validated categorical palette (dataviz reference, light mode) + secondary encoding by line style
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#222222", "#6b6b6b", "#d9d9d6"
BAND = "#1baf7a"

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset": "stix", "font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9,
    "legend.fontsize": 7.5, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.0,
    "savefig.dpi": 300, "savefig.bbox": "tight", "legend.frameon": False,
})
T_F = 50e-3
CASES = [("open_inductor", "Open inductor", C1, "-"),
         ("shorted_switch", "Shorted switch", C2, "--"),
         ("open_diode", "Open diode", C3, "-.")]


def load(name):
    d = np.load(os.path.join(RES, name + ".npz"))
    return {k: d[k] for k in d.files}


def meta(name):
    return json.load(open(os.path.join(RES, name + ".json")))


def t_detect(name):
    ev = [e for e in meta(name)["events"] if e["event"].startswith("FAULT_")]
    return ev[0]["t"] if ev else None


def save(fig, name):
    fig.savefig(os.path.join(OUT, name))
    plt.close(fig)
    print("wrote", name)


# ---------------------------------------------------------------- Fig. 1
def box(ax, x, y, w, h, text, fc="#f4f6fa", ec=MUTED, fs=8, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fc, ec=ec, lw=0.8))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=INK,
            weight="bold" if bold else "normal", linespacing=1.25)


def arrow(ax, p, q, color=INK, ls="-", text=None, toff=(0, 0.12)):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=9, lw=0.8, color=color, ls=ls))
    if text:
        ax.text((p[0] + q[0]) / 2 + toff[0], (p[1] + q[1]) / 2 + toff[1], text, ha="center",
                fontsize=6.8, color=color)


def fig_architecture():
    fig, ax = plt.subplots(figsize=(7.16, 3.6))
    ax.set_xlim(0, 12.2)
    ax.set_ylim(0, 7.2)
    ax.axis("off")
    ax.grid(False)
    box(ax, 0.1, 3.0, 1.5, 1.2, "48 V\nbattery\n(EV LV bus)", bold=True)
    rows = {1: 5.0, 2: 1.0}
    for k, y in rows.items():
        c = C1 if k == 1 else C2
        box(ax, 2.3, y, 1.6, 1.3, f"K{k}\nG2RL-1A\nrelay", fc="#eef4fc" if k == 1 else "#fff4ec")
        box(ax, 4.4, y, 1.6, 1.3, f"R$_{{SH{k}}}$ 10 mΩ\n+ AMC1300\n(isolated)")
        box(ax, 6.5, y, 1.7, 1.3, f"L$_{k}$ 1 mH\nQ$_{k}$ 650 V\nD$_{k}$ SiC SBD")
        ax.text(2.3, y + 1.42 if k == 1 else y - 0.42, f"Phase {k} ({'0°' if k == 1 else '180°'} carrier)",
                fontsize=7.5, color=c)
        arrow(ax, (1.6, 3.6), (2.3, y + 0.65))
        arrow(ax, (3.9, y + 0.65), (4.4, y + 0.65))
        arrow(ax, (6.0, y + 0.65), (6.5, y + 0.65))
        arrow(ax, (8.2, y + 0.65), (9.0, 3.6))
    box(ax, 9.0, 3.0, 1.6, 1.2, "200 V bus\nC$_{out}$ + load\n(≈200 W)", bold=True)
    box(ax, 2.6, 2.85, 5.6, 1.5, "Digital controller\n3 fault detectors + debounce · relay open + gate inhibit\n"
        "outer V-loop / inner I-loops · mode-aware current limits", fc="#f2faf6", fs=7)
    # isolated current sensing (green dashed), commands (grey dotted)
    arrow(ax, (5.2, 5.0), (5.2, 4.35), color=C3, ls="--")
    ax.text(5.3, 4.6, "i$_{L1}$", fontsize=7, color=C3)
    arrow(ax, (5.2, 2.3), (5.2, 2.85), color=C3, ls="--")
    ax.text(5.3, 2.5, "i$_{L2}$", fontsize=7, color=C3)
    arrow(ax, (9.0, 3.3), (8.2, 3.3), color=C3, ls="--")
    ax.text(8.35, 3.42, "V$_{out}$", fontsize=7, color=C3)
    arrow(ax, (3.1, 4.35), (3.1, 5.0), color=MUTED, ls=":")
    arrow(ax, (3.1, 2.85), (3.1, 2.3), color=MUTED, ls=":")
    arrow(ax, (7.35, 4.35), (7.35, 5.0), color=MUTED, ls=":")
    arrow(ax, (7.35, 2.85), (7.35, 2.3), color=MUTED, ls=":")
    ax.text(10.75, 1.1, "— — isolated sensing\n· · · · relay / PWM / gate-inhibit\n           commands", fontsize=6.8,
            color=MUTED, va="bottom")
    save(fig, "fig01_architecture.png")


# ---------------------------------------------------------------- Fig. 3
def fig_flow():
    fig, ax = plt.subplots(figsize=(7.16, 3.8))
    ax.set_xlim(0, 14.4)
    ax.set_ylim(0.4, 7.6)
    ax.axis("off")
    ax.grid(False)
    box(ax, 0.2, 6.3, 3.4, 1.0, "Sample i$_{L1}$, i$_{L2}$, V$_{out}$\n(5 MS/s isolated ADC)", fs=7.5)
    box(ax, 0.2, 4.1, 3.4, 1.7, "Level detectors (per sample)\nopen L: i < 0.21 A for 100 µs\n"
        "short: i > I$_{trip}$ for 60 µs\nI$_{trip}$ = 3.59 A (2-ph) / 6.76 A (1-ph)", fs=6.4)
    box(ax, 4.1, 4.1, 3.8, 1.7, "Off-time template detector\n(once per switching period)\n"
        "window = (1−D)T, delay-compensated\nr ≥ 0.80  and  0.5 ≤ β ≤ 2.0", fs=6.4)
    box(ax, 8.4, 4.1, 2.6, 1.7, "Debounce\n3 consecutive\nviolating windows", fs=7)
    box(ax, 11.5, 4.1, 2.7, 1.7, "Classify\nmax i < 0.21 A → open L\nβ < 0 → shorted switch\n"
        "else → open diode", fs=7)
    box(ax, 11.5, 1.6, 2.7, 1.6, "Isolate faulted phase\ngate inhibit\nopen input relay K$_k$\nlog event",
        fc="#fff4ec", fs=7)
    box(ax, 6.9, 1.6, 4.1, 1.6, "Reconfigure (same control law)\nI$_{ref,k}$ = I$_{ref,tot}$ / N$_{active}$, N$_{active}$ = 1\n"
        "limits → 5.0 A clamp, 6.76 A trip\nouter V PI trims D (anti-windup)", fc="#f2faf6", fs=7)
    box(ax, 3.0, 1.6, 3.4, 1.6, "Degraded-mode operation\nsingle phase, no shutdown\n"
        "higher ripple (reported)", fs=7)
    arrow(ax, (1.9, 6.3), (1.9, 5.8))
    arrow(ax, (3.6, 6.8), (6.0, 5.8))
    arrow(ax, (7.9, 4.95), (8.4, 4.95))
    ax.plot([1.9, 1.9, 9.7], [4.1, 3.65, 3.65], color=INK, lw=0.8)
    arrow(ax, (9.7, 3.65), (9.7, 4.1))
    ax.text(4.2, 3.75, "level timer already debounced", fontsize=6.5, color=MUTED)
    arrow(ax, (11.0, 4.95), (11.5, 4.95))
    arrow(ax, (12.85, 4.1), (12.85, 3.2))
    arrow(ax, (11.5, 2.4), (11.0, 2.4))
    arrow(ax, (6.9, 2.4), (6.4, 2.4))
    ax.text(0.2, 0.75, "Detectors armed after soft-start (t ≥ 30 ms); template learned from 250 healthy cycles "
            "(40–45 ms); no blanking after reconfiguration.", fontsize=7, color=MUTED)
    save(fig, "fig03_fault_management_flow.png")


# ---------------------------------------------------------------- Fig. 4
def fig_validation():
    a = np.load(os.path.join(RES, "validation", "openloop_c150u.npy"))
    b = np.load(os.path.join(RES, "validation", "openloop_c14u.npy"))
    fig, ax = plt.subplots(1, 2, figsize=(7.16, 2.5))
    for d, lab, c, ls in ((b, "C$_{out}$ = 14 µF (stress case)", C2, "--"), (a, "C$_{out}$ = 150 µF", C1, "-")):
        m = d[:, 0] <= 40e-3
        ax[0].plot(d[m, 0] * 1e3, d[m, 1], color=c, ls=ls, lw=0.8, label=lab)
    vf = a[a[:, 0] > 50e-3, 1].mean()
    ax[0].axhspan(vf * 0.98, vf * 1.02, color=BAND, alpha=0.15, lw=0, label="±2 % of final value")
    ax[0].set_xlabel("t (ms)")
    ax[0].set_ylabel("V$_{out}$ (V)")
    ax[0].set_title("(a) Open-loop start-up, D = 0.76")
    ax[0].legend(loc="lower right")
    m = (b[:, 0] >= 79.94e-3) & (b[:, 0] <= 80e-3)
    ax[1].plot(b[m, 0] * 1e6 - 79940, b[m, 2], color=C1, ls="-", label="i$_{L1}$")
    ax[1].plot(b[m, 0] * 1e6 - 79940, b[m, 3], color=C2, ls="--", label="i$_{L2}$")
    ax[1].axhline(2.39127, color=MUTED, lw=0.7, ls=":")
    ax[1].text(1, 2.42, "Table IV peak 2.39127 A", fontsize=7, color=MUTED)
    ax[1].set_xlabel("t (µs, steady state, C$_{out}$ = 14 µF)")
    ax[1].set_ylabel("Phase current (A)")
    ax[1].set_title("(b) 180° interleaved phase currents")
    ax[1].legend(loc="lower right", ncol=2)
    fig.tight_layout()
    save(fig, "fig04_openloop_validation.png")


# ---------------------------------------------------------------- Fig. 5
def fig_vout():
    fig, ax = plt.subplots(1, 2, figsize=(7.16, 2.6), sharey=True)
    for j, (tag, title) in enumerate((("noisy", "(a) C$_{out}$ = 14 µF"), ("c150u_noisy", "(b) C$_{out}$ = 150 µF"))):
        for name, lab, c, ls in CASES:
            r = load(f"{name}_{tag}")["rec"]
            m = (r[:, 0] >= 49.8e-3) & (r[:, 0] <= 51.5e-3)
            ax[j].plot(r[m, 0] * 1e3, r[m, 1], color=c, ls=ls, lw=0.9, label=lab)
        ax[j].axhspan(190, 210, color=BAND, alpha=0.12, lw=0, label="±5 % band (190–210 V)")
        ax[j].axvline(50, color=INK, lw=0.6, ls=":")
        ax[j].text(50.02, 186.5, "fault", fontsize=7, color=INK)
        ax[j].set_title(title)
        ax[j].set_xlabel("t (ms)")
        ax[j].set_ylim(185, 205)
    ax[0].set_ylabel("V$_{out}$ (V)")
    ax[1].legend(loc="lower right")
    fig.tight_layout()
    save(fig, "fig05_vout_fault_response.png")


# ---------------------------------------------------------------- Fig. 6
def fig_currents():
    fig, ax = plt.subplots(3, 1, figsize=(7.16, 5.6), sharex=True)
    for k, (name, lab, c, ls) in enumerate(CASES):
        n = f"{name}_noisy"
        r = load(n)["rec"]
        m = (r[:, 0] >= 49.9e-3) & (r[:, 0] <= 50.8e-3)
        ax[k].plot(r[m, 0] * 1e3, r[m, 2], color=C1, ls="-", lw=0.8, label="i$_{L1}$ (faulted phase)")
        ax[k].plot(r[m, 0] * 1e3, r[m, 3], color=C2, ls="--", lw=0.8, label="i$_{L2}$ (surviving phase)")
        ax[k].axhline(I_SHORT_TH_2PH, color=MUTED, ls=":", lw=0.8)
        ax[k].axhline(I_SHORT_TH_1PH, color=INK, ls=":", lw=0.8)
        ax[k].text(50.81, I_SHORT_TH_2PH, " 3.59 A", fontsize=7, va="center", color=MUTED)
        ax[k].text(50.81, I_SHORT_TH_1PH, " 6.76 A", fontsize=7, va="center", color=INK)
        td = t_detect(n)
        ax[k].axvline(50, color=INK, lw=0.6, ls=":")
        ax[k].axvline(td * 1e3, color=INK, lw=0.6)
        ax[k].text(td * 1e3 + 0.005, 6.1, f"isolated +{(td - T_F) * 1e6:.1f} µs", fontsize=7, color=INK)
        ax[k].set_title(f"({'abc'[k]}) {lab}", loc="left")
        ax[k].set_ylabel("A")
        ax[k].set_ylim(-0.3, 7.3)
    ax[0].legend(loc="lower right", bbox_to_anchor=(0.97, 0.08), ncol=2)
    ax[2].set_xlabel("t (ms)  — dotted: fault onset; solid: detection + isolation")
    fig.tight_layout()
    save(fig, "fig06_phase_currents.png")


# ---------------------------------------------------------------- Fig. 7
def fig_signatures():
    """Sensed (noise-free) phase-1 current over two switching periods before and after each fault."""
    fig, ax = plt.subplots(1, 3, figsize=(7.16, 2.4), sharey=True)
    for k, (name, lab, c, ls) in enumerate(CASES):
        n = f"{name}_noisy"
        d = load(n)
        raw, sc = d["raw"], d["scores"]
        td = t_detect(n)
        pre = (raw[:, 0] >= 49.96e-3) & (raw[:, 0] < 50.0e-3)
        post = (raw[:, 0] >= td - 40e-6) & (raw[:, 0] < td)
        ax[k].plot((raw[pre, 0] - 49.96e-3) * 1e6, raw[pre, 1], color=MUTED, ls="-", lw=0.9, label="healthy (49.96 ms)")
        ax[k].plot((raw[post, 0] - (td - 40e-6)) * 1e6, raw[post, 1], color=c, ls=ls, lw=1.1,
                   label="last 2 periods before trip")
        s = sc[(sc[:, 1] == 1) & (sc[:, 0] <= td + 1e-9)][-1]
        ax[k].text(0.97, 0.93 if k != 1 else 0.30, f"tripping window\nr = {s[2]:.2f}, β = {s[3]:.2f}",
                   transform=ax[k].transAxes, ha="right", va="top", fontsize=7, color=INK)
        ax[k].set_title(f"({'abc'[k]}) {lab}")
        ax[k].set_xlabel("t (µs)")
    ax[0].set_ylabel("sensed i$_{L1}$ (A)")
    ax[0].legend(loc="lower left", fontsize=6.5)
    fig.tight_layout()
    save(fig, "fig07_offtime_signatures.png")


# ---------------------------------------------------------------- Fig. 8
def fig_scores():
    n = "open_diode_noisy"
    sc = load(n)["scores"]
    td = t_detect(n)
    fig, ax = plt.subplots(1, 2, figsize=(7.16, 2.4), sharex=True)
    for k, c, ls, lab in ((1, C1, "-", "phase 1 (faulted)"), (2, C2, "--", "phase 2 (surviving)")):
        m = (sc[:, 1] == k) & (sc[:, 0] >= 49.5e-3) & (sc[:, 0] <= 52e-3)
        ax[0].plot(sc[m, 0] * 1e3, sc[m, 2], color=c, ls=ls, marker="o", ms=2.5, lw=0.7, label=lab)
        ax[1].plot(sc[m, 0] * 1e3, sc[m, 3], color=c, ls=ls, marker="o", ms=2.5, lw=0.7, label=lab)
    ax[0].axhline(0.8, color=INK, ls=":", lw=0.8)
    ax[0].text(51.3, 0.82, "r = 0.80", fontsize=7)
    ax[1].axhspan(0.5, 2.0, color=BAND, alpha=0.12, lw=0)
    ax[1].text(51.2, 2.08, "accept 0.5 ≤ β ≤ 2.0", fontsize=7)
    for a in ax:
        a.axvline(50, color=INK, lw=0.6, ls=":")
        a.axvline(td * 1e3, color=INK, lw=0.6)
        a.set_xlabel("t (ms)")
    ax[0].set_ylabel("Pearson r")
    ax[1].set_ylabel("slope ratio β")
    ax[0].set_title("(a) shape: correlation with template")
    ax[1].set_title("(b) slope ratio vs template")
    ax[0].legend(loc="lower left")
    fig.tight_layout()
    save(fig, "fig08_template_scores_open_diode.png")


# ---------------------------------------------------------------- Fig. 9
def fig_relay():
    a = load("shorted_switch")["rec"]
    b = load("shorted_switch_relay5ms")["rec"]
    fig, ax = plt.subplots(figsize=(3.5, 2.4))
    for r, lab, c, ls in ((a, "ideal relay", C1, "-"), (b, "5 ms release (G2RL max)", C2, "--")):
        m = (r[:, 0] >= 49.5e-3) & (r[:, 0] <= 58e-3)
        ax.plot(r[m, 0] * 1e3, np.maximum(r[m, 2], 1e-2), color=c, ls=ls, lw=0.9, label=lab)
    ax.axhline(I_SHORT_TH_2PH, color=MUTED, ls=":", lw=0.8)
    ax.set_yscale("log")
    ax.set_ylim(1e-2, 400)
    ax.set_xlabel("t (ms)")
    ax.set_ylabel("i$_{L1}$ (A), log scale")
    ax.text(55.1, 175, f"peak {b[:, 2].max():.0f} A", fontsize=7)
    ax.legend(loc="lower right")
    save(fig, "fig09_relay_release_sensitivity.png")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    fig_architecture()
    fig_flow()
    fig_validation()
    fig_vout()
    fig_currents()
    fig_signatures()
    fig_scores()
    fig_relay()
