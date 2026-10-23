"""Table 6: statistics of the 30 random-fault-instant runs (results/*_randNN.*).
  python -I sim/random_summary.py -> results/random_fault_summary.json + printed table rows
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import controller as C  # noqa: E402

RES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
rows = []
for f in sorted(glob.glob(os.path.join(RES, "*_rand??.json"))):
    m = json.load(open(f))
    name = os.path.basename(f)[:-5]
    ev = [e for e in m["events"] if e["event"].startswith("FAULT_")]
    tf = m["t_fault_s"]
    r = np.load(os.path.join(RES, name + ".npz"))["rec"]
    post = r[r[:, 0] >= tf]
    rows.append(dict(run=name, case=m["case"], tf=tf, phase=float((tf % C.T) / C.T),
                     det_us=float((ev[0]["t"] - tf) * 1e6), cls=ev[0]["event"][6:],
                     dip_V=float(200 - post[:, 1].min()), i1pk=float(post[:, 2].max()), i2pk=float(post[:, 3].max())))
json.dump(rows, open(os.path.join(RES, "random_fault_summary.json"), "w"), indent=1)
for c in ("open_inductor", "shorted_switch", "open_diode", None):
    R = [x for x in rows if c is None or x["case"] == c]
    d = np.array([x["det_us"] for x in R])
    print(f"{c or 'all':15s} {sum(x['cls'] == x['case'] for x in R)}/{len(R)} correct | det {d.mean():.1f} ± {d.std():.1f} "
          f"({d.min():.1f}-{d.max():.1f}) us | dip {min(x['dip_V'] for x in R):.2f}-{max(x['dip_V'] for x in R):.2f} V | "
          f"i2pk {max(x['i2pk'] for x in R):.2f} A | i1pk {max(x['i1pk'] for x in R):.2f} A")
