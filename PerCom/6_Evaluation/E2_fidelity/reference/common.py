"""E2 independent reference — shared pieces derived from the written specifications only.

Sources (see READ_LOG.md): RUNTIME_CONTRACT R1–R13, VERIFICATION_CONTRACT (inputs, time/reaction, ACTION
observation), SERVICE_MODEL, FRONTEND_CORRECTNESS §1–§3, PROTOCOL_DRAFT §1.4/§7 (S1–S11, L1).
No code from explorer/, timeline_ir/ or lowering/ is used. Decisions the specifications leave open are listed in
SPEC_GAPS.md and referenced here as G<n>.
"""
from __future__ import annotations

import ast
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DEFAULT_CATALOG = REPO / "files" / "service_list_ver2.0.7.json"

INPUT_GRID_MS = 100          # R2
REACTION_BUDGET = 200_000    # statements at one logical time before L1 "does not finish" error


class RefUnsupported(Exception):
    """REF-UNSUPPORTED: the specifications do not define the construct, or they say it is refused."""

    def __init__(self, category, msg=""):
        super().__init__(f"{category}: {msg}")
        self.category = category
        self.msg = msg


class RefError(Exception):
    """Reference error: invalid history or a reaction that does not finish (L1)."""

    def __init__(self, category, msg=""):
        super().__init__(f"{category}: {msg}")
        self.category = category
        self.msg = msg


# ───────────────────────────── time ─────────────────────────────
UNIT_MS = {"MSEC": 1, "SEC": 1000, "MIN": 60_000, "HOUR": 3_600_000, "DAY": 86_400_000}   # DAY: G15
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def clock_read(member_lower, t_abs_ms):
    """S11: t=0 is Monday 00:00:00, no DST."""
    if member_lower == "hour":
        return (t_abs_ms // 3_600_000) % 24
    if member_lower == "minute":
        return (t_abs_ms // 60_000) % 60
    if member_lower == "weekday":
        return WEEKDAYS[(t_abs_ms // 86_400_000) % 7]
    if member_lower == "timestamp":
        return t_abs_ms // 1000
    raise RefUnsupported("clock-member", f"Clock.{member_lower} is not defined by S11")


def next_clock_boundary(now_ms, t_start_ms):
    """Clock values (Hour/Minute/Weekday/Timestamp) only change at absolute multiples of 1000 ms."""
    t_abs = t_start_ms + now_ms
    return (t_abs // 1000 + 1) * 1000 - t_start_ms


# ───────────────────────────── values ─────────────────────────────
def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def vclass(v):
    if v is None:
        return "none"
    if isinstance(v, bool):
        return "bool"
    if is_num(v):
        return "num"
    if isinstance(v, str):
        return "str"
    return "other"


def cmp_values(op, a, b):
    """Comparison. BOOL is its own type (R10); None equals only None (G3)."""
    ca, cb = vclass(a), vclass(b)
    if op in ("==", "!="):
        if ca == "none" or cb == "none":
            r = ca == cb
        elif ca == cb and ca in ("bool", "num", "str"):
            r = a == b
        else:
            raise RefUnsupported("mixed-type-compare", f"{a!r} {op} {b!r}")
        return r if op == "==" else not r
    if op not in ("<", ">", "<=", ">="):
        raise RefUnsupported("operator", op)
    if ca == "none" or cb == "none":
        return False            # author decision 2026-09-14: ordered comparison with a missing value is false (G3)
    if (ca == cb == "num") or (ca == cb == "str"):
        return {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]
    raise RefUnsupported("ordered-compare-type", f"{a!r} {op} {b!r}")


def to_text(v):
    """S8 number formatting; None -> '' (VERIFICATION_CONTRACT symbolic note, G5); BOOL undefined (G5)."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        raise RefUnsupported("text-conversion", "BOOL to text is not specified")
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if not math.isfinite(v):
            raise RefUnsupported("text-conversion", repr(v))
        r = repr(v)
        if "e" in r or "E" in r:
            raise RefUnsupported("text-conversion", f"no decimal form for {r}")
        return r
    raise RefUnsupported("text-conversion", repr(v))


def arith(op, a, b, null_zero=False):
    """+ - * / %. '+' with a STRING operand is concatenation (S8). '/' is real division (S7).
    null_zero: HANDOFF 'null 산술은 0 으로 강제' (IR only, G4)."""
    if op == "+" and (isinstance(a, str) or isinstance(b, str)):
        return to_text(a) + to_text(b)
    if null_zero:
        a = 0 if a is None else a
        b = 0 if b is None else b
    if not (is_num(a) and is_num(b)):
        raise RefUnsupported("arith-type", f"{a!r} {op} {b!r}")
    if op == "+":
        r = a + b
    elif op == "-":
        r = a - b
    elif op == "*":
        r = a * b
    elif op == "/":
        if b == 0:
            raise RefUnsupported("division-by-zero", f"{a!r} / {b!r}")
        r = a / b
    elif op == "%":
        if isinstance(a, int) and isinstance(b, int) and a >= 0 and b > 0:
            r = a % b
        else:
            raise RefUnsupported("modulo-domain", f"{a!r} % {b!r}")
    else:
        raise RefUnsupported("operator", op)
    if isinstance(r, float) and not math.isfinite(r):
        raise RefUnsupported("non-finite", f"{a!r} {op} {b!r}")
    return r


def val_eq(a, b, eps=0.0):
    """ACTION observation equality: 1 == 1.0, true != 1, "1" != "1.0"."""
    ca, cb = vclass(a), vclass(b)
    if ca != cb:
        return False
    if ca == "num":
        return a == b if eps == 0.0 else abs(a - b) <= eps
    return a == b


# ───────────────────────────── catalog ─────────────────────────────
READ_ROLE = {("weatherprovider", "forecast"), ("weatherprovider", "getweatherinfo"),
             ("armrobotdetail", "getmotion"), ("armrobotdetail", "listmotions"),
             ("menuprovider", "getmenu"), ("newsprovider", "getnewsdigest"),
             ("cloudserviceprovider", "isavailable")}          # SERVICE_MODEL §2


class Member:
    def __init__(self, service, mid, kind, vtype=None, fmt=None, bound=None, args=None, ret="VOID"):
        self.service, self.id, self.kind = service, mid, kind
        self.type, self.format, self.bound = vtype, fmt, bound
        self.args = args or []
        self.ret = ret

    @property
    def read_role(self):
        return self.kind == "function" and (self.service.lower(), self.id.lower()) in READ_ROLE

    @property
    def result_type(self):
        return self.type if self.kind == "value" else self.ret

    def __repr__(self):
        return f"{self.service}.{self.id}"


class Catalog:
    def __init__(self, path=None):
        self.path = str(path or DEFAULT_CATALOG)
        data = json.loads(Path(self.path).read_text(encoding="utf-8"))
        self.services = {}      # lower id -> {"id", "members": {lower: Member}, "conflicts": set, "enums": {}}
        self.enums = {}
        for s in data["skills"]:
            enums = {e["id"]: [m["value"] for m in e.get("members", [])] for e in (s.get("enums") or [])}
            self.enums.update({k: v for k, v in enums.items() if k not in self.enums})
            entry = {"id": s["id"], "members": {}, "conflicts": set(), "enums": enums}
            for v in s.get("values") or []:
                self._add(entry, Member(s["id"], v["id"], "value", v.get("type"), v.get("format"), v.get("bound")))
            for f in s.get("functions") or []:
                ret = f.get("return_type", "VOID")
                ret = ret if isinstance(ret, str) else ret.get("type", "VOID")
                args = [dict(id=a["id"], type=a.get("type"), format=a.get("format"), bound=a.get("bound"))
                        for a in (f.get("arguments") or [])]
                self._add(entry, Member(s["id"], f["id"], "function", args=args, ret=ret))
            self.services[s["id"].lower()] = entry

    @staticmethod
    def _add(entry, m):
        key = m.id.lower()
        if key in entry["members"]:
            entry["conflicts"].add(key)
        entry["members"][key] = m

    def service(self, name):
        return self.services.get(str(name).lower())

    def member(self, service_name, member_name):
        svc = self.service(service_name)
        if svc is None:
            return None
        key = str(member_name).lower()
        if key in svc["conflicts"]:
            raise RefUnsupported("catalog-alias-conflict", f"{svc['id']}.{member_name}")
        return svc["members"].get(key)

    def enum_values(self, service_name, fmt):
        svc = self.service(service_name)
        if svc and fmt in svc["enums"]:
            return svc["enums"][fmt]
        return self.enums.get(fmt)


def device_has_category(devices, device_id, service_id):
    info = devices.get(device_id)
    if info is None:
        return False
    return any(str(c).lower() == service_id.lower() for c in (info.get("category") or []))


def resolve_device_member(catalog, devices, device_id, name):
    """SERVICE_MODEL §1: case-insensitive name, optional service prefix `service_member`; the device must declare the
    capability as a category. Ambiguity between categories is refused."""
    if device_id not in devices:
        raise RefUnsupported("device-not-in-inventory", device_id)
    cats = [str(c) for c in (devices[device_id].get("category") or [])]
    if "_" in name:
        pre, rest = name.split("_", 1)
        svc = catalog.service(pre)
        if svc is not None:
            m = catalog.member(pre, rest)
            if m is not None:
                if not device_has_category(devices, device_id, svc["id"]):
                    raise RefUnsupported("capability", f"{device_id} lacks category {svc['id']} for {name}")
                return m
    found = []
    for c in cats:
        m = catalog.member(c, name)
        if m is not None and all(m is not f for f in found):
            found.append(m)
    if not found:
        raise RefUnsupported("unknown-member", f"{name} on {device_id} {cats}")
    if len(found) > 1:
        raise RefUnsupported("ambiguous-member", f"{name} on {device_id}: {found}")
    return found[0]


def check_typed(catalog, service_id, spec_type, fmt, bound, value, what):
    """SERVICE_MODEL §1 argument type/range/ENUM checks; violations are refused (G21)."""
    t = (spec_type or "").upper()
    if t in ("BOOL", "BOOLEAN"):
        ok = isinstance(value, bool)
    elif t == "INTEGER":
        ok = isinstance(value, int) and not isinstance(value, bool)
    elif t == "DOUBLE":
        ok = is_num(value)
    elif t == "STRING":
        ok = isinstance(value, str)
    elif t == "ENUM":
        ok = isinstance(value, str)
        members = catalog.enum_values(service_id, fmt) if fmt else None
        if ok and members is not None and value not in members:
            raise RefUnsupported("arg-domain", f"{what}: {value!r} not in {fmt}")
    else:
        raise RefUnsupported("arg-type-unsupported", f"{what}: type {spec_type}")
    if not ok:
        raise RefUnsupported("arg-type", f"{what}: {value!r} is not {spec_type}")
    if bound and is_num(value):
        lo, hi = bound[0], bound[1]
        if not (lo <= value <= hi):
            raise RefUnsupported("arg-range", f"{what}: {value!r} outside {bound}")


# ───────────────────────────── inputs ─────────────────────────────
_KEY_RE = re.compile(r"^([^.()\s]+)\.([A-Za-z_][A-Za-z0-9_]*)(?:\((.*)\))?$")


def typed_key(v):
    if isinstance(v, bool):
        return ("bool", v)
    if isinstance(v, int):
        return ("int", v)
    if isinstance(v, float):
        return ("float", v)
    if isinstance(v, str):
        return ("str", v)
    if v is None:
        return ("none", None)
    raise RefUnsupported("query-arg-type", repr(v))


def parse_input_key(key):
    m = _KEY_RE.match(key.strip())
    if not m:
        raise RefError("history-key", f"cannot parse input key {key!r}")
    dev, member, inner = m.group(1), m.group(2), m.group(3)
    args = ()
    if inner is not None and inner.strip():
        try:
            args = ast.literal_eval("(" + inner + ",)")
        except Exception as exc:
            raise RefError("history-key", f"{key!r}: {exc}")
    return (dev, member.lower(), tuple(typed_key(a) for a in args))


class Inputs:
    """R2: one joint snapshot per 100 ms grid point, held in between. `events` = [(t_rel_ms, {key: value})];
    the first entry is at t=0. Keys: "Device.Member" or "Device.Member(<literal args>)" for queries (FRONTEND §1)."""

    def __init__(self, events, catalog, devices):
        self.catalog, self.devices = catalog, devices
        evs = sorted(((int(t), u) for t, u in events), key=lambda e: e[0])
        if not evs or evs[0][0] != 0:
            raise RefError("history", "first event must be at t=0")
        self.changes = []
        for t, upd in evs:
            if t % INPUT_GRID_MS:
                raise RefError("history-grid", f"input change at {t} ms is off the 100 ms grid")
            self.changes.append((t, {parse_input_key(k): v for k, v in (upd or {}).items()}))
        self.state = {}
        self.idx = 0

    def advance_to(self, t):
        while self.idx < len(self.changes) and self.changes[self.idx][0] <= t:
            self.state.update(self.changes[self.idx][1])
            self.idx += 1

    def next_change_after(self, t):
        for tc, _ in self.changes[self.idx:]:
            if tc > t:
                return tc
        return None

    def read(self, device_id, member, args=()):
        # concrete input member collision on one device is refused (SERVICE_MODEL §1, G31)
        info = self.devices.get(device_id) or {}
        owners = [c for c in (info.get("category") or []) if self.catalog.member(c, member.id) is not None]
        if len({o.lower() for o in owners}) > 1:
            raise RefUnsupported("input-member-collision", f"{device_id}.{member.id} in {owners}")
        key = (device_id, member.id.lower(), tuple(typed_key(a) for a in args))
        is_bool = (member.result_type or "").upper() in ("BOOL", "BOOLEAN")
        non_null = (member.service.lower(), member.id.lower()) == ("menuprovider", "getmenu")   # VERIFICATION_CONTRACT
        if key not in self.state or (non_null and self.state[key] is None):
            if is_bool:
                raise RefError("history-missing-bool", f"{device_id}.{member.id}{args or ''} has no value (R10)")
            if non_null:
                raise RefError("history-missing-nonnull", f"{device_id}.GetMenu{args} must be a STRING")
            return None
        v = self.state[key]
        if is_bool and not isinstance(v, bool):
            raise RefError("history-bool-invalid", f"{device_id}.{member.id} = {v!r} (R10)")
        return v

    def read_holiday(self):
        for key in (("Clock", "isholiday", ()), ("clock", "isholiday", ())):
            if key in self.state:
                v = self.state[key]
                if not isinstance(v, bool):
                    raise RefError("history-bool-invalid", f"Clock.IsHoliday = {v!r}")
                return v
        raise RefError("history-missing-bool", "Clock.IsHoliday has no value (R10)")


# ───────────────────────────── scheduling ─────────────────────────────
class Delay:
    __slots__ = ("until",)

    def __init__(self, until):
        self.until = until


class Wait:
    """obj.poll(now) -> None (keep blocking) | result; obj.deadline() -> int|None; obj.clock_sensitive: bool"""
    __slots__ = ("obj",)

    def __init__(self, obj):
        self.obj = obj


class Runtime:
    def __init__(self, catalog, devices, inputs, t_start_ms, horizon_ms, faults=None):
        self.catalog, self.devices, self.inputs = catalog, devices, inputs
        self.t_start, self.horizon = int(t_start_ms), int(horizon_ms)
        self.faults = list(faults or [])
        self.now = 0
        self.steps_now = 0
        self.raw = []          # (t, service, method, args, device)
        self.groups = []       # (t, [sig...], fanout)
        self.kill_at = None

    def tick(self):
        self.steps_now += 1
        if self.steps_now > REACTION_BUDGET:
            raise RefError("reaction-does-not-finish", f"more than {REACTION_BUDGET} statements at t={self.now} ms (L1)")

    def clock(self, member_lower):
        if member_lower == "isholiday":
            return self.inputs.read_holiday()
        return clock_read(member_lower, self.t_start + self.now)

    def emit(self, service, method, args, device_ids, fanout):
        sigs = []
        for d in device_ids:
            self.raw.append((self.now, service, method, list(args), d))
            sigs.append({"service": service, "method": method, "args": list(args), "device": d})
            for f in self.faults:     # E1 rule T7 (G25)
                if (self.kill_at is None and f["service"].lower() == service.lower()
                        and f["method"].lower() == method.lower() and f["device"] == d):
                    self.kill_at = self.now + int(f["after_ms"])
        self.groups.append((self.now, sigs, bool(fanout)))


def _advance(gen, value=None):
    try:
        return gen.send(value)
    except StopIteration:
        return None


def run_program(rt, gen):
    """Reaction loop: at each instant apply the input snapshot first (R6), then resume the blocked program.
    Wake-up instants: delay expiry, input changes, internal wait deadlines, clock boundaries for clock-reading waits."""
    rt.now = 0
    rt.inputs.advance_to(0)
    req = _advance(gen)
    while req is not None:
        if isinstance(req, Delay):
            nt = req.until
        elif isinstance(req, Wait):
            cands = [rt.inputs.next_change_after(rt.now), req.obj.deadline()]
            if req.obj.clock_sensitive:
                cands.append(next_clock_boundary(rt.now, rt.t_start))
            cands = [c for c in cands if c is not None and c > rt.now]
            nt = min(cands) if cands else None
        else:
            raise RefError("internal", f"bad request {req!r}")
        if nt is None or nt > rt.horizon:
            break
        if rt.kill_at is not None and nt >= rt.kill_at:
            break
        rt.now = nt
        rt.steps_now = 0
        rt.inputs.advance_to(nt)
        if isinstance(req, Delay):
            req = _advance(gen)
        else:
            r = req.obj.poll(nt)
            if r is not None:
                req = _advance(gen, r)


# ───────────────────────────── observation ─────────────────────────────
def normal_form(groups):
    """VERIFICATION_CONTRACT 'ACTION 관찰': per time, call groups in execution order; inside a fan-out group the
    per-device signature sequences are concatenated in device-ID order (stable, so one device keeps its order)."""
    out = []
    for t, sigs, fanout in groups:
        g = sorted(sigs, key=lambda s: str(s["device"])) if fanout else list(sigs)
        if out and out[-1]["t"] == t:
            out[-1]["groups"].append(g)
        else:
            out.append({"t": t, "groups": [g]})
    return out


def sig_eq(x, y, eps=0.0):
    return (x["service"] == y["service"] and x["method"] == y["method"] and x["device"] == y["device"]
            and len(x["args"]) == len(y["args"])
            and all(val_eq(a, b, eps) for a, b in zip(x["args"], y["args"])))


def compare(trace_a, trace_b, device_sets=None):
    """Exact equality of two normalised traces (times and call-group structure, typed argument equality).
    With `device_sets` (author decision B2, 2026-09-14) both traces are first put in the B2 normal form; traces that
    are already in B2 form (entries with "units") are used as they are."""
    if device_sets is not None or _is_b2(trace_a) or _is_b2(trace_b):
        return compare_b2(trace_a, trace_b, device_sets)
    n = max(len(trace_a), len(trace_b))
    for i in range(n):
        if i >= len(trace_a) or i >= len(trace_b):
            return False, {"index": i, "a": trace_a[i] if i < len(trace_a) else None,
                           "b": trace_b[i] if i < len(trace_b) else None, "reason": "length"}
        ea, eb = trace_a[i], trace_b[i]
        if ea["t"] != eb["t"]:
            return False, {"index": i, "a": ea, "b": eb, "reason": "time"}
        if len(ea["groups"]) != len(eb["groups"]):
            return False, {"index": i, "a": ea, "b": eb, "reason": "group count"}
        for ga, gb in zip(ea["groups"], eb["groups"]):
            if len(ga) != len(gb) or not all(sig_eq(x, y) for x, y in zip(ga, gb)):
                return False, {"index": i, "a": ea, "b": eb, "reason": "signature"}
    return True, None


# ───────────────────── binding decision B0–B2 (whisoo, 2026-09-14) ─────────────────────
# BINDING_DECISION_2026-09-14.md. B0: a slot is one IR binding entry (`Service` or `Service#k` -> device list or
# {"any"/"all": [...]}); its device set is the device list without the quantifier.

def parse_binding_slots(binding):
    """-> [{"service": lower service, "slot": key, "quantifier": None|"any"|"all", "devices": [ids]}] in key order.
    Entries whose shape is not a list / {"any"|"all": list} are skipped here (run_ir refuses them, G9)."""
    out = []
    for key, val in (binding or {}).items():
        m = re.fullmatch(r"(.+?)(?:#([0-9]+))?", str(key))
        svc = m.group(1).lower()
        if isinstance(val, list):
            q, devs = None, val
        elif isinstance(val, dict) and len(val) == 1 and next(iter(val)) in ("any", "all") \
                and isinstance(next(iter(val.values())), list):
            q = next(iter(val))
            devs = val[q]
        else:
            continue
        out.append({"service": svc, "slot": str(key), "k": int(m.group(2) or 1), "quantifier": q,
                    "devices": [str(d) for d in devs]})
    out.sort(key=lambda x: x["k"])      # stable: per service, slot #1, #2, ... regardless of JSON key order (G8)
    return out


class DeviceSets:
    """Device sets of the IR binding slots (plus explicit `Svc[d,...]` sites of the IR, one set per site)."""

    def __init__(self, slots):
        self.slots = list(slots)

    def services(self):
        return {s["service"] for s in self.slots}

    def distinct(self, service_lower):
        """-> [(devices in first-appearance order, {quantifiers of the slots with this set})]. Index order (B5):
        binding slots of the service by slot number (`S` = #1, `S#2`, ...), then explicit `S[d,...]` IR sites in IR
        compile-walk order; a set equal to an earlier one is not repeated."""
        out, seen = [], {}
        for s in self.slots:
            if s["service"] != service_lower:
                continue
            fs = frozenset(s["devices"])
            if fs not in seen:
                seen[fs] = len(out)
                out.append((list(dict.fromkeys(s["devices"])), set()))
            out[seen[fs]][1].add(s["quantifier"])
        return out

    def large(self):
        """(service lower, frozenset) for every set with |D| >= 2 (B2)."""
        return list(dict.fromkeys((s["service"], frozenset(s["devices"])) for s in self.slots
                                  if len(set(s["devices"])) >= 2))


def _as_sets(device_sets):
    if device_sets is None or isinstance(device_sets, DeviceSets):
        return device_sets
    return DeviceSets(device_sets)


def _is_b2(trace):
    return bool(trace) and "units" in trace[0]


def _same_call(x, y):
    return (x["service"] == y["service"] and x["method"] == y["method"] and len(x["args"]) == len(y["args"])
            and all(val_eq(a, b) for a, b in zip(x["args"], y["args"])))


def b2_normal_form(trace, device_sets):
    """B2: inside one instant, a maximal run of consecutive calls with equal (service, method, typed args) whose
    target devices all lie in one device set D of that service with |D| >= 2 becomes one unit
    {"kind": "set", ..., "devices": the unique containing set, else the called ids}, repeated k times (k = most calls
    on one device in the run; revised 2026-09-14). Every other call stays in its original call group
    ({"kind": "group", "sigs": [...]}, split only where a set unit was taken out). Times and unit order are kept."""
    if _is_b2(trace):
        return trace
    large = _as_sets(device_sets).large() if device_sets is not None else []
    out = []
    for entry in trace:
        items = [(gi, s) for gi, g in enumerate(entry["groups"]) for s in g]
        units, i, open_group = [], 0, None
        while i < len(items):
            gi, s = items[i]
            alive = [D for svc, D in large if svc == str(s["service"]).lower() and s["device"] in D]
            if alive:
                devs, j = {s["device"]}, i + 1
                calls = {s["device"]: 1}
                while j < len(items):
                    s2 = items[j][1]
                    if not _same_call(s, s2):
                        break
                    nd = devs | {s2["device"]}
                    nxt = [D for D in alive if nd <= D]
                    if not nxt:
                        break
                    devs, alive, j = nd, nxt, j + 1
                    calls[s2["device"]] = calls.get(s2["device"], 0) + 1
                # B2 (revised 2026-09-14): target = the one binding set (|D| >= 2) holding every called device, else
                # the called devices; the unit is observed k times, k = most calls received by one device in the run
                target = alive[0] if len(alive) == 1 else devs
                unit = {"kind": "set", "service": s["service"], "method": s["method"], "args": list(s["args"]),
                        "devices": sorted(target, key=str)}
                units.extend(dict(unit) for _ in range(max(calls.values())))
                open_group = None
                i = j
                continue
            if open_group is not None and open_group[0] == gi:
                open_group[1]["sigs"].append(s)
            else:
                u = {"kind": "group", "sigs": [s]}
                units.append(u)
                open_group = (gi, u)
            i += 1
        out.append({"t": entry["t"], "units": units})
    return out


def _unit_eq(x, y):
    if x["kind"] != y["kind"]:
        return False
    if x["kind"] == "set":
        return _same_call(x, y) and set(x["devices"]) == set(y["devices"])
    return len(x["sigs"]) == len(y["sigs"]) and all(sig_eq(a, b) for a, b in zip(x["sigs"], y["sigs"]))


def compare_b2(trace_a, trace_b, device_sets):
    if device_sets is None and any(t and not _is_b2(t) for t in (trace_a, trace_b)):
        raise ValueError("compare: one trace is in B2 form and the other is not; pass device_sets")
    a = b2_normal_form(trace_a, device_sets)
    b = b2_normal_form(trace_b, device_sets)
    n = max(len(a), len(b))
    for i in range(n):
        if i >= len(a) or i >= len(b):
            return False, {"index": i, "a": a[i] if i < len(a) else None, "b": b[i] if i < len(b) else None,
                           "reason": "length"}
        ea, eb = a[i], b[i]
        if ea["t"] != eb["t"]:
            return False, {"index": i, "a": ea, "b": eb, "reason": "time"}
        if len(ea["units"]) != len(eb["units"]):
            return False, {"index": i, "a": ea, "b": eb, "reason": "unit count"}
        for ua, ub in zip(ea["units"], eb["units"]):
            if not _unit_eq(ua, ub):
                return False, {"index": i, "a": ea, "b": eb, "reason": "unit"}
    return True, None
