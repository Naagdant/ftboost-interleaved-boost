"""Additional runs for the revised manuscript (revision 2).

  python -I sim/run_extra.py <case> --tag TAG [--baseline] [--fuse] [--aval] [--cout F] [--relay-delay S]

--fuse  : main input fuse between the source and the input capacitor (Littelfuse 0891 series,
          10 A, 58 VDC low-profile MINI; typical I^2t 102 A^2 s from the datasheet). First-order
          thermal model dQ/dt = i^2 - Q/tau (tau = 1 s), melting at Q = 102 A^2 s; 6 mohm when
          closed, arcing ignored. Once Q reaches 102 A^2 s a latch keeps the fuse open (a melted
          element does not reclose when it cools). tau = 1 s lets the fuse carry its 10 A rating indefinitely and
          puts the opening times at 135/200/350/600 % of rating at 0.82/0.29/0.087/0.028 s
          (datasheet band 0.75-120 / 0.15-5 / 0.08-0.25 / 0.03-0.1 s). Q starts at 17.4 A^2 s,
          i.e. thermal equilibrium at the nominal 4.17 A input current.
--aval  : integrates the energy dissipated in MOSFET Q1 while V_DS > 400 V (avalanche only;
          the healthy switch node never exceeds ~201 V).

Same controller, netlist and settings as run_case.py otherwise. Extra traces are stored in the
.npz as `extra` with columns t, i_fuse, Q (I2t state), E_aval, fuse-blown flag (decimated to 1 MS/s).
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import netlist  # noqa: E402
from controller import Controller  # noqa: E402
from ngspice_shared import NgSpice  # noqa: E402
from run_case import CASES, RESULTS, T_FAULT  # noqa: E402

FUSE_I2T = 102.0      # A^2 s, Littelfuse 0891010 (10 A, 58 VDC), typical
FUSE_R = 6e-3
FUSE_TAU = 1.0         # s (thermal time constant, with C = 1 F)
FUSE_Q0 = 4.17 ** 2 * FUSE_TAU   # equilibrium at the nominal input current


def transform(text, fuse, aval):
    out = []
    for ln in text.splitlines():
        tok = ln.split()
        if fuse and tok and tok[0] == "RSRC1":
            out += ["RSRC1 VSRC NF1 20m", "VFUSE NF1 NF2 DC 0", "SFUSE NF2 VIN NFC 0 SWFUSE",
                    "BFI 0 NI2T I = I(VFUSE)*I(VFUSE)", f"CI2T NI2T 0 1 IC={FUSE_Q0:g}", f"RI2T NI2T 0 {FUSE_TAU:g}",
                    "BBLOW 0 NBLOW I = u(V(NI2T) - %g)" % FUSE_I2T, "CBLOW NBLOW 0 1u", "RBLOW NBLOW 0 1e12",
                    "BFC NFC 0 V = 0.5 - V(NBLOW)",
                    f".model SWFUSE sw vt=0 vh=0 ron={FUSE_R:g} roff=1G"]
            continue
        if aval and tok and tok[0] == "XQ1":
            out += ["VQS1 SW1 SW1X DC 0", "XQ1 SW1X " + " ".join(tok[2:])]
            out += ["BEAV 0 NEAV I = V(SW1)*I(VQS1)*u(V(SW1)-400)", "CEAV NEAV 0 1", "REAV NEAV 0 1e12"]
            continue
        if ln.startswith(".save"):
            extra = (["v(ni2t)", "i(vfuse)", "v(nblow)"] if fuse else []) + (["v(neav)"] if aval else [])
            ln = ln + " " + " ".join(extra)
        out.append(ln)
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case", choices=CASES)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--fuse", action="store_true")
    ap.add_argument("--aval", action="store_true")
    ap.add_argument("--cout", type=float, default=None)
    ap.add_argument("--relay-delay", type=float, default=5e-3)
    ap.add_argument("--tstop", type=float, default=80e-3)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    ctl = Controller(relay_release_delay=a.relay_delay, noise_scale=1.0, adaptive_window=True,
                     seed=a.seed, use_ssd=True, fault_tolerant=not a.baseline, blank=0.0)
    extra = []
    last = [None]

    def on_data(d):
        ctl.data(d)
        t = d["time"]
        if last[0] is None or t - last[0] >= 1e-6:
            last[0] = t
            extra.append((t, d.get("vfuse#branch", 0.0), d.get("ni2t", 0.0), d.get("neav", 0.0), d.get("nblow", 0.0)))

    ng = NgSpice(on_data=on_data, on_vsrc=ctl.vsrc)
    net = netlist.prepare(netlist.export(), tstop=a.tstop,
                          faults={k: (b, v, T_FAULT) for k, (b, v, _) in CASES[a.case].items()},
                          cout=a.cout)
    ng.load(transform(net, a.fuse, a.aval))
    t0 = time.time()
    ng.cmd("run")
    wall = time.time() - t0
    errs = [l for l in ng.log if "rror" in l or "too small" in l]
    name = a.case + "_" + a.tag
    np.savez_compressed(os.path.join(RESULTS, name + ".npz"),
                        rec=np.array(ctl.rec), scores=np.array(ctl.scores or [(0, 0, 0)]),
                        raw=np.array(ctl.raw, dtype=np.float32), periods=np.array(ctl.periods),
                        extra=np.array(extra))
    meta = {"case": a.case, "tag": a.tag, "relay_release_delay_s": a.relay_delay, "cout_F": a.cout or 14e-6,
            "noise_scale": 1.0, "blank_s": ctl.blank, "adaptive_window": True, "seed": a.seed,
            "baseline": a.baseline, "ssd": True, "ssd_delay_s": ctl.ssd_delay, "fuse": a.fuse,
            "fuse_i2t_A2s": FUSE_I2T if a.fuse else None, "aval": a.aval,
            "t_fault_s": T_FAULT if CASES[a.case] else None, "tstop_s": a.tstop,
            "wall_s": round(wall, 1), "spice_errors": errs[:20], "events": ctl.events}
    with open(os.path.join(RESULTS, name + ".json"), "w") as f:
        json.dump(meta, f, indent=1)
    ex = np.array(extra)
    print(name, "done in", round(wall, 1), "s;", "spice errors:", len(errs))
    if a.fuse:
        k = int(np.argmax(ex[:, 4] > 0.5)) if (ex[:, 4] > 0.5).any() else None
        print("  fuse:", "opened at %.4f ms" % (ex[k, 0] * 1e3) if k else "intact",
              "| I2t final %.2f A2s | peak i_fuse %.1f A" % (ex[-1, 2], np.abs(ex[:, 1]).max()))
    if a.aval:
        print("  avalanche energy in Q1: %.3f mJ total" % (ex[-1, 3] * 1e3))
    for e in ctl.events:
        print(f"  {e['t']*1e3:9.4f} ms  ph{e['phase']}  {e['event']}  {e['detail']}")


if __name__ == "__main__":
    main()
