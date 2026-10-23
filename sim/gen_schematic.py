"""Generate kicad/ft_boost/ft_boost.kicad_sch from real KiCad library symbols.

Every pin gets a short wire stub ending in a net label (or GND symbol), so
connectivity is exact and verifiable by ERC / netlist export. Re-run after
editing the tables below:  python3 -I sim/gen_schematic.py
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import SymbolLib, dump, first, find, pin_abs, q, unq  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ = os.path.join(ROOT, "kicad", "ft_boost")
SYMDIR = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/"
MODLIB = "ft_boost_models.lib"
STUB = 2.54

LIBS = {n: SymbolLib(SYMDIR + n + ".kicad_sym", n)
        for n in ["Device", "Relay", "Isolator_Analog", "Simulation_SPICE", "power", "Connector_Generic"]}

ROOT_UUID = str(uuid.uuid5(uuid.NAMESPACE_URL, "ft_boost-root"))
_n = [0]


def uid():
    _n[0] += 1
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ft_boost-{_n[0]}"))


def sub(model, pins):
    return {"Sim.Device": "SPICE",
            "Sim.Params": f'type="X" model="{model}" lib="{MODLIB}"',
            "Sim.Pins": pins}


def vdc(val):
    return {"Sim.Device": "V", "Sim.Type": "DC", "Sim.Params": f"dc={val}", "Sim.Pins": "1=+ 2=-"}


SW_NC = {"Sim.Device": "SW", "Sim.Type": "V", "Sim.Params": "thr=0.5 ron=1m roff=1G",
         "Sim.Pins": "1=no+ 2=no- 3=ctrl+ 4=ctrl-"}
SW_SHORT = {"Sim.Device": "SW", "Sim.Type": "V", "Sim.Params": "thr=0.5 ron=10m roff=1G",
            "Sim.Pins": "1=no+ 2=no- 3=ctrl+ 4=ctrl-"}

# ---------------------------------------------------------------------------
# Component table: (lib, symbol, ref, value, x, y, rot, sim_fields, {pin: net})
# ---------------------------------------------------------------------------
parts = []
texts = []


def snap(v, g=2.54):
    return round(round(v / g) * g, 2)


def P(lib, sym, ref, val, x, y, nets, sim=None, rot=0):
    parts.append((lib, sym, ref, val, snap(x), snap(y), rot, sim or {}, nets))


def phase(k, y0):
    x = 40.64
    sx = 33.02
    texts.append((x - 10, y0 - 22, f"PHASE {k} — relay-isolated boost leg "
                  f"({'0' if k == 1 else '180'} deg carrier)", 2.5))
    P("Relay", "G2RL-1A", f"K{k}", "G2RL-1A 12V", x, y0,
      {"A1": f"RLY{k}", "A2": "GND", "13": "VIN", "14": f"NK{k}"},
      sub("G2RL1A", "13=COM 14=NO A1=A1 A2=A2"))
    P("Device", "D", f"DFW{k}", "UF4007", x + sx, y0 - 8, {"1": f"NR{k}", "2": f"NFW{k}"},
      sub("DFAST", "1=K 2=A"))
    P("Device", "D_Zener", f"DZ{k}", "SMBJ100A", x + sx, y0 + 8, {"1": "GND", "2": f"NFW{k}"},
      sub("TVS100", "1=K 2=A"))
    P("Device", "R_Shunt", f"RSH{k}", "10m Kelvin", x + 2 * sx, y0,
      {"1": f"NR{k}", "2": f"SNP{k}", "3": f"SNN{k}", "4": f"NS{k}"},
      sub("RSHUNT10M", "1=F1 2=S1 3=S2 4=F2"))
    P("Isolator_Analog", "AMC1300DWV", f"U{k}", "AMC1300", x + 3 * sx + 6, y0,
      {"1": f"VISO{k}", "2": f"SNP{k}", "3": f"SNN{k}", "4": f"NS{k}",
       "5": "GND", "6": f"ISN{k}", "7": f"ISP{k}", "8": "V3V3"},
      sub("AMC1300", "1=VDD1 2=VINP 3=VINN 4=GND1 5=GND2 6=VOUTN 7=VOUTP 8=VDD2"))
    P("Simulation_SPICE", "VDC", f"VISO{k}", "5V iso DC/DC", x + 4 * sx + 6, y0,
      {"1": f"VISO{k}", "2": f"NS{k}"}, vdc(5))
    P("Device", "R", f"RDCR{k}", "60m (L DCR)", x + 5 * sx, y0, {"1": f"NS{k}", "2": f"NL{k}"},
      {"Sim.Device": "R", "Sim.Params": "r=60m", "Sim.Pins": "1=+ 2=-"})
    P("Device", "L", f"L{k}", "1mH", x + 6 * sx, y0, {"1": f"NL{k}", "2": f"NLX{k}"},
      {"Sim.Device": "L", "Sim.Params": "l=1m", "Sim.Pins": "1=+ 2=-"})
    P("Simulation_SPICE", "SWITCH", f"SOL{k}", "FAULT: open L", x + 7 * sx, y0,
      {"1": f"NLX{k}", "2": f"SW{k}", "3": f"FOL{k}", "4": "GND"}, SW_NC)
    P("Device", "Q_NMOS", f"Q{k}", "650V 80mR", x + 8 * sx, y0,
      {"D": f"SW{k}", "G": f"G{k}", "S": "GND"}, sub("NMOS650V", "D=D G=G S=S"))
    P("Simulation_SPICE", "SWITCH", f"SSW{k}", "FAULT: short Q", x + 9 * sx, y0,
      {"1": f"SW{k}", "2": "GND", "3": f"FSW{k}", "4": "GND"}, SW_SHORT)
    P("Simulation_SPICE", "SWITCH", f"SOD{k}", "FAULT: open D", x + 10 * sx, y0,
      {"1": f"SW{k}", "2": f"NA{k}", "3": f"FOD{k}", "4": "GND"}, SW_NC)
    P("Device", "D_Schottky", f"D{k}", "650V SiC SBD", x + 11 * sx, y0,
      {"1": "VOUT", "2": f"NA{k}"}, sub("SICSBD650", "1=K 2=A"))
    # gate drive / PWM
    y1 = y0 + 34
    texts.append((x - 10, y1 - 14, f"Phase {k} PWM + gate drive, controller I/O and fault injection", 1.8))
    P("Simulation_SPICE", "ESOURCE", f"EG{k}", "PWM_GDRV", x, y1,
      {"1": f"G{k}", "2": "GND", "3": f"DUTY{k}", "4": f"CAR{k}"},
      sub("PWM_GDRV", "1=G 2=GND 3=DUTY 4=CARR"))
    td = "0" if k == 1 else "10u"
    P("Simulation_SPICE", "VPULSE", f"VCAR{k}", f"carrier td={td}", x + sx, y1,
      {"1": f"CAR{k}", "2": "GND"},
      {"Sim.Device": "V", "Sim.Type": "PULSE",
       "Sim.Params": f"y1=0 y2=1 td={td} tr=19.99u tf=10n tw=0 per=20u", "Sim.Pins": "1=+ 2=-"})
    P("Simulation_SPICE", "VDC", f"VDUTY{k}", "CTRL duty (0.76)", x + 2 * sx, y1,
      {"1": f"DUTY{k}", "2": "GND"}, vdc(0.76))
    P("Simulation_SPICE", "VDC", f"VRLY{k}", "CTRL relay coil (12V)", x + 3 * sx, y1,
      {"1": f"RLY{k}", "2": "GND"}, vdc(12))
    P("Simulation_SPICE", "SWITCH", f"SSD{k}", "SSD: solid-state disconnect", x + 4 * sx, y1,
      {"1": f"NK{k}", "2": f"NR{k}", "3": f"SSDC{k}", "4": "GND"},
      {"Sim.Device": "SW", "Sim.Type": "V", "Sim.Params": "thr=0.5 ron=20m roff=1G",
       "Sim.Pins": "1=no+ 2=no- 3=ctrl+ 4=ctrl-"})
    P("Simulation_SPICE", "VDC", f"VSSD{k}", "CTRL SSD gate (1=on)", x + 8 * sx, y1,
      {"1": f"SSDC{k}", "2": "GND"}, vdc(1))
    P("Simulation_SPICE", "VDC", f"VFOL{k}", "INJ open-L (1=ok)", x + 5 * sx, y1,
      {"1": f"FOL{k}", "2": "GND"}, vdc(1))
    P("Simulation_SPICE", "VDC", f"VFSW{k}", "INJ short-Q (0=ok)", x + 6 * sx, y1,
      {"1": f"FSW{k}", "2": "GND"}, vdc(0))
    P("Simulation_SPICE", "VDC", f"VFOD{k}", "INJ open-D (1=ok)", x + 7 * sx, y1,
      {"1": f"FOD{k}", "2": "GND"}, vdc(1))


phase(1, 50)
phase(2, 150)

yc = 250
texts.append((30, yc - 22, "INPUT BUS, OUTPUT BUS, FEEDBACK, AUX SUPPLY", 2.5))
P("Simulation_SPICE", "VDC", "VIN1", "48V", 40, yc, {"1": "VSRC", "2": "GND"}, vdc(48))
P("Device", "R", "RSRC1", "20m", 74, yc, {"1": "VSRC", "2": "VIN"},
  {"Sim.Device": "R", "Sim.Params": "r=20m", "Sim.Pins": "1=+ 2=-"})
P("Device", "C", "CIN1", "100u", 108, yc, {"1": "VIN", "2": "GND"},
  {"Sim.Device": "C", "Sim.Params": "c=100u", "Sim.Pins": "1=+ 2=-"})
P("Device", "C", "COUT1", "14u 450V film", 160, yc, {"1": "VOUT", "2": "NESR"},
  {"Sim.Device": "C", "Sim.Params": "c=14u", "Sim.Pins": "1=+ 2=-"})
P("Device", "R", "RESR1", "10m ESR", 194, yc, {"1": "NESR", "2": "GND"},
  {"Sim.Device": "R", "Sim.Params": "r=10m", "Sim.Pins": "1=+ 2=-"})
P("Device", "R", "RLOAD1", "200 (1 A @ 200 V)", 228, yc, {"1": "VOUT", "2": "GND"},
  {"Sim.Device": "R", "Sim.Params": "r=200", "Sim.Pins": "1=+ 2=-"})
P("Device", "R", "RFB1", "1.99Meg", 262, yc, {"1": "VOUT", "2": "VFB"},
  {"Sim.Device": "R", "Sim.Params": "r=1.99Meg", "Sim.Pins": "1=+ 2=-"})
P("Device", "R", "RFB2", "10k", 296, yc, {"1": "VFB", "2": "GND"},
  {"Sim.Device": "R", "Sim.Params": "r=10k", "Sim.Pins": "1=+ 2=-"})
P("Simulation_SPICE", "VDC", "VAUX1", "3.3V (AMC1300 VDD2)", 330, yc, {"1": "V3V3", "2": "GND"}, vdc(3.3))

P("Connector_Generic", "Conn_01x08", "J1", "MCU/DSP interface (ADC in, PWM out)", 370, yc,
  {"1": "ISP1", "2": "ISN1", "3": "ISP2", "4": "ISN2", "5": "VFB", "6": "DUTY1", "7": "DUTY2", "8": "GND"},
  {"Sim.Enable": "0"})
for i, net in enumerate(["GND", "V3V3", "VISO1", "VISO2", "NS1", "NS2"]):
    P("power", "PWR_FLAG", f"#FLG0{i + 1}", "PWR_FLAG", 410 + 20 * i, yc, {"1": net})

texts.append((30, yc + 30,
              "Controller I/O (VDUTYk, VRLYk, VSSDk) default to open-loop values so the sheet runs in the KiCad simulator as-is.\n"
              "sim/run_case.py rewrites them as ngspice 'external' sources driven by the Python firmware model\n"
              "(fault detection, debounce, template correlation, relay isolation, closed-loop reconfiguration)\n"
              "and rewrites VFOLk / VFSWk / VFODk as PWL steps at t = 50 ms for the fault-injection matrix.", 1.8))
texts.append((30, yc + 52, ".tran 50n 80m 0 50n", 1.8))


# ---------------------------------------------------------------------------
def prop(name, val, x, y, hide=False, angle=0):
    eff = ["effects", ["font", ["size", "1.27", "1.27"]]]
    if hide:
        eff.append(["hide", "yes"])
    return ["property", q(name), q(val), ["at", f"{x:.2f}", f"{y:.2f}", str(angle)], eff]


def build():
    lib_syms, used = [], set()
    items = []
    for lib, sym, ref, val, x, y, rot, sim, nets in parts:
        key = f"{lib}:{sym}"
        L = LIBS[lib]
        if key not in used:
            used.add(key)
            lib_syms.append(L.get(sym))
        pins = L.pins(sym)
        assert set(nets) == set(pins), (ref, sorted(pins), sorted(nets))
        node = ["symbol", ["lib_id", q(key)], ["at", f"{x:.2f}", f"{y:.2f}", str(rot)],
                ["unit", "1"], ["exclude_from_sim", "yes" if sim.pop("Sim.Enable", "1") == "0" else "no"],
                ["in_bom", "yes"], ["on_board", "yes"], ["dnp", "no"], ["uuid", q(uid())],
                prop("Reference", ref, x + 4, y - 9, ref.startswith("#")),
                prop("Value", val, x + 4, y + 10),
                prop("Footprint", "", x, y, True),
                prop("Datasheet", "", x, y, True)]
        for k, v in sim.items():
            node.append(prop(k, v, x, y, True))
        for pn in pins:
            node.append(["pin", q(pn), ["uuid", q(uid())]])
        node.append(["instances", ["project", q("ft_boost"),
                     ["path", q("/" + ROOT_UUID), ["reference", q(ref)], ["unit", "1"]]]])
        items.append(node)
        for pn, net in nets.items():
            (px, py), (ox, oy) = pin_abs((x, y), rot, pins[pn])
            ex, ey = px + ox * STUB, py + oy * STUB
            items.append(["wire", ["pts", ["xy", f"{px:.2f}", f"{py:.2f}"], ["xy", f"{ex:.2f}", f"{ey:.2f}"]],
                          ["stroke", ["width", "0"], ["type", "default"]], ["uuid", q(uid())]])
            if net == "GND":
                if "power:GND" not in used:
                    used.add("power:GND")
                    lib_syms.append(LIBS["power"].get("GND"))
                _n[0] += 1
                pref = f"#PWR{_n[0]:04d}"
                items.append(["symbol", ["lib_id", q("power:GND")], ["at", f"{ex:.2f}", f"{ey:.2f}", "0"],
                              ["unit", "1"], ["exclude_from_sim", "no"], ["in_bom", "yes"],
                              ["on_board", "yes"], ["dnp", "no"], ["uuid", q(uid())],
                              prop("Reference", pref, ex, ey + 6, True),
                              prop("Value", "GND", ex, ey + 4, True),
                              prop("Footprint", "", ex, ey, True), prop("Datasheet", "", ex, ey, True),
                              ["pin", q("1"), ["uuid", q(uid())]],
                              ["instances", ["project", q("ft_boost"),
                               ["path", q("/" + ROOT_UUID), ["reference", q(pref)], ["unit", "1"]]]]])
            else:
                ang, just = {(1, 0): ("0", "left"), (-1, 0): ("180", "right"),
                             (0, -1): ("90", "left"), (0, 1): ("270", "right")}[(ox, oy)]
                items.append(["label", q(net), ["at", f"{ex:.2f}", f"{ey:.2f}", ang],
                              ["fields_autoplaced", "yes"],
                              ["effects", ["font", ["size", "1.27", "1.27"]], ["justify", just, "bottom"]],
                              ["uuid", q(uid())]])
    for x, y, t, sz in texts:
        items.append(["text", q(t), ["exclude_from_sim", "no"], ["at", f"{x:.2f}", f"{y:.2f}", "0"],
                      ["effects", ["font", ["size", str(sz), str(sz)]], ["justify", "left", "bottom"]],
                      ["uuid", q(uid())]])

    sch = ["kicad_sch", ["version", "20250114"], ["generator", q("eeschema")],
           ["generator_version", q("9.0")], ["uuid", q(ROOT_UUID)], ["paper", q("A2")],
           ["title_block", ["title", q("Fault-tolerant redundant-phase interleaved boost (48 V -> 200 V)")],
            ["date", q("2026-10-18")], ["rev", q("A")],
            ["comment", "1", q("2 x 1 mH, 50 kHz, 180 deg interleaved; per-phase isolated sensing + relay isolation")],
            ["comment", "2", q("Generated by sim/gen_schematic.py — edit the generator, not this file")]],
           ["lib_symbols"] + lib_syms] + items + [
           ["sheet_instances", ["path", q("/"), ["page", q("1")]]], ["embedded_fonts", "no"]]
    return dump(sch) + "\n"


if __name__ == "__main__":
    os.makedirs(PROJ, exist_ok=True)
    with open(os.path.join(PROJ, "ft_boost.kicad_sch"), "w") as f:
        f.write(build())
    pro = os.path.join(PROJ, "ft_boost.kicad_pro")
    if not os.path.exists(pro):
        with open(pro, "w") as f:
            f.write('{\n  "meta": {"filename": "ft_boost.kicad_pro", "version": 1},\n'
                    '  "sheets": [["' + ROOT_UUID + '", "Root"]]\n}\n')
    print("wrote", os.path.join(PROJ, "ft_boost.kicad_sch"), len(parts), "parts")
