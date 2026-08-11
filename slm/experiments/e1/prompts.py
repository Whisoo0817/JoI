# -*- coding: utf-8 -*-
"""E1 prompt builders — batch / marked / interleave arms.

FAIRNESS CONTRACT (do not break this without re-running all arms):
  * All three arms share the byte-identical grammar spec ``SPEC``.
  * All three arms get 3 few-shot demonstrations built from the SAME synthetic
    example data (``_EXAMPLES`` / ``_STEP_EXAMPLE``), covering the same three
    phenomena: (a) a cron-anchored call, (b) a whenever-trigger wait+cycle with
    two calls, (c) an if/then containing a duration.
  * The ONLY thing that differs between arms is the GRANULARITY at which the
    command is presented (whole / bar-marked / one clause per turn) plus the
    3-5 line "## Input" note that explains that granularity.
  * All few-shot commands are hand-written synthetic Korean commands invented
    for this file. Nothing is taken from dataset.csv (see the leak check in
    ``__main__``).

Run standalone:
    /home/ikess/joi-llm/venv_llama/bin/python prompts.py
"""

from __future__ import annotations

import json

__all__ = [
    "SPEC",
    "FEWSHOT_BATCH",
    "FEWSHOT_MARKED",
    "FEWSHOT_STEP",
    "build_batch_messages",
    "build_marked_messages",
    "build_step_messages",
    "format_devices",
    "USE_SYSTEM_ROLE",
]

# If the served chat template rejects a system role (e.g. Gemma), flip this to
# False: the spec is then prepended to the first user message instead. The
# rendered text is otherwise identical, so arms stay comparable either way.
USE_SYSTEM_ROLE = True


# ---------------------------------------------------------------------------
# Shared grammar spec (distilled from files/ir_extractor.md; pipeline-specific
# parts — [Resolved Args], [Command Hints], [Bind Hints], R-rules — dropped)
# ---------------------------------------------------------------------------

SPEC = """\
# Timeline IR extractor
Convert a Korean IoT command into a Timeline IR JSON object.
Output ONLY one JSON object, no prose, no markdown, no code fences:
  {"timeline":[<step>, <step>, ...]}
If the command cannot be expressed, output {"error":"<reason>"} instead.

## The 8 step ops
1. {"op":"start_at","anchor":"now"}
   {"op":"start_at","anchor":"cron","cron":"<min> <hour> <dom> <mon> <dow>"}
   Exactly one start_at, always the first step of the timeline.
2. {"op":"wait","cond":"<expr>","edge":"none"|"rising","for":"<N UNIT>"?}
   Blocks until cond becomes true. Optional "for" = cond must stay true
   continuously for that long (only for "N분 동안 계속/유지되면"). A plain pause
   is `delay`, never wait.for.
3. {"op":"delay","duration":"<N UNIT>"}  UNIT in HOUR|MIN|SEC|MSEC, one space: "5 MIN".
4. {"op":"read","var":"<name>","src":"<Category.Attr>"}
   Use only when one attribute is compared at two different moments, or when a
   text argument must embed a device value as $name. Otherwise put Category.Attr
   straight into the expression.
5. {"op":"call","target":"<Category.Method>","args":{...}}
6. {"op":"if","cond":"<expr>","then":[...],"else":[]}   else may be empty.
7. {"op":"cycle","until":"<expr>"|null,"period":"<N UNIT>","count":"<name>"?,"body":[...]}
   period is REQUIRED. body describes ONE iteration. until is tested before each
   iteration. count is a tick index 0,1,2,... (only for alternation or a repeat cap).
8. {"op":"break"}   exits the nearest cycle.

## Expressions (wait.cond, if.cond, cycle.until)
- Device attribute: Category.Attr, category taken from [Devices]. NEVER a device id.
- Literals: numbers 30 / 3.14 ; quoted strings "open" "cool" "saturday" ; true ; false.
  Enum / mode / state values MUST be quoted: Door.DoorState == "open"  (not == open).
- Variables: $name for a read result; a cycle count var is written bare: n % 2 == 0.
- Operators: + - * / ( ) == != < > <= >= abs(x) and the WORDS and / or / not.
  NEVER && || ! . Forbidden: min max floor ceil round Math.* and any()/all().
- Every cond is a complete boolean expression with a comparator:
  "MotionSensor.Motion == true", never the bare "MotionSensor.Motion".
- Date/time in a cond uses the Clock service, never a time string:
  Clock.Hour 0-23, Clock.Minute 0-59, Clock.Day 1-31, Clock.Month 1-12, Clock.Year (integers)
  Clock.Weekday is a lowercase quoted enum: Clock.Weekday == "saturday"
  Window end at a whole hour H  -> "Clock.Hour >= H" only, no Minute term.
  Window end at H시 M분 (M != 0) -> "Clock.Hour > H or (Clock.Hour == H and Clock.Minute >= M)"

## Targets and args
- target / src are "Category.Method", Category being a category listed in [Devices].
  Never a device id (WRONG: Living_Light.On), never a category that is not listed.
- Generic power / level / color members live on their sub-service, not on the parent
  category: Switch.On, Switch.Off, Switch.Toggle, LevelControl.MoveToLevel,
  ColorControl.MoveToColor. WRONG: Light.On, Fan.Switch, Speaker.Switch.
  Category-specific methods keep their category: Washer.SetWasherMode, Speaker.Speak.
- ONE call covers every device a clause targets ("침실 조명 모두 켜줘" = one call).
  Device scope (모두 / 아무 / 태그 / 층·구역) is resolved by a later stage and NEVER
  appears in the IR: no Selector / Scope / Target / Devices / Tags key in args.
- args uses the method's own argument names; use {} when the method takes none.

## Cron
5 fields: minute hour day-of-month month day-of-week. MINUTE IS FIRST.
Copy the stated minutes exactly. 오후/PM adds 12, 오전 12시 = 0, 자정 = "0 0 * * *".
  오후 6시 -> "0 18 * * *"   아침 7시 30분 -> "30 7 * * *"   밤 11시 -> "0 23 * * *"
Day-of-week field is digits 1-7 (1=월 ... 7=일), never names, never 0:
  매일 / no day phrase -> *    월요일 -> 1    월·수 -> 1,3    주말 -> 6,7    평일 -> 1-5
A stated day filter MUST survive into the 5th field; dropping it is an error.
A specific date (크리스마스, 1월 1일) uses fields 3 and 4 and leaves the 5th as *.

## Choosing the shape
- Wall-clock time / weekday / date (오후 6시에, 매주 월요일, 크리스마스에) -> start_at cron.
  Pure periodicity with no wall-clock anchor (5분마다, 매시간) -> start_at now +
  cycle(period="N UNIT"); never encode it as cron.  Otherwise -> start_at now.
- ~하면 / ~인 경우 / ~이면 (instantaneous state test)      -> if
- ~할 때 / ~되면 (one-shot: block until it happens)        -> wait(edge:"none") then the calls
- ~할 때마다 / 매번 / ~될 때마다 (re-arms forever)          -> cycle(period="1 SEC"){ wait(..., edge:"rising"); calls }
- ~한 뒤 그때부터 N마다 (fires once, then repeats forever)  -> wait(edge:"none") OUTSIDE the cycle,
  then cycle(period="N UNIT"){ calls }
- edge is decided by POSITION only: top-level wait -> "none", wait inside a cycle -> "rising".
  Never "falling": negate the cond instead (cond:"RainSensor.Rain == false").
- Inside a periodic (N마다) cycle a state test is `if`, never `wait`.
- After a cron start_at, a single sensor check is `if`, not a cycle.
- H시부터 H2시까지 N마다 -> start_at cron at H + cycle(until="Clock.Hour >= H2", period="N UNIT").
- K번 반복 / K회 후 중지 -> cycle(count:"n", until:"n >= K").
  A와 B를 번갈아 -> cycle(count:"n"){ if(n % 2 == 0){A} else {B} } — A and B must differ.
  토글은 하나의 동작이다: 그냥 call(Switch.Toggle), count/cycle 금지.
- 시간대: 아침·오전 6-12시, 오후 12-18시, 저녁 18-22시, 밤 22-6시.

## Order and completeness
Steps execute in written order; a delay between two actions sits between the two calls.
Keep EVERY action, condition, time, threshold, value and unit stated in the command.
Do not drop one, do not merge two into one, do not invent one that was not stated.\
"""


# --- arm-specific input notes (kept to a similar length on purpose) ---------

_NOTE_BATCH = """\
## Input
[Devices] lists the connected devices, one per line as "device_id: [Category, ...]".
[Command] is the whole Korean command, in one piece.
Read the whole command, then emit the complete timeline that covers all of it.
Output ONLY the JSON object."""

_NOTE_MARKED = """\
## Input
[Devices] lists the connected devices, one per line as "device_id: [Category, ...]".
[Command] is the whole Korean command with its clause boundaries marked by " | ".
The bars are clause boundaries, not part of the text; each clause contributes one or
more steps. Cover every clause, in order, then emit the complete timeline.
Output ONLY the JSON object."""

_NOTE_STEP = """\
## Input
[Devices] lists the connected devices, one per line as "device_id: [Category, ...]".
The command arrives one clause at a time. [Clauses done] are the clauses already folded
in, [Timeline so far] is the timeline you produced for them, [Next clause] is the new one.
Fold the next clause in and re-emit the FULL updated timeline: keep the earlier steps,
and restructure or nest them only if the new clause requires it.
Output ONLY the JSON object."""


# ---------------------------------------------------------------------------
# rendering helpers
# ---------------------------------------------------------------------------

def _j(obj) -> str:
    """Compact, deterministic, UTF-8-preserving JSON."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def format_devices(connected_devices) -> str:
    """OPTIONAL convenience for the runner (builders never call it).

    Turns dataset.csv's ``connected_devices`` JSON (str or dict) into the
    "device_id: [Category, ...]" listing the few-shots use. Deterministic:
    insertion order preserved. Whatever the runner decides to pass, it must
    pass the SAME string to all three arms.
    """
    if isinstance(connected_devices, str):
        connected_devices = json.loads(connected_devices, strict=False)
    lines = []
    for dev_id, info in connected_devices.items():
        cats = info.get("category", []) if isinstance(info, dict) else list(info)
        lines.append("%s: [%s]" % (dev_id, ", ".join(cats)))
    return "\n".join(lines)


_TAIL = "Output ONLY the JSON object."


def _batch_user(cmd: str, devices: str) -> str:
    return "[Devices]\n%s\n\n[Command]\n%s\n\n%s" % (devices.strip(), cmd.strip(), _TAIL)


def _marked_user(marked_cmd: str, devices: str) -> str:
    return "[Devices]\n%s\n\n[Command] (clauses separated by \" | \")\n%s\n\n%s" % (
        devices.strip(), marked_cmd.strip(), _TAIL,
    )


def _step_user(done_clauses, next_clause: str, ir_so_far, devices: str) -> str:
    done = "\n".join("%d. %s" % (i + 1, c.strip()) for i, c in enumerate(done_clauses)) \
        if done_clauses else "(none — this is the first clause)"
    return (
        "[Devices]\n%s\n\n[Clauses done]\n%s\n\n[Timeline so far]\n%s\n\n"
        "[Next clause]\n%s\n\n%s"
    ) % (devices.strip(), done, _j({"timeline": list(ir_so_far or [])}),
         next_clause.strip(), _TAIL)


# ---------------------------------------------------------------------------
# Few-shot source data — 100% hand-written synthetic. NOT from dataset.csv.
# The batch and marked arms render these same three examples; the only
# difference is whether the clauses are joined with " " or with " | ".
# ---------------------------------------------------------------------------

_EXAMPLES = [
    # (a) cron-anchored call — weekday-of-week digit, minute-first cron, two calls
    {
        "clauses": [
            "매주 토요일 아침 9시 30분에 세탁기를 표준 모드로 돌리고",
            "스피커로 \"세탁 시작\"이라고 알려줘.",
        ],
        "devices": "Laundry_Washer: [Washer, Switch]\n"
                   "Laundry_Dryer: [Dryer, Switch]\n"
                   "Living_Speaker: [Speaker]",
        "timeline": [
            {"op": "start_at", "anchor": "cron", "cron": "30 9 * * 6"},
            {"op": "call", "target": "Washer.SetWasherMode", "args": {"Mode": "normal"}},
            {"op": "call", "target": "Speaker.Speak", "args": {"Text": "세탁 시작"}},
        ],
    },
    # (b) whenever-trigger: wait inside a cycle, two calls in the body
    {
        "clauses": [
            "주방에서 가스가 감지될 때마다 가스 밸브를 잠그고",
            "스피커로 \"가스 경보\"라고 알려줘.",
        ],
        "devices": "Kitchen_GasSensor: [GasSensor]\n"
                   "Kitchen_Valve: [Valve, Switch]\n"
                   "Kitchen_Speaker: [Speaker]\n"
                   "Kitchen_Light: [Light, Switch, LevelControl]",
        "timeline": [
            {"op": "start_at", "anchor": "now"},
            {"op": "cycle", "until": None, "period": "1 SEC", "body": [
                {"op": "wait", "cond": "GasSensor.Gas == true", "edge": "rising"},
                {"op": "call", "target": "Valve.Close", "args": {}},
                {"op": "call", "target": "Speaker.Speak", "args": {"Text": "가스 경보"}},
            ]},
        ],
    },
    # (c) if/then containing a duration — Switch sub-service, delay between calls
    {
        "clauses": [
            "지금 지하실 일산화탄소 수치가 50을 넘으면 환풍기를 켜고",
            "20분 후 환풍기를 다시 꺼줘.",
        ],
        "devices": "Basement_CoSensor: [CarbonMonoxideSensor]\n"
                   "Basement_Fan: [Fan, Switch]\n"
                   "Basement_Window: [Window, Switch]",
        "timeline": [
            {"op": "start_at", "anchor": "now"},
            {"op": "if", "cond": "CarbonMonoxideSensor.CarbonMonoxide > 50",
             "then": [
                 {"op": "call", "target": "Switch.On", "args": {}},
                 {"op": "delay", "duration": "20 MIN"},
                 {"op": "call", "target": "Switch.Off", "args": {}},
             ],
             "else": []},
        ],
    },
]

# One synthetic 3-clause command, built up over 3 turns. Deliberately covers the
# same three phenomena as _EXAMPLES: (a) cron-anchored call, (c) if/then with a
# duration, (b) whenever wait+cycle with two calls.
_STEP_EXAMPLE = {
    "devices": "Living_Light: [Light, Switch, LevelControl]\n"
               "Living_AirConditioner: [AirConditioner, Switch]\n"
               "Living_TemperatureSensor: [TemperatureSensor]\n"
               "Living_ContactSensor: [ContactSensor]\n"
               "Living_AirPurifier: [AirPurifier, Switch]\n"
               "Living_Speaker: [Speaker]",
    "clauses": [
        "평일 저녁 7시에 거실 조명을 켜고",
        "실내 온도가 28도를 넘으면 에어컨을 제습 모드로 돌린 뒤 30분 후에 멈춰줘.",
        "그리고 창문이 열릴 때마다 공기청정기를 끄고 스피커로 \"창문 열림\"이라고 알려줘.",
    ],
    "states": [
        # after clause 1
        [
            {"op": "start_at", "anchor": "cron", "cron": "0 19 * * 1-5"},
            {"op": "call", "target": "Switch.On", "args": {}},
        ],
        # after clause 2
        [
            {"op": "start_at", "anchor": "cron", "cron": "0 19 * * 1-5"},
            {"op": "call", "target": "Switch.On", "args": {}},
            {"op": "if", "cond": "TemperatureSensor.Temperature > 28",
             "then": [
                 {"op": "call", "target": "AirConditioner.SetAirConditionerMode",
                  "args": {"Mode": "dry"}},
                 {"op": "delay", "duration": "30 MIN"},
                 {"op": "call", "target": "Switch.Off", "args": {}},
             ],
             "else": []},
        ],
        # after clause 3
        [
            {"op": "start_at", "anchor": "cron", "cron": "0 19 * * 1-5"},
            {"op": "call", "target": "Switch.On", "args": {}},
            {"op": "if", "cond": "TemperatureSensor.Temperature > 28",
             "then": [
                 {"op": "call", "target": "AirConditioner.SetAirConditionerMode",
                  "args": {"Mode": "dry"}},
                 {"op": "delay", "duration": "30 MIN"},
                 {"op": "call", "target": "Switch.Off", "args": {}},
             ],
             "else": []},
            {"op": "cycle", "until": None, "period": "1 SEC", "body": [
                {"op": "wait", "cond": "ContactSensor.Contact == \"open\"", "edge": "rising"},
                {"op": "call", "target": "Switch.Off", "args": {}},
                {"op": "call", "target": "Speaker.Speak", "args": {"Text": "창문 열림"}},
            ]},
        ],
    ],
}


def _mk_fewshot(joiner: str, user_fn) -> list:
    msgs = []
    for ex in _EXAMPLES:
        msgs.append({"role": "user",
                     "content": user_fn(joiner.join(ex["clauses"]), ex["devices"])})
        msgs.append({"role": "assistant",
                     "content": _j({"timeline": ex["timeline"]})})
    return msgs


FEWSHOT_BATCH = _mk_fewshot(" ", _batch_user)
FEWSHOT_MARKED = _mk_fewshot(" | ", _marked_user)

FEWSHOT_STEP = []
for _i, _clause in enumerate(_STEP_EXAMPLE["clauses"]):
    FEWSHOT_STEP.append({
        "role": "user",
        "content": _step_user(
            _STEP_EXAMPLE["clauses"][:_i],
            _clause,
            _STEP_EXAMPLE["states"][_i - 1] if _i > 0 else [],
            _STEP_EXAMPLE["devices"],
        ),
    })
    FEWSHOT_STEP.append({
        "role": "assistant",
        "content": _j({"timeline": _STEP_EXAMPLE["states"][_i]}),
    })
del _i, _clause


# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------

def _assemble(note: str, fewshot: list, final_user: str) -> list:
    """SPEC + arm note as system (or folded into the first user turn), then the
    shared few-shots, then the live turn."""
    head = SPEC + "\n\n" + note
    shots = [dict(m) for m in fewshot]
    last = {"role": "user", "content": final_user}
    if USE_SYSTEM_ROLE:
        return [{"role": "system", "content": head}] + shots + [last]
    first = shots[0] if shots else last
    first["content"] = head + "\n\n" + first["content"]
    return shots + [last]


def build_batch_messages(cmd: str, devices: str) -> list:
    """Arm A — the whole Korean command in one shot."""
    return _assemble(_NOTE_BATCH, FEWSHOT_BATCH, _batch_user(cmd, devices))


def build_marked_messages(marked_cmd: str, devices: str) -> list:
    """Arm B — same command, clause boundaries pre-marked inline with " | "."""
    return _assemble(_NOTE_MARKED, FEWSHOT_MARKED, _marked_user(marked_cmd, devices))


def build_step_messages(done_clauses: list, next_clause: str,
                        ir_so_far: list, devices: str) -> list:
    """Arm C — one clause per turn; model re-emits the FULL updated timeline.

    ``done_clauses`` / ``ir_so_far`` are the state after the previous turn
    (both empty on the first clause). ``ir_so_far`` is a list of steps, i.e.
    the value of the "timeline" key, not the wrapper object.
    """
    return _assemble(_NOTE_STEP, FEWSHOT_STEP,
                     _step_user(done_clauses, next_clause, ir_so_far, devices))


# ---------------------------------------------------------------------------
# self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os

    SEP = "=" * 78

    DEMO_DEVICES = ("Bedroom_Humidifier: [Humidifier, Switch]\n"
                    "Bedroom_HumiditySensor: [HumiditySensor]\n"
                    "Bedroom_Light: [Light, Switch, LevelControl]")
    DEMO_CLAUSES = [
        "밤 10시에 침실 조명을 30% 밝기로 낮추고",
        "습도가 40 미만이면 가습기를 켜줘.",
    ]
    DEMO_CMD = " ".join(DEMO_CLAUSES)
    DEMO_MARKED = " | ".join(DEMO_CLAUSES)
    DEMO_IR_SO_FAR = [
        {"op": "start_at", "anchor": "cron", "cron": "0 22 * * *"},
        {"op": "call", "target": "LevelControl.MoveToLevel", "args": {"Level": 30}},
    ]

    arms = [
        ("A batch", build_batch_messages(DEMO_CMD, DEMO_DEVICES)),
        ("B marked", build_marked_messages(DEMO_MARKED, DEMO_DEVICES)),
        ("C interleave (turn 2 of 2)",
         build_step_messages(DEMO_CLAUSES[:1], DEMO_CLAUSES[1],
                             DEMO_IR_SO_FAR, DEMO_DEVICES)),
    ]

    for name, msgs in arms:
        print(SEP)
        print("ARM %s — %d messages" % (name, len(msgs)))
        print(SEP)
        for m in msgs:
            print("--- [%s] ---" % m["role"])
            print(m["content"])
        print()

    # ---------------- size table ----------------
    print(SEP)
    print("SPEC lines: %d" % len(SPEC.splitlines()))
    print(SEP)
    print("%-28s %7s %7s %9s %9s %9s" %
          ("arm", "msgs", "shots", "chars", "~tokens", "shot~tok"))
    for name, msgs in arms:
        text = "\n".join(m["content"] for m in msgs)
        shot_text = "\n".join(
            m["content"] for m in msgs
            if m["role"] != "system" and m is not msgs[-1])
        n_shot = sum(1 for m in msgs if m["role"] == "assistant")
        print("%-28s %7d %7d %9d %9d %9d" %
              (name, len(msgs), n_shot, len(text), len(text) // 3,
               len(shot_text) // 3))

    # ---------------- leak check (read-only) ----------------
    print(SEP)
    DS = "/home/ikess/joi-llm/joi_new/dataset.csv"
    fewshot_texts = []
    for ex in _EXAMPLES:
        fewshot_texts.append(" ".join(ex["clauses"]))
    fewshot_texts.append(" ".join(_STEP_EXAMPLE["clauses"]))
    fewshot_texts.extend(c for ex in _EXAMPLES for c in ex["clauses"])
    fewshot_texts.extend(_STEP_EXAMPLE["clauses"])

    if not os.path.exists(DS):
        print("LEAK CHECK: dataset not found, skipped")
    else:
        import csv
        csv.field_size_limit(10 ** 7)
        with open(DS, encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))

        def _norm(s):
            return "".join(s.split())

        def _lcs(a, b):
            """longest common substring length"""
            prev = [0] * (len(b) + 1)
            best = 0
            for i in range(1, len(a) + 1):
                cur = [0] * (len(b) + 1)
                ai = a[i - 1]
                for jj in range(1, len(b) + 1):
                    if ai == b[jj - 1]:
                        v = prev[jj - 1] + 1
                        cur[jj] = v
                        if v > best:
                            best = v
                prev = cur
            return best

        exact = []
        worst = (0, "", "")
        for ft in fewshot_texts:
            nf = _norm(ft)
            for r in rows:
                for col in ("command_kor", "command_eng"):
                    dc = r[col]
                    nd = _norm(dc)
                    if not nd:
                        continue
                    if nd == nf or nd in nf or nf in nd:
                        exact.append((r["index"], col, dc, ft))
                    if col == "command_kor":
                        L = _lcs(nf, nd)
                        if L > worst[0]:
                            worst = (L, ft, dc)
        print("LEAK CHECK over %d dataset rows x %d few-shot strings" %
              (len(rows), len(fewshot_texts)))
        print("  exact / substring matches : %d  %s" %
              (len(exact), "OK (none)" if not exact else exact[:3]))
        print("  longest common substring  : %d chars" % worst[0])
        print("    few-shot : %s" % worst[1])
        print("    dataset  : %s" % worst[2])
