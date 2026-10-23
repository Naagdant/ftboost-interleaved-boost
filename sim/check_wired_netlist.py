"""Compare the connectivity of the wired schematic with the simulated netlist.

Exports kicad/ft_boost_wired/ft_boost_wired.kicad_sch with kicad-cli, then compares the two SPICE
netlists as partitions of element terminals into nets (net names are ignored, because the wired
schematic names some nets automatically). Also compares every element's model / value text.
  python3 -I sim/check_wired_netlist.py
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "kicad", "ft_boost", "ft_boost.cir")
WDIR = os.path.join(ROOT, "kicad", "ft_boost_wired")
NNODES = {"R": 2, "L": 2, "C": 2, "V": 2, "I": 2, "D": 2, "S": 4, "E": 4, "G": 4, "B": 2, "M": 4}


def elements(path):
    out = {}
    for ln in open(path):
        t = ln.split()
        if not t or t[0][0] in ".+*":
            continue
        ref = t[0].upper()
        if ref[0] == "X":
            nodes, rest = t[1:-1], t[-1:]
        else:
            n = NNODES[ref[0]]
            nodes, rest = t[1:1 + n], t[1 + n:]
        out[ref] = ([x.lstrip("/").upper().replace("GND", "0") for x in nodes], " ".join(rest))
    return out


def partition(el):
    nets = {}
    for ref, (nodes, _) in el.items():
        for i, n in enumerate(nodes):
            nets.setdefault(n, set()).add((ref, i))
    return {frozenset(v) for v in nets.values()}


def main():
    wired = os.path.join(WDIR, "wired.cir")
    subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "spice", "-o", wired,
                    os.path.join(WDIR, "ft_boost_wired.kicad_sch")], check=True, capture_output=True)
    a, b = elements(REF), elements(wired)
    ok = True
    if set(a) != set(b):
        ok = False
        print("element sets differ: only simulated", sorted(set(a) - set(b)), "only wired", sorted(set(b) - set(a)))
    for ref in sorted(set(a) & set(b)):
        if a[ref][1].lower() != b[ref][1].lower():
            ok = False
            print("model/value differs:", ref, "|", a[ref][1], "|", b[ref][1])
    pa, pb = partition(a), partition(b)
    if pa != pb:
        ok = False
        for s in sorted(pa - pb, key=lambda s: sorted(s)):
            print("net only in simulated netlist:", sorted(s))
        for s in sorted(pb - pa, key=lambda s: sorted(s)):
            print("net only in wired schematic:  ", sorted(s))
    print(f"{len(a)} elements, {len(pa)} nets in the simulated netlist; {len(b)} elements, {len(pb)} nets wired")
    print("IDENTICAL CONNECTIVITY" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
