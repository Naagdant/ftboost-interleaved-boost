"""Summaries of the revision-3 runs (saturation, transistor-level SSD, start-up and double faults).

  python3 -I sim/analyze_rev3.py            -> prints a table and writes results/rev3_summary.json
"""
import glob
import json
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")


def summarize(name):
    m = json.load(open(os.path.join(RES, name + ".json")))
    d = np.load(os.path.join(RES, name + ".npz"))
    rec, ex, sc = d["rec"], d["extra"], d["scores"]
    t = rec[:, 0]
    faults = []
    for item in filter(None, m["faults"].split(",")):
        kind, rest = item.split(":")
        k, tf = rest.split("@")
        faults.append((kind, int(k), float(tf)))
    tf0 = min((f[2] for f in faults), default=50e-3)
    ev = [e for e in m["events"] if e["event"].startswith(("FAULT_", "SHUTDOWN"))]
    det = []
    for e in ev:
        if e["event"].startswith("FAULT_"):
            own = [f for f in faults if f[1] == e["phase"]]
            ref = own[0][2] if own else None
            det.append({"phase": e["phase"], "class": e["event"][6:],
                        "t_ms": round(e["t"] * 1e3, 4),
                        "latency_us": round((e["t"] - ref) * 1e6, 1) if ref is not None else None,
                        "true": own[0][0] if own else "healthy (false trip)"})
    post = t >= tf0
    out = {"name": name, "faults": m["faults"], "sat": m["sat_ik_A"], "ssd_real": m["ssd_real"],
           "early_arm": m["early_arm"], "detections": det,
           "shutdown": any(e["event"] == "SHUTDOWN" for e in ev),
           "spice_errors": len(m["spice_errors"]), "t_end_ms": round(t[-1] * 1e3, 3),
           "vout_min_post": round(float(rec[post, 1].min()), 2), "vout_max_post": round(float(rec[post, 1].max()), 2),
           "vout_end": round(float(rec[t >= t[-1] - 5e-3, 1].mean()), 2),
           "i1_max_post": round(float(rec[post, 2].max()), 2), "i2_max_post": round(float(rec[post, 3].max()), 2),
           "i1_max_all": round(float(rec[t > 1e-3, 2].max()), 2), "i2_max_all": round(float(rec[t > 1e-3, 3].max()), 2)}
    ss = t >= t[-1] - 8e-3                                  # last 8 ms: degraded or healthy steady state
    for k, col in ((1, 2), (2, 3)):
        out[f"i{k}_ss_pk"] = round(float(rec[ss, col].max()), 3)
        out[f"i{k}_ss_pp"] = round(float(rec[ss, col].max() - rec[ss, col].min()), 3)
        out[f"i{k}_ss_rms"] = round(float(np.sqrt((rec[ss, col] ** 2).mean())), 3)
    if sc.shape[1] >= 5:
        for k in (1, 2):
            s = sc[(sc[:, 1] == k) & (sc[:, 0] >= t[-1] - 8e-3)]
            if len(s):
                out[f"beta{k}_ss"] = [round(float(s[:, 3].min()), 3), round(float(s[:, 3].max()), 3)]
                out[f"r{k}_ss_min"] = round(float(s[:, 2].min()), 3)
            s = sc[(sc[:, 1] == k) & (sc[:, 0] < 45e-3)]
            if len(s):
                out[f"r{k}_pre_learn_min"] = round(float(s[:, 2].min()), 3)
                out[f"beta{k}_pre_learn"] = [round(float(s[:, 3].min()), 3), round(float(s[:, 3].max()), 3)]
    if m["ssd_real"]:
        te = ex[:, 0]
        vssd1 = ex[:, 1] - ex[:, 2]
        out["ssd1_vblock_max"] = round(float(vssd1[te > 1e-3].max()), 1)
        out["nr1_min"] = round(float(ex[te > 1e-3, 2].min()), 1)
        if det:
            td = det[0]["t_ms"] * 1e-3
            after = (t > td + 1e-6) & (np.abs(rec[:, 2]) < 0.05)
            if after.any():
                out["ssd1_current_zero_after_cmd_us"] = round(float((t[after][0] - td - 1e-6) * 1e6), 2)
    return out


def main():
    rows = [summarize(os.path.basename(f)[:-5]) for f in sorted(glob.glob(os.path.join(RES, "rev3_*.json"))) if not f.endswith("rev3_summary.json")]
    json.dump(rows, open(os.path.join(RES, "rev3_summary.json"), "w"), indent=1)
    for r in rows:
        print(json.dumps(r))


if __name__ == "__main__":
    main()
