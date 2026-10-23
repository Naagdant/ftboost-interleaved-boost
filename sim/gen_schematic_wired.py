"""Wired, publication-layout KiCad schematic of the fault-tolerant converter (revision 2).

The original sim/gen_schematic.py connects every pin through a short stub and a net label,
which is exact but unreadable as a figure. This generator places the SAME parts (same
references, values and Sim.* fields, taken from gen_schematic.py) in a left-to-right power-flow
layout and draws the power path, clamps, fault-injection switches and current-sense lines as
wires. Control and supply nets (gate drive, relay coil, SSD and fault-injection controls,
isolated supplies, ADC outputs) keep net labels, as is usual for signal nets.

Written in KiCad 7 format (KiCad 8-10 open it). Verify with
  python3 -I sim/gen_schematic_wired.py && python3 -I sim/check_wired_netlist.py
which exports the netlist with kicad-cli and compares its connectivity with the simulated
netlist kicad/ft_boost/ft_boost.cir.
"""
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import SymbolLib, dump, pin_abs, q  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "kicad", "ft_boost_wired")
SYMDIR = "/usr/share/kicad/symbols/"

# --- the part table of the simulated schematic (refs, values, Sim.* fields, nets) -----------
_src = open(os.path.join(ROOT, "sim", "gen_schematic.py")).read()
_src = _src.replace('SYMDIR = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/"',
                    f'SYMDIR = "{SYMDIR}"')
_src = _src.split("# ---------------------------------------------------------------------------\ndef prop(")[0]
_ns = {"__file__": os.path.join(ROOT, "sim", "gen_schematic.py"), "__name__": "gen_parts"}
exec(compile(_src, "gen_schematic.py", "exec"), _ns)
PARTS = {p[2]: p for p in _ns["parts"]}          # ref -> (lib, sym, ref, val, x, y, rot, sim, nets)

LIBS = {n: SymbolLib(SYMDIR + n + ".kicad_sym", n)
        for n in ["Device", "Relay", "Amplifier_Difference", "Simulation_SPICE", "power", "Connector_Generic"]}
# KiCad 7 library names for the two symbols that moved in later versions
REMAP = {("Device", "Q_NMOS"): ("Device", "Q_NMOS_GDS", {"G": "1", "D": "2", "S": "3"}, "2=D 1=G 3=S"),
         ("Isolator_Analog", "AMC1300DWV"): ("Amplifier_Difference", "AMC1300DWV", None, None)}

ROOT_UUID = str(uuid.uuid5(uuid.NAMESPACE_URL, "ft_boost_wired-root"))
_n = [0]
TXT = 2.3           # reference / value text size [mm], larger than KiCad's 1.27 for print
LBL = 2.0


def uid():
    _n[0] += 1
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ft_boost_wired-{_n[0]}"))


placed = {}      # ref -> dict(lib, sym, x, y, rot, val, sim, nets, pins)
wires, labels, gnds, junctions, texts, noconn = [], [], [], [], [], []


def g(v):
    return round(round(v / 1.27) * 1.27, 2)


def place(ref, x, y, rot=0, ref_at=None, val_at=None, val=None, hide_val=False):
    lib, sym, _, v, _, _, _, sim, nets = PARTS[ref]
    sim = dict(sim)
    if (lib, sym) in REMAP:
        lib, sym, pmap, spins = REMAP[(lib, sym)]
        if pmap:
            nets = {pmap[k]: n for k, n in nets.items()}
            sim["Sim.Pins"] = spins
    pins = LIBS[lib].pins(sym)
    assert set(pins) == set(nets), (ref, pins, nets)
    x, y = g(x), g(y)
    abs_p = {pn: pin_abs((x, y), rot, pins[pn]) for pn in pins}
    placed[ref] = dict(lib=lib, sym=sym, x=x, y=y, rot=rot, val=val or v, sim=sim, nets=nets, pins=abs_p,
                       ref_at=ref_at, val_at=val_at, hide_val=hide_val)
    return placed[ref]


def P(ref, pn):
    (px, py), _ = placed[ref]["pins"][pn]
    return (round(px, 2), round(py, 2))


def wire(*pts):
    """Polyline through pin references ('Q1.D') or points; orthogonal segments only."""
    pts = [P(*p.split(".")) if isinstance(p, str) else (g(p[0]), g(p[1])) for p in pts]
    for a, b in zip(pts, pts[1:]):
        if a != b:
            assert a[0] == b[0] or a[1] == b[1], ("non-orthogonal wire", a, b)
            wires.append((a, b))


def junction(p):
    junctions.append((g(p[0]), g(p[1])))


def label(pin, net, d=(1, 0), length=2.54):
    (px, py) = P(*pin.split("."))
    ex, ey = px + d[0] * length, py + d[1] * length
    wires.append(((px, py), (ex, ey)))
    labels.append((net, ex, ey, d))


def gnd(pin, length=2.54):
    (px, py) = P(*pin.split("."))
    wires.append(((px, py), (px, py + length)))
    gnds.append((px, py + length))


def gnd_at(p):
    gnds.append((g(p[0]), g(p[1])))


def text(x, y, s, size=2.2, bold=False):
    texts.append((x, y, s, size, bold))


# =========================================================================== layout
def phase(k, Y):
    """One boost leg along the row y = Y, components left to right."""
    s = str(k)
    # input relay, contact at the bottom: COM (13) left, NO (14) right
    K = place("K" + s, 36.83, Y - 7.62, 270, val="G2RL-1A")
    # SSD switch on the row
    place("SSD" + s, 57.15, Y, 90, val="SSD, 20 mΩ", hide_val=True)
    # clamp column at the SSD output
    place("DFW" + s, 68.58, Y + 8.89, 270)
    place("DZ" + s, 68.58, Y + 19.05, 90)
    # Kelvin shunt on the row, AMC1300 above it
    place("RSH" + s, 82.55, Y, 90, val="10 mΩ Kelvin")
    place("U" + s, 99.06, Y - 20.32, 0)
    place("RDCR" + s, 113.03, Y, 90, val="60 mΩ")
    place("L" + s, 128.27, Y, 90, val="1 mH")
    place("SOL" + s, 140.97, Y, 90, val="inj. open L", hide_val=True)
    # switch node: MOSFET and stuck-on fault switch hang below the row
    xw = 157.48
    place("Q" + s, xw - 2.54, Y + 10.16, 0, val="650 V")
    place("SSW" + s, xw + 20.32, Y + 10.16, 0, val="inj. short Q", hide_val=True)
    place("SOD" + s, 191.77, Y, 90, val="inj. open D", hide_val=True)
    place("D" + s, 207.01, Y, 180, val="SiC SBD", ref_at=(0, -7.4, "center"), val_at=(0, -4.6, "center"))

    # --- power path wires
    wire("K%s.14" % s, "SSD%s.1" % s)                                   # NK
    wire("SSD%s.2" % s, (68.58, Y), "RSH%s.1" % s)                       # NR
    wire((68.58, Y), "DFW%s.1" % s)
    junction((68.58, Y))
    wire("DFW%s.2" % s, "DZ%s.2" % s)                                   # NFW
    gnd("DZ%s.1" % s)
    wire("RSH%s.4" % s, (P("RSH" + s, "4")[0] + 5.08, Y), "RDCR%s.1" % s)  # NS
    wire("RDCR%s.2" % s, "L%s.1" % s)                                   # NL
    wire("L%s.2" % s, "SOL%s.1" % s)                                    # NLX
    wire("SOL%s.2" % s, (xw, Y), (xw + 20.32, Y), "SOD%s.1" % s)        # SW
    wire((xw, Y), "Q%s.2" % s)
    junction((xw, Y))
    wire((xw + 20.32, Y), "SSW%s.1" % s)
    junction((xw + 20.32, Y))
    gnd("Q%s.3" % s)
    gnd("SSW%s.2" % s)
    wire("SOD%s.2" % s, "D%s.2" % s)                                    # NA
    # current-sense lines: shunt sense pins up to the AMC1300 inputs
    wire("RSH%s.2" % s, (P("RSH" + s, "2")[0], P("U" + s, "2")[1]), "U%s.2" % s)   # SNP
    wire("RSH%s.3" % s, (P("RSH" + s, "3")[0], P("U" + s, "3")[1]), "U%s.3" % s)   # SNN
    # AMC1300 high-side ground (GND1) to the shunt's far end (NS) with a wire
    wire("U%s.4" % s, (P("U" + s, "4")[0], Y - 7.62), (P("RSH" + s, "4")[0] + 5.08, Y - 7.62),
         (P("RSH" + s, "4")[0] + 5.08, Y))
    junction((P("RSH" + s, "4")[0] + 5.08, Y))
    labels.append(("NS" + s, P("RSH" + s, "4")[0] + 5.08, Y - 7.62, (-1, 0)))
    # signal nets as labels
    label("U%s.1" % s, "VISO" + s, (0, -1))
    label("U%s.8" % s, "V3V3", (0, -1))
    gnd("U%s.5" % s)
    label("U%s.7" % s, "ISP" + s, (1, 0))
    label("U%s.6" % s, "ISN" + s, (1, 0))
    label("K%s.A1" % s, "RLY" + s, (0, -1))
    gnd_at_pin_up("K%s.A2" % s)
    label("SSD%s.3" % s, "SSDC" + s, (0, 1))
    gnd("SSD%s.4" % s)
    label("SOL%s.3" % s, "FOL" + s, (0, 1))
    gnd("SOL%s.4" % s)
    label("SOD%s.3" % s, "FOD" + s, (0, 1), length=5.08)
    gnd("SOD%s.4" % s)
    label("Q%s.1" % s, "G" + s, (0, 1))
    label("SSW%s.3" % s, "FSW" + s, (-1, 0))
    gnd("SSW%s.4" % s)
    text(30.48, Y - 33.02, f"PHASE {k}  ({'0°' if k == 1 else '180°'} carrier)", 2.4, True)


def gnd_at_pin_up(pin):
    """GND symbol for a pin that points upwards: short wire up, then over, then down to a GND symbol."""
    (px, py) = P(*pin.split("."))
    wires.append(((px, py), (px, py - 2.54)))
    wires.append(((px, py - 2.54), (px - 3.81, py - 2.54)))
    wires.append(((px - 3.81, py - 2.54), (px - 3.81, py + 2.54)))
    gnds.append((px - 3.81, py + 2.54))


Y1, Y2 = 60.96, 132.08
phase(1, Y1)
phase(2, Y2)

# input: source, source resistance, input capacitor, VIN bus feeding both relays
place("VIN1", -5.08, 101.6, 0, val="48 V", ref_at=(2.6, 4.4, "left"), val_at=(2.6, 7.0, "left"))
place("RSRC1", 3.81, 91.44, 90, val="20 mΩ")
place("CIN1", 12.7, 101.6, 0, val="100 µF", ref_at=(-2.6, -1.0, "right"), val_at=(-2.6, 1.6, "right"))
xbus = 20.32
wire("VIN1.1", (-5.08, 91.44), "RSRC1.1")
wire("RSRC1.2", (12.7, 91.44), (xbus, 91.44))
wire((12.7, 91.44), "CIN1.1")
junction((12.7, 91.44))
wire((xbus, P("K1", "13")[1]), (xbus, 91.44), (xbus, P("K2", "13")[1]))
junction((xbus, 91.44))
wire((xbus, P("K1", "13")[1]), "K1.13")
wire((xbus, P("K2", "13")[1]), "K2.13")
gnd("VIN1.2")
gnd("CIN1.2")

# output bus: both diodes to VOUT, capacitor + ESR, load, feedback divider
xv = 220.98
yb = 83.82
wire("D1.1", (xv, Y1))
wire("D2.1", (xv, Y2))
wire((xv, Y1), (xv, yb), (xv, Y2))
junction((xv, yb))
place("COUT1", 233.68, 91.44, 0, val="14 µF")
place("RESR1", 233.68, 106.68, 0, val="10 mΩ ESR")
place("RLOAD1", 248.92, 99.06, 0, val="200 Ω")
place("RFB1", 264.16, 91.44, 0, val="1.99 MΩ")
place("RFB2", 264.16, 106.68, 0, val="10 kΩ")
wire((xv, yb), (233.68, yb), (248.92, yb), (264.16, yb))
for r in ("COUT1", "RLOAD1", "RFB1"):
    wire((P(r, "1")[0], yb), r + ".1")
junction((233.68, yb))
junction((248.92, yb))
wire("COUT1.2", "RESR1.1")
gnd("RESR1.2")
gnd("RLOAD1.2", length=7.62 + 2.54)
wire("RFB1.2", (264.16, 99.06), "RFB2.1")
gnd("RFB2.2")
wire((264.16, 99.06), (274.32, 99.06))
junction((264.16, 99.06))
labels.append(("VFB", 274.32, 99.06, (1, 0)))
labels.append(("VOUT", 233.68, yb, (0, -1)))

# ---------------------------------------------------------------- control / supply block
yc = 177.8
text(20.32, yc - 8.89, "CONTROLLER INTERFACE, GATE DRIVE, FAULT INJECTION AND AUXILIARY SUPPLIES", 2.4, True)
text(20.32, yc - 4.83, "CTRL: ngspice 'external' sources driven by the firmware model.  "
     "INJ: fault-injection controls, stepped at t = 50 ms.", 1.8)
SHORT = {"VCAR1": "carrier, td = 0", "VCAR2": "carrier, td = 10 µs", "VDUTY": "duty (CTRL)",
         "VRLY": "relay coil (CTRL)", "VSSD": "SSD gate (CTRL)", "VFOL": "open L (INJ)",
         "VFSW": "short Q (INJ)", "VFOD": "open D (INJ)", "VAUX1": "3.3 V"}


def two_pin_block(ref, x, y, top, bot):
    place(ref, x, y, 0, val=SHORT.get(ref, SHORT.get(ref[:-1])))
    top_label(ref + ".1", top)
    gnd(ref + ".2") if bot == "GND" else label(ref + ".2", bot, (0, 1))


def top_label(pin, net):
    """Label for an upward pin: short wire up, then a horizontal label to the right."""
    (px, py) = P(*pin.split("."))
    wires.append(((px, py), (px, py - 1.27)))
    wires.append(((px, py - 1.27), (px + 2.54, py - 1.27)))
    labels.append((net, px + 2.54, py - 1.27, (1, 0)))


col, dxc, dyr = 22.86, 36.83, 21.59
for k in (1, 2):
    s = str(k)
    ya = yc + 10.16 + (k - 1) * (2 * dyr + 5.08)
    yb_ = ya + dyr
    text(col - 2.54, ya - 6.0, f"Phase {k}", 2.0, True)
    place("EG" + s, col + 7.62, ya + 5.08, 0, val="PWM + gate drive")
    top_label("EG%s.1" % s, "G" + s)
    gnd("EG%s.2" % s)
    label("EG%s.3" % s, "DUTY" + s, (-1, 0))
    label("EG%s.4" % s, "CAR" + s, (-1, 0))
    for i, (ref, top) in enumerate((("VCAR", "CAR"), ("VDUTY", "DUTY"), ("VRLY", "RLY"), ("VSSD", "SSDC"))):
        two_pin_block(ref + s, col + 7.62 + (i + 1) * dxc, ya + 5.08, top + s, "GND")
    for i, (ref, top) in enumerate((("VFOL", "FOL"), ("VFSW", "FSW"), ("VFOD", "FOD"))):
        two_pin_block(ref + s, col + 7.62 + (i + 1) * dxc, yb_ + 5.08, top + s, "GND")
    place("VISO" + s, col + 7.62 + 4 * dxc, yb_ + 5.08, 0, val="5 V iso")
    top_label("VISO%s.1" % s, "VISO" + s)
    (px, py) = P("VISO" + s, "2")
    wires.append(((px, py), (px, py + 1.27)))
    wires.append(((px, py + 1.27), (px + 2.54, py + 1.27)))
    labels.append(("NS" + s, px + 2.54, py + 1.27, (1, 0)))
xr = col + 7.62 + 5 * dxc + 12.7
two_pin_block("VAUX1", xr, yc + 15.24, "V3V3", "GND")
place("J1", xr + 30.48, yc + 15.24, 0, val="MCU/DSP I/O")
for pn, net in PARTS["J1"][8].items():
    if net == "GND":
        (px, py) = P("J1", pn)
        wires.append(((px, py), (px - 5.08, py)))
        wires.append(((px - 5.08, py), (px - 5.08, py + 2.54)))
        gnds.append((px - 5.08, py + 2.54))
    else:
        label("J1." + pn, net, (-1, 0))
for i, net in enumerate(["GND", "V3V3", "VISO1", "VISO2", "NS1", "NS2"]):
    ref = f"#FLG0{i + 1}"
    PARTS[ref] = ("power", "PWR_FLAG", ref, "PWR_FLAG", 0, 0, 0, {}, {"1": net})
    place(ref, xr + (i % 3) * 12.7, yc + 45.72 + (i // 3) * 17.78, 0)
    if net == "GND":
        gnd(ref + ".1")
    else:
        label(ref + ".1", net, (0, 1))


# =========================================================================== output
def shift(dx):
    """Move the whole drawing right by dx (keeps the input source inside the sheet frame)."""
    global wires, labels, gnds, junctions, texts
    for p in placed.values():
        p["x"] = round(p["x"] + dx, 2)
    wires = [((a[0] + dx, a[1]), (b[0] + dx, b[1])) for a, b in wires]
    labels = [(n, x + dx, y, d) for n, x, y, d in labels]
    gnds = [(x + dx, y) for x, y in gnds]
    junctions = [(x + dx, y) for x, y in junctions]
    texts = [(x + dx, y, t, sz, b) for x, y, t, sz, b in texts]


def prop(name, val, x, y, hide=False, angle=0, size=1.27, justify=None):
    eff = ["effects", ["font", ["size", f"{size:g}", f"{size:g}"]]]
    if justify:
        eff.append(["justify", justify])
    if hide:
        eff.append("hide")
    return ["property", q(name), q(val), ["at", f"{x:.2f}", f"{y:.2f}", str(angle)], eff]


def text_pos(p):
    """Reference / value positions beside the body, chosen from the orientation."""
    x, y, rot, sym = p["x"], p["y"], p["rot"], p["sym"]
    if p.get("ref_at"):
        (a, b, ja), (c, d, jb) = p["ref_at"], p["val_at"]
        if rot in (90, 270):          # justification is mirrored for fields on rotated symbols
            ja, jb = [{"left": "right", "right": "left"}.get(j, j) for j in (ja, jb)]
        return (x + a, y + b, ja), (x + c, y + d, jb)
    if sym in ("R", "L", "C", "D", "D_Schottky", "D_Zener", "R_Shunt") and rot in (90, 180) and sym != "D_Zener":
        return (x, y - 4.6, "center"), (x, y + 5.0, "center")
    if sym == "D_Zener":
        return (x + 2.6, y - 1.0, "right"), (x + 2.6, y + 1.6, "right")
    if sym == "D" and rot == 270:
        return (x + 2.6, y - 1.0, "left"), (x + 2.6, y + 1.6, "left")
    if sym in ("R", "C", "VDC", "VPULSE") and rot == 0:
        return (x + 2.6, y - 1.0, "left"), (x + 2.6, y + 1.6, "left")
    if sym == "SWITCH" and rot == 90:
        return (x, y - 3.6, "center"), (x, y - 6.0, "center")
    if sym == "SWITCH" and rot == 0:
        return (x + 2.6, y - 2.2, "left"), (x + 2.6, y + 0.4, "left")
    if sym == "Q_NMOS_GDS":
        return (x + 4.6, y - 1.0, "left"), (x + 4.6, y + 1.6, "left")
    if sym == "G2RL-1A":
        return (x + 9.5, y - 4.0, "left"), (x + 9.5, y - 1.4, "left")
    if sym == "AMC1300DWV":
        return (x + 5.0, y - 8.6, "left"), (x + 9.5, y + 5.6, "left")
    if sym == "ESOURCE":
        return (x + 2.6, y - 1.0, "left"), (x + 2.6, y + 1.6, "left")
    if sym == "Conn_01x08":
        return (x, y - 10.0, "center"), (x - 4.0, y + 14.0, "left")
    return (x + 3, y - 3, "left"), (x + 3, y + 3, "left")


DX = 20.32


def build():
    shift(DX)
    lib_syms, used, items = [], set(), []
    for ref, p in placed.items():
        key = f"{p['lib']}:{p['sym']}"
        if key not in used:
            used.add(key)
            lib_syms.append(LIBS[p["lib"]].get(p["sym"]))
        sim = dict(p["sim"])
        excl = sim.pop("Sim.Enable", "1") == "0"
        (rx, ry, rj), (vx, vy, vj) = text_pos(p)
        flag = ref.startswith("#")
        fa = 90 if p["rot"] in (90, 270) else 0     # keeps field text horizontal on rotated symbols
        node = ["symbol", ["lib_id", q(key)], ["at", f"{p['x']:.2f}", f"{p['y']:.2f}", str(p["rot"])],
                ["unit", "1"], ["in_bom", "yes"], ["on_board", "yes"], ["dnp", "no"], ["uuid", q(uid())],
                prop("Reference", ref, rx, ry, flag, angle=fa, size=TXT, justify=None if rj == "center" else rj),
                prop("Value", p["val"], vx, vy, flag or p["hide_val"], angle=fa, size=TXT * 0.9,
                     justify=None if vj == "center" else vj),
                prop("Footprint", "", p["x"], p["y"], True), prop("Datasheet", "", p["x"], p["y"], True)]
        if excl:
            node.append(prop("Sim.Enable", "0", p["x"], p["y"], True))
        for k, v in sim.items():
            node.append(prop(k, v, p["x"], p["y"], True))
        for pn in p["pins"]:
            node.append(["pin", q(pn), ["uuid", q(uid())]])
        node.append(["instances", ["project", q("ft_boost_wired"),
                     ["path", q("/" + ROOT_UUID), ["reference", q(ref)], ["unit", "1"]]]])
        items.append(node)
    if "power:GND" not in used:
        used.add("power:GND")
        lib_syms.append(LIBS["power"].get("GND"))
    for i, (x, y) in enumerate(gnds):
        pref = f"#PWR{i + 1:04d}"
        items.append(["symbol", ["lib_id", q("power:GND")], ["at", f"{x:.2f}", f"{y:.2f}", "0"], ["unit", "1"],
                      ["in_bom", "yes"], ["on_board", "yes"], ["dnp", "no"], ["uuid", q(uid())],
                      prop("Reference", pref, x, y + 6, True), prop("Value", "GND", x, y + 4, True),
                      prop("Footprint", "", x, y, True), prop("Datasheet", "", x, y, True),
                      ["pin", q("1"), ["uuid", q(uid())]],
                      ["instances", ["project", q("ft_boost_wired"),
                       ["path", q("/" + ROOT_UUID), ["reference", q(pref)], ["unit", "1"]]]]])
    for (a, b) in wires:
        items.append(["wire", ["pts", ["xy", f"{a[0]:.2f}", f"{a[1]:.2f}"], ["xy", f"{b[0]:.2f}", f"{b[1]:.2f}"]],
                      ["stroke", ["width", "0"], ["type", "default"]], ["uuid", q(uid())]])
    for (x, y) in set(junctions):
        items.append(["junction", ["at", f"{x:.2f}", f"{y:.2f}"], ["diameter", "0"], ["color", "0", "0", "0", "0"],
                      ["uuid", q(uid())]])
    for net, x, y, d in labels:
        ang, just = {(1, 0): ("0", "left"), (-1, 0): ("180", "right"),
                     (0, -1): ("90", "left"), (0, 1): ("270", "right")}[tuple(d)]
        items.append(["label", q(net), ["at", f"{x:.2f}", f"{y:.2f}", ang], ["fields_autoplaced"],
                      ["effects", ["font", ["size", f"{LBL:g}", f"{LBL:g}"]], ["justify", just, "bottom"]],
                      ["uuid", q(uid())]])
    for x, y, t, sz, bold in texts:
        font = ["font", ["size", f"{sz:g}", f"{sz:g}"]] + (["bold"] if bold else [])
        items.append(["text", q(t), ["at", f"{x:.2f}", f"{y:.2f}", "0"],
                      ["effects", font, ["justify", "left", "bottom"]], ["uuid", q(uid())]])
    sch = ["kicad_sch", ["version", "20230121"], ["generator", "eeschema"], ["uuid", q(ROOT_UUID)],
           ["paper", q("A3")],
           ["title_block", ["title", q("Fault-tolerant two-phase interleaved boost converter, 48 V to 200 V")],
            ["date", q("2026-10-20")], ["rev", q("B")],
            ["comment", "1", q("2 x 1 mH, 50 kHz, 180 deg interleaved; input relay + SSD per phase; AMC1300 sensing")],
            ["comment", "2", q("Same parts and connectivity as the simulated schematic (sim/check_wired_netlist.py)")]],
           ["lib_symbols"] + lib_syms] + items + [["sheet_instances", ["path", q("/"), ["page", q("1")]]]]
    return dump(sch) + "\n"


if __name__ == "__main__":
    missing = set(PARTS) - set(placed)
    assert not missing, f"parts not placed: {sorted(missing)}"
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "ft_boost_wired.kicad_sch"), "w") as f:
        f.write(build())
    with open(os.path.join(OUTDIR, "ft_boost_wired.kicad_pro"), "w") as f:
        f.write('{\n  "meta": {"filename": "ft_boost_wired.kicad_pro", "version": 1}\n}\n')
    lib = os.path.join(ROOT, "kicad", "ft_boost", "ft_boost_models.lib")
    dst = os.path.join(OUTDIR, "ft_boost_models.lib")
    if not os.path.exists(dst):
        open(dst, "w").write(open(lib).read())
    print("wrote", OUTDIR, len(placed), "parts,", len(wires), "wires,", len(labels), "labels")
