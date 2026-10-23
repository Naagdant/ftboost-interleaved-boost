"""Fig. 2: power-stage circuit diagram of the fault-tolerant two-phase interleaved boost converter."""
import os
import schemdraw
import schemdraw.elements as elm
from schemdraw import flow

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "paper", "elsevier", "figures")


def leg(d, y, k, shift, x_out):
    """One phase: relay K, SSD, shunt, L, then MOSFET to ground and diode to the bus."""
    d += elm.Line().at((0, y)).right().length(0.6 + shift)
    d += elm.Switch().right().label(f"K$_{k}$", loc="top").label("relay", loc="bottom", fontsize=8)
    d += elm.Switch().right().label(f"SSD$_{k}$", loc="top").label("1 µs", loc="bottom", fontsize=8)
    rs = elm.Resistor().right().label(f"R$_{{sh{k}}}$", loc="top").label("→ AMC1300", loc="bottom", fontsize=8)
    d += rs
    d += elm.Inductor2(loops=3).right().label(f"L$_{k}$ = 1 mH", loc="top")
    sw = d.here
    d += elm.Dot()
    d += elm.Diode().right().label(f"D$_{k}$", loc="top")
    d += elm.Line().right().tox(x_out)
    d += elm.Dot()
    d += elm.Line().at(sw).down().length(0.8)
    q = elm.NFet(bulk=False).anchor("drain").theta(0).reverse().label(f"Q$_{k}$", loc="left", ofst=0.3)
    d += q
    d += elm.Line().at(q.source).down().toy(0)
    return sw


def main():
    os.makedirs(OUT, exist_ok=True)
    schemdraw.config(fontsize=11, font="serif")
    with schemdraw.Drawing(show=False) as d:
        d.config(unit=2.2)
        d += elm.SourceV().at((0, 0)).up().length(4).label("$V_{in}$\n48 V", loc="left")
        d += elm.Line().at((0, 4)).up().length(4)
        x_out = 19.0
        leg(d, 8, 1, 5.5, x_out)       # phase 1 on top, shifted so Q1 drops beside phase 2
        leg(d, 4, 2, 0.0, x_out)
        d += elm.Line().at((x_out, 8)).down().toy(4)
        d += elm.Capacitor().at((x_out, 4)).down().toy(0).label("C$_{out}$", loc="bottom")
        d += elm.Line().at((x_out, 4)).right().length(2.5)
        d += elm.Resistor().down().toy(0).label("R = 200 Ω", loc="bottom")
        d += elm.Line().at((x_out + 2.5, 4)).right().length(0.8)
        d += elm.Dot(open=True).label("V$_{out}$ = 200 V", loc="right")
        d += elm.Line().at((0, 0)).right().tox(x_out + 2.5)
        d += elm.Ground().at((x_out / 2, 0))
        box = flow.Box(w=12, h=1.6).at((x_out / 2 - 6, -1.5)).anchor("NW").label(
            "Controller: 5 MS/s ADC · template + level detectors\nclassify · isolate (gate → SSD → relay) · ACM loops",
            fontsize=9)
        d += box
        d += elm.Line(ls="--", color="gray").at((1.0, -2.3)).tox(x_out / 2 - 6)
        d += elm.Label().at((0.2, -2.3)).label("i$_{L1}$, i$_{L2}$, V$_{out}$", fontsize=8, color="gray")
        d += elm.Line(ls="--", color="gray").at((x_out / 2 + 6, -2.3)).tox(x_out + 2)
        d += elm.Label().at((x_out + 2.4, -2.3)).label("d$_1$, d$_2$, SSD, K", fontsize=8, color="gray")
        d.save(os.path.join(OUT, "fig02_circuit.png"), dpi=300)
        d.save(os.path.join(OUT, "fig02_circuit.pdf"))
    print("wrote fig02_circuit")


if __name__ == "__main__":
    main()
