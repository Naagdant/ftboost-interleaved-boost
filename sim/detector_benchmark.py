"""Benchmark of fault detectors on identical sensor traces (offline replay).

Fault traces come from the conventional-converter runs (*_baseline): the faulted phase is
never isolated there, so every detector sees exactly what it would see in a real converter
up to the moment it would trip. Healthy traces (healthy_final and the robustness runs)
give the false-trip statistics. Each detector is replayed with fresh sensor-noise draws.

  python -I sim/detector_benchmark.py    -> results/detector_benchmark.json, results/threshold_sensitivity.json
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import controller as C  # noqa: E402
from replay import RES, noisy, pearson_vec  # noqa: E402

FAULT_RUNS = {"open_inductor": "open_inductor_baseline", "shorted_switch": "shorted_switch_baseline",
              "open_diode": "open_diode_baseline"}
HEALTHY_RUNS = ["healthy_final", "healthy_c150u_final", "healthy_loadstep", "healthy_vin43", "healthy_vin53",
                "healthy_l2mismatch"]


def load(name):
    d = np.load(os.path.join(RES, name + ".npz"))
    meta = json.load(open(os.path.join(RES, name + ".json")))
    return d["raw"].astype(float), d["periods"], d["rec"], meta


def windows(raw, periods, rec, sig, adaptive):
    """Yield (t_window_end, phase, window samples, Vout-Vin ratio info) for every scored off-time window."""
    t0 = raw[0, 0]
    tmpl_acc, tmpl, dv_learn = {1: [], 2: []}, {}, {}
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
        if learning:
            if n == C.WIN_LEN:
                tmpl_acc[k].append(win)
                dv_learn[k] = vo - vin
            continue
        if raw[e, 0] < C.T_LEARN[1] or not tmpl_acc[k]:
            continue
        if k not in tmpl:
            tmpl[k] = list(np.mean(tmpl_acc[k], axis=0))
        r, beta = C.template_match(list(win), tmpl[k], n, (vo - vin) / dv_learn[k])
        yield raw[e, 0], k, win, r, beta


def run_template(name, scale, seed, mode, r_th=0.8, b_lo=0.5, b_hi=2.0):
    """mode: proposed | r_fixed | r_adaptive | beta_only. Returns list of trips (t, phase, class)."""
    raw, periods, rec, meta = load(name)
    rng = np.random.default_rng(seed)
    sig = {1: noisy(raw[:, 1], scale, rng), 2: noisy(raw[:, 2], scale, rng)}
    adaptive = mode != "r_fixed"
    bad, trips = {1: 0, 2: 0}, []
    for t, k, win, r, beta in windows(raw, periods, rec, sig, adaptive):
        if t < C.T_ARM:
            continue
        if mode == "proposed":
            v = r < r_th or not (b_lo <= beta <= b_hi)
        elif mode in ("r_fixed", "r_adaptive"):
            v = r < r_th
        else:
            v = not (b_lo <= beta <= b_hi)
        bad[k] = bad[k] + 1 if v else 0
        if bad[k] >= C.DIODE_N:
            if mode == "proposed" or mode == "beta_only":
                cls = C.classify(list(win), beta)
            else:                                   # earlier rule: inverted ramp = short, else open diode
                cls = "shorted_switch" if r < -0.5 else "open_diode"
            trips.append((t, k, cls))
            bad[k] = 0
            if len(trips) > 20:
                break
    return trips, meta


def run_level(name, scale, seed):
    """Brief's level detectors only (per sample, armed after soft-start)."""
    raw, periods, rec, meta = load(name)
    rng = np.random.default_rng(seed)
    trips = []
    duty_k = {1: periods[periods[:, 1] == 1], 2: periods[periods[:, 1] == 2]}
    for k in (1, 2):
        i = noisy(raw[:, k], scale, rng)
        t = raw[:, 0]
        arm = t >= C.T_ARM
        d = np.interp(t, duty_k[k][:, 0], duty_k[k][:, 2])
        low = arm & (i < C.I_OPEN_TH) & (d > 0.05)
        high = arm & (i > C.I_SHORT_TH_2PH)
        for mask, need, cls in ((low, C.T_OPEN, "open_inductor"), (high, C.T_SHORT, "shorted_switch")):
            run = 0
            for j in np.flatnonzero(mask | np.r_[False, mask[:-1]]):     # walk only near candidate samples
                run = run + 1 if mask[j] else 0
                if run * C.TS >= need:
                    trips.append((t[j], k, cls))
                    break
    return sorted(trips), meta


def evaluate(detector, scale=1.0, seeds=5, **kw):
    res = {"faults": {}, "healthy": {}}
    for fault, name in FAULT_RUNS.items():
        out = []
        for s in range(seeds):
            trips, meta = run_level(name, scale, s) if detector == "level" else run_template(name, scale, s, detector, **kw)
            tf = meta["t_fault_s"]
            pre = [x for x in trips if x[0] < tf]
            post = [x for x in trips if x[0] >= tf and x[1] == 1]
            out.append({"false_before_fault": len(pre),
                        "latency_us": round((post[0][0] - tf) * 1e6, 1) if post else None,
                        "class": post[0][2] if post else None})
        lat = [o["latency_us"] for o in out if o["latency_us"] is not None]
        res["faults"][fault] = {"detected": f"{len(lat)}/{seeds}",
                                "latency_us": [min(lat), max(lat)] if lat else None,
                                "correct_class": sum(o["class"] == fault for o in out),
                                "false_before_fault": sum(o["false_before_fault"] for o in out)}
    ft, total_s = 0, 0.0
    for name in HEALTHY_RUNS:
        if not os.path.exists(os.path.join(RES, name + ".npz")):
            continue
        for s in range(seeds):
            trips, meta = run_level(name, scale, s) if detector == "level" else run_template(name, scale, s, detector, **kw)
            ft += len(trips)
            total_s += meta["tstop_s"] - C.T_LEARN[1]
    res["healthy"] = {"false_trips": ft, "observed_s": round(total_s, 3)}
    return res


def _job(args):
    det, scale, seeds, kw = args
    return evaluate(det, scale, seeds=seeds, **kw)


def main():
    from multiprocessing import Pool
    jobs = {f"{det}@{scale:g}x": (det, scale, 5, {})
            for det in ("level", "r_fixed", "r_adaptive", "beta_only", "proposed") for scale in (1.0, 3.0)}
    sens = {f"r{r}_b{lo}-{hi}@{scale:g}x": ("proposed", scale, 3, {"r_th": r, "b_lo": lo, "b_hi": hi})
            for r in (0.6, 0.8, 0.95) for (lo, hi) in ((0.3, 3.0), (0.5, 2.0), (0.8, 1.25)) for scale in (1.0, 3.0)}
    with Pool(int(os.environ.get("NPROC", "6"))) as pool:
        for name, jb in (("detector_benchmark", jobs), ("threshold_sensitivity", sens)):
            res = dict(zip(jb, pool.map(_job, list(jb.values()))))
            json.dump(res, open(os.path.join(RES, name + ".json"), "w"), indent=1, default=float)
            for key, e in res.items():
                print(f"{key:24s} healthy FT {e['healthy']['false_trips']:3d} | " +
                      " | ".join(f"{k[:9]} {v['detected']} {v['latency_us']} cls {v['correct_class']}"
                                 for k, v in e["faults"].items()), flush=True)


if __name__ == "__main__":
    main()
