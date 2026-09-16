"""Shared pieces of the one-shot repair harness: Explorer verification in a subprocess,
counterexample feedback (F1 input history, F2 same-instant action mismatch, F3 numbered candidate
lines), IR timing facts, the model call, and output parsing. Used by dev/run_repair.py (prompt
development) and run_e3_feedback.py (the E3 68-case run)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root (joi/self_feedback/repair_core.py -> ../..)
PY = sys.executable
BASE_URL = os.environ.get("REPAIR_BASE_URL", "http://localhost:8002/v1")

VERIFY = r'''
import json, sys, os
sys.path.insert(0, os.environ["ROOT"]); os.chdir(os.environ["ROOT"])
from explorer.verification.gate import gate_pair
ir, bind, devs, jb = json.loads(sys.stdin.read())
g = gate_pair(ir, bind, devs, jb)
pr = g.product
out = {"verdict": g.verdict, "confirmed": g.confirmed, "claim": getattr(pr, "claim", None),
       "closed": getattr(pr, "closed", None), "n_states": getattr(pr, "n_states", None),
       "notes": [n for n in (g.notes or []) if "service model evidence" not in n][-3:]}
if pr and pr.divergences:
    d = pr.divergences[0]
    out["witness"] = {"t0_ms": d.t0_ms, "input_step_ms": d.input_step_ms, "initial_gv": d.initial_gv,
                      "path": [[dict(i), int(dw)] for i, dw in d.path], "input": dict(d.input_), "dwell_ms": d.dwell_ms,
                      "actions_ir": d.actions_a, "actions_joi": d.actions_b}
print("@@" + json.dumps(out, ensure_ascii=False, default=repr))
'''


def verify(ir, bind, devs, jb, timeout=240):
    try:
        p = subprocess.run([PY, "-c", VERIFY], input=json.dumps([ir, bind, devs, jb]), text=True,
                           capture_output=True, timeout=timeout, env={**os.environ, "ROOT": str(ROOT)})
        line = next((l for l in p.stdout.splitlines() if l.startswith("@@")), None)
        if line is None:
            return {"verdict": "CRASH", "stderr": p.stderr[-1500:]}
        return json.loads(line[2:])
    except subprocess.TimeoutExpired:
        return {"verdict": "TIMEOUT"}


def fmt_actions(acts):
    out = []
    for step in acts or []:
        for a in step:
            svc, member, args, targets = a[0], a[1], a[2], a[3]
            vals = [v for _, v in (args[1] if isinstance(args, (list, tuple)) and len(args) > 1 else [])]
            out.append({"targets": list(targets), "call": f"{svc}.{member}", "args": vals})
    return out


def feedback(w, script):
    t = 0
    hist = []
    for inp, dwell in w["path"]:
        hist.append({"at_ms": t, "inputs": inp, "held_ms": dwell})
        t += dwell
    hist.append({"at_ms": t, "inputs": w["input"], "held_ms": w["dwell_ms"]})
    mismatch = t + w["dwell_ms"]
    ir_a, joi_a = fmt_actions(w["actions_ir"]), fmt_actions(w["actions_joi"])
    kind = ("joi_missing_action" if ir_a and not joi_a else "joi_extra_action" if joi_a and not ir_a
            else "different_actions")
    return {
        "F1_input_history": {
            "description": "External inputs of one failing execution, relative milliseconds from start. "
                           "Each row holds its inputs for held_ms; the last row ends at the first mismatch.",
            "input_step_ms": w["input_step_ms"], "initial_gv": w["initial_gv"], "history": hist},
        "F2_action_mismatch": {
            "same_instant_ms": mismatch, "mismatch_kind": kind,
            "ir_actions": ir_a, "joi_actions": joi_a,
            "note": "An empty list means that side emitted nothing at this instant."},
        "F3_candidate_lines": [{"line": i, "text": l} for i, l in enumerate(script.splitlines(), 1)],
    }


FORCE_TAIL = "\n\nI have used my thinking budget. I will now commit to the checklist row that matches the IR and write the final JSON answer.\n</think>\n\n"


UNIT_MS = {"MSEC": 1, "SEC": 1000, "MIN": 60000, "HOUR": 3600000}


def dur_ms(text):
    n, u = str(text).split()
    return int(float(n) * UNIT_MS[u])


def ir_timing_facts(ir):
    """Deterministic facts read off the IR: durations in ms and in 100 ms ticks. No repair advice."""
    facts = []

    def walk(steps, depth):
        for st in steps or []:
            op = st.get("op")
            if op == "wait" and st.get("for"):
                ms = dur_ms(st["for"])
                facts.append({"ir_node": f"wait(for: {st['for']})", "duration_ms": ms, "ticks_at_100ms": ms // 100,
                              "note": "sustain window; the condition must hold for the whole duration"})
            if op == "cycle":
                ms = dur_ms(st["period"])
                facts.append({"ir_node": f"cycle(period {st['period']})", "period_ms": ms,
                              "note": "period between completed bodies" + (", nested" if depth else "")})
                walk(st.get("body"), depth + 1)
            if op == "delay":
                facts.append({"ir_node": f"delay({st['duration']})", "duration_ms": dur_ms(st["duration"])})
            for k in ("then", "else"):
                if st.get(k):
                    walk(st[k], depth)
    walk(ir.get("timeline"), 0)
    return facts


def call_model(system, user, think, seed=0, max_tokens=8192, budget_force=False, answer_tokens=3000, temperature=0.6, top_p=0.95, top_k=20):
    """One chat call. With budget_force, a reasoning run that hits max_tokens is continued once with
    the thinking closed, so the model must answer with what it has (budget forcing)."""
    from openai import OpenAI
    client = OpenAI(api_key="EMPTY", base_url=BASE_URL)
    model = client.models.list().data[0].id
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    kw = dict(model=model, messages=messages, temperature=temperature, top_p=top_p, max_tokens=max_tokens, seed=seed,
              extra_body={"chat_template_kwargs": {"enable_thinking": think}, "top_k": top_k})
    t0 = time.time()
    r = client.chat.completions.create(**kw)
    msg = r.choices[0].message
    reasoning = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None)
    out = {"content": msg.content or "", "reasoning": reasoning, "finish": r.choices[0].finish_reason,
           "usage": r.usage.model_dump() if r.usage else {}, "seconds": time.time() - t0, "model": model,
           "forced": False}
    if budget_force and think and r.choices[0].finish_reason == "length" and reasoning:
        partial = "<think>\n" + reasoning + FORCE_TAIL
        kw2 = dict(kw, messages=messages + [{"role": "assistant", "content": partial}], max_tokens=answer_tokens,
                   extra_body={"chat_template_kwargs": {"enable_thinking": think}, "top_k": top_k,
                               "continue_final_message": True, "add_generation_prompt": False})
        r2 = client.chat.completions.create(**kw2)
        m2 = r2.choices[0].message
        # vLLM's reasoning parser files the continued text under reasoning; take whichever is present.
        text2 = m2.content or getattr(m2, "reasoning_content", None) or getattr(m2, "reasoning", None) or ""
        out.update(content=text2, finish=r2.choices[0].finish_reason, forced=True,
                   usage2=r2.usage.model_dump() if r2.usage else {}, seconds=time.time() - t0)
    return out


def parse_block(content, name):
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        return None, "no json object"
    try:
        obj = json.loads(m.group(0))
    except Exception as e:
        return None, f"json error: {e}"
    jb = obj.get("joi_block") if isinstance(obj, dict) else None
    if not isinstance(jb, dict) or not isinstance(jb.get("script"), str):
        return None, "no joi_block.script"
    jb = {"name": name, "cron": jb.get("cron", "") or "", "period": int(jb.get("period", 0) or 0), "script": jb["script"]}
    return {"joi_block": jb, "diagnosis": obj.get("diagnosis")}, None




def build_payload(ir, binding, devices, candidate, fb, name="Scenario", ir_facts=True):
    """The user message. Deterministic: the same inputs give the same text."""
    payload = {
        "task": "repair_confirmed_timeline_ir_to_joi",
        "immutable_specification": {"timeline_ir": ir, "binding_slots": binding, "device_inventory": devices},
        "current_candidate": candidate,
        "counterexample_feedback": fb,
    }
    if ir_facts:
        payload["ir_timing_facts"] = ir_timing_facts(ir)
    payload["output_constraints"] = {"format": "one JSON object only", "preserve_name": name,
                                     "complete_joi_block_required": True}
    return payload


def render_payload(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2)
