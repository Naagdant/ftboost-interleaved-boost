"""Tiny S-expression reader/writer for KiCad symbol libraries and schematics."""
import math
import re

_TOK = re.compile(r'\s*(\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+)')


def parse(text):
    stack, cur = [], []
    pos = 0
    while True:
        m = _TOK.match(text, pos)
        if not m:
            break
        tok = m.group(1)
        pos = m.end()
        if tok == "(":
            stack.append(cur)
            cur = []
        elif tok == ")":
            done = cur
            cur = stack.pop()
            cur.append(done)
        else:
            cur.append(tok)
    return cur[0] if len(cur) == 1 else cur


def dump(node, indent=0):
    if not isinstance(node, list):
        return node
    simple = all(not isinstance(x, list) for x in node)
    if simple:
        return "(" + " ".join(node) + ")"
    pad = "\t" * (indent + 1)
    parts = []
    head = []
    for x in node:
        if isinstance(x, list):
            break
        head.append(x)
    rest = node[len(head):]
    out = "(" + " ".join(head)
    for x in rest:
        out += "\n" + pad + (dump(x, indent + 1) if isinstance(x, list) else x)
    return out + "\n" + "\t" * indent + ")"


def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def unq(s):
    if s.startswith('"'):
        return s[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return s


def find(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def first(node, key):
    r = find(node, key)
    return r[0] if r else None


class SymbolLib:
    """Loads a .kicad_sym and returns flattened (extends-resolved) symbol nodes."""

    def __init__(self, path, nickname):
        self.nick = nickname
        root = parse(open(path, encoding="utf-8").read())
        self.syms = {unq(s[1]): s for s in find(root, "symbol")}

    def get(self, name):
        s = self.syms[name]
        ext = first(s, "extends")
        if ext:
            parent = self.get(unq(ext[1]))
            # child overrides properties; geometry comes from parent
            child_props = {unq(p[1]): p for p in find(s, "property")}
            node = ["symbol", q(f"{self.nick}:{name}")]
            for x in parent[2:]:
                if isinstance(x, list) and x[0] == "property" and unq(x[1]) in child_props:
                    node.append(child_props.pop(unq(x[1])))
                elif isinstance(x, list) and x[0] == "symbol":
                    sub = list(x)
                    sub[1] = q(unq(x[1]).replace(unq(parent[1]).split(":")[-1], name, 1))
                    node.append(sub)
                else:
                    node.append(x)
            node.extend(child_props.values())
            return node
        node = list(s)
        node[1] = q(f"{self.nick}:{name}")
        return node

    def pins(self, name):
        """{pin_number: (x, y, angle)} in library coordinates (y up)."""
        out = {}

        def walk(n):
            for x in n:
                if isinstance(x, list):
                    if x[0] == "pin":
                        at = first(x, "at")
                        num = unq(first(x, "number")[1])
                        out[num] = (float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0)
                    else:
                        walk(x)

        walk(self.get(name))
        return out


def pin_abs(sym_xy, rot, pin):
    """Schematic coords of a pin endpoint and its outward unit vector.
    KiCad schematic y axis points down; symbol rotation is CCW in library frame."""
    px, py, pa = pin
    r = math.radians(rot)
    # rotate in library frame (y up)
    rx = px * math.cos(r) - py * math.sin(r)
    ry = px * math.sin(r) + py * math.cos(r)
    a = math.radians(pa + rot)
    # pin angle points from the endpoint toward the body; outward is opposite
    ox, oy = -math.cos(a), -math.sin(a)
    return (sym_xy[0] + rx, sym_xy[1] - ry), (round(ox), -round(oy))
