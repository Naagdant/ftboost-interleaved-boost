"""Offline replay of the off-time template (open-diode / stuck-switch) detector.

The shape detector does not act on the circuit until it trips, so replaying it on
the logged noise-free 5 MS/s sensor trace of a closed-loop run is exact up to the
first trip in that run. This lets us sweep sensor-noise level, threshold, blanking
and window mode over many noise seeds without re-running SPICE.

  python -I sim/replay.py [--tags n1 c150u_n1] [--noise 1 2 3] [--th 0.8] [--blank 0 1e-3] [--seeds 5]
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import controller as C  # noqa: E402

RES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
CASES = ["healthy", "open_inductor", "shorted_switch", "open_diode"]


def noisy(raw_i, scale, rng):
    """Same noise chain as Controller.adc(), vectorised; returns sensed current [A]."""
    v = raw_i * C.K_ISNS
    if scale:
        a = math.exp(-2 * math.pi * C.AMC_BW * C.TS)
        b = math.sqrt(1 - a * a)
        w = rng.standard_normal(len(v))
        amc = np.empty_like(v)
        st = 0.0
        for j in range(len(v)):          # one-pole band-limit (300 kHz)
            st = a * st + b * w[j]
            amc[j] = st
        v = v + scale * (C.AMC_GAIN * C.AMC_VN_RMS * amc
                         + C.ADC_NOISE_LSB * C.ADC_LSB * rng.standard_normal(len(v)))
    v = np.clip(v, -C.ADC_FS / 2, C.ADC_FS / 2 - C.ADC_LSB)
    return np.round(v / C.ADC_LSB) * C.ADC_LSB / C.K_ISNS


def pearson_vec(x, y):
    x = x - x.mean()
    y = y - y.mean()
    d = math.sqrt((x * x).sum() * (y * y).sum())
    return float((x * y).sum() / d) if d > 0 else 0.0


def replay(name, scale, th, blank, adaptive, seed):
    d = np.load(os.path.join(RES, name + ".npz"))
    meta = json.load(open(os.path.join(RES, name + ".json")))
    raw, periods, rec = d["raw"].astype(float), d["periods"], d["rec"]
    t0 = raw[0, 0]
    rng = np.random.default_rng(seed)
    sig = {1: noisy(raw[:, 1], scale, rng), 2: noisy(raw[:, 2], scale, rng)}
    faults = [e for e in meta["events"] if e["event"].startswith("FAULT_")]
    t_reconf = faults[0]["t"] if faults else None
    tf = meta["t_fault_s"]
    faulted = 1 if tf else None           # the matrix always injects into phase 1

    out = {"windows": {1: [], 2: []}}     # (t, r, category, n, beta)
    tmpl_dv = {}
    tmpl_acc = {1: [], 2: []}
    tmpl = {}
    bad = {1: 0, 2: 0}
    out["false_trip"] = None
    out["detect"] = None
    for row in periods:
        ts, k, duty = row[0], int(row[1]), row[2]
        vin = row[5] if len(row) > 5 else 47.8
        vo = float(np.interp(ts, rec[:, 0], rec[:, 1]))
        learning = C.T_LEARN[0] <= ts < C.T_LEARN[1]
        n = C.window_samples(duty, adaptive, learning)
        if not n:
            continue
        t_end = ts + duty * C.T + C.T_SNS_DELAY + n * C.TS
        e = int(math.ceil((t_end - t0) / C.TS - 1e-6))
        if e >= len(raw) or e - n + 1 < 0:
            continue
        win = sig[k][e - n + 1:e + 1]
        tw = raw[e, 0]
        if learning:
            if n == C.WIN_LEN:
                tmpl_acc[k].append(win)
                tmpl_dv[k] = vo - vin
            continue
        if tw < C.T_LEARN[1]:
            continue
        if k not in tmpl:
            tmpl[k] = list(np.mean(tmpl_acc[k], axis=0))
        # the faulted phase stops being scored once the run isolated it
        if k == faulted and t_reconf is not None and tw > t_reconf:
            continue
        r, beta = C.template_match(list(win), tmpl[k], n, (vo - vin) / tmpl_dv[k])
        is_faulted_post = (k == faulted and tf is not None and tw >= tf)
        in_blank = (t_reconf is not None and k != faulted and t_reconf <= tw < t_reconf + blank)
        post_reconf = (t_reconf is not None and k != faulted and tw >= t_reconf)
        cat = ("faulted" if is_faulted_post else
               "survivor_reconf_1ms" if post_reconf and tw < t_reconf + 1e-3 else
               "survivor_steady" if post_reconf else "healthy")
        out["windows"][k].append((tw, r, cat, n, beta))
        if in_blank:
            continue
        bad[k] = bad[k] + 1 if (r < th or not (C.SLOPE_LO <= beta <= C.SLOPE_HI)) else 0
        if bad[k] >= C.DIODE_N:
            if is_faulted_post:
                if out["detect"] is None:
                    out["detect"] = {"t": tw, "latency_us": (tw - tf) * 1e6, "r": r, "beta": beta,
                                     "class": C.classify(list(win), beta)}
            elif out["false_trip"] is None:
                out["false_trip"] = {"t": tw, "phase": k, "r": r, "category": cat}
            bad[k] = 0
    return out


def fisher_rate(rs, th, windows_per_s=2 * C.FSW):
    """Gaussian fit on Fisher-z of healthy-window r -> P(r<th) per window and the
    expected false-trip rate per hour for DIODE_N consecutive low windows."""
    z = np.arctanh(np.clip(np.array(rs), -0.999999, 0.999999))
    mu, sd = float(z.mean()), float(z.std())
    if sd == 0:
        return 0.0, 0.0, mu, sd
    p = 0.5 * math.erfc((mu - math.atanh(th)) / (sd * math.sqrt(2)))
    per_hour = (p ** C.DIODE_N) * windows_per_s * 3600
    return p, per_hour, mu, sd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", nargs="+", default=["n1", "c150u_n1"])
    ap.add_argument("--noise", nargs="+", type=float, default=[0.0, 1.0, 2.0, 3.0])
    ap.add_argument("--th", nargs="+", type=float, default=[0.8])
    ap.add_argument("--blank", nargs="+", type=float, default=[0.0, 1e-3])
    ap.add_argument("--fixed-window", action="store_true")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--out", default=os.path.join(RES, "replay_summary.json"))
    a = ap.parse_args()
    rows = []
    for tag in a.tags:
        for scale in a.noise:
            for th in a.th:
                for blank in a.blank:
                    agg = {}
                    for case in CASES:
                        name = f"{case}_{tag}"
                        if not os.path.exists(os.path.join(RES, name + ".npz")):
                            continue
                        res = [replay(name, scale, th, blank, not a.fixed_window, s) for s in range(a.seeds)]
                        cats, betas = {}, {}
                        for r_ in res:
                            for k in (1, 2):
                                for (_, r, cat, n, beta) in r_["windows"][k]:
                                    cats.setdefault(cat, []).append(r)
                                    betas.setdefault(cat, []).append(beta)
                        agg[case] = {
                            "false_trips": sum(r_["false_trip"] is not None for r_ in res),
                            "false_trip_examples": [r_["false_trip"] for r_ in res if r_["false_trip"]][:2],
                            "detect_latency_us": [round(r_["detect"]["latency_us"], 1) if r_["detect"] else None
                                                  for r_ in res],
                            "r_min": {c: round(min(v), 4) for c, v in cats.items()},
                            "r_p001": {c: round(float(np.quantile(v, 0.001)), 4) for c, v in cats.items()},
                            "beta_range": {c: [round(min(v), 3), round(max(v), 3)] for c, v in betas.items()},
                            "detect_class": [r_["detect"]["class"] if r_["detect"] else None for r_ in res],
                        }
                        if case == "healthy":
                            p, ph, mu, sd = fisher_rate(cats["healthy"], th)
                            agg[case]["p_window_below_th"] = p
                            agg[case]["false_trips_per_hour_est"] = ph
                        if "survivor_steady" in cats:
                            p, ph, mu, sd = fisher_rate(cats["survivor_steady"], th, C.FSW)
                            agg[case]["survivor_false_trips_per_hour_est"] = ph
                    row = {"tag": tag, "noise": scale, "th": th, "blank_ms": blank * 1e3,
                           "adaptive": not a.fixed_window, "seeds": a.seeds, "cases": agg}
                    rows.append(row)
                    ft = {c: v["false_trips"] for c, v in agg.items()}
                    det = {c: v["detect_latency_us"] for c, v in agg.items() if c in ("open_diode", "shorted_switch")}
                    print(f"[{tag} noise={scale} th={th} blank={blank*1e3:.1f}ms] false trips/seeds {ft}  "
                          f"shape-detect us {det}")
                    for c, v in agg.items():
                        print(f"     {c:15s} rmin {v['r_min']}  beta {v['beta_range']}  "
                              + (f"P(r<th)/win {v.get('p_window_below_th', 0):.2e} "
                                 f"FT/h {v.get('false_trips_per_hour_est', 0):.2e}" if c == "healthy" else
                                 f"survivor FT/h {v.get('survivor_false_trips_per_hour_est', 0):.2e}"))
    json.dump(rows, open(a.out, "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
