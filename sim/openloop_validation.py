"""Open-loop model validation and C_out calibration (no controller, D = 0.76, no faults).

  python -I sim/openloop_validation.py 80e-3 results/validation/openloop_c14u.npy
  python -I sim/openloop_validation.py 50e-3 results/validation/openloop_c40u.npy 40e-6
  python -I sim/openloop_validation.py 60e-3 results/validation/openloop_c150u.npy 150e-6

args: tstop [s], output .npy, optional C_out override [F] (schematic default 14 uF).
Prints per-phase RMS/peak current (vs. Table IV), output ripple and 2 % settling time.
Saved columns: t, Vout, i_L1, i_L2, V_sw1.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import netlist  # noqa: E402
from ngspice_shared import NgSpice  # noqa: E402

tstop = float(sys.argv[1])
out = sys.argv[2]
cout = float(sys.argv[3]) if len(sys.argv) > 3 else None
rows = []


def on_data(d):
    rows.append((d["time"], d["vout"], (d["nr1"] - d["ns1"]) / 0.01, (d["nr2"] - d["ns2"]) / 0.01, d["sw1"]))


ng = NgSpice(on_data)
ng.load(netlist.prepare(netlist.export(), tstop=tstop, external=False, cout=cout))
t0 = time.time()
ng.cmd("run")
print("wall", round(time.time() - t0, 1), "s points", len(rows))
a = np.array(rows)
t = a[:, 0]
m = t > tstop - 2e-3
for k, c in (("1", 2), ("2", 3)):
    i = a[m, c]
    dt = np.diff(t[m])
    rms = np.sqrt((i[:-1] ** 2 * dt).sum() / dt.sum())
    print(f"phase {k}: RMS {rms:.4f} A  peak {i.max():.4f}  min {i.min():.4f}")
print("Vout ripple pp", np.ptp(a[m, 1]), "Vsw max", a[m, 4].max())
vf = a[t > tstop - 10e-3, 1].mean()
outside = np.abs(a[:, 1] - vf) > 0.02 * vf
print("2% settling ms", t[outside][-1] * 1e3, "final", vf)
np.save(out, a)
