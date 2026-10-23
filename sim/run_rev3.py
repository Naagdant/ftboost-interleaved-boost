"""Revision-3 runs: inductor saturation, a transistor-level SSD, start-up faults and double faults.

  python -I sim/run_rev3.py --tag TAG [--faults SPEC] [--sat IK] [--ssd-real] [--early-arm]
                            [--tstop S] [--cout F] [--baseline] [--relay-delay S]

--faults  comma-separated list kind:phase@time, kind in open_inductor | shorted_switch | open_diode,
          e.g. "open_inductor:1@0.05,shorted_switch:2@0.06". Default: none (healthy).
--sat IK  soft-saturating inductors in both phases, flux model phi(i) = L0*IK*atan(i/IK), so the
          differential inductance is L0/(1 + (i/IK)^2): 80 % of L0 at i = IK/2.
--ssd-real  each SSD is two back-to-back 200 V MOSFETs (10 mohm each) with an isolated 12 V gate
          driver and a 4.7 ohm gate resistor, instead of an ideal 20 mohm switch.
--early-arm  controller start-up protection (controller.early_arm).

Same controller, power stage and settings as run_case.py otherwise (noise on, adaptive window,
no blanking, SSD + relay with 5 ms release). Extra traces in the .npz `extra`: t, v(nk1), v(nr1),
v(nk2), v(nr2), i_L1 (true, through the inductor), i_L2 (decimated to 1 MS/s).
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

RESULTS = os.path.join(netlist.ROOT, "results")
SRC = {"open_inductor": ("VFOL", 1, 0), "shorted_switch": ("VFSW", 0, 1), "open_diode": ("VFOD", 1, 0)}

SSD_MODEL = """.subckt NMOS200V D G S
M1 D G S VDM200
.model VDM200 VDMOS(Rg=1 Vto=3.5 Rd=6m Rs=2m Rb=10m Kp=60 Lambda=0.01
+ Cgdmax=1.2n Cgdmin=60p A=0.5 Cgs=4.5n Cjo=1.5n Is=1e-10 N=1.1 Tt=60n bv=200 ibv=250u)
.ends NMOS200V"""


def parse_faults(spec):
    out = {}
    for item in filter(None, (spec or "").split(",")):
        kind, rest = item.split(":")
        k, t = rest.split("@")
        name, before, after = SRC[kind]
        out[f"{name}{int(k)}"] = (before, after, float(t))
    return out


def transform(text, sat_ik, ssd_real):
    out = []
    for ln in text.splitlines():
        tok = ln.split()
        if sat_ik and tok and tok[0] in ("L1", "L2"):
            k = tok[0][1]
            n1, n2 = tok[1], tok[2]
            # flux-based soft-saturating inductor: phi = integral of v; i = IK*tan(phi/(L0*IK))
            out += [f"BPHI{k} 0 NPHI{k} I = V({n1},{n2})", f"CPHI{k} NPHI{k} 0 1", f"RPHI{k} NPHI{k} 0 1e12",
                    f"BL{k} {n1} {n2} I = {sat_ik:g}*tan(V(NPHI{k})/(1m*{sat_ik:g}))"]
            continue
        if ssd_real and tok and tok[0] in ("SSD1", "SSD2"):
            k = tok[0][-1]
            nk, nr, ctl = tok[1], tok[2], tok[3]
            out += [f"XSA{k} {nk} GS{k} CS{k} NMOS200V", f"XSB{k} {nr} GS{k} CS{k} NMOS200V",
                    f"BGD{k} GD{k} CS{k} V = 12*V({ctl})", f"RGD{k} GD{k} GS{k} 4.7",
                    f"RCS{k} CS{k} 0 10Meg"]
            continue
        if ln.startswith(".save"):
            ln += " v(nk1) v(nk2)"
        out.append(ln)
    if ssd_real:
        out.insert(len(out) - 1, SSD_MODEL)
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--faults", default="")
    ap.add_argument("--sat", type=float, default=0.0)
    ap.add_argument("--ssd-real", action="store_true")
    ap.add_argument("--early-arm", action="store_true")
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--cout", type=float, default=None)
    ap.add_argument("--relay-delay", type=float, default=5e-3)
    ap.add_argument("--tstop", type=float, default=80e-3)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    ctl = Controller(relay_release_delay=a.relay_delay, noise_scale=1.0, adaptive_window=True, seed=a.seed,
                     use_ssd=True, fault_tolerant=not a.baseline, blank=0.0, early_arm=a.early_arm)
    extra, last = [], [None]

    def on_data(d):
        ctl.data(d)
        t = d["time"]
        if last[0] is None or t - last[0] >= 1e-6:
            last[0] = t
            extra.append((t, d.get("nk1", 0.0), d.get("nr1", 0.0), d.get("nk2", 0.0), d.get("nr2", 0.0)))

    faults = parse_faults(a.faults)
    ng = NgSpice(on_data=on_data, on_vsrc=ctl.vsrc)
    net = netlist.prepare(netlist.export(), tstop=a.tstop, faults=faults, cout=a.cout)
    ng.load(transform(net, a.sat, a.ssd_real))
    t0 = time.time()
    ng.cmd("run")
    wall = time.time() - t0
    errs = [l for l in ng.log if "rror" in l or "too small" in l]
    name = "rev3_" + a.tag
    np.savez_compressed(os.path.join(RESULTS, name + ".npz"),
                        rec=np.array(ctl.rec), scores=np.array(ctl.scores or [(0, 0, 0, 0, 0)]),
                        periods=np.array(ctl.periods), extra=np.array(extra))
    meta = {"tag": a.tag, "faults": a.faults, "sat_ik_A": a.sat or None, "ssd_real": a.ssd_real,
            "early_arm": a.early_arm, "baseline": a.baseline, "cout_F": a.cout or 14e-6,
            "relay_release_delay_s": a.relay_delay, "tstop_s": a.tstop, "seed": a.seed,
            "wall_s": round(wall, 1), "spice_errors": errs[:20], "events": ctl.events}
    with open(os.path.join(RESULTS, name + ".json"), "w") as f:
        json.dump(meta, f, indent=1)
    rec = np.array(ctl.rec)
    print(name, "done in", round(wall, 1), "s; spice errors:", len(errs), "| final t = %.4f ms" % (rec[-1, 0] * 1e3))
    for e in ctl.events:
        if e["event"] != "template_learned":
            print(f"  {e['t']*1e3:9.4f} ms  ph{e['phase']}  {e['event']}  {e['detail']}")


if __name__ == "__main__":
    main()
