"""Export the KiCad schematic to SPICE and prepare it for ngspice co-simulation."""
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ = os.path.join(ROOT, "kicad", "ft_boost")
KICAD_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"

SAVE = ["vout", "vin", "vfb", "nr1", "ns1", "nr2", "ns2",
        "isp1", "isn1", "isp2", "isn2", "sw1", "sw2"]


def export():
    out = os.path.join(PROJ, "ft_boost.cir")
    if not os.path.exists(KICAD_CLI):  # Linux workspace: use the netlist kicad-cli exported on the Mac
        return open(out).read()
    subprocess.run([KICAD_CLI, "sch", "export", "netlist", "--format", "spice",
                    "-o", out, os.path.join(PROJ, "ft_boost.kicad_sch")],
                   check=True, capture_output=True)
    return open(out).read()


def pwl_step(before, after, t_fault, tr=100e-9):
    return f"PWL(0 {before} {t_fault:g} {before} {t_fault + tr:g} {after})"


def load_step(r_add, t_on, t_off):
    """Extra netlist lines: r_add switched in parallel with the load between t_on and t_off."""
    return [f"RSTEP VOUT nstep {r_add:g}",
            "SSTEP nstep 0 cstep 0 SWSTEP",
            f"VCSTEP cstep 0 PWL(0 0 {t_on:g} 0 {t_on + 1e-7:g} 1 {t_off:g} 1 {t_off + 1e-7:g} 0)",
            ".model SWSTEP sw vt=0.5 ron=1m roff=1G"]


def prepare(text, tstop=80e-3, tmax=50e-9, external=True, faults=None, cout=None,
            overrides=None, extra=None):
    """overrides: {ref: "value tokens"} replaces everything after the nodes, e.g.
    {"RLOAD1": "400", "VIN1": "DC 43.2", "L2": "1.1m"}; extra: additional netlist lines."""
    """faults: {source_ref: (before, after, t)}  e.g. {"VFOL1": (1, 0, 50e-3)}"""
    lib = os.path.join(PROJ, "ft_boost_models.lib")
    out = []
    for line in text.splitlines():
        if line.startswith(".tran") or line.startswith(".end"):
            continue
        if line.startswith(".include"):
            line = f'.include "{lib}"'
        elif not line.startswith(("+", ".", "*")):
            toks = line.split()
            toks = [t[1:] if t.startswith("/") else t for t in toks]
            toks = ["0" if t == "GND" else t for t in toks]
            ref = toks[0].upper()
            if external and ref.startswith(("VDUTY", "VRLY", "VSSD")):
                toks = toks[:3] + ["dc", "0", "external"]
            if faults and ref in faults:
                b, a, t = faults[ref]
                toks = toks[:3] + [pwl_step(b, a, t)]
            if cout and ref == "COUT1":
                toks[3] = f"{cout:g}"
            if overrides and ref in overrides:
                toks = toks[:3] + str(overrides[ref]).split()
            line = " ".join(toks)
        out.append(line)
    out.extend(extra or [])
    out.append(".options reltol=1e-3 abstol=1e-9 vntol=1e-5 method=gear maxord=2 itl4=50")
    out.append(".save " + " ".join(f"v({n})" for n in SAVE))
    out.append(f".tran {tmax:g} {tstop:g} 0 {tmax:g} uic")
    out.append(".end")
    return "\n".join(out)
