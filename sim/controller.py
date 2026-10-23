"""Discrete-time controller ('firmware') for the fault-tolerant interleaved boost.

Runs against the KiCad/ngspice power stage through external sources:
  inputs  : ISPk/ISNk (AMC1300 outputs), VFB, VIN       (sampled at FS_ADC)
  outputs : VDUTYk (duty command to PWM_GDRV), VRLYk (relay coil drive)

Implements the brief's FINALIZED detection thresholds and control law, plus
the agreed revisions (see DESIGN_NOTES.md):
  * mode-aware overcurrent limits (3.6 A two-phase / 6.76 A single-phase)
  * input-side relay isolation + gate inhibit
  * off-time template detector: Pearson r >= 0.8 AND slope ratio 0.5..2 over a
    duty-adaptive window; catches open diode, stuck switch and open inductor
  * AMC1300 + 12-bit ADC noise/quantization on the sensed currents
"""
import math
import random
from collections import deque

# --- converter / brief constants -------------------------------------------
FSW = 50e3
T = 1 / FSW
VREF = 200.0
D_NOM = 0.76
I_RMS_HEALTHY = 2.08112          # Table IV per-phase RMS
I_PK_HEALTHY = 2.39127           # Table IV per-phase conduction peak

# --- detection thresholds (brief, FINALIZED) -------------------------------
I_OPEN_TH = 0.10 * I_RMS_HEALTHY         # 0.208 A
T_OPEN = 5 * T                           # 100 us
I_SHORT_TH_2PH = 1.5 * I_PK_HEALTHY      # 3.587 A  (brief: > 3.6 A)
T_SHORT = 3 * T                          # 60 us
DIODE_N = 3                              # consecutive windows (3-5 cycle debounce)
DIODE_R_TH = 0.80                        # Pearson correlation threshold (tuned, see notes)
# Pearson r is blind to slope magnitude, so the template match also checks the off-time
# slope ratio beta = fitted slope / template slope, normalised by the measured (Vout-Vin).
# In CCM the off-time di/dt = -(Vout-Vin)/L regardless of load, so healthy beta ~ 1;
# open diode (avalanche collapse) beta >> 1 or ~0, stuck switch beta < 0, open L beta ~ 0.
SLOPE_LO, SLOPE_HI = 0.5, 2.0

# --- agreed revision: single-phase (degraded) mode limits -------------------
L_PH = 1e-3
DI_PP = 48 * D_NOM / (L_PH * FSW)                         # 0.73 A ripple
I_PK_1PH = 2 * math.sqrt(I_RMS_HEALTHY**2 - DI_PP**2 / 12) + DI_PP / 2   # ~4.51 A
I_SHORT_TH_1PH = 1.5 * I_PK_1PH                           # ~6.76 A
I_LIM_2PH = 3.0     # per-phase avg current-reference clamp, keeps peak < 3.6 A
I_LIM_1PH = 5.0     # single-phase peak ~5.4 A + loop overshoot stays < 6.76 A
SSD_DELAY = 1e-6            # solid-state disconnect turn-off (driver + MOSFET), first to open
BLANK_AFTER_RECONF = 0.0   # was 1 ms with the fixed window; the duty-adaptive window
                           # keeps the survivor at r >= 0.968 during reconfiguration (see notes)

# --- sensing ----------------------------------------------------------------
FS_ADC = 5e6
TS = 1 / FS_ADC
K_ISNS = 8.2 * 0.010             # AMC1300 gain x shunt  [V/A]
K_VFB = (1.99e6 + 10e3) / 10e3   # divider ratio
T_SNS_DELAY = 2.3e-6             # AMC1300 delay + filter lag, compensated in firmware
WIN_LEN = int(round((1 - D_NOM) * T / TS))   # 24 samples = nominal off-time (template length)
WIN_GUARD = 2                    # samples dropped at the end of the off-time (next turn-on corner)
WIN_MIN = 6                      # shorter windows (D > ~0.86) are skipped, not scored

# --- sensor noise (per phase) ----------------------------------------------
# AMC1300: SNR 81 dB typ for a full-scale (+/-250 mV) sine in 10 kHz -> 15.7 uV rms,
# i.e. ~0.157 uV/rtHz; integrated over its ~300 kHz bandwidth -> ~86 uV rms input-referred.
AMC_VN_RMS = 86e-6               # input-referred, band-limited to 300 kHz [V rms]
AMC_BW = 300e3
AMC_GAIN = 8.2
# 12-bit ADC across the AMC1300's +/-2.05 V differential output swing
ADC_BITS = 12
ADC_FS = 2 * AMC_GAIN * 0.25     # 4.1 V span
ADC_LSB = ADC_FS / 2 ** ADC_BITS # 1.0 mV  -> 12.2 mA per LSB
ADC_NOISE_LSB = 1.0              # typical MCU SAR ADC transition noise [LSB rms]

# --- control gains (per update, updates at 50 kHz per loop) -----------------
KP_V, KI_V = 0.25, 0.005
KP_I, KI_I = 0.12, 0.02
D_MAX = 0.90
T_ARM = 30e-3                     # detectors armed after soft-start
# start-up protection (revision 2, option early_arm=True; off by default so the original runs
# are reproduced exactly): overcurrent armed after the 1 ms inrush, open-inductor detector once
# the phase is in continuous conduction, and, until the healthy template has been learned, the
# template detector compares each window with the analytical healthy ramp of Eq. (7).
T_ARM_OC = 1e-3
T_ARM_OL = 10e-3
T_ARM_TMPL = 10e-3
L_NOM = 1e-3
T_LEARN = (40e-3, 45e-3)          # healthy template learning window


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else 0.0


class Phase:
    def __init__(self, k):
        self.k = k
        self.offset = 0.0 if k == 1 else T / 2
        self.active = True
        self.inhibit = False
        self.relay_on = True
        self.relay_open_at = None
        self.ssd_on = True
        self.ssd_open_at = None
        self.duty = 0.0
        self.integ = 0.0
        self.isum = 0.0
        self.icnt = 0
        self.iavg = 0.0
        self.next_start = self.offset
        self.low_t = 0.0
        self.high_t = 0.0
        self.diode_bad = 0
        self.blank_until = 0.0
        self.buf = deque(maxlen=200)          # recent (t, i_sensed)
        self.win_events = deque()             # times at which an off-window completes
        self.tmpl_acc = None
        self.tmpl_n = 0
        self.template = None
        self.tmpl_dv = 152.0
        self.fault = None


class Controller:
    def __init__(self, relay_release_delay=0.0, diode_r_th=DIODE_R_TH, noise_scale=1.0,
                 blank=BLANK_AFTER_RECONF, adaptive_window=True, seed=1, record_raw=True,
                 use_ssd=True, ssd_delay=SSD_DELAY, fault_tolerant=True, early_arm=False):
        self.early_arm = early_arm
        self.ph = [Phase(1), Phase(2)]
        self.use_ssd = use_ssd
        self.ssd_delay = ssd_delay
        # fault_tolerant=False: conventional interleaved boost baseline -- same power stage and
        # control loops, but no fault isolation (detectors only log what they would have done)
        self.fault_tolerant = fault_tolerant
        self.noise_scale = noise_scale
        self.blank = blank
        self.adaptive = adaptive_window
        self.rng = random.Random(seed)
        self._amc_state = [0.0, 0.0]
        self._amc_a = math.exp(-2 * math.pi * AMC_BW * TS)
        self._amc_b = math.sqrt(1 - self._amc_a ** 2)
        self.record_raw = record_raw
        self.raw = []          # 5 MS/s noise-free sensed currents (for offline replay)
        self.periods = []      # (t_start, phase, duty, window_samples, vo, vin)
        self.relay_delay = relay_release_delay
        self.diode_r_th = diode_r_th
        self.n_active = 2
        self.vinteg = 0.0
        self.iref_tot = 0.0
        self.vsum = 0.0
        self.vcnt = 0
        self.vo = 48.0
        self.vin = 48.0
        self.t_next_adc = 0.0
        self.prev = None
        self.events = []
        self.rec = []          # 1 MHz decimated record
        self.scores = []       # (t, k, pearson r, slope ratio beta, n)
        self._dec = 0

    # ---- external source callback ----------------------------------------
    def vsrc(self, name, t):
        if name.startswith("vduty"):
            p = self.ph[int(name[-1]) - 1]
            return -0.05 if p.inhibit else p.duty
        if name.startswith("vssd"):
            return 1.0 if self.ph[int(name[-1]) - 1].ssd_on else 0.0
        if name.startswith("vrly"):
            return 12.0 if self.ph[int(name[-1]) - 1].relay_on else 0.0
        return 0.0

    def vref(self, t):
        return min(VREF, 50.0 + (VREF - 50.0) * max(0.0, t - 1e-3) / 20e-3)

    # ---- per accepted SPICE point: resample to ADC rate ---------------------
    def data(self, d):
        t = d["time"]
        if self.prev is None:
            self.prev = d
        p = self.prev
        tp = p["time"]
        while self.t_next_adc <= t:
            ts = self.t_next_adc
            a = 0.0 if t == tp else (ts - tp) / (t - tp)
            s = {k: p[k] + a * (d[k] - p[k]) for k in d}
            self.sample(ts, s)
            self.t_next_adc += TS
        self.prev = d

    # ---- one ADC sample ----------------------------------------------------
    def adc(self, k, vdiff):
        """AMC1300 noise (band-limited) + ADC transition noise + 12-bit quantization."""
        if self.noise_scale:
            st = self._amc_a * self._amc_state[k] + self._amc_b * self.rng.gauss(0, 1)
            self._amc_state[k] = st
            vdiff += self.noise_scale * (AMC_GAIN * AMC_VN_RMS * st
                                         + ADC_NOISE_LSB * ADC_LSB * self.rng.gauss(0, 1))
        vdiff = min(max(vdiff, -ADC_FS / 2), ADC_FS / 2 - ADC_LSB)
        return round(vdiff / ADC_LSB) * ADC_LSB

    def sample(self, t, s):
        clean = [s["isp1"] - s["isn1"], s["isp2"] - s["isn2"]]
        if self.record_raw:
            self.raw.append((t, clean[0] / K_ISNS, clean[1] / K_ISNS))
        isns = [self.adc(0, clean[0]) / K_ISNS, self.adc(1, clean[1]) / K_ISNS]
        vo = s["vfb"] * K_VFB
        self.vin = s["vin"]
        self.vsum += vo
        self.vcnt += 1

        for p, i in zip(self.ph, isns):
            p.buf.append((t, i))
            p.isum += i
            p.icnt += 1
            if p.ssd_open_at is not None and t >= p.ssd_open_at:
                p.ssd_on = False
                p.ssd_open_at = None
            if p.relay_open_at is not None and t >= p.relay_open_at:
                p.relay_on = False
                p.relay_open_at = None
            if p.active and (t >= T_ARM or (self.early_arm and t >= T_ARM_OC)):
                self.detect_level(p, i, t)
            while p.win_events and p.win_events[0][0] <= t:
                _, n = p.win_events.popleft()
                if p.active:
                    self.detect_shape(p, t, n)

        # period boundaries -> control updates
        for p in self.ph:
            if t >= p.next_start:
                self.period(p, t)
                p.next_start += T

        self._dec += 1
        if self._dec >= 5:
            self._dec = 0
            itrue = [(s["nr1"] - s["ns1"]) / 0.01, (s["nr2"] - s["ns2"]) / 0.01]
            self.rec.append((t, vo, itrue[0], itrue[1], isns[0], isns[1],
                             self.vsrc("vduty1", t), self.vsrc("vduty2", t),
                             s["sw1"], s["sw2"], self.vref(t), self.iref_tot))

    def detect_level(self, p, i, t):
        mode1 = self.n_active == 1
        ith = I_SHORT_TH_1PH if mode1 else I_SHORT_TH_2PH
        p.high_t = p.high_t + TS if i > ith else 0.0
        if p.high_t >= T_SHORT:
            self.trip(p, t, "shorted_switch", f"i={i:.2f} A > {ith:.2f} A for {T_SHORT*1e6:.0f} us")
            return
        if t < p.blank_until:
            p.low_t = 0.0
            return
        ol_armed = t >= T_ARM or (self.early_arm and t >= T_ARM_OL)
        cond = ol_armed and (not p.inhibit) and p.duty > 0.05 and i < I_OPEN_TH
        p.low_t = p.low_t + TS if cond else 0.0
        if p.low_t >= T_OPEN:
            self.trip(p, t, "open_inductor", f"i<{I_OPEN_TH:.3f} A for {T_OPEN*1e6:.0f} us")

    def detect_shape(self, p, t, n):
        win = [i for (tt, i) in p.buf if t - n * TS - 1e-12 < tt <= t + 1e-12][-n:]
        if len(win) < n:
            return
        if T_LEARN[0] <= t < T_LEARN[1] and self.n_active == 2:
            if n != WIN_LEN:
                return
            if p.tmpl_acc is None:
                p.tmpl_acc = [0.0] * WIN_LEN
            p.tmpl_acc = [a + b for a, b in zip(p.tmpl_acc, win)]
            p.tmpl_n += 1
            return
        if p.template is None and p.tmpl_n and t >= T_LEARN[1]:
            p.template = [a / p.tmpl_n for a in p.tmpl_acc]
            p.tmpl_dv = self.vo - self.vin
            self.events.append({"t": t, "phase": p.k, "event": "template_learned",
                                "detail": f"{p.tmpl_n} cycles averaged"})
        if p.template is None:
            if not (self.early_arm and t >= T_ARM_TMPL and not (T_LEARN[0] <= t < T_LEARN[1])):
                return
            # before learning: analytical healthy ramp, slope -(Vout - Vin)/L per sample (Eq. 7)
            s_a = -(self.vo - self.vin) / L_NOM / FS_ADC
            ramp = [s_a * j for j in range(n)]
            r, beta = pearson(win, ramp), (slope(win) / s_a if s_a else 0.0)
        else:
            r, beta = template_match(win, p.template, n, (self.vo - self.vin) / p.tmpl_dv)
        self.scores.append((t, p.k, r, beta, n))
        if t < p.blank_until:
            return
        bad = r < self.diode_r_th or not (SLOPE_LO <= beta <= SLOPE_HI)
        p.diode_bad = p.diode_bad + 1 if bad else 0
        if p.diode_bad >= DIODE_N:
            kind = classify(win, beta)
            self.trip(p, t, kind, f"template r={r:.3f} beta={beta:.2f} outside "
                                  f"(r>={self.diode_r_th}, {SLOPE_LO}<=beta<={SLOPE_HI}) for {DIODE_N} windows")

    def trip(self, p, t, kind, detail):
        if not self.fault_tolerant:
            if p.fault is None:
                p.fault = kind
                self.events.append({"t": t, "phase": p.k, "event": "WOULD_DETECT_" + kind,
                                    "detail": detail + " (baseline: no isolation)"})
            p.low_t = p.high_t = 0.0
            p.diode_bad = 0
            return
        p.fault = kind
        p.active = False
        p.inhibit = True
        p.relay_open_at = t + self.relay_delay
        if self.use_ssd:
            p.ssd_open_at = t + self.ssd_delay
        self.n_active -= 1
        self.events.append({"t": t, "phase": p.k, "event": "FAULT_" + kind, "detail": detail})
        self.events.append({"t": t, "phase": p.k, "event": "gate_inhibit+relay_open_cmd",
                            "detail": f"relay contact opens at {p.relay_open_at*1e3:.4f} ms"
                                      + (f", SSD opens at {p.ssd_open_at*1e3:.4f} ms" if self.use_ssd else "")})
        for q_ in self.ph:
            if q_.active:
                q_.blank_until = t + self.blank
                q_.diode_bad = 0
        if self.n_active == 0:
            self.events.append({"t": t, "phase": 0, "event": "SHUTDOWN",
                                "detail": "no healthy phase left: all gates inhibited, SSDs and relays open"})
            return
        self.events.append({"t": t, "phase": 0, "event": "RECONFIGURED",
                            "detail": f"degraded mode: {self.n_active} active phase(s), "
                                      f"I_trip={I_SHORT_TH_1PH:.2f} A, I_lim={I_LIM_1PH} A"})

    def period(self, p, t):
        p.iavg = p.isum / p.icnt if p.icnt else 0.0
        p.isum, p.icnt = 0.0, 0
        if p.k == 1:                      # outer voltage loop @ 50 kHz
            self.vo = self.vsum / self.vcnt if self.vcnt else self.vo
            self.vsum, self.vcnt = 0.0, 0
            ilim = I_LIM_1PH if self.n_active == 1 else I_LIM_2PH
            imax = ilim * self.n_active
            e = self.vref(t) - self.vo
            self.vinteg = min(self.vinteg, imax)
            u = KP_V * e + self.vinteg + KI_V * e
            if not ((u > imax and e > 0) or (u < 0 and e < 0)):   # anti-windup
                self.vinteg = min(max(self.vinteg + KI_V * e, 0.0), imax)
            self.iref_tot = min(max(KP_V * e + self.vinteg, 0.0), imax)
        if not p.active:
            p.duty = 0.0
            return
        ilim = I_LIM_1PH if self.n_active == 1 else I_LIM_2PH
        iref = min(self.iref_tot / max(self.n_active, 1), ilim)
        e = iref - p.iavg
        dff = 1 - self.vin / max(self.vo, self.vin)
        u = dff + KP_I * e + p.integ + KI_I * e
        if not ((u > D_MAX and e > 0) or (u < 0 and e < 0)):     # anti-windup
            p.integ = min(max(p.integ + KI_I * e, -0.5), 0.5)
        p.duty = min(max(dff + KP_I * e + p.integ, 0.0), D_MAX)
        # off-window (sensor-delay compensated) starts at turn-off; length follows the
        # commanded off-time (1-D)*T, except while learning the full-length template
        learning = T_LEARN[0] <= t < T_LEARN[1]
        n = window_samples(p.duty, self.adaptive, learning)
        self.periods.append((t, p.k, p.duty, n, self.vo, self.vin))
        if n:
            p.win_events.append((t + p.duty * T + T_SNS_DELAY + n * TS, n))


def window_samples(duty, adaptive=True, learning=False):
    """Off-time window length in ADC samples (0 = too short to score)."""
    if learning or not adaptive:
        return WIN_LEN
    n = int(round((1 - duty) * T / TS)) - WIN_GUARD
    return min(n, WIN_LEN + 8) if n >= WIN_MIN else 0


def slope(x):
    n = len(x)
    tm = (n - 1) / 2
    xm = sum(x) / n
    return sum((j - tm) * (v - xm) for j, v in enumerate(x)) / sum((j - tm) ** 2 for j in range(n))


def template_match(win, tmpl, n, dv_ratio):
    """(Pearson r, slope ratio beta) of an n-sample off-time window vs the healthy
    template; beta is normalised by the expected slope change (Vout-Vin)/(Vout-Vin)_learn."""
    t_ = template_for(tmpl, n)
    ts = slope(t_) * max(dv_ratio, 0.2)
    return pearson(win, t_), (slope(win) / ts if ts else 0.0)


def classify(win, beta):
    """Fault type from the window: no current at all -> open inductor; current still
    rising with the gate off -> stuck-on switch; otherwise collapsed ramp -> open diode."""
    if max(win) < I_OPEN_TH:
        return "open_inductor"
    if beta < 0:
        return "shorted_switch"
    return "open_diode"


def template_for(tmpl, n):
    """Healthy off-time template for an n-sample window: the first n samples (same
    turn-off alignment and sensor rounding); linear extrapolation if n is longer."""
    if n <= len(tmpl):
        return tmpl[:n]
    slope = (tmpl[-1] - tmpl[-5]) / 4
    return tmpl + [tmpl[-1] + slope * (j + 1) for j in range(n - len(tmpl))]
