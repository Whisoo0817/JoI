"""E2 independent reference — public API.

run_ir(ir, binding, devices, events, horizon_ms, catalog_path=None, t_start_ms=0, cron="")
run_joi(block, devices, events, horizon_ms, catalog_path=None, t_start_ms=0)
compare(trace_a, trace_b) -> (equal, first_difference)

Each run returns {"status": "ok"|"unsupported"|"error", "trace": normalised trace, "raw_actions": [...],
"detail": str, "category": str}. `faults` (E1 rule T7) is an optional extra keyword.
On "unsupported"/"error" the trace holds the ACTIONs issued before the stop (diagnostic only).
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import common                                   # noqa: E402
from common import Catalog, Inputs, RefError, RefUnsupported, Runtime, normal_form, run_program  # noqa: E402

_CATALOGS = {}


def _catalog(path):
    key = str(path or common.DEFAULT_CATALOG)
    if key not in _CATALOGS:
        _CATALOGS[key] = Catalog(key)
    return _CATALOGS[key]


def _package(rt, status, category="", detail=""):
    groups = rt.groups if rt is not None else []
    raw = rt.raw if rt is not None else []
    return {"status": status, "trace": normal_form(groups), "raw_actions": [tuple(a) for a in raw],
            "category": category, "detail": detail}


def _run(make_program, devices, events, horizon_ms, catalog_path, t_start_ms, faults):
    rt = None
    try:
        cat = _catalog(catalog_path)
        prog = make_program(cat)
        inputs = Inputs(events, cat, devices)
        rt = Runtime(cat, devices, inputs, t_start_ms, horizon_ms, faults)
        run_program(rt, prog.gen(rt))
        return _package(rt, "ok")
    except RefUnsupported as e:
        return _package(rt, "unsupported", e.category, f"REF-UNSUPPORTED[{e.category}]: {e.msg}")
    except RefError as e:
        return _package(rt, "error", e.category, f"REF-ERROR[{e.category}]: {e.msg}")
    except Exception as e:      # internal fault of the reference
        tb = traceback.format_exc(limit=3)
        return _package(rt, "error", "internal", f"internal {type(e).__name__}: {e}\n{tb}")


def run_ir(ir, binding, devices, events, horizon_ms, catalog_path=None, t_start_ms=0, cron="", faults=None):
    """`cron` is accepted and erased: one firing window starting at t_start_ms (HANDOFF, VERIFICATION_CONTRACT)."""
    from ir_ref import IrProgram
    return _run(lambda cat: IrProgram(ir, binding, devices, cat), devices, events, horizon_ms, catalog_path,
                t_start_ms, faults)


def run_joi(block, devices, events, horizon_ms, catalog_path=None, t_start_ms=0, faults=None):
    """block = {name, cron, period, script}; cron erased (one window)."""
    from joi_ref import JoiProgram
    return _run(lambda cat: JoiProgram(block, devices, cat), devices, events, horizon_ms, catalog_path,
                t_start_ms, faults)


def compare(trace_a, trace_b):
    return common.compare(trace_a, trace_b)
