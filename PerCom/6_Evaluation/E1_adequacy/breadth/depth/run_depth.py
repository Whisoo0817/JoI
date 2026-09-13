"""E1 depth additions runner.

python depth/run_depth.py [CASE_ID ...] [--explorer]   -> depth/runs/e1_depth.json

Per case (README outcome fields):
  frontend     validate_ir + catalog check against the E1 fixture catalog; grammar_check (extractor.md)
  runner       prepare_pair compile, then replay of every frozen history under rules T1-T7 (depth_cases.py)
  joi          only for cases whose Timeline result is partial/impossible: the same histories on JoI block(s)
  explorer     auxiliary, only with --explorer; never part of E1 adequacy

IR in depth_attempts.py marks each device atom as `Svc[Dev,...].Member`. `lower()` strips the marks and
builds the binding table in the gate's walk order (explorer.verification.gate._Rewriter.walk): per step,
cond then until, then read.src, then call.target, then nested lists in key order. A service bound to one
device set everywhere gets one merged slot; otherwise one slot per occurrence.
"""
from __future__ import annotations

import json
import re
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
E1 = HERE.parents[1]
ROOT = HERE.parents[4]
for p in (ROOT, E1, HERE):
    sys.path.insert(0, str(p))

from depth_cases import CASES, CASE_BY_ID, TOLERANCE_MS, NUM_EPS  # noqa: E402
from depth_attempts import ATTEMPTS  # noqa: E402
import fixture  # noqa: E402
from grammar_check import check_ir  # noqa: E402
from run_e1 import history_inputs, erase_cron, explorer_self_product, _num  # noqa: E402

from timeline_ir.timeline_ir import validate_ir, validate_ir_against_catalog, IRValidationError  # noqa: E402
from timeline_ir.catalog import load_catalog  # noqa: E402
from explorer.verification.gate import prepare_pair  # noqa: E402

MARK = re.compile(r"([A-Za-z_]\w*)\[([^\]]+)\]\.(\w+)")


# ── IR lowering: marked atoms -> plain IR + binding table ────────────────────

def lower(marked):
    ir = json.loads(json.dumps(marked))
    occ = []                                   # (service, (ids...)) in gate walk order

    def strip(text):
        def sub(m):
            occ.append((m.group(1), tuple(x.strip() for x in m.group(2).split(","))))
            return f"{m.group(1)}.{m.group(3)}"
        return MARK.sub(sub, text)

    def walk(steps):
        for s in steps:
            for f in ("cond", "until"):
                if isinstance(s.get(f), str):
                    s[f] = strip(s[f])
            if s.get("op") == "read":
                s["src"] = strip(s["src"])
            if s.get("op") == "call":
                s["target"] = strip(s["target"])
                for k, v in list((s.get("args") or {}).items()):
                    if isinstance(v, str) and MARK.search(v):
                        s["args"][k] = strip(v)
            for v in list(s.values()):
                if isinstance(v, list):
                    walk(v)

    walk(ir["timeline"])
    binding = {}
    for svc in dict.fromkeys(s for s, _ in occ):
        sets = [ids for s, ids in occ if s == svc]
        if len(set(sets)) == 1:
            binding[svc] = list(sets[0])
        else:
            for i, ids in enumerate(sets, 1):
                binding[svc if i == 1 else f"{svc}#{i}"] = list(ids)
    return ir, binding


# ── replay with several deployed instances and T7 fault injection ────────────

def replay(runners, hist, t_start):
    step_ms, horizon = hist["step_ms"], hist["horizon"]
    changes = history_inputs(hist["events"])
    for t in changes:
        if t % step_ms:
            raise ValueError(f"input change at {t} off the {step_ms} ms grid")
    faults = [dict(f, service=f["service"].lower(), method=f["method"].lower()) for f in hist.get("faults", [])]
    state = [({}, {}) for _ in runners]
    killed_at = [None] * len(runners)
    inputs, trace, fault_log = {}, [], []
    for rel in range(0, horizon + 1, step_ms):
        if rel in changes:
            inputs.update(changes[rel])
        for i, r in enumerate(runners):
            if killed_at[i] is not None and rel >= killed_at[i]:
                continue                        # T7: terminated before it steps
            values, gv = state[i]
            res = r.step(values, gv, dict(inputs), t_start + rel, first_tick=(rel == 0))
            state[i] = (res.vars, res.gv)
            for a in res.actions:
                targets = tuple(a.target) if isinstance(a.target, (list, tuple)) else (a.target,)
                row = (rel, str(a.service).lower(), str(a.method).lower(), tuple(_num(x) for x in a.args), targets)
                trace.append(row + (i,))
                for f in faults:
                    if row[1] == f["service"] and row[2] == f["method"] and f["device"] in targets:
                        due = rel + f["after_ms"]
                        if killed_at[i] is None or due < killed_at[i]:
                            killed_at[i] = due
                        fault_log.append({"instance": i, "issued_ms": rel, "failure_delivered_ms": due,
                                          "command": f"{a.service}.{a.method}"})
    return trace, fault_log


def expected_trace(hist):
    out = []
    for t, sm, args, dev in hist["expected"]:
        svc, meth = sm.split(".")
        out.append((t, svc.lower(), meth.lower(), tuple(_num(a) for a in args), (dev,)))
    return out


def _same_args(a, b):
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if isinstance(x, (int, float)) and isinstance(y, (int, float)) \
                and not isinstance(x, bool) and not isinstance(y, bool):
            if abs(x - y) > NUM_EPS:
                return False
        elif x != y:
            return False
    return True


def _same_sig(e, a):
    return e[1] == a[1] and e[2] == a[2] and e[4] == a[4] and _same_args(e[3], a[3])


def compare(expected, actual):
    """Rule T5: unordered within equal times; exact = equal multisets of (time, signature)."""
    actual = [a[:5] for a in actual]

    def pair(tol):
        free = list(range(len(actual)))
        missing = []
        for e in expected:
            best = None
            for j in free:
                a = actual[j]
                if _same_sig(e, a) and abs(e[0] - a[0]) <= tol:
                    if best is None or abs(e[0] - a[0]) < abs(e[0] - actual[best][0]):
                        best = j
            if best is None:
                missing.append(e)
            else:
                free.remove(best)
        return missing, [actual[j] for j in free]

    miss_x, extra_x = pair(0)
    miss_t, extra_t = pair(TOLERANCE_MS)
    return {"exact": not miss_x and not extra_x, "match": not miss_t and not extra_t,
            "missing": miss_t, "extra": extra_t}


# ── per case ─────────────────────────────────────────────────────────────────

def compile_pair(ir, binding, devices, catalog_path, script="", period=0):
    ir_exec, erased = erase_cron(ir)
    pair = prepare_pair(ir_exec, binding, devices, {"cron": "", "period": period, "script": script},
                        service_catalog=catalog_path)
    return pair, erased


def run_histories(case, runners_factory):
    rows, n_match, n_exact = [], 0, 0
    for h in case["histories"]:
        exp = expected_trace(h)
        try:
            act, faults = replay(runners_factory(), h, case["t_start_ms"])
        except Exception as e:
            rows.append({"name": h["name"], "error": f"{type(e).__name__}: {e}", "match": False, "exact": False})
            continue
        cmp = compare(exp, act)
        n_match += cmp["match"]
        n_exact += cmp["exact"]
        rows.append({"name": h["name"], "kind": h["kind"], **cmp, "faults": faults,
                     "expected": exp, "actual": [a[:5] + (f"instance {a[5]}",) for a in act]})
    return rows, f"{n_match}/{len(case['histories'])}", f"{n_exact}/{len(case['histories'])}"


def run_case(case, entry, catalog_path, catalog, do_explorer):
    row = {"id": case["id"], "lang": entry["lang"], "lang_reason": entry.get("lang_reason", ""),
           "stubs": case["stubs"]}
    for a in entry.get("refused_attempts", []):
        ir_a, bind_a = lower(a["ir"])
        try:
            validate_ir(ir_a)
            validate_ir_against_catalog(ir_a, catalog)
            msg = "frontend accepted"
            compile_pair(ir_a, bind_a, case["devices"], catalog_path)
            msg += "; runner compiled"
        except Exception as e:
            msg = f"refused: {type(e).__name__}: {str(e)[:300]}"
        row.setdefault("refused_attempts", []).append({"label": a["label"], "result": msg})

    ir, binding = lower(entry["ir"])
    row["ir"], row["binding"] = ir, binding
    try:
        validate_ir(ir)
        validate_ir_against_catalog(ir, catalog)
        row["frontend"] = "accepted"
    except IRValidationError as e:
        row["frontend"] = f"rejected: {str(e)[:300]}"
    row["extractor_grammar_outside"] = check_ir(ir)

    try:
        pair, erased = compile_pair(ir, binding, case["devices"], catalog_path)
        row["runner"] = "compiled" + (" (cron anchor erased)" if erased else "")
    except Exception as e:
        row["runner"] = f"refused: {type(e).__name__}: {str(e)[:300]}"
        pair = None
    if pair is not None:
        def ir_factory():
            p, _ = compile_pair(ir, binding, case["devices"], catalog_path)
            return [p.ir_runner]
        row["histories"], row["match"], row["exact"] = run_histories(case, ir_factory)
        row["explorer"] = explorer_self_product(pair) if do_explorer else {"verdict": "not run"}

    if entry.get("joi"):
        j = entry["joi"]

        def joi_factory():
            return [compile_pair(ir, binding, case["devices"], catalog_path, s["script"], s.get("period", 0))[0].code_runner
                    for s in j["blocks"]]
        try:
            hist, m, x = run_histories(case, joi_factory)
            row["joi"] = {"blocks": [b["name"] for b in j["blocks"]], "note": j.get("note", ""),
                          "histories": hist, "match": m, "exact": x}
        except Exception as e:
            row["joi"] = {"error": f"{type(e).__name__}: {str(e)[:400]}"}
    return row


def main(argv):
    ids = [a for a in argv if not a.startswith("--")] or [c["id"] for c in CASES]
    do_explorer = "--explorer" in argv
    catalog_path, sha = fixture.build()
    catalog = load_catalog(catalog_path)
    out = HERE / "runs" / "e1_depth.json"
    old = {r["id"]: r for r in json.loads(out.read_text())} if out.exists() else {}
    for cid in ids:
        try:
            row = run_case(CASE_BY_ID[cid], ATTEMPTS[cid], catalog_path, catalog, do_explorer)
        except Exception:
            row = {"id": cid, "crash": traceback.format_exc()[-2000:]}
        row["fixture_catalog_sha256"] = sha
        old[cid] = row
        print(f"{cid}: lang={row.get('lang','?')} | frontend={str(row.get('frontend','?'))[:50]} | "
              f"runner={str(row.get('runner','?'))[:50]} | C={row.get('match','-')} (exact {row.get('exact','-')}) | "
              f"JoI={row.get('joi',{}).get('match', row.get('joi',{}).get('error','-')) if row.get('joi') else '-'} | "
              f"E={row.get('explorer',{}).get('verdict','-')}")
        for a in row.get("refused_attempts", []):
            print(f"    attempt {a['label']}: {a['result'][:160]}")
        if row.get("crash"):
            print(row["crash"])
        for src, hs in (("IR", row.get("histories", [])), ("JoI", row.get("joi", {}).get("histories", []))):
            for h in hs:
                if not h.get("match"):
                    print(f"    ✗ {src} {h['name']}: {h.get('error') or {'missing': h['missing'], 'extra': h['extra']}}")
                if h.get("faults"):
                    print(f"      faults: {h['faults']}")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps([old[c["id"]] for c in CASES if c["id"] in old], ensure_ascii=False, indent=1, default=str))
    print(f"-> {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
