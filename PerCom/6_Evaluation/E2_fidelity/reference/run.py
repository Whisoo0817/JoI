"""E2 independent reference — public API.

run_ir(ir, binding, devices, events, horizon_ms, catalog_path=None, t_start_ms=0, cron="", faults=None,
       binding_decision=False)
run_joi(block, devices, events, horizon_ms, catalog_path=None, t_start_ms=0, faults=None, binding=<not given>, ir=None,
        selector_assignment=None)
selector_space(block, devices, binding, ir, catalog_path=None) -> {"domains": [n_i], "tag_choice": [c_i]}
compare(trace_a, trace_b, device_sets=None) -> (equal, first_difference)
device_sets(ir, binding, catalog_path=None) -> [slot dicts]

Each run returns {"status": "ok"|"unsupported"|"error", "trace": normalised trace, "raw_actions": [...],
"detail": str, "category": str}. `faults` (E1 rule T7) is an optional extra keyword.
On "unsupported"/"error" the trace holds the ACTIONs issued before the stop (diagnostic only).

Binding decision of 2026-09-14 (BINDING_DECISION_2026-09-14.md, SPEC_GAPS B1/B2), opt-in so that runs without the new
keywords are unchanged:
- run_joi(..., binding=<pair binding, may be None>, ir=<pair IR>): selectors follow B1 over the device sets of the
  binding plus the explicit `Svc[d,...]` sites of the IR.
- run_ir(..., binding_decision=True): same device sets.
With either, "trace" is the B2 normal form (entries {"t", "units"}); the previous normal form is kept as
"trace_groups" and the sets as "device_sets". compare() of two B2 traces applies B2; compare(a, b, device_sets=...)
turns previous-form traces into B2 form first.

B5 (same date): selector_space lists the assignable JoI selector occurrences (service with >= 2 distinct device sets),
one per source occurrence, in source order (statements in order; if: cond, then, else; loop: cond, body; action
selector before its arguments; comparison left before right). n_i = number of distinct device sets of that service,
indexed: binding slots by slot number (#1, #2, ...), then explicit IR `Svc[d,...]` sites in IR walk order, repeats
dropped. c_i = B1.2 tag-rule index (0 when B1.2 falls back to M or is unsupported). run_joi(...,
selector_assignment=[a_1..a_k]) makes occurrence i use set a_i; None keeps B1.2. On a JoI that cannot be parsed or
prepared, selector_space returns empty lists plus "status": "unsupported"|"error" and "detail".
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import common                                   # noqa: E402
from common import (Catalog, DeviceSets, Inputs, RefError, RefUnsupported, Runtime, b2_normal_form,  # noqa: E402
                    normal_form, parse_binding_slots, run_program)

_CATALOGS = {}
_NOT_GIVEN = object()


def _catalog(path):
    key = str(path or common.DEFAULT_CATALOG)
    if key not in _CATALOGS:
        _CATALOGS[key] = Catalog(key)
    return _CATALOGS[key]


def device_sets(ir, binding, catalog_path=None):
    """B0: one device set per binding slot, plus one per explicit `Svc[d,...]` site of the IR (pairs whose binding
    is None use that form; each explicit site is its own set)."""
    from ir_ref import IrProgram
    slots = parse_binding_slots(binding)
    if ir is not None:
        for svc, devs in IrProgram.collect_explicit_sites(ir, _catalog(catalog_path)):
            slots.append({"service": svc.lower(), "slot": f"{svc}[{','.join(devs)}]", "quantifier": None,
                          "devices": [str(d) for d in devs]})
    return slots


def _package(rt, status, category="", detail="", sets=None):
    groups = rt.groups if rt is not None else []
    raw = rt.raw if rt is not None else []
    out = {"status": status, "trace": normal_form(groups), "raw_actions": [tuple(a) for a in raw],
           "category": category, "detail": detail}
    if sets is not None:
        out["trace_groups"] = out["trace"]
        out["trace"] = b2_normal_form(out["trace_groups"], sets)
        out["device_sets"] = sets
    return out


def _run(make_program, devices, events, horizon_ms, catalog_path, t_start_ms, faults, make_sets=None):
    rt = None
    sets = None
    try:
        cat = _catalog(catalog_path)
        sets = make_sets() if make_sets is not None else None
        prog = make_program(cat, sets)
        inputs = Inputs(events, cat, devices)
        rt = Runtime(cat, devices, inputs, t_start_ms, horizon_ms, faults)
        run_program(rt, prog.gen(rt))
        return _package(rt, "ok", sets=sets)
    except RefUnsupported as e:
        return _package(rt, "unsupported", e.category, f"REF-UNSUPPORTED[{e.category}]: {e.msg}", sets=sets)
    except RefError as e:
        return _package(rt, "error", e.category, f"REF-ERROR[{e.category}]: {e.msg}", sets=sets)
    except Exception as e:      # internal fault of the reference
        tb = traceback.format_exc(limit=3)
        return _package(rt, "error", "internal", f"internal {type(e).__name__}: {e}\n{tb}", sets=sets)


def run_ir(ir, binding, devices, events, horizon_ms, catalog_path=None, t_start_ms=0, cron="", faults=None,
           binding_decision=False):
    """`cron` is accepted and erased: one firing window starting at t_start_ms (HANDOFF, VERIFICATION_CONTRACT).
    binding_decision=True: trace in B2 normal form over device_sets(ir, binding)."""
    from ir_ref import IrProgram
    make_sets = (lambda: device_sets(ir, binding, catalog_path)) if binding_decision else None
    return _run(lambda cat, sets: IrProgram(ir, binding, devices, cat), devices, events, horizon_ms, catalog_path,
                t_start_ms, faults, make_sets)


def run_joi(block, devices, events, horizon_ms, catalog_path=None, t_start_ms=0, faults=None, binding=_NOT_GIVEN,
            ir=None, selector_assignment=None):
    """block = {name, cron, period, script}; cron erased (one window).
    binding (given, even None) + ir: selectors follow B1 and the trace is in B2 normal form.
    selector_assignment (B5): one device-set index per occurrence of selector_space(); needs binding. A wrong length
    or index gives status "error", category "selector-assignment"."""
    from joi_ref import JoiProgram
    make_sets = None if binding is _NOT_GIVEN else (lambda: device_sets(ir, binding, catalog_path))
    if binding is _NOT_GIVEN and selector_assignment is not None:
        make_sets = None
    return _run(lambda cat, sets: JoiProgram(block, devices, cat,
                                             device_sets=None if sets is None else DeviceSets(sets),
                                             selector_assignment=selector_assignment),
                devices, events, horizon_ms, catalog_path, t_start_ms, faults, make_sets)


def selector_space(block, devices, binding, ir, catalog_path=None):
    """B5: {"domains": [n_1..n_k], "tag_choice": [c_1..c_k]} (ordering in the module docstring)."""
    from joi_ref import JoiProgram
    try:
        cat = _catalog(catalog_path)
        prog = JoiProgram(block, devices, cat, device_sets=DeviceSets(device_sets(ir, binding, catalog_path)))
        return prog.selector_space()
    except RefUnsupported as e:
        return {"domains": [], "tag_choice": [], "status": "unsupported",
                "detail": f"REF-UNSUPPORTED[{e.category}]: {e.msg}"}
    except RefError as e:
        return {"domains": [], "tag_choice": [], "status": "error", "detail": f"REF-ERROR[{e.category}]: {e.msg}"}


def compare(trace_a, trace_b, device_sets=None):
    return common.compare(trace_a, trace_b, device_sets)
