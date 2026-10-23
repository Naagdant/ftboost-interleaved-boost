"""Open-loop validation runs (Table 4, Fig. 5 data): D = 0.76, no faults, no controller.

Reconstruction of the original scratch script used for results/validation/openloop_c{14,40,150}u.npy.
  python -I sim/openloop_check.py 80e-3 results/validation/openloop_c14u.npy            (14 uF)
  python -I sim/openloop_check.py 60e-3 results/validation/openloop_c150u.npy 150e-6
Prints per-phase RMS/peak current and the 2 % settling time.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import netlist  # noqa: E402
from ngspice_shared import NgSpice  # noqa: E402

tstop = float(sys.argv[1])
rows = []


def on_data(d):
    rows.append((d["time"], d["vout"], (d["nr1"] - d["ns1"]) / 0.01, (d["nr2"] - d["ns2"]) / 0.01, d["sw1"]))


ng = NgSpice(on_data)
ng.load(netlist.prepare(netlist.export(), tstop=tstop, external=False,
                        cout=float(sys.argv[3]) if len(sys.argv) > 3 else None))
t0 = time.time()
ng.cmd("run")
print("wall", round(time.time() - t0, 1), "s, points", len(rows))
a = np.array(rows)
t = a[:, 0]
m = t > tstop - 2e-3
for k, c in (("1", 2), ("2", 3)):
    i = a[m, c]
    dt = np.diff(t[m])
    print(f"phase {k}: RMS {np.sqrt((i[:-1] ** 2 * dt).sum() / dt.sum()):.4f} A  peak {i.max():.4f} A")
vf = a[t > tstop - 10e-3, 1].mean()
print("final Vout", round(vf, 2), "V; 2 % settling", round(t[np.abs(a[:, 1] - vf) > 0.02 * vf][-1] * 1e3, 2), "ms")
np.save(sys.argv[2], a)
