"""Write the exact SPICE netlist of every simulated case to kicad/ft_boost/netlists/<run>.cir.

Re-exports the KiCad schematic (kicad-cli) and applies, per run, the fault steps, C_out and
overrides recorded in results/<run>.json -- the same transformation run_case.py applies in memory.
  python3 -I sim/export_netlists.py
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import netlist  # noqa: E402

FAULT_SRC = {"open_inductor": ("VFOL1", 1, 0), "shorted_switch": ("VFSW1", 0, 1), "open_diode": ("VFOD1", 1, 0)}


def main():
    out = os.path.join(netlist.PROJ, "netlists")
    os.makedirs(out, exist_ok=True)
    text = netlist.export()
    n = 0
    for f in sorted(glob.glob(os.path.join(netlist.ROOT, "results", "*.json"))):
        m = json.load(open(f))
        if "case" not in m:
            continue
        faults = {}
        if m["case"] in FAULT_SRC and m.get("t_fault_s"):
            src, b, a = FAULT_SRC[m["case"]]
            faults[src] = (b, a, m["t_fault_s"])
        extra = netlist.load_step(400, 50e-3, 65e-3) if m.get("loadstep") else []
        cout = m.get("cout_F") if m.get("cout_F") and abs(m["cout_F"] - 14e-6) > 1e-9 else None
        cir = netlist.prepare(text, tstop=m.get("tstop_s", 80e-3), faults=faults, cout=cout,
                              overrides=m.get("overrides") or None, extra=extra)
        hdr = (f"* {os.path.basename(f)[:-5]}: case={m['case']} relay_delay={m.get('relay_release_delay_s')} "
               f"ssd={m.get('ssd', 'n/a')} baseline={m.get('baseline', False)} noise={m.get('noise_scale', 'n/a')}\n"
               "* VDUTYk/VRLYk/VSSDk are ngspice 'external' sources driven by sim/controller.py\n")
        open(os.path.join(out, os.path.basename(f)[:-5] + ".cir"), "w").write(hdr + cir + "\n")
        n += 1
    print("wrote", n, "netlists to", out)


if __name__ == "__main__":
    main()
