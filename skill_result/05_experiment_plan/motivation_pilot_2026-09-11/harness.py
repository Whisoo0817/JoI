"""Evaluation harness for the motivation pilot.

Checks a generated JoI block against a task's hidden gold specification, stage by
stage, so that the result can be reported as a funnel:

  format -> syntax -> modeled_fragment -> api_binding -> runtime
         -> nominal histories -> boundary histories

Behavior is judged by concrete replay of hand-written input histories, NOT by the
Behavioral Explorer's search. The gold Timeline IR is executed by the reference IR
runner and must reproduce the hand-derived expected trace (checked in controls.py).
"""
from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass, field, asdict
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from timeline_ir.pipeline_helpers import (  # noqa: E402
    _apply_service_prefix, _normalize_script_newlines,
    _post_process_joi_any_quantifiers, _strip_selector_extra_parens,
)
from explorer.runtime.interp import Unsupported, parse  # noqa: E402
from explorer.runtime.ground import ground  # noqa: E402
from explorer.verification.gate import prepare_pair, devs_of, pick_by_rule  # noqa: E402
from explorer.verification.service_model import ServiceModel  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tasks import TASKS, TOLERANCE_MS  # noqa: E402

TASK_BY_ID = {t["id"]: t for t in TASKS}
STAGES = ["format", "syntax", "modeled_fragment", "api_binding", "runtime", "nominal", "boundary"]


# ── post-processing shared by all conditions (same as the production pipeline) ──

def postprocess_script(script: str) -> str:
    s = _strip_selector_extra_parens(script)
    s = _apply_service_prefix(s)
    s = _normalize_script_newlines(s)
    return _post_process_joi_any_quantifiers(s)


def parse_model_output(raw: str) -> tuple[dict | None, str]:
    """Extract {cron, period, script} from a raw completion. Returns (block, error)."""
    text = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.DOTALL)
    text = re.sub(r"<Reasoning>.*?</Reasoning>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start = text.find("{")
    if start < 0:
        return None, "no JSON object"
    # Tolerate raw newlines inside the script string (same repair as production).
    m = re.search(r'"script"\s*:\s*"(.*?)"\s*\}', text[start:], re.DOTALL)
    body = text[start:]
    if m:
        body = body[:m.start(1)] + m.group(1).replace("\n", "\\n") + body[m.end(1):]
    try:
        obj, _ = json.JSONDecoder().raw_decode(body)
    except json.JSONDecodeError as e:
        return None, f"JSON decode: {e}"
    if not isinstance(obj, dict) or not isinstance(obj.get("script"), str):
        return None, "missing string script"
    # Lenient repair: one level of JSON nested inside the script string.
    inner = obj["script"].strip()
    if inner.startswith("{"):
        try:
            nested = json.loads(inner, strict=False)
            if isinstance(nested, dict) and isinstance(nested.get("script"), str):
                obj = {**obj, **{k: v for k, v in nested.items() if k in ("script", "period", "cron")}}
        except json.JSONDecodeError:
            pass
    period = obj.get("period", 0)
    if isinstance(period, str) and period.strip().isdigit():
        period = int(period.strip())
    if isinstance(period, float) and period.is_integer():
        period = int(period)
    if type(period) is not int or period < 0:
        return None, f"invalid period {obj.get('period')!r}"
    cron = obj.get("cron", "") or ""
    if not isinstance(cron, str):
        return None, "invalid cron"
    return {"cron": cron.strip(), "period": period, "script": obj["script"]}, ""


# ── ANTLR grammar ────────────────────────────────────────────────────────────

def grammar_errors(script: str) -> list | None:
    try:
        from antlr4 import InputStream, CommonTokenStream
        from antlr4.error.ErrorListener import ErrorListener
        from lowering.parser.generated.JOILangLexer import JOILangLexer
        from lowering.parser.generated.JOILangParser import JOILangParser
    except ImportError:
        return None
    errors = []

    class L(ErrorListener):
        def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
            errors.append(f"{line}:{column} {msg}")

    lexer = JOILangLexer(InputStream(script))
    lexer.removeErrorListeners(); lexer.addErrorListener(L())
    parser = JOILangParser(CommonTokenStream(lexer))
    parser.removeErrorListeners(); parser.addErrorListener(L())
    parser.scenario()
    return errors


# ── replay ───────────────────────────────────────────────────────────────────

def _lower_first(s: str) -> str:
    return s[:1].lower() + s[1:]


def history_inputs(events):
    """[(t, {"Dev.Attr": v})] -> {t: {"Dev.attr": v}} with runner key spelling."""
    out = {}
    for t, upd in events:
        out.setdefault(t, {}).update({f"{k.split('.')[0]}.{_lower_first(k.split('.')[1])}": v
                                      for k, v in upd.items()})
    return out


_DUR = re.compile(r"(\d+)\s*(MSEC|SEC|MIN|HOUR)")
_UNIT = {"MSEC": 1, "SEC": 1000, "MIN": 60000, "HOUR": 3600000}


def replay_step_ms(*texts: str, period: int = 0) -> int:
    """Largest step that still hits every input change, deadline and period tick."""
    g = 1000
    for text in texts:
        for n, u in _DUR.findall(text or ""):
            g = math.gcd(g, int(n) * _UNIT[u])
    if period:
        g = math.gcd(g, period)
    return max(g, 1)


def replay(runner, events, horizon_ms: int, step_ms: int) -> list[tuple]:
    changes = history_inputs(events)
    for t in changes:
        if t % step_ms:
            raise ValueError(f"input change at {t} is off the replay grid {step_ms}")
    values, gv, inputs, trace = {}, {}, {}, []
    for t in range(0, horizon_ms + 1, step_ms):
        if t in changes:
            inputs.update(changes[t])
        res = runner.step(values, gv, dict(inputs), t, first_tick=(t == 0))
        values, gv = res.vars, res.gv
        for a in res.actions:
            targets = tuple(a.target) if isinstance(a.target, (list, tuple)) else (a.target,)
            trace.append((t, str(a.service).lower(), str(a.method).lower(),
                          tuple(_num(x) for x in a.args), targets))
    return trace


def _num(x):
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float, Fraction)):
        return float(x)
    return x


def expected_trace(hist) -> list[tuple]:
    out = []
    for t, sm, args, dev in hist["expected"]:
        svc, meth = sm.split(".")
        out.append((t, svc.lower(), meth.lower(), tuple(_num(a) for a in args), (dev,)))
    return out


def compare(expected: list[tuple], actual: list[tuple], horizon_ms: int) -> dict:
    """Same ACTION signatures in the same order; each time within TOLERANCE_MS."""
    exact = expected == actual
    sig = lambda a: a[1:]
    tolerant = (len(expected) == len(actual)
                and all(sig(e) == sig(a) and abs(e[0] - a[0]) <= TOLERANCE_MS
                        for e, a in zip(expected, actual)))
    edge_only = False
    if not tolerant:
        cut = horizon_ms - TOLERANCE_MS
        e2 = [e for e in expected if e[0] <= cut]
        a2 = [a for a in actual if a[0] <= cut]
        edge_only = (len(e2) == len(a2)
                     and all(sig(e) == sig(a) and abs(e[0] - a[0]) <= TOLERANCE_MS for e, a in zip(e2, a2)))
    return {"exact": exact, "match": tolerant or edge_only, "horizon_edge_only": edge_only and not tolerant}


# ── staged evaluation ────────────────────────────────────────────────────────

@dataclass
class Result:
    task: str
    stage_failed: str | None = None      # first failed stage, None if all passed
    failure: str = ""
    block: dict | None = None
    histories: list = field(default_factory=list)
    nominal_pass: bool | None = None
    boundary_pass: bool | None = None
    boundary_pass_nl_determined: bool | None = None
    exact_all: bool | None = None

    def to_json(self):
        return asdict(self)


def prepare_ir_runner(task):
    return prepare_pair(task["ir"], task["binding"], task["devices"],
                        {"cron": "", "period": 0, "script": ""})


def evaluate_block(task: dict, raw: str | None = None, block: dict | None = None) -> Result:
    r = Result(task["id"])
    if block is None:
        block, err = parse_model_output(raw)
        if block is None:
            r.stage_failed, r.failure = "format", err
            return r
    block = dict(block)
    block["script"] = postprocess_script(block["script"])
    r.block = block

    errs = grammar_errors(block["script"])
    if errs:
        r.stage_failed, r.failure = "syntax", "; ".join(errs[:3])
        return r

    try:
        stmts = parse(block["script"])
    except Unsupported as e:
        r.stage_failed, r.failure = "modeled_fragment", f"parse: {e}"
        return r
    except Exception as e:  # parser crash on odd input
        r.stage_failed, r.failure = "modeled_fragment", f"parse {type(e).__name__}: {e}"
        return r
    if block["cron"] and block["cron"] != "x":
        r.stage_failed, r.failure = "modeled_fragment", f"cron schedule {block['cron']!r} not modeled"
        return r

    try:
        model = ServiceModel(task["devices"], None)
        model.normalize_ir(task["ir"], task["binding"])
        model.validate_source(stmts)
        gstmts, rep = ground(stmts, devs_of(task["devices"]), pick=pick_by_rule)
        if rep.floating:
            raise Unsupported(f"unresolved selectors: {rep.floating}")
        model.validate_joi(gstmts)
    except Unsupported as e:
        r.stage_failed, r.failure = "api_binding", str(e)
        return r
    except Exception as e:
        r.stage_failed, r.failure = "api_binding", f"{type(e).__name__}: {e}"
        return r

    try:
        pair = prepare_pair(task["ir"], task["binding"], task["devices"], block)
    except Unsupported as e:
        r.stage_failed, r.failure = "modeled_fragment", f"prepare: {e}"
        return r
    except Exception as e:
        r.stage_failed, r.failure = "modeled_fragment", f"prepare {type(e).__name__}: {e}"
        return r

    step = replay_step_ms(json.dumps(task["ir"]), block["script"], period=block["period"])
    nominal, boundary, boundary_nl, exact_all = True, True, True, True
    for h in task["histories"]:
        exp = expected_trace(h)
        try:
            ir_trace = replay(pair.ir_runner, h["events"], h["horizon_ms"], step)
        except Exception as e:
            raise RuntimeError(f"gold IR replay failed on {task['id']}/{h['name']}: {e}") from e
        gold_ok = compare(exp, ir_trace, h["horizon_ms"])["exact"]
        try:
            code_trace = replay(pair.code_runner, h["events"], h["horizon_ms"], step)
        except Exception as e:
            r.stage_failed, r.failure = "runtime", f"{h['name']}: {type(e).__name__}: {e}"
            r.histories.append({"name": h["name"], "error": r.failure})
            return r
        cmp = compare(exp, code_trace, h["horizon_ms"])
        r.histories.append({"name": h["name"], "kind": h["kind"], "nl_determined": h["nl_determined"],
                            "gold_ir_reproduces_expected": gold_ok, **cmp,
                            "expected": exp, "actual": code_trace})
        exact_all &= cmp["exact"]
        if h["kind"] == "nominal":
            nominal &= cmp["match"]
        else:
            boundary &= cmp["match"]
            if h["nl_determined"]:
                boundary_nl &= cmp["match"]
    r.nominal_pass, r.boundary_pass, r.boundary_pass_nl_determined, r.exact_all = nominal, boundary, boundary_nl, exact_all
    if not nominal:
        r.stage_failed = "nominal"
    elif not boundary:
        r.stage_failed = "boundary"
    return r
