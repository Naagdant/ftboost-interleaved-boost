"""Minimal ctypes wrapper around KiCad's bundled libngspice (shared-library API).

Lets a Python 'firmware' controller drive SPICE `external` voltage sources
(GetVSRCData callback) and observe circuit nodes at every accepted time point
(SendData callback) — i.e. a co-simulation of digital controller + power stage.
"""
import ctypes as C
import os

LIB_CANDIDATES = [
    "/usr/lib/x86_64-linux-gnu/libngspice.so.0",
    "/Applications/KiCad/KiCad.app/Contents/PlugIns/sim/libngspice.0.dylib",
    "/Applications/KiCad/KiCad.app/Contents/Frameworks/libngspice.0.dylib",
]


class vecvalues(C.Structure):
    _fields_ = [("name", C.c_char_p), ("creal", C.c_double), ("cimag", C.c_double),
                ("is_scale", C.c_bool), ("is_complex", C.c_bool)]


class vecvaluesall(C.Structure):
    _fields_ = [("veccount", C.c_int), ("vecindex", C.c_int),
                ("vecsa", C.POINTER(C.POINTER(vecvalues)))]


SendChar = C.CFUNCTYPE(C.c_int, C.c_char_p, C.c_int, C.c_void_p)
SendStat = C.CFUNCTYPE(C.c_int, C.c_char_p, C.c_int, C.c_void_p)
ControlledExit = C.CFUNCTYPE(C.c_int, C.c_int, C.c_bool, C.c_bool, C.c_int, C.c_void_p)
SendData = C.CFUNCTYPE(C.c_int, C.POINTER(vecvaluesall), C.c_int, C.c_int, C.c_void_p)
SendInitData = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_int, C.c_void_p)
BGThreadRunning = C.CFUNCTYPE(C.c_int, C.c_bool, C.c_int, C.c_void_p)
GetVSRCData = C.CFUNCTYPE(C.c_int, C.POINTER(C.c_double), C.c_double, C.c_char_p, C.c_int, C.c_void_p)
GetISRCData = C.CFUNCTYPE(C.c_int, C.POINTER(C.c_double), C.c_double, C.c_char_p, C.c_int, C.c_void_p)
GetSyncData = C.CFUNCTYPE(C.c_int, C.c_double, C.POINTER(C.c_double), C.c_double, C.c_int, C.c_int, C.c_int, C.c_void_p)


class NgSpice:
    """on_data(dict name->value) is called per accepted point;
    on_vsrc(name, time) -> float supplies external source values."""

    def __init__(self, on_data=None, on_vsrc=None, verbose=False):
        lib = next(p for p in LIB_CANDIDATES if os.path.exists(p))
        # code models (XSPICE) live next to the plugin
        os.environ.setdefault("SPICE_LIB_DIR", "/usr/lib/x86_64-linux-gnu/ngspice" if lib.endswith(".so.0") else os.path.join(os.path.dirname(lib), "ngspice"))
        self.lib = C.CDLL(lib)
        self.on_data, self.on_vsrc, self.verbose = on_data, on_vsrc, verbose
        self.log = []
        self._names = None

        def _char(s, i, u):
            line = s.decode(errors="replace")
            self.log.append(line)
            if verbose:
                print(line)
            return 0

        def _data(p, n, i, u):
            if self.on_data is None:
                return 0
            va = p.contents
            if self._names is None:
                self._names = [va.vecsa[k].contents.name.decode().lower() for k in range(va.veccount)]
            self.on_data({self._names[k]: va.vecsa[k].contents.creal for k in range(va.veccount)})
            return 0

        def _vsrc(vp, t, name, i, u):
            vp[0] = self.on_vsrc(name.decode().lower(), t) if self.on_vsrc else 0.0
            return 0

        self._cbs = [SendChar(_char), SendStat(lambda s, i, u: 0),
                     ControlledExit(lambda *a: 0), SendData(_data),
                     SendInitData(lambda *a: 0), BGThreadRunning(lambda *a: 0),
                     GetVSRCData(_vsrc), GetISRCData(lambda *a: 0)]
        self.lib.ngSpice_Init(self._cbs[0], self._cbs[1], self._cbs[2], self._cbs[3],
                              self._cbs[4], self._cbs[5], None)
        ident = C.c_int(0)
        self.lib.ngSpice_Init_Sync(self._cbs[6], self._cbs[7], None, C.byref(ident), None)

    def cmd(self, s):
        return self.lib.ngSpice_Command(s.encode())

    def load(self, netlist_text):
        lines = [l for l in netlist_text.splitlines()]
        arr = (C.c_char_p * (len(lines) + 1))(*[l.encode() for l in lines], None)
        self._names = None
        return self.lib.ngSpice_Circ(arr)
