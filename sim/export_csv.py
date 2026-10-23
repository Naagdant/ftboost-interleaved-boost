"""CSV versions of the run summaries (no third-party packages needed).
  python3 -I sim/export_csv.py -> results/summary.csv, results/random_fault_summary.csv
"""
import csv
import json
import os

RES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
rows = []
for s in json.load(open(os.path.join(RES, "summary.json"))):
    pf, po = s["pre_fault"], s["post_fault"]
    det = po["detection"][0] if po["detection"] else {}
    rows.append({"run": s["case"], "detected_as": det.get("type", ""), "latency_us": det.get("latency_us", ""),
                 "vout_min_V": po["vout_min"], "vout_max_V": po["vout_max"], "recovery_ms": po["recovery_time_ms"],
                 "no_shutdown": po["no_shutdown"], "faulted_peak_A": po["i1_peak"], "surviving_peak_A": po["i2_peak"],
                 "i1_rms_pre_A": pf["i1_rms"], "i1_peak_pre_A": pf["i1_peak"], "vout_end_pp_V": po["vout_end_pp"]})
with open(os.path.join(RES, "summary.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
r = json.load(open(os.path.join(RES, "random_fault_summary.json")))
with open(os.path.join(RES, "random_fault_summary.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(r[0]))
    w.writeheader()
    w.writerows(r)
print("wrote summary.csv (%d rows), random_fault_summary.csv (%d rows)" % (len(rows), len(r)))
