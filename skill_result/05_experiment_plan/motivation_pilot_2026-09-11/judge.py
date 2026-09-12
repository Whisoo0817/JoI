"""LLM-as-judge on the pilot's executable JoI programs.

Question: given the precise behavior specification, the JoI execution model and one
program, does an LLM judge accept wrong programs or reject correct ones?

Programs: every unique (task, period, script) that reached the behavior stages in
runs/results_{gpt54mini,qwen9b,qwen9b_think}.jsonl. The generation condition does
not matter here; every judge sees the same [Behavior Specification].

Ground truth (fixed before any judge call):
  correct  passes every hand-written history (1 s tolerance)
  wrong    fails a history; kind = visible (nominal) or silent (boundary only)
  error group of a wrong program, from its classify.py mechanism:
    static    visible by reading the code against the spec
    temporal  needs following inputs over time
    runtime   needs the JoI execution rules (period after body, := first run, ticks)

A judge that answers INCORRECT must give a counterexample input history. It is replayed
against the gold IR; if the traces differ (1 s tolerance) the rejection is a real divergence
the hand-written histories missed, and the program is reported separately, not as a false reject.

python judge.py --judge gpt54mini --repeats 3
python judge.py --judge gemma26b --repeats 1
python judge.py --report
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from harness import TASK_BY_ID, compare, expected_trace, replay, replay_step_ms  # noqa: E402
from generate import openai_key, service_block, precision_block  # noqa: E402
from classify import LABELS  # noqa: E402

OUT = HERE / "runs" / "judge"
GEN_MODELS = ["gpt54mini", "qwen9b", "qwen9b_think"]
JUDGES = {
    "gpt54mini": dict(kind="openai", model="gpt-5.4-mini-2026-03-17", reasoning_effort="medium",
                      max_completion_tokens=16000, workers=6),
    "gemma26b": dict(kind="vllm", model="cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit", base_url="http://localhost:8002/v1",
                     enable_thinking=False, temperature=0.0, max_tokens=12000, workers=2),
    "gemma26b_think": dict(kind="vllm", model="cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit", base_url="http://localhost:8002/v1",
                           enable_thinking=True, temperature=0.0, max_tokens=20000, workers=2),
}

# Labels for qwen9b_think failures, fixed before the judge run (same taxonomy as classify.py).
EXTRA_LABELS = {
    ("qwen9b_think", "IR", "T06", 1): "tick_conversion",
    ("qwen9b_think", "IR", "T09", 3): "snapshot_lifetime",
    ("qwen9b_think", "IR", "T11", 1): "counter_per_tick",
    ("qwen9b_think", "IR", "T11", 2): "counter_per_tick",
    ("qwen9b_think", "IR", "T11", 3): "counter_per_tick",
    ("qwen9b_think", "IR", "T12", 1): "counter_per_tick",
    ("qwen9b_think", "IR", "T12", 3): "counter_per_tick",
    ("qwen9b_think", "NL", "T11", 3): "broken_state_logic",
    ("qwen9b_think", "NL", "T12", 3): "sustain_as_delay_recheck",
}
GROUP = {
    "inverted_condition": "static", "spurious_operation": "static", "no_temporal_logic": "static",
    "control_misuse": "static",
    "sustain_as_delay_recheck": "temporal", "repeat_policy": "temporal", "broken_state_logic": "temporal",
    "counter_per_tick": "runtime", "tick_conversion": "runtime", "snapshot_lifetime": "runtime",
}

# Judge spec v2 (2026-09-11): the v1 run showed that "changes from closed to open" left the start state
# ambiguous; the gold IR treats a condition that already holds at t = 0 as occurring at t = 0.
# v1 verdicts are kept in runs/judge_v1_initial_state_ambiguous/.
INITIAL_STATE = {
    "T01": "If the door is already open when the automation starts, the 60 seconds are counted from t = 0.",
    "T02": "If there is already no motion when the automation starts, the 120 seconds are counted from t = 0.",
    "T03": "If the door is already open when the automation starts, that counts as an opening at t = 0.",
    "T04": "If the garage door is already open when the automation starts, the light is turned on immediately at t = 0.",
    "T05": "If the temperature is already above 28°C when the automation starts, that counts as a rise at t = 0.",
    "T06": "If motion is already detected when the automation starts, that counts as a change to motion at t = 0.",
    "T09": "If the door is already open when the automation starts, that counts as an opening at t = 0.",
    "T11": "If the mailbox is already open when the automation starts, that counts as an opening at t = 0.",
    "T12": "If the door is already open when the automation starts, the 60 seconds are counted from t = 0.",
}

_ref = (HERE / "prompts" / "joi_reference.md").read_text()
JOI_RULES = _ref[_ref.index("# JoI Execution Model"):_ref.index("# Strict Selector Rule")].strip()

SYSTEM = f"""# Role
You are an expert reviewer of JoI smart-home automations. You decide whether one JoI program implements a behavior specification.

# What counts as correct
- Judge only observable behavior: which device commands are issued, with which arguments, and when.
- The program is CORRECT if, for every possible input history (any valid initial sensor values and any later changes), it issues the same commands with the same arguments in the same order as the specification requires, each within 1 second of the required time. Differences of up to 1 second caused by polling are acceptable.
- Structure, style, variable names and efficiency do not matter. A program that looks unusual but behaves identically is CORRECT.
- Selectors and member names have already been validated; do not judge them.

# Output
First reason as much as you need. Then output exactly one JSON object as the last thing in your answer:
{{"verdict": "CORRECT" or "INCORRECT", "reason": "<one or two sentences>", "counterexample": null or {{"events": [[t_seconds, {{"<Input>": value, ...}}], ...]}}}}
- If the verdict is INCORRECT, give a concrete counterexample input history on which the program's commands differ from the specification. The first event must be at t = 0 and set every input listed in [Inputs]. Times are whole seconds. Use the input names exactly as listed.
- If the verdict is CORRECT, counterexample is null.

{JOI_RULES}
"""


def task_inputs(task):
    """[(name, type, meaning)] for every input that appears in the task histories."""
    svc = json.loads(service_block(task))
    rows, seen = [], set()
    for h in task["histories"]:
        for _, upd in h["events"]:
            for k, v in upd.items():
                if k in seen:
                    continue
                seen.add(k)
                dev, attr = k.split(".")
                selector, desc, typ = "", "", type(v).__name__
                for sname, members in svc.items():
                    if attr in members and dev in task["binding"].get(sname, []):
                        desc, typ = members[attr].get("descriptor", ""), members[attr].get("type", typ)
                        selector = task["selectors"].get(f"{sname}.{attr}", "")
                rows.append((k, typ, f"read by {selector}.{attr}. {desc}".strip()))
    return rows


def display_script(script):
    """Show the program as the generator wrote it: `.contactSensor_contact` -> `.Contact`, re-indented."""
    s = re.sub(r"\)\.[a-z][A-Za-z0-9]*_([a-z])(\w*)", lambda m: ")." + m.group(1).upper() + m.group(2), script)
    out, depth = [], 0
    for line in s.splitlines():
        t = line.strip()
        if not t:
            continue
        if t.startswith("}"):
            depth = max(depth - 1, 0)
        out.append("    " * depth + t)
        if t.endswith("{"):
            depth += 1
    return "\n".join(out)


def build_messages(task, block):
    inputs = "\n".join(f"- {n} ({t}): {d}" for n, t, d in task_inputs(task))
    user = (f"[Command]\n{task['command']}\n\n"
            f"[Behavior Specification]\n{task['spec']}{(' ' + INITIAL_STATE[task['id']]) if task['id'] in INITIAL_STATE else ''}\n\n"
            f"[Precision Selectors]\n{precision_block(task)}\n\n"
            f"[Service Details]\n{service_block(task)}\n\n"
            f"[Inputs]\n{inputs}\n\n"
            f"[JoI Program]\n{json.dumps({'cron': block['cron'], 'period': block['period'], 'script': display_script(block['script'])}, ensure_ascii=False, indent=1)}")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def collect_programs():
    progs = {}
    for m in GEN_MODELS:
        path = HERE / "runs" / f"results_{m}.jsonl"
        for line in path.read_text().splitlines():
            r = json.loads(line)
            if r["stage_failed"] not in (None, "nominal", "boundary"):
                continue
            b = r["block"]
            pid = r["task"] + "_" + hashlib.sha1(f"{b['period']}\n{b['script']}".encode()).hexdigest()[:8]
            src = (m, r["condition"], r["task"], r["sample"])
            if pid not in progs:
                mech = None
                if r["stage_failed"]:
                    mech = LABELS.get(src, (EXTRA_LABELS.get(src),))[0]
                progs[pid] = {"id": pid, "task": r["task"], "block": {"cron": b["cron"], "period": b["period"], "script": b["script"]},
                              "label": "correct" if r["stage_failed"] is None else "wrong",
                              "kind": {None: None, "nominal": "visible", "boundary": "silent"}[r["stage_failed"]],
                              "mechanism": mech, "group": GROUP.get(mech), "sources": []}
            progs[pid]["sources"].append(list(src))
    return progs


def call_judge(cfg, messages):
    from openai import OpenAI
    t0 = time.perf_counter()
    if cfg["kind"] == "openai":
        resp = OpenAI(api_key=openai_key()).chat.completions.create(
            model=cfg["model"], messages=messages, reasoning_effort=cfg["reasoning_effort"],
            max_completion_tokens=cfg["max_completion_tokens"])
    else:
        resp = OpenAI(api_key="EMPTY", base_url=cfg["base_url"]).chat.completions.create(
            model=cfg["model"], messages=messages, temperature=cfg["temperature"], max_tokens=cfg["max_tokens"],
            extra_body={"chat_template_kwargs": {"enable_thinking": cfg["enable_thinking"]}})
    ch = resp.choices[0]
    return {"raw": ch.message.content or "", "finish_reason": ch.finish_reason,
            "usage": resp.usage.model_dump() if resp.usage else {}, "seconds": round(time.perf_counter() - t0, 2)}


def parse_verdict(raw):
    text = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.DOTALL)
    dec, found = json.JSONDecoder(), None
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = dec.raw_decode(text[m.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "verdict" in obj:
            found = obj
    if not found:
        return None
    v = str(found.get("verdict", "")).strip().upper()
    if v not in ("CORRECT", "INCORRECT"):
        return None
    return {"verdict": v, "reason": found.get("reason", ""), "counterexample": found.get("counterexample")}


def check_counterexample(task, block, cex):
    """Replay the judge's history on gold IR and program. Returns (valid_divergence, note)."""
    from explorer.verification.gate import prepare_pair
    try:
        events = cex["events"] if isinstance(cex, dict) else cex
        names = {n for n, _, _ in task_inputs(task)}
        init = dict(task["histories"][0]["events"][0][1])
        norm, t_last = [], 0
        for t, upd in events:
            t_ms = int(round(float(t) * 1000))
            bad = [k for k in upd if k not in names]
            if bad:
                return None, f"unknown inputs {bad}"
            if t_ms == 0:
                upd = {**init, **upd}
            norm.append((t_ms, dict(upd)))
            t_last = max(t_last, t_ms)
        if not norm or norm[0][0] != 0:
            norm.insert(0, (0, init))
        horizon = t_last + max(h["horizon_ms"] for h in task["histories"])
        pair = prepare_pair(task["ir"], task["binding"], task["devices"], block)
        step = min(replay_step_ms(json.dumps(task["ir"]), block["script"], period=block["period"]), 1000)
        ir_tr = replay(pair.ir_runner, norm, horizon, step)
        code_tr = replay(pair.code_runner, norm, horizon, step)
        cmp = compare(ir_tr, code_tr, horizon)
        return (not cmp["match"]), {"ir": ir_tr[:8], "code": code_tr[:8]}
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def run(judge, repeats):
    cfg = JUDGES[judge]
    progs = collect_programs()
    (OUT).mkdir(parents=True, exist_ok=True)
    (OUT / "programs.json").write_text(json.dumps(progs, ensure_ascii=False, indent=1))
    jobs = []
    for p in progs.values():
        for k in range(1, repeats + 1):
            path = OUT / judge / f"{p['id']}_r{k}.json"
            if not path.exists():
                jobs.append((p, k, path))
    print(f"{len(progs)} programs, {len(jobs)} judge calls for {judge}", flush=True)

    def work(job):
        p, k, path = job
        task = TASK_BY_ID[p["task"]]
        msgs = build_messages(task, p["block"])
        rec = {"program": p["id"], "repeat": k, "judge": judge, "config": {x: y for x, y in cfg.items() if x != "workers"}}
        try:
            rec.update(call_judge(cfg, msgs))
        except Exception as e:  # noqa: BLE001
            return f"{p['id']} r{k} ERROR {type(e).__name__}: {e}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        return f"{p['id']} r{k} {rec['seconds']}s {rec['finish_reason']}"

    with ThreadPoolExecutor(cfg["workers"]) as ex:
        for fut in as_completed([ex.submit(work, j) for j in jobs]):
            print(fut.result(), flush=True)


def report():
    progs = json.loads((OUT / "programs.json").read_text())
    summary = {}
    for jdir in sorted(d for d in OUT.iterdir() if d.is_dir()):
        judge, rows = jdir.name, []
        for f in sorted(jdir.glob("*.json")):
            rec = json.loads(f.read_text())
            p = progs[rec["program"]]
            v = parse_verdict(rec.get("raw"))
            row = {"program": p["id"], "repeat": rec["repeat"], "task": p["task"], "label": p["label"], "kind": p["kind"],
                   "group": p["group"], "mechanism": p["mechanism"], "verdict": v["verdict"] if v else "UNPARSED",
                   "finish_reason": rec.get("finish_reason"), "reason": v["reason"] if v else None}
            if v and v["verdict"] == "INCORRECT":
                ok, note = check_counterexample(TASK_BY_ID[p["task"]], p["block"], v["counterexample"])
                row["cex_valid"], row["cex_note"] = ok, note
            rows.append(row)
        (OUT / f"verdicts_{judge}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in rows) + "\n")
        summary[judge] = summarize(judge, rows)
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))


def summarize(judge, rows):
    c = Counter()
    by_group = defaultdict(Counter)
    for r in rows:
        if r["verdict"] == "UNPARSED":
            c["unparsed"] += 1
            continue
        if r["label"] == "correct":
            c["correct_total"] += 1
            if r["verdict"] == "INCORRECT":
                if r.get("cex_valid"):
                    c["correct_rejected_real_divergence"] += 1
                else:
                    c["correct_rejected_false"] += 1
        else:
            c["wrong_total"] += 1
            c[f"wrong_{r['kind']}_total"] += 1
            by_group[r["group"]]["total"] += 1
            if r["verdict"] == "CORRECT":
                c["wrong_accepted"] += 1
                c[f"wrong_{r['kind']}_accepted"] += 1
                by_group[r["group"]]["accepted"] += 1
            elif r.get("cex_valid"):
                c["wrong_rejected_with_valid_cex"] += 1
    per_prog = defaultdict(set)
    for r in rows:
        if r["verdict"] != "UNPARSED":
            per_prog[r["program"]].add(r["verdict"])
    c["programs_with_mixed_verdicts"] = sum(1 for s in per_prog.values() if len(s) > 1)
    c["programs_judged"] = len(per_prog)
    print(f"\n=== {judge}: {len(rows)} verdicts")
    print(f"  correct programs rejected: {c['correct_rejected_false']}/{c['correct_total']} false"
          f" (+{c['correct_rejected_real_divergence']} with a counterexample that really diverges)")
    print(f"  wrong programs accepted:   {c['wrong_accepted']}/{c['wrong_total']}"
          f"  [visible {c['wrong_visible_accepted']}/{c['wrong_visible_total']}, silent {c['wrong_silent_accepted']}/{c['wrong_silent_total']}]")
    print(f"  wrong rejected with a valid counterexample: {c['wrong_rejected_with_valid_cex']}")
    print("  by error group:", {g: f"{v['accepted']}/{v['total']} accepted" for g, v in by_group.items()})
    print(f"  programs with different verdicts across repeats: {c['programs_with_mixed_verdicts']}/{c['programs_judged']}; unparsed {c['unparsed']}")
    return {**c, "by_group": {g: dict(v) for g, v in by_group.items()}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", choices=sorted(JUDGES))
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0, help="smoke test: only the first N programs")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        report()
    else:
        if a.limit:
            _orig = collect_programs
            collect_programs = lambda: dict(list(_orig().items())[:a.limit])  # noqa: E731
        run(a.judge, a.repeats)
