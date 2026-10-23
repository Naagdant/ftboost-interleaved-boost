"""Figures for the Elsevier/Springer single-column manuscript (paper/elsevier/).

Reuses the parent figure set (sim/paper_figures.py) and its palette, redirected to the final
result set (SSD + 5 ms relay, tags *_final / *_c150u_final), and adds the SSD architecture and
flow, isolation-timing, proposed-vs-conventional, detector feature-space and robustness figures.

  python -I sim/paper_figs_elsevier.py
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import controller as C  # noqa: E402
import paper_figures as PF  # noqa: E402  (sets rcParams + palette)

plt = PF.plt
ROOT = PF.ROOT
RES = PF.RES
OUT = os.path.join(ROOT, "paper", "elsevier", "figures")
PF.OUT = OUT
_load, _meta = PF.load, PF.meta


def _final(name):
    return name.replace("c150u_noisy", "c150u_final").replace("_noisy", "_final")


PF.load = lambda name: _load(_final(name))
PF.meta = lambda name: _meta(_final(name))
C1, C2, C3, INK, MUTED = PF.C1, PF.C2, PF.C3, PF.INK, PF.MUTED
W1 = 6.3          # single-column text width [in]
FAULTS = [("open_inductor", "Open inductor"), ("shorted_switch", "Shorted switch"), ("open_diode", "Open diode")]


def first_fault(name):
    ev = [e for e in _meta(name)["events"] if e["event"].startswith(("FAULT_", "WOULD_DETECT_"))]
    return ev[0]["t"] if ev else None


def fig_architecture():
    box, arrow = PF.box, PF.arrow
    fig, ax = plt.subplots(figsize=(W1, 3.3))
    ax.set_xlim(0, 15.6)
    ax.set_ylim(0, 8.2)
    ax.axis("off")
    ax.grid(False)
    box(ax, 0.1, 3.6, 1.5, 1.4, "48 V\nbattery", fs=7.5)
    for k, y in ((1, 5.8), (2, 2.0)):
        xs = [2.3, 4.0, 5.7, 7.4, 9.1]
        labs = ["Relay K$_%d$\nG2RL-1A" % k, "SSD$_%d$\n(1 µs off)" % k, "Shunt\n10 mΩ", "L$_%d$\n1 mH" % k,
                "S$_%d$ / D$_%d$\n650 V" % (k, k)]
        for i, (x, t) in enumerate(zip(xs, labs)):
            box(ax, x, y, 1.45, 1.1, t, fc="#fff4ec" if i < 2 else "#f4f6fa", fs=6.6)
            if i:
                arrow(ax, (xs[i - 1] + 1.45, y + 0.55), (x, y + 0.55))
        arrow(ax, (1.6, 4.3), (2.3, y + 0.55))
        arrow(ax, (10.55, y + 0.55), (11.3, 5.9 + (0.35 if k == 1 else -0.35)))
        ax.text(2.3, y + 1.25, f"Phase {k} ({'0°' if k == 1 else '180°'} carrier)", fontsize=7, style="italic",
                color=MUTED)
        box(ax, 5.55, y - 1.15, 1.75, 0.75, "AMC1300\nisolated amp", fs=6.2, fc="#f7f7f5")
        arrow(ax, (6.42, y), (6.42, y - 0.4), color=MUTED)
    box(ax, 11.3, 5.0, 1.9, 1.8, "C$_{out}$\n200 V bus\nload", fs=7.5)
    box(ax, 13.6, 0.4, 1.9, 7.2, "Controller\n\n5 MS/s, 12-bit\nADC\n\nlevel +\ntemplate\ndetectors\n(r, β)\n\nclassify\n\nisolate:\ngate → SSD\n→ relay\n\nACM loops\n(V outer,\nI inner)",
        fc="#f2faf6", fs=6.3)
    for y in (4.65, 0.85):
        ax.plot([7.3, 13.1], [y + 0.0, y + 0.0], color=MUTED, lw=0.7, ls="--")
        arrow(ax, (13.1, y), (13.6, y), color=MUTED, ls="--")
    ax.text(9.6, 4.75, "i$_{L1}$ (isolated)", fontsize=6.3, color=MUTED)
    ax.text(9.6, 0.95, "i$_{L2}$ (isolated)", fontsize=6.3, color=MUTED)
    arrow(ax, (13.2, 5.9), (13.6, 5.9), color=MUTED, ls="--")
    ax.text(13.05, 6.95, "V$_{out}$", fontsize=6.3, color=MUTED)
    ax.text(10.9, 7.75, "gate, SSD and relay commands, duty d$_1$, d$_2$  ←", fontsize=6.3, color=C3)
    save_both(fig, "fig01_architecture")


def fig_flow():
    """Parent flow chart with the SSD-first isolation sequence."""
    box, arrow = PF.box, PF.arrow
    fig, ax = plt.subplots(figsize=(W1, 3.5))
    ax.set_xlim(0, 14.4)
    ax.set_ylim(0.4, 7.6)
    ax.axis("off")
    ax.grid(False)
    box(ax, 0.2, 6.3, 3.4, 1.0, "Sample i$_{L1}$, i$_{L2}$, V$_{out}$\n(5 MS/s isolated ADC)", fs=7)
    box(ax, 0.2, 4.1, 3.4, 1.7, "Level detectors (per sample)\nopen L: i < 0.21 A for 100 µs\n"
        "short: i > I$_{trip}$ for 60 µs\nI$_{trip}$ = 3.59 A (2-ph) / 6.76 A (1-ph)", fs=6.2)
    box(ax, 4.1, 4.1, 3.8, 1.7, "Off-time template detector\n(once per switching period)\n"
        "window = (1−D)T, delay-compensated\nr ≥ 0.80  and  0.5 ≤ β ≤ 2.0", fs=6.2)
    box(ax, 8.4, 4.1, 2.6, 1.7, "Debounce\n3 consecutive\nviolating windows", fs=6.8)
    box(ax, 11.5, 4.1, 2.7, 1.7, "Classify\nmax i < 0.21 A → open L\nβ < 0 → shorted switch\nelse → open diode", fs=6.6)
    box(ax, 11.5, 1.5, 2.7, 1.8, "Isolate faulted phase\n1) gate inhibit (t$_d$)\n2) SSD off (t$_d$ + 1 µs)\n"
        "3) relay open (≤ 5 ms)", fc="#fff4ec", fs=6.6)
    box(ax, 6.9, 1.5, 4.1, 1.8, "Reconfigure (same control law)\nI$_{ref,k}$ = I$_{ref,tot}$ / N$_{active}$, N$_{active}$ = 1\n"
        "limits → 5.0 A clamp, 6.76 A trip\nouter V PI trims D (anti-windup)", fc="#f2faf6", fs=6.6)
    box(ax, 3.0, 1.5, 3.4, 1.8, "Degraded-mode operation\nsingle phase, no shutdown\nhigher ripple (reported)", fs=6.6)
    arrow(ax, (1.9, 6.3), (1.9, 5.8))
    arrow(ax, (3.6, 6.8), (6.0, 5.8))
    arrow(ax, (7.9, 4.95), (8.4, 4.95))
    ax.plot([1.9, 1.9, 9.7], [4.1, 3.65, 3.65], color=INK, lw=0.8)
    arrow(ax, (9.7, 3.65), (9.7, 4.1))
    ax.text(4.2, 3.75, "level timer already debounced", fontsize=6.3, color=MUTED)
    arrow(ax, (11.0, 4.95), (11.5, 4.95))
    arrow(ax, (12.85, 4.1), (12.85, 3.3))
    arrow(ax, (11.5, 2.4), (11.0, 2.4))
    arrow(ax, (6.9, 2.4), (6.4, 2.4))
    ax.text(0.2, 0.7, "Detectors armed after soft-start (t ≥ 30 ms); template learned from 250 healthy cycles "
            "(40–45 ms); no blanking after reconfiguration.", fontsize=6.6, color=MUTED)
    save_both(fig, "fig04_fault_management_flow")


def fig_isolation_timing():
    a = _load("shorted_switch_relay5ms")["rec"]     # relay only, 5 ms release
    b = _load("shorted_switch_final")["rec"]        # gate + SSD (1 us) + relay 5 ms
    fig, ax = plt.subplots(figsize=(4.2, 2.6))
    for r, lab, c, ls in ((a, "relay only (5 ms release)", C2, "--"),
                          (b, "SSD (1 µs) + relay (5 ms release)", C1, "-")):
        m = (r[:, 0] >= 49.5e-3) & (r[:, 0] <= 58e-3)
        ax.plot(r[m, 0] * 1e3, np.maximum(r[m, 2], 1e-2), color=c, ls=ls, lw=0.9, label=lab)
    ax.axhline(C.I_SHORT_TH_2PH, color=MUTED, ls=":", lw=0.8)
    ax.text(57.9, 4.3, "3.59 A", fontsize=6.5, color=MUTED, ha="right")
    ax.set_yscale("log")
    ax.set_ylim(1e-2, 400)
    ax.set_xlabel("t (ms)")
    ax.set_ylabel("i$_{L1}$ (A), log scale")
    ax.text(55.2, 175, f"peak {a[:, 2].max():.0f} A", fontsize=7)
    ax.text(50.3, 7.5, f"peak {b[b[:, 0] > 50e-3, 2].max():.2f} A", fontsize=7, color=C1)
    ax.legend(loc="lower right")
    save_both(fig, "fig13_isolation_timing")


def fig_comparison():
    fig, ax = plt.subplots(2, 3, figsize=(W1, 3.6), sharex=True)
    for j, (case, title) in enumerate(FAULTS):
        rp, rb = _load(f"{case}_final")["rec"], _load(f"{case}_baseline")["rec"]
        for r, lab, c, ls in ((rb, "conventional", C2, "--"), (rp, "proposed", C1, "-")):
            m = r[:, 0] >= 48e-3
            ax[0, j].plot(r[m, 0] * 1e3, r[m, 1], color=c, ls=ls, lw=0.8, label=lab)
            ax[1, j].plot(r[m, 0] * 1e3, np.abs(r[m, 2]), color=c, ls=ls, lw=0.5, label=lab)
        ax[0, j].axhspan(190, 210, color=PF.BAND, alpha=0.12, lw=0)
        ax[0, j].set_ylim(120, 225)
        ax[0, j].set_title(f"({'abc'[j]}) {title}")
        ax[1, j].set_yscale("symlog", linthresh=5)
        ax[1, j].set_ylim(0, 400)
        ax[1, j].set_xlabel("t (ms)")
        ax[1, j].set_xlim(48, 80)
        for k in range(2):
            ax[k, j].axvline(50, color=MUTED, lw=0.6, ls=":")
    ax[0, 0].set_ylabel("V$_{out}$ (V)")
    ax[1, 0].set_ylabel("|i$_{L1}$| faulted phase (A)")
    ax[0, 0].legend(loc="lower left")
    save_both(fig, "fig11_proposed_vs_conventional")


def fig_feature_space():
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    hr, hb = [], []
    for n in ["healthy_final", "healthy_c150u_final", "healthy_loadstep", "healthy_vin43", "healthy_vin53",
              "healthy_l2mismatch"]:
        if os.path.exists(os.path.join(RES, n + ".npz")):
            sc = _load(n)["scores"]
            hr += list(sc[:, 2])
            hb += list(sc[:, 3])
    for case, _ in FAULTS:
        sc = _load(f"{case}_final")["scores"]
        h = sc[sc[:, 0] < 50e-3]
        hr += list(h[:, 2])
        hb += list(h[:, 3])
    ax.scatter(hb, hr, s=2, color=C1, alpha=0.2, rasterized=True, label=f"healthy windows (n = {len(hr):,})")
    for (case, title), mk, c in zip(FAULTS, ("s", "^", "o"), (INK, C2, C3)):
        sc = _load(f"{case}_final")["scores"]
        td = first_fault(f"{case}_final")
        f = sc[(sc[:, 1] == 1) & (sc[:, 0] >= 50e-3) & (sc[:, 0] <= td + 1e-9)][-C.DIODE_N:]   # tripping windows
        ax.scatter(f[:, 3], f[:, 2], s=22, marker=mk, facecolor="none", edgecolor=c, lw=0.9,
                   label=f"faulted: {title.lower()}")
    ax.add_patch(plt.Rectangle((C.SLOPE_LO, C.DIODE_R_TH), C.SLOPE_HI - C.SLOPE_LO, 1.03 - C.DIODE_R_TH,
                               fill=False, ls="--", color=INK, lw=0.8))
    ax.text(C.SLOPE_HI + 0.05, 0.86, "acceptance\nregion", fontsize=6.5, color=INK)
    ax.set_xlabel("off-time slope ratio β")
    ax.set_ylabel("template correlation r")
    ax.set_xlim(-0.8, 4.5)
    ax.set_ylim(-1.1, 1.08)
    ax.legend(loc="lower right", fontsize=6.3)
    save_both(fig, "fig14_detector_feature_space")


def fig_robustness():
    names = [("healthy_loadstep", "(a) load 0.5 → 1 → 0.5 p.u."), ("healthy_vin43", "(b) V$_{in}$ = 43.2 V"),
             ("healthy_vin53", "(c) V$_{in}$ = 52.8 V"), ("healthy_l2mismatch", "(d) L$_2$ = 1.1 mH")]
    fig, ax = plt.subplots(2, 4, figsize=(W1, 3.0), sharex=True)
    for j, (n, title) in enumerate(names):
        r = _load(n)["rec"]
        m = r[:, 0] >= 40e-3
        ax[0, j].plot(r[m, 0] * 1e3, r[m, 1], color=C1, lw=0.8)
        ax[0, j].axhspan(190, 210, color=PF.BAND, alpha=0.12, lw=0)
        ax[0, j].set_ylim(185, 215)
        ax[0, j].set_title(title, fontsize=7.5)
        ax[1, j].plot(r[m, 0] * 1e3, r[m, 2], color=C2, lw=0.35, label="i$_{L1}$")
        ax[1, j].plot(r[m, 0] * 1e3, r[m, 3], color=C1, lw=0.35, label="i$_{L2}$")
        ax[1, j].axhline(C.I_SHORT_TH_2PH, color=MUTED, ls=":", lw=0.8)
        ax[1, j].set_ylim(0, 4)
        ax[1, j].set_xlabel("t (ms)")
    ax[0, 0].set_ylabel("V$_{out}$ (V)")
    ax[1, 0].set_ylabel("i$_L$ (A)")
    ax[1, 0].legend(loc="upper left", fontsize=6)
    save_both(fig, "fig15_robustness")


def fig_schematic():
    """KiCad schematic (with SSDs) rendered from kicad-cli PDF export."""
    kc = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
    sch = os.path.join(ROOT, "kicad", "ft_boost", "ft_boost.kicad_sch")
    pdf = os.path.join(OUT, "fig02_schematic_full.pdf")
    subprocess.run([kc, "sch", "export", "pdf", "--black-and-white", "-o", pdf, sch], check=True,
                   capture_output=True)
    png = os.path.join(OUT, "fig02_schematic_full.png")
    subprocess.run(["sips", "-s", "format", "png", "-Z", "3600", pdf, "--out", png], check=True,
                   capture_output=True)
    img = plt.imread(png)                       # crop to the drawn area (drop empty lower sheet)
    h, w = img.shape[:2]
    plt.imsave(png, img[int(0.035 * h):int(0.73 * h), int(0.03 * w):int(0.80 * w)])


def fig_illustrative():
    """Fig. 3: detector on recorded phase-1 windows around the open-diode fault."""
    import math
    import replay
    d = _load("open_diode_final")
    raw, sc = d["raw"].astype(float), d["scores"]
    rng = np.random.default_rng(1)          # same noise seed as the closed-loop run's controller is not
    sig = replay.noisy(raw[:, 1], 1.0, rng)  # reproducible here; windows are re-noised for display only
    ph1 = sc[sc[:, 1] == 1]
    rows = [ph1[(ph1[:, 0] > 49.9e-3) & (ph1[:, 0] < 50e-3)][-1]] + list(ph1[ph1[:, 0] >= 50.01e-3][:3])
    # healthy template: mean of learned windows is not stored; rebuild from 40-45 ms clean trace windows
    fig, ax = plt.subplots(1, 4, figsize=(W1, 2.1), sharey=True)
    t0 = raw[0, 0]
    for j, row in enumerate(rows):
        t_end, r, beta, n = row[0], row[2], row[3], int(row[4])
        e = int(round((t_end - t0) / C.TS))
        x = sig[e - n + 1:e + 1]
        tt = (np.arange(n) - (n - 1)) * C.TS * 1e6
        ax[j].plot(tt, x, "o", ms=2.6, color=C2 if (r < C.DIODE_R_TH or not C.SLOPE_LO <= beta <= C.SLOPE_HI) else C1)
        k = np.polyfit(tt, x, 1)
        ax[j].plot(tt, np.polyval(k, tt), color=INK, lw=0.8)
        ref = x.mean() + (tt - tt.mean()) * (-0.152)        # healthy slope through the window centre
        ax[j].plot(tt, ref, "--", color=MUTED, lw=0.8)
        bad = r < C.DIODE_R_TH or not (C.SLOPE_LO <= beta <= C.SLOPE_HI)
        ax[j].set_title(("(a) healthy" if j == 0 else f"({'abcd'[j]}) window {j} after fault") +
                        f"\nr = {r:.3f}, β = {beta:.2f}" + ("\nviolation" if bad else "\naccepted"), fontsize=7,
                        color=C2 if bad else INK)
        ax[j].set_xlabel("t − t$_{end}$ (µs)")
    ax[0].set_ylabel("sensed i$_{L1}$ (A)")
    ax[0].set_ylim(-0.4, 2.8)
    ax[3].plot([], [], "--", color=MUTED, label="healthy slope")
    ax[3].plot([], [], color=INK, label="least-squares fit")
    ax[3].legend(fontsize=6, loc="upper right")
    save_both(fig, "fig03_illustrative_example")


def fig_random_latency():
    """Fig. 10: detection latency against the fault instant within the switching period."""
    import glob
    fig, ax = plt.subplots(1, 2, figsize=(W1, 2.4))
    marks = {"open_inductor": ("s", INK), "shorted_switch": ("^", C2), "open_diode": ("o", C3)}
    rows = []
    for f in sorted(glob.glob(os.path.join(RES, "*_rand??.json"))):
        m = json.load(open(f))
        ev = [e for e in m["events"] if e["event"].startswith("FAULT_")]
        if not ev:
            continue
        tf = m["t_fault_s"]
        phase = ((tf % C.T) / C.T)
        lat = (ev[0]["t"] - tf) * 1e6
        r = _load(os.path.basename(f)[:-5])["rec"]
        post = r[r[:, 0] >= tf]
        rows.append((m["case"], phase, lat, 200 - post[:, 1].min()))
    for case, (mk, c) in marks.items():
        x = [p for (cs, p, l, dv) in rows if cs == case]
        y = [l for (cs, p, l, dv) in rows if cs == case]
        dv = [v for (cs, p, l, v) in rows if cs == case]
        ax[0].scatter(x, y, marker=mk, facecolor="none", edgecolor=c, s=20, lw=0.9, label=case.replace("_", " "))
        ax[1].scatter(x, dv, marker=mk, facecolor="none", edgecolor=c, s=20, lw=0.9)
    bound = (3 * C.T + C.T_SNS_DELAY + 2 * C.TS) * 1e6
    ax[0].axhline(bound, color=MUTED, ls="--", lw=0.8)
    ax[0].text(0.02, bound + 0.8, f"bound, Eq. (18): {bound:.1f} µs", fontsize=6.5, color=MUTED)
    ax[0].set_xlabel("fault instant within the period (phase-1 carrier, 0–1)")
    ax[0].set_ylabel("detection time (µs)")
    ax[1].axhline(10, color=MUTED, ls=":", lw=0.8)
    ax[1].text(0.02, 9.8, "±5 % limit (10 V)", fontsize=6.5, color=MUTED)
    ax[1].set_ylim(6.8, 10.4)
    ax[1].set_xlabel("fault instant within the period (0–1)")
    ax[1].set_ylabel("output dip (V)")
    ax[0].legend(fontsize=6, loc="upper center")
    save_both(fig, "fig10_random_fault_instants")
    return rows


def fig_benchmark():
    """Fig. 12: detection time and false trips of the five detectors (nominal noise)."""
    b = json.load(open(os.path.join(RES, "detector_benchmark.json")))
    dets = [("level", "level only"), ("r_fixed", "r, fixed window"), ("r_adaptive", "r, adaptive"),
            ("beta_only", "β only"), ("proposed", "proposed (r + β)")]
    faults = [("open_inductor", "OL"), ("shorted_switch", "SC"), ("open_diode", "OD")]
    fig, ax = plt.subplots(1, 2, figsize=(W1, 2.4), gridspec_kw={"width_ratios": [3, 1.3]})
    w = 0.16
    for i, (dk, dl) in enumerate(dets):
        e = b[f"{dk}@1x"]
        for j, (fk, fl) in enumerate(faults):
            v = e["faults"][fk]
            x = j + (i - 2) * w
            if v["latency_us"]:
                ax[0].bar(x, v["latency_us"][1], w, color=[INK, C2, MUTED, C3, C1][i], label=dl if j == 0 else None)
            else:
                ax[0].text(x, 3, "×", ha="center", fontsize=9, color=[INK, C2, MUTED, C3, C1][i])
        ax[1].bar(i, e["healthy"]["false_trips"], color=[INK, C2, MUTED, C3, C1][i])
    ax[0].set_xticks(range(3))
    ax[0].set_xticklabels(["open inductor", "shorted switch", "open diode"])
    ax[0].set_ylabel("detection time (µs)  (× = missed)")
    ax[0].legend(fontsize=5.8, ncol=2, loc="upper left")
    ax[1].set_xticks(range(5))
    ax[1].set_xticklabels(["L", "rF", "rA", "β", "P"], fontsize=7)
    ax[1].set_ylabel("false trips, healthy runs")
    save_both(fig, "fig12_detector_benchmark")


def rename_parent_figures():
    ren = {"fig04_openloop_validation.png": "fig05_openloop_validation.png",
           "fig05_vout_fault_response.png": "fig06_vout_fault_response.png",
           "fig06_phase_currents.png": "fig07_phase_currents.png",
           "fig07_offtime_signatures.png": "fig08_offtime_signatures.png",
           "fig08_template_scores_open_diode.png": "fig09_template_scores_open_diode.png"}
    for a, b in reversed(list(ren.items())):
        if os.path.exists(os.path.join(OUT, a)):
            os.replace(os.path.join(OUT, a), os.path.join(OUT, b))


def save_both(fig, stem):
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT, f"{stem}.{ext}"))
    plt.close(fig)
    print("wrote", stem)


def main():
    os.makedirs(OUT, exist_ok=True)
    fig_architecture()
    fig_schematic()
    fig_flow()
    PF.fig_validation()          # open-loop validation (unchanged data)
    PF.fig_vout()                # -> fig05 (final runs)
    PF.fig_currents()            # -> fig06
    PF.fig_signatures()          # -> fig07
    PF.fig_scores()              # -> fig08
    rename_parent_figures()      # parent numbering -> manuscript numbering (fig05-fig09)
    fig_illustrative()           # fig03
    fig_isolation_timing()       # fig13
    fig_comparison()             # fig11
    fig_feature_space()          # fig14
    fig_robustness()             # fig15
    if os.path.exists(os.path.join(RES, 'detector_benchmark.json')):
        fig_benchmark()          # fig12
    fig_random_latency()         # fig10


if __name__ == "__main__":
    main()
