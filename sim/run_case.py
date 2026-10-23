"""Run one fault-injection case of the brief's test matrix.

  python -I sim/run_case.py <case> [--relay-delay SECONDS] [--tstop S]

Cases (single fault, phase 1, injected at t = 50 ms, run to 80 ms):
  healthy | open_inductor | shorted_switch | open_diode
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

T_FAULT = 50e-3
CASES = {
    "healthy": {},
    "open_inductor": {"VFOL1": (1, 0, T_FAULT)},
    "shorted_switch": {"VFSW1": (0, 1, T_FAULT)},
    "open_diode": {"VFOD1": (1, 0, T_FAULT)},
}
RESULTS = os.path.join(netlist.ROOT, "results")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case", choices=CASES)
    ap.add_argument("--relay-delay", type=float, default=0.0)
    ap.add_argument("--tstop", type=float, default=80e-3)
    ap.add_argument("--tag", default="")
    ap.add_argument("--cout", type=float, default=None, help="override C_out [F]")
    ap.add_argument("--noise", type=float, default=1.0,
                    help="sensor noise scale (1 = AMC1300 + 12-bit ADC typical, 0 = quantization only)")
    ap.add_argument("--blank", type=float, default=None, help="post-reconfiguration shape-detector blanking [s]")
    ap.add_argument("--fixed-window", action="store_true", help="old fixed 4.8 us correlation window")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--tfault", type=float, default=T_FAULT, help="fault injection instant [s]")
    ap.add_argument("--baseline", action="store_true",
                    help="conventional interleaved boost: same stage + loops, no fault isolation")
    ap.add_argument("--no-ssd", action="store_true", help="relay only, no solid-state disconnect")
    ap.add_argument("--ssd-delay", type=float, default=None)
    ap.add_argument("--rload", type=float, default=None, help="load resistance [ohm] (default 200)")
    ap.add_argument("--vin", type=float, default=None, help="input voltage [V] (default 48)")
    ap.add_argument("--l2", type=float, default=None, help="phase-2 inductance [H] (mismatch test)")
    ap.add_argument("--loadstep", action="store_true",
                    help="RLOAD 400 ohm with an extra 400 ohm switched in at 50 ms and out at 65 ms")
    a = ap.parse_args()

    kw = {} if a.blank is None else {"blank": a.blank}
    if a.ssd_delay is not None:
        kw["ssd_delay"] = a.ssd_delay
    ov, extra = {}, []
    if a.rload:
        ov["RLOAD1"] = f"{a.rload:g}"
    if a.vin:
        ov["VIN1"] = f"DC {a.vin:g}"
    if a.l2:
        ov["L2"] = f"{a.l2:g}"
    if a.loadstep:
        ov["RLOAD1"] = "400"
        extra = netlist.load_step(400, 50e-3, 65e-3)
    ctl = Controller(relay_release_delay=a.relay_delay, noise_scale=a.noise,
                     adaptive_window=not a.fixed_window, seed=a.seed,
                     use_ssd=not a.no_ssd, fault_tolerant=not a.baseline, **kw)
    ng = NgSpice(on_data=ctl.data, on_vsrc=ctl.vsrc)
    ng.load(netlist.prepare(netlist.export(), tstop=a.tstop, faults={k: (b, v, a.tfault) for k, (b, v, _) in CASES[a.case].items()}, cout=a.cout,
                                overrides=ov, extra=extra))
    t0 = time.time()
    ng.cmd("run")
    wall = time.time() - t0
    errs = [l for l in ng.log if "rror" in l or "too small" in l]

    name = a.case + (a.tag and "_" + a.tag)
    os.makedirs(RESULTS, exist_ok=True)
    np.savez_compressed(os.path.join(RESULTS, name + ".npz"),
                        rec=np.array(ctl.rec), scores=np.array(ctl.scores or [(0, 0, 0)]),
                        raw=np.array(ctl.raw, dtype=np.float32), periods=np.array(ctl.periods))
    meta = {"case": a.case, "tag": a.tag, "relay_release_delay_s": a.relay_delay, "cout_F": a.cout or 14e-6,
            "noise_scale": a.noise, "blank_s": ctl.blank, "adaptive_window": not a.fixed_window, "seed": a.seed,
            "baseline": a.baseline, "ssd": not a.no_ssd, "ssd_delay_s": ctl.ssd_delay, "overrides": ov,
            "loadstep": a.loadstep,
            "t_fault_s": a.tfault if CASES[a.case] else None, "tstop_s": a.tstop,
            "wall_s": round(wall, 1), "spice_errors": errs[:20], "events": ctl.events}
    with open(os.path.join(RESULTS, name + ".json"), "w") as f:
        json.dump(meta, f, indent=1)
    print(name, "done in", round(wall, 1), "s;", len(ctl.events), "events")
    for e in ctl.events:
        print(f"  {e['t']*1e3:9.4f} ms  ph{e['phase']}  {e['event']}  {e['detail']}")


if __name__ == "__main__":
    main()
