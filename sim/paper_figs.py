"""Publication figures + tables (IEEE style) from the final result set.

  python -I sim/paper_figs.py      -> paper_figs/*.pdf|png, paper_figs/tables.md
Run sim/analyze.py first (needs results/summary.json).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

import controller as C  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
OUT = os.path.join(ROOT, "paper_figs")
FAULTS = [("open_inductor", "Open inductor"), ("shorted_switch", "Shorted switch"), ("open_diode", "Open diode")]
COL1, COL2 = 3.5, 7.16      # IEEE single / double column width [in]

plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.labelsize": 8, "legend.fontsize": 6.5,
                     "xtick.labelsize": 7, "ytick.labelsize": 7, "lines.linewidth": 0.8,
                     "axes.grid": True, "grid.alpha": 0.3, "savefig.dpi": 300})
BLUE, ORANGE, GRAY, RED = "#1f4e9c", "#d9741c", "#7f7f7f", "#b22222"


def load(name):
    d = np.load(os.path.join(RES, name + ".npz"))
    meta = json.load(open(os.path.join(RES, name + ".json")))
    return d, meta


def save(fig, name):
    fig.tight_layout(pad=0.4)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"))
    plt.close(fig)


def fault_t(meta):
    f = [e for e in meta["events"] if e["event"].startswith(("FAULT_", "WOULD_DETECT_"))]
    return f[0]["t"] if f else None


def fig_comparison():
    """Proposed vs conventional: Vout and phase currents for each fault."""
    fig, ax = plt.subplots(3, 3, figsize=(COL2, 4.6), sharex=True)
    for j, (case, title) in enumerate(FAULTS):
        (dp, mp), (db, mb) = load(f"{case}_final"), load(f"{case}_baseline")
        rp, rb = dp["rec"], db["rec"]
        for r, lab, c, ls in ((rb, "Conventional", GRAY, "-"), (rp, "Proposed", BLUE, "-")):
            m = (r[:, 0] >= 48e-3)
            ax[0, j].plot(r[m, 0] * 1e3, r[m, 1], color=c, ls=ls, label=lab)
        ax[0, j].axhspan(190, 210, color="green", alpha=0.10, lw=0)
        ax[0, j].set_ylim(120, 230)
        ax[0, j].set_title(title, fontsize=8)
        m = rp[:, 0] >= 48e-3
        ax[1, j].plot(rp[m, 0] * 1e3, rp[m, 2], color=RED, lw=0.5, label="$i_{L1}$ (faulted)")
        ax[1, j].plot(rp[m, 0] * 1e3, rp[m, 3], color=BLUE, lw=0.5, label="$i_{L2}$ (surviving)")
        ax[1, j].axhline(C.I_SHORT_TH_1PH, color="k", ls=":", lw=0.7, label="6.76 A bound")
        ax[1, j].set_ylim(-0.5, 8)
        m = rb[:, 0] >= 48e-3
        ax[2, j].plot(rb[m, 0] * 1e3, rb[m, 2], color=RED, lw=0.5, label="$i_{L1}$")
        ax[2, j].plot(rb[m, 0] * 1e3, rb[m, 3], color=GRAY, lw=0.5, label="$i_{L2}$")
        if case == "shorted_switch":
            ax[2, j].set_yscale("symlog", linthresh=10)
        for k in range(3):
            ax[k, j].axvline(50, color=RED, lw=0.6, ls="--")
        ax[2, j].set_xlabel("Time (ms)")
        ax[2, j].set_xlim(48, 80)
    ax[0, 0].set_ylabel("$V_{out}$ (V)")
    ax[1, 0].set_ylabel("Proposed\nphase current (A)")
    ax[2, 0].set_ylabel("Conventional\nphase current (A)")
    ax[0, 0].legend(loc="lower left")
    ax[1, 0].legend(loc="upper left", ncol=1)
    ax[2, 0].legend(loc="upper left")
    save(fig, "fig_proposed_vs_conventional")


def fig_detection_zoom():
    """Fault onset -> detection -> isolation -> recovery, proposed design."""
    fig, ax = plt.subplots(3, 3, figsize=(COL2, 4.2), sharex=True)
    for j, (case, title) in enumerate(FAULTS):
        d, meta = load(f"{case}_final")
        r = d["rec"]
        td = fault_t(meta)
        m = (r[:, 0] >= 49.9e-3) & (r[:, 0] <= 51.0e-3)
        t = r[m, 0] * 1e3
        ax[0, j].plot(t, r[m, 1], color=BLUE)
        ax[0, j].axhspan(190, 210, color="green", alpha=0.10, lw=0)
        ax[0, j].set_ylim(185, 205)
        ax[0, j].set_title(f"{title} (detected in {(td - 50e-3) * 1e6:.0f} µs)", fontsize=8)
        ax[1, j].plot(t, r[m, 2], color=RED, lw=0.6, label="$i_{L1}$ true")
        ax[1, j].plot(t, r[m, 4], color=ORANGE, lw=0.6, ls="--", label="$i_{L1}$ sensed (AMC1300+ADC)")
        ax[1, j].plot(t, r[m, 3], color=BLUE, lw=0.6, label="$i_{L2}$ true")
        ax[2, j].plot(t, np.maximum(r[m, 6], -0.05), color=RED, lw=0.7, label="$d_1$")
        ax[2, j].plot(t, r[m, 7], color=BLUE, lw=0.7, label="$d_2$")
        for k in range(3):
            ax[k, j].axvline(50, color=RED, lw=0.6, ls="--")
            ax[k, j].axvline(td * 1e3, color="k", lw=0.6)
        ax[2, j].set_xlabel("Time (ms)")
    ax[0, 0].set_ylabel("$V_{out}$ (V)")
    ax[1, 0].set_ylabel("Current (A)")
    ax[2, 0].set_ylabel("Duty")
    ax[1, 0].legend(loc="upper left")
    ax[2, 0].legend(loc="center left")
    save(fig, "fig_detection_zoom")


def fig_feature_space():
    """Detector feature space: every scored off-time window (r, beta)."""
    fig, ax = plt.subplots(figsize=(COL1, 2.6))
    healthy_r, healthy_b = [], []
    for name in ["healthy_final", "healthy_c150u_final", "healthy_loadstep", "healthy_vin43",
                 "healthy_vin53", "healthy_l2mismatch"]:
        if os.path.exists(os.path.join(RES, name + ".npz")):
            sc = load(name)[0]["scores"]
            healthy_r += list(sc[:, 2])
            healthy_b += list(sc[:, 3])
    for case, title in FAULTS:
        d, meta = load(f"{case}_final")
        sc = d["scores"]
        healthy = sc[sc[:, 0] < 50e-3]
        healthy_r += list(healthy[:, 2])
        healthy_b += list(healthy[:, 3])
    ax.scatter(healthy_b, healthy_r, s=2, color=BLUE, alpha=0.25, label=f"healthy windows (n={len(healthy_r)})",
               rasterized=True)
    marks = {"open_inductor": ("s", "open inductor"), "shorted_switch": ("^", "shorted switch"),
             "open_diode": ("o", "open diode")}
    for case, title in FAULTS:
        d, meta = load(f"{case}_final")
        sc = d["scores"]
        td = fault_t(meta)
        f = sc[(sc[:, 1] == 1) & (sc[:, 0] >= 50e-3) & (sc[:, 0] <= td + 1e-9)]
        mk, lab = marks[case]
        ax.scatter(f[:, 3], f[:, 2], s=18, marker=mk, facecolor="none", edgecolor=RED, lw=0.8,
                   label=f"faulted: {lab}")
    ax.add_patch(plt.Rectangle((C.SLOPE_LO, C.DIODE_R_TH), C.SLOPE_HI - C.SLOPE_LO, 1.02 - C.DIODE_R_TH,
                               fill=False, ls="--", color="k", lw=0.8))
    ax.text(C.SLOPE_HI, C.DIODE_R_TH - 0.06, "healthy region", ha="right", fontsize=6.5)
    ax.set_xlabel(r"Off-time slope ratio $\beta$")
    ax.set_ylabel("Template correlation $r$")
    ax.set_xlim(-0.8, 4.5)
    ax.set_ylim(-1.1, 1.05)
    ax.legend(loc="lower right", fontsize=5.5, markerscale=1)
    save(fig, "fig_detector_feature_space")


def fig_noise_margin():
    p = os.path.join(RES, "replay_noise_sweep.json")
    if not os.path.exists(p):
        return
    rows = [r for r in json.load(open(p)) if r["tag"] == "noisy"]
    nz = [r["noise"] for r in rows]
    rmin = [r["cases"]["healthy"]["r_min"]["healthy"] for r in rows]
    surv = [min(v["r_min"].get("survivor_reconf_1ms", 9) for v in r["cases"].values()) for r in rows]
    fth = [max(r["cases"]["healthy"]["false_trips_per_hour_est"], 1e-300) for r in rows]
    fig, ax = plt.subplots(1, 2, figsize=(COL1, 1.9))
    sig = [16 * n for n in nz]
    ax[0].plot(sig, rmin, "o-", color=BLUE, ms=3, label="healthy")
    ax[0].plot(sig, surv, "s-", color=ORANGE, ms=3, label="survivor, 1 ms after reconf.")
    ax[0].axhline(C.DIODE_R_TH, color="k", ls="--", lw=0.7)
    ax[0].set_xlabel("Sensed-current noise (mA rms)")
    ax[0].set_ylabel("min $r$")
    ax[0].legend(fontsize=5.5, loc="lower left")
    ax[1].semilogy(sig, np.clip(fth, 1e-120, None), "o-", color=BLUE, ms=3)
    ax[1].axhline(1e-6, color="k", ls=":", lw=0.7)
    ax[1].set_xlabel("Sensed-current noise (mA rms)")
    ax[1].set_ylabel("Est. false trips / h")
    save(fig, "fig_noise_margin")


def fig_robustness():
    names = [("healthy_loadstep", "Load step 0.5→1→0.5 p.u."), ("healthy_vin43", "$V_{in}$ = 43.2 V (−10 %)"),
             ("healthy_vin53", "$V_{in}$ = 52.8 V (+10 %)"), ("healthy_l2mismatch", "$L_2$ = 1.1 mH (+10 %)")]
    names = [n for n in names if os.path.exists(os.path.join(RES, n[0] + ".npz"))]
    if not names:
        return
    fig, ax = plt.subplots(2, len(names), figsize=(COL2, 2.8), sharex=True, squeeze=False)
    for j, (n, title) in enumerate(names):
        r = load(n)[0]["rec"]
        m = r[:, 0] >= 40e-3
        ax[0, j].plot(r[m, 0] * 1e3, r[m, 1], color=BLUE)
        ax[0, j].axhspan(190, 210, color="green", alpha=0.10, lw=0)
        ax[0, j].set_ylim(185, 215)
        ax[0, j].set_title(title, fontsize=7.5)
        ax[1, j].plot(r[m, 0] * 1e3, r[m, 2], color=RED, lw=0.4, label="$i_{L1}$")
        ax[1, j].plot(r[m, 0] * 1e3, r[m, 3], color=BLUE, lw=0.4, label="$i_{L2}$")
        ax[1, j].axhline(C.I_SHORT_TH_2PH, color="k", ls=":", lw=0.7)
        ax[1, j].set_xlabel("Time (ms)")
        ax[1, j].set_ylim(0, 4)
    ax[0, 0].set_ylabel("$V_{out}$ (V)")
    ax[1, 0].set_ylabel("Phase current (A)")
    ax[1, 0].legend(loc="upper left")
    save(fig, "fig_robustness_no_false_trip")


def tables():
    S = {s["case"]: s for s in json.load(open(os.path.join(RES, "summary.json")))}
    L = []

    def det(s):
        d = s["post_fault"]["detection"]
        return (f"{d[0]['type'].replace('_', ' ')} / {d[0]['latency_us']:.1f} µs") if d else "none"

    L.append("## Table A. Fault-injection matrix, proposed design (SSD + 5 ms relay, sensor noise on, no blanking)\n")
    L.append("| Fault | C_out | Classified / latency | Vout min–max (V) | Recovery to ±5 % | Faulted-phase peak (A) | Surviving peak (A) | Shutdown | Result |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for tag, cl in (("final", "14 µF"), ("c150u_final", "150 µF")):
        for case, title in [("healthy", "None (healthy)")] + FAULTS:
            s = S.get(f"{case}_{tag}")
            if not s:
                continue
            po = s["post_fault"]
            ok = po["recovered_within_1ms"] and po["no_shutdown"] and po["i2_time_above_1ph_bound_us"] == 0
            ok = ok and (case == "healthy" or bool(po["detection"])) and (case != "healthy" or not po["detection"])
            L.append(f"| {title} | {cl} | {det(s) if case != 'healthy' else 'no trip'} | {po['vout_min']:.1f}–{po['vout_max']:.1f} | "
                     f"{po['recovery_time_ms']:.2f} ms | {po['i1_peak']:.2f} | {po['i2_peak']:.2f} | "
                     f"{'no' if po['no_shutdown'] else 'yes'} | {'PASS' if ok else 'FAIL'} |")
    L.append("\n## Table B. Proposed vs conventional interleaved boost (same stage and loops, 14 µF)\n")
    L.append("| Fault | Design | Vout at 75–80 ms (V) | Vout min (V) | Faulted-phase peak (A) | Faulted-switch peak V_DS (V) | Outcome |")
    L.append("|---|---|---|---|---|---|---|")
    for case, title in FAULTS:
        for tag, lab in (("final", "Proposed"), ("baseline", "Conventional")):
            s = S.get(f"{case}_{tag}")
            if not s:
                continue
            r = np.load(os.path.join(RES, f"{case}_{tag}.npz"))["rec"]
            post = r[:, 0] >= 50e-3
            vds = float(r[post, 8].max())
            po = s["post_fault"]
            if tag == "final":
                outc = "isolated, regulated in single-phase mode"
            else:
                outc = []
                if po["vout_end_mean"] < 190:
                    outc.append("output out of regulation")
                if po["i1_peak"] > 20:
                    outc.append(f"short-circuit current {po['i1_peak']:.0f} A")
                if vds > 600:
                    outc.append("MOSFET avalanches every cycle")
                outc = "; ".join(outc) or "regulated (fault masked)"
            L.append(f"| {title} | {lab} | {po['vout_end_mean']:.1f} | {po['vout_min']:.1f} | {po['i1_peak']:.2f} | {vds:.0f} | {outc} |")
    L.append("\n## Table C. Robustness (no false trips expected)\n")
    L.append("| Condition | Fault | Detection | Vout min–max (V) | Peak phase current (A) | Result |")
    L.append("|---|---|---|---|---|---|")
    rob = [("healthy_loadstep", "Load step 0.5→1→0.5 p.u. at 50/65 ms", None),
           ("healthy_vin43", "Vin 43.2 V (−10 %)", None), ("healthy_vin53", "Vin 52.8 V (+10 %)", None),
           ("healthy_l2mismatch", "L2 = 1.1 mH (+10 % mismatch)", None),
           ("open_inductor_halfload", "Half load (400 Ω)", "open inductor"),
           ("shorted_switch_halfload", "Half load (400 Ω)", "shorted switch"),
           ("open_diode_halfload", "Half load (400 Ω)", "open diode"),
           ("open_diode_vin43", "Vin 43.2 V", "open diode"), ("shorted_switch_vin53", "Vin 52.8 V", "shorted switch")]
    for name, cond, f in rob:
        s = S.get(name)
        if not s:
            continue
        po = s["post_fault"]
        d = po["detection"]
        if f is None:
            ok = not d and po["vout_min"] >= 190 and po["vout_max"] <= 210
            dtxt = "no trip" if not d else f"FALSE TRIP ({d[0]['type']})"
        else:
            ok = bool(d) and d[0]["type"] == f.replace(" ", "_") and po["recovered_within_1ms"] and po["no_shutdown"]
            dtxt = det(s)
        pk = max(po["i1_peak"], po["i2_peak"])
        L.append(f"| {cond} | {f or '—'} | {dtxt} | {po['vout_min']:.1f}–{po['vout_max']:.1f} | {pk:.2f} | {'PASS' if ok else 'FAIL'} |")
    open(os.path.join(OUT, "tables.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


def fig_architecture():
    """Block diagram of one phase leg + shared bus + controller."""
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    fig, ax = plt.subplots(figsize=(6.5, 3.1))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 48)
    ax.axis("off")

    def box(x, y, w, h, txt, fc="#eef2fa", ec=BLUE, fs=6.5):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=0.8",
                                    fc=fc, ec=ec, lw=0.8))
        ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=fs)

    def arrow(x1, y1, x2, y2, c="k", ls="-"):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=6,
                                     color=c, lw=0.7, ls=ls))
    box(1, 28, 8, 8, "48 V\nbattery")
    for k, y in ((1, 34), (2, 18)):
        x = 13
        steps = [("Relay\n(G2RL)", 8), ("SSD\n(1 µs)", 8), ("Shunt\n10 mΩ", 8), ("L$_%d$\n1 mH" % k, 8),
                 ("S$_%d$ / D$_%d$\n650 V" % (k, k), 10)]
        prev = None
        for i, (t, w) in enumerate(steps):
            box(x, y, w, 7, t, fc="#fff4e6" if i < 2 else "#eef2fa", ec=ORANGE if i < 2 else BLUE)
            if prev is not None:
                arrow(prev, y + 3.5, x - 0.4, y + 3.5)
            prev = x + w + 0.4
            x += w + 3.5
        arrow(9.4, 32, 12.6, y + 3.5)
        arrow(prev, y + 3.5, 69.6, 27 + (3 if k == 1 else -3))
        ax.text(12, y + 8.2, f"Phase {k} ({'0°' if k == 1 else '180°'})", fontsize=6.5, style="italic")
        box(35.5, y - 7.5, 12, 5, "AMC1300\nisolated amp", fc="#f2f2f2", ec=GRAY, fs=6)
        arrow(39.5, y - 0.3, 41.5, y - 2.1, c=GRAY)
    box(70, 22, 11, 12, "C$_{out}$\n200 V bus\nload")
    box(35, 1, 46, 7, "Controller: ADC (5 MS/s, 12-bit) → level + template detectors (r, β) → "
                      "classify → isolate → ACM loops", fc="#eaf5ea", ec="green", fs=6)
    for y in (11 + 18 - 18, ):
        pass
    arrow(41.5, 26.5 - 18 + 2, 50, 8.4, c=GRAY, ls="--")
    arrow(41.5, 26.5 - 2, 55, 8.4, c=GRAY, ls="--")
    ax.text(84, 4.5, "gate inhibit,\nSSD / relay cmd,\nduty", fontsize=5.8, color="green")
    arrow(81.4, 6, 90, 6, c="green")
    ax.text(70, 37, "V$_{out}$ feedback", fontsize=5.8, color="green")
    save(fig, "fig_architecture")


def main():
    os.makedirs(OUT, exist_ok=True)
    fig_architecture()
    fig_comparison()
    fig_detection_zoom()
    fig_feature_space()
    fig_noise_margin()
    fig_robustness()
    tables()


if __name__ == "__main__":
    main()
