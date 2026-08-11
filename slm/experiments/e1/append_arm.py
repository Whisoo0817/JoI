# -*- coding: utf-8 -*-
"""append-only interleave arm.

The full-rewrite interleave arm degrades hard with turn index (parse failure
7% -> 52% by turn 4) because the model must re-emit an ever longer timeline.
Here each turn emits ONLY the new steps, so output length is constant in the
number of turns. Nesting is expressed as a 3-way closed choice instead of a
free-form path:

    {"into": "top" | "last_then" | "last_body", "append": [ <step>, ... ]}

Grammar spec and device/service block are IDENTICAL to the other arms — the
only difference is what the model is asked to emit.
"""
import copy, json, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prompts as P  # noqa: E402

TAIL = 'Output ONLY the JSON object of the form {"into": ..., "append": [...]}.'

NOTE = """\
You extend a Timeline IR one clause at a time.
You are given the timeline built from the previous clauses and ONE new clause.
Emit ONLY the NEW steps that this clause adds — never repeat existing steps.
Choose where they attach with "into":
  "top"       - append at the end of the top-level timeline
  "last_then" - append inside the "then" branch of the most recent if step
  "last_body" - append inside the "body" of the most recent cycle step
If the clause adds nothing, emit {"into":"top","append":[]}."""

FEWSHOT = [
    # 1. first clause: anchor + action at top level
    ({"devices": "Office_Plug: [Switch]\nOffice_Light: [Light, Switch]",
      "done": [], "state": [],
      "next": "평일 저녁 7시에 사무실 조명을 켜고"},
     {"into": "top", "append": [{"op": "start_at", "anchor": "cron", "cron": "0 19 * * 1-5"},
                                {"op": "call", "target": "Switch.On", "args": {}}]}),
    # 2. a condition opens a branch
    ({"devices": "Office_Temp: [TemperatureSensor]\nOffice_AC: [AirConditioner, Switch]",
      "done": ["평일 저녁 7시에 사무실 조명을 켜고"],
      "state": [{"op": "start_at", "anchor": "cron", "cron": "0 19 * * 1-5"},
                {"op": "call", "target": "Switch.On", "args": {}}],
      "next": "온도가 28도를 넘으면"},
     {"into": "top", "append": [{"op": "if", "cond": "TemperatureSensor.Temperature > 28",
                                 "then": [], "else": []}]}),
    # 3. the action of that condition goes INSIDE the branch
    ({"devices": "Office_Temp: [TemperatureSensor]\nOffice_AC: [AirConditioner, Switch]",
      "done": ["평일 저녁 7시에 사무실 조명을 켜고", "온도가 28도를 넘으면"],
      "state": [{"op": "start_at", "anchor": "cron", "cron": "0 19 * * 1-5"},
                {"op": "call", "target": "Switch.On", "args": {}},
                {"op": "if", "cond": "TemperatureSensor.Temperature > 28", "then": [], "else": []}],
      "next": "에어컨을 제습 모드로 돌린 뒤 30분 후에 꺼줘."},
     {"into": "last_then", "append": [
         {"op": "call", "target": "AirConditioner.SetAirConditionerMode", "args": {"Mode": "dry"}},
         {"op": "delay", "duration": "30 MIN"},
         {"op": "call", "target": "Switch.Off", "args": {}}]}),
]


def _user(devices, done, state, nxt):
    d = "\n".join("%d. %s" % (i + 1, c.strip()) for i, c in enumerate(done)) \
        if done else "(none — this is the first clause)"
    return ("[Devices]\n%s\n\n[Clauses done]\n%s\n\n[Timeline so far]\n%s\n\n"
            "[Next clause]\n%s\n\n%s") % (
        devices.strip(), d, json.dumps({"timeline": list(state or [])}, ensure_ascii=False),
        nxt.strip(), TAIL)


def build_append_messages(done_clauses, next_clause, ir_so_far, devices):
    msgs = [{"role": "system", "content": P.SPEC + "\n\n" + NOTE}]
    for u, a in FEWSHOT:
        msgs.append({"role": "user",
                     "content": _user(u["devices"], u["done"], u["state"], u["next"])})
        msgs.append({"role": "assistant", "content": json.dumps(a, ensure_ascii=False)})
    msgs.append({"role": "user", "content": _user(devices, done_clauses, ir_so_far, next_clause)})
    return msgs


def _last_with(state, key):
    """Most recently added step (depth-first, latest first) owning `key`."""
    for st in reversed(state):
        if isinstance(st, dict):
            for sub in ("body", "then"):
                if isinstance(st.get(sub), list):
                    hit = _last_with(st[sub], key)
                    if hit is not None:
                        return hit
            if isinstance(st.get(key), list):
                return st
    return None


def apply_append(state, obj):
    """Return a NEW state with obj's steps attached. Tolerant of shape drift."""
    state = copy.deepcopy(list(state or []))
    if not isinstance(obj, dict):
        return state, "not a dict"
    steps = obj.get("append")
    if steps is None:                      # tolerate a bare timeline / list
        steps = obj.get("timeline") if isinstance(obj.get("timeline"), list) else None
    if steps is None and isinstance(obj.get("steps"), list):
        steps = obj["steps"]
    if not isinstance(steps, list):
        return state, "no append list"
    steps = [s for s in steps if isinstance(s, dict) and "op" in s]
    into = obj.get("into", "top")
    if into == "last_then":
        host = _last_with(state, "then")
        if host is not None:
            host["then"] = list(host.get("then") or []) + steps
            return state, None
    elif into == "last_body":
        host = _last_with(state, "body")
        if host is not None:
            host["body"] = list(host.get("body") or []) + steps
            return state, None
    state.extend(steps)
    return state, None


if __name__ == "__main__":
    st = []
    for obj in [{"into": "top", "append": [{"op": "start_at", "anchor": "now"}]},
                {"into": "top", "append": [{"op": "if", "cond": "A > 1", "then": [], "else": []}]},
                {"into": "last_then", "append": [{"op": "call", "target": "X.On", "args": {}}]},
                {"into": "last_then", "append": [{"op": "cycle", "until": None,
                                                  "period": "5 MIN", "body": []}]},
                {"into": "last_body", "append": [{"op": "call", "target": "Y.Off", "args": {}}]},
                {"garbage": True}]:
        st, err = apply_append(st, obj)
        print("err=%-14s state=%s" % (err, json.dumps({"timeline": st}, ensure_ascii=False)))
    print()
    for m in build_append_messages(["가"], "나", [{"op": "start_at", "anchor": "now"}], "D: [Light]")[-1:]:
        print(m["content"][:500])
