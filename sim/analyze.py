"""Score every results/*.npz run against the brief's success criteria and plot it."""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from controller import I_PK_HEALTHY, I_RMS_HEALTHY, I_SHORT_TH_1PH, I_SHORT_TH_2PH  # noqa: E402

RES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
BAND = (190.0, 210.0)
C = dict(t=0, vo=1, i1=2, i2=3, s1=4, s2=5, d1=6, d2=7, sw1=8, sw2=9, vref=10, iref=11)


def longest_run(mask, dt):
    best = cur = 0
    for m in mask:
        cur = cur + 1 if m else 0
        best = max(best, cur)
    return best * dt


def rms(x):
    return float(np.sqrt(np.mean(x ** 2)))


def score(name):
    meta = json.load(open(os.path.join(RES, name + ".json")))
    d = np.load(os.path.join(RES, name + ".npz"))
    r, sc = d["rec"], d["scores"]
    t = r[:, 0]
    dt = float(np.median(np.diff(t)))
    tf = meta["t_fault_s"] or 50e-3
    pre = (t >= 40e-3) & (t < tf)
    post = t >= tf
    end = t >= 75e-3
    out = {"case": name, "events": meta["events"], "wall_s": meta["wall_s"],
           "spice_errors": meta["spice_errors"]}
    out["pre_fault"] = {
        "vout_mean": float(r[pre, 1].mean()), "vout_pp": float(np.ptp(r[pre, 1])),
        "i1_rms": rms(r[pre, 2]), "i2_rms": rms(r[pre, 3]),
        "i1_peak": float(r[pre, 2].max()), "i2_peak": float(r[pre, 3].max()),
        "tableIV_rms": I_RMS_HEALTHY, "tableIV_peak": I_PK_HEALTHY}
    vo = r[post, 1]
    outside = (vo < BAND[0]) | (vo > BAND[1])
    t_last_out = float(t[post][outside][-1]) if outside.any() else tf
    rec = t_last_out - tf
    faults = [e for e in meta["events"] if e["event"].startswith("FAULT_")]
    out["post_fault"] = {
        "vout_min": float(vo.min()), "vout_max": float(vo.max()),
        "recovery_time_ms": rec * 1e3,
        "recovered_within_1ms": bool(rec <= 1e-3),
        "vout_end_mean": float(r[end, 1].mean()), "vout_end_pp": float(np.ptp(r[end, 1])),
        "no_shutdown": bool(BAND[0] <= r[end, 1].mean() <= BAND[1] and r[end, 3].mean() > 1.0),
        "detection": [{"phase": e["phase"], "type": e["event"][6:],
                       "latency_us": (e["t"] - tf) * 1e6, "detail": e["detail"]} for e in faults],
        "i1_peak": float(r[post, 2].max()),
        "i1_time_above_2ph_bound_us": longest_run(r[post, 2] > I_SHORT_TH_2PH, dt) * 1e6,
        "i2_peak": float(r[post, 3].max()),
        "i2_time_above_2ph_bound_us": longest_run(r[post, 3] > I_SHORT_TH_2PH, dt) * 1e6,
        "i2_time_above_1ph_bound_us": longest_run(r[post, 3] > I_SHORT_TH_1PH, dt) * 1e6,
        "i2_end_rms": rms(r[end, 3]), "i2_end_peak": float(r[end, 3].max()),
        "i2_end_pp": float(np.ptp(r[end, 3])),
    }
    if sc.ndim == 2 and len(sc) > 1:
        for k in (1, 2):
            m = (sc[:, 1] == k)
            pm = m & (sc[:, 0] < tf)
            qm = m & (sc[:, 0] >= tf)
            out[f"corr_ph{k}"] = {"pre_min": float(sc[pm, 2].min()) if pm.any() else None,
                                 "post_min": float(sc[qm, 2].min()) if qm.any() else None,
                                 "post_first5": [round(float(x), 3) for x in sc[qm, 2][:5]]}
            if sc.shape[1] > 3:      # slope ratio beta logged
                out[f"corr_ph{k}"]["beta_pre_range"] = ([round(float(sc[pm, 3].min()), 3),
                                                         round(float(sc[pm, 3].max()), 3)] if pm.any() else None)
                out[f"corr_ph{k}"]["beta_post_range"] = ([round(float(sc[qm, 3].min()), 3),
                                                          round(float(sc[qm, 3].max()), 3)] if qm.any() else None)
            if faults and k != faults[0]["phase"]:
                tr = faults[0]["t"]
                b = m & (sc[:, 0] >= tr) & (sc[:, 0] < tr + 1e-3)
                a_ = m & (sc[:, 0] >= tr + 1e-3)
                out[f"corr_ph{k}"].update({
                    "survivor_reconf_1ms_min": float(sc[b, 2].min()) if b.any() else None,
                    "survivor_reconf_1ms_windows_below_0.8": int((sc[b, 2] < 0.8).sum()),
                    "survivor_after_1ms_min": float(sc[a_, 2].min()) if a_.any() else None})
                if sc.shape[1] > 3 and b.any():
                    out[f"corr_ph{k}"]["survivor_reconf_1ms_beta_range"] = [
                        round(float(sc[b, 3].min()), 3), round(float(sc[b, 3].max()), 3)]
    plot(name, r, sc, tf, meta)
    return out


def plot(name, r, sc, tf, meta):
    t = r[:, 0] * 1e3
    fig, ax = plt.subplots(3, 2, figsize=(13, 8.5), sharex="col")
    for col, (a, b) in enumerate([(0, 80), (tf * 1e3 - 0.3, tf * 1e3 + 1.5)]):
        m = (t >= a) & (t <= b)
        ax[0, col].plot(t[m], r[m, 1], lw=0.8, label="Vout")
        ax[0, col].plot(t[m], r[m, 10], "--", lw=0.8, color="gray", label="Vref")
        ax[0, col].axhspan(*BAND, color="tab:green", alpha=0.12, label="±5 % band")
        ax[0, col].set_ylabel("V")
        ax[1, col].plot(t[m], r[m, 2], lw=0.6, label="i_L1 (faulted phase)")
        ax[1, col].plot(t[m], r[m, 3], lw=0.6, label="i_L2 (surviving phase)")
        ax[1, col].axhline(I_SHORT_TH_2PH, color="r", ls=":", lw=0.8, label="3.59 A (2-ph bound)")
        ax[1, col].axhline(I_SHORT_TH_1PH, color="m", ls=":", lw=0.8, label="6.76 A (1-ph bound)")
        ax[1, col].set_ylabel("A")
        ax[2, col].plot(t[m], r[m, 6], lw=0.7, label="duty 1 (<0 = inhibited)")
        ax[2, col].plot(t[m], r[m, 7], lw=0.7, label="duty 2")
        ax[2, col].set_ylabel("duty")
        ax[2, col].set_xlabel("t [ms]")
        for e in meta["events"]:
            if e["event"].startswith("FAULT_"):
                for k in range(3):
                    ax[k, col].axvline(e["t"] * 1e3, color="k", lw=0.6, alpha=0.5)
        if meta["t_fault_s"]:
            for k in range(3):
                ax[k, col].axvline(tf * 1e3, color="r", lw=0.6, alpha=0.5)
    ax[0, 1].set_ylim(150, 240)
    ax[0, 0].set_ylim(0, 320)
    for a in ax[:, 1]:
        a.legend(fontsize=7, loc="upper right")
    ax[0, 0].set_title(f"{name}: full run")
    ax[0, 1].set_title("zoom: fault onset (red) / detection (black)")
    fig.tight_layout()
    fig.savefig(os.path.join(RES, name + ".png"), dpi=110)
    plt.close(fig)


def main():
    names = sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(RES, "*.npz")))
    allres = [score(n) for n in names]
    json.dump(allres, open(os.path.join(RES, "summary.json"), "w"), indent=1)
    for s in allres:
        pf, po = s["pre_fault"], s["post_fault"]
        print(f"\n== {s['case']}  (wall {s['wall_s']} s, spice errors: {len(s['spice_errors'])})")
        print(f"  pre : Vout {pf['vout_mean']:.2f} V pp {pf['vout_pp']:.2f} | I1 rms {pf['i1_rms']:.3f} pk {pf['i1_peak']:.3f}"
              f" | I2 rms {pf['i2_rms']:.3f} pk {pf['i2_peak']:.3f}")
        print(f"  post: Vout min {po['vout_min']:.1f} max {po['vout_max']:.1f}; recovery {po['recovery_time_ms']:.3f} ms"
              f" ({'PASS' if po['recovered_within_1ms'] else 'FAIL'}); end {po['vout_end_mean']:.2f} V pp {po['vout_end_pp']:.2f};"
              f" no_shutdown={po['no_shutdown']}")
        print(f"  i1 peak {po['i1_peak']:.2f} A (>{I_SHORT_TH_2PH:.2f} A for {po['i1_time_above_2ph_bound_us']:.0f} us);"
              f" i2 peak {po['i2_peak']:.2f} A (>{I_SHORT_TH_2PH:.2f}: {po['i2_time_above_2ph_bound_us']:.0f} us,"
              f" >{I_SHORT_TH_1PH:.2f}: {po['i2_time_above_1ph_bound_us']:.0f} us); i2 end rms {po['i2_end_rms']:.2f} pk {po['i2_end_peak']:.2f}")
        for d_ in po["detection"]:
            print(f"  DETECT ph{d_['phase']} {d_['type']} after {d_['latency_us']:.1f} us  [{d_['detail']}]")
        for k in (1, 2):
            if f"corr_ph{k}" in s:
                print(f"  corr ph{k}: {s[f'corr_ph{k}']}")


if __name__ == "__main__":
    main()
