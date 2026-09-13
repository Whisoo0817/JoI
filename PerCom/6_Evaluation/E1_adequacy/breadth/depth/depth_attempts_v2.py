"""E1 depth additions — v2 encodings after the author semantic audit.

Written after depth_cases_v2.py / fixture_v2.py were hashed and committed (commit 85d3ab8).
v1 encodings in depth_attempts.py are imported read-only; a case reuses its v1 IR when the author approved it.
Each case lists its deployed automations. Every automation is one Timeline IR; `joi` is its separately
lowered JoI block (hand-lowered 1:1, used where the deployment is part of the adjudicated result).
"""
from depth_attempts import ATTEMPTS as V1

ATTEMPTS = {}


def _reuse(cid, label, reason):
    ATTEMPTS[cid] = dict(label=label, label_reason=reason, source="v1 IR reused unchanged",
                         automations=[dict(name="main", ir=V1[cid]["ir"])])


# ─────────────────────────────────────────────────────────────────────────────
# E1-092 — two independent automations
_TRIGGER = {"op": "wait", "cond": "House[House_Hub].ShutdownRequested == true", "edge": "rising"}
ATTEMPTS["E1-092"] = dict(
    label="complete via multi-Timeline decomposition",
    label_reason=("The two flows share no state, join or ordering, so they are deployed as two Timeline IRs with the "
                  "same trigger. Under rule T7 the injected Alexa failure stops only automation A. This is not "
                  "fork-join or shared-state parallelism inside one Timeline; v1 (single Timeline, 0/1) stays recorded."),
    source="v2 encoding",
    history=["v1: single Timeline interleaving both flows (depth_attempts.py) — 0/1, Alarm.Set missing.",
             "v2 (below): automation A = Alexa flow, automation B = house flow; each lowered to its own JoI block."],
    automations=[
        dict(name="A_alexa", ir={"timeline": [
            {"op": "start_at", "anchor": "now"}, dict(_TRIGGER),
            {"op": "call", "target": "Alexa[Echo].AnnounceTasks", "args": {}},
            {"op": "delay", "duration": "1 SEC"},
            {"op": "call", "target": "Alexa[Echo].AnnounceNews", "args": {}},
            {"op": "delay", "duration": "1 SEC"},
            {"op": "call", "target": "Alexa[Echo].AnnounceAlarmSettings", "args": {}}]},
             joi=V1["E1-092"]["joi"]["blocks"][0]),
        dict(name="B_house", ir={"timeline": [
            {"op": "start_at", "anchor": "now"}, dict(_TRIGGER),
            {"op": "call", "target": "Lights[Downstairs_Lights].Off", "args": {"Area": "downstairs"}},
            {"op": "delay", "duration": "1 SEC"},
            {"op": "call", "target": "Locks[Door_Locks].Lock", "args": {"Doors": "front, back"}},
            {"op": "delay", "duration": "1 SEC"},
            {"op": "call", "target": "Alarm[Alarm_Panel].Set", "args": {"Mode": "armed"}}]},
             joi=V1["E1-092"]["joi"]["blocks"][1]),
    ])

# ─────────────────────────────────────────────────────────────────────────────
_reuse("E1-095", "complete for fixed-cardinality aggregation",
       ("Five snapshot reads at 10-14 h and (v1+...+v5)/5 at 15 h satisfy the fixed interpretation. The refused "
        "accumulator attempt in v1 is kept as evidence of a separate boundary: no general mutable accumulator or "
        "input-dependent aggregation inside Timeline IR (general statistics are delegated to a backend service)."))
_reuse("E1-028", "complete for the fixed bound of two",
       "Two parity-indexed timestamp slots are equivalent to 'fewer than two dispenses in the rolling 4 h' for bound 2 only.")
_reuse("E1-062", "complete", "Approved as v1: previous-state snapshot, four guarded branches, no feedback commands.")
_reuse("E1-086", "complete", "Approved as v1: timeout-abort stages; switching off cancels and closes both zones.")

# ─────────────────────────────────────────────────────────────────────────────
# E1-099 — motion first at the deadline instant
_DEADLINE = "Clock.Timestamp >= $t_on + 300 + 120 * $k"
ATTEMPTS["E1-099"] = dict(
    label="complete", source="v2 encoding",
    label_reason="Same deadline arithmetic as v1; the branch order now tests motion before the deadline.",
    history=["v1: deadline tested first; at a motion on the deadline instant it turns the light off (kept as audit "
             "evidence, rerun on the new history below).",
             "v2 (below): motion branch first; the deadline branch runs only when no motion is present."],
    automations=[dict(name="main", ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "cycle", "until": None, "period": "0 MSEC", "body": [
            {"op": "wait", "cond": "Switch[Hall_Light].Switch == true", "edge": "rising"},
            {"op": "read", "var": "t_on", "src": "Clock.Timestamp"},
            {"op": "cycle", "until": None, "period": "0 MSEC", "count": "k", "body": [
                {"op": "wait", "cond": f"MotionSensor[Hall_Motion].Motion == true or {_DEADLINE}", "edge": "none"},
                {"op": "if", "cond": "MotionSensor[Hall_Motion].Motion == true",
                 "then": [
                     {"op": "read", "var": "t_m", "src": "Clock.Timestamp"},
                     {"op": "wait", "cond": "MotionSensor[Hall_Motion].Motion == false", "edge": "none"}],
                 "else": [
                     {"op": "if", "cond": "$t_m == null or Clock.Timestamp - $t_m >= 120",
                      "then": [{"op": "call", "target": "Switch[Hall_Light].Off", "args": {}}]},
                     {"op": "break"}]},
            ]},
        ]}]})],
)

# ─────────────────────────────────────────────────────────────────────────────
# E1-034 — repeating policy
ATTEMPTS["E1-034"] = dict(
    label="complete", source="v2 encoding",
    label_reason=("A cycle repeats: sustained 4 h wait, alert, confirmation wait with a 1-minute timeout whose branch "
                  "turns the oven off. A confirmation ends the iteration, so the next 4 h wait starts at that instant."),
    history=["v1: one-shot; after a confirmation nothing further happens (kept; rerun on the new history below).",
             "v2 (below): the same steps inside a cycle."],
    automations=[dict(name="main", ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "cycle", "until": None, "period": "0 MSEC", "body": [
            {"op": "wait", "cond": "Oven[Kitchen_Oven].State == true", "edge": "none", "for": "4 HOUR"},
            {"op": "call", "target": "Notify[Owner_Phone].OvenOverrun", "args": {}},
            {"op": "wait", "cond": "Notify[Owner_Phone].ConfirmContinue == true", "edge": "none", "timeout": "1 MIN",
             "on_timeout": [{"op": "call", "target": "Oven[Kitchen_Oven].Off", "args": {}}]},
        ]}]})],
)

# ─────────────────────────────────────────────────────────────────────────────
# E1-072 — platform daylight input
_P = "PresenceSensor[Home_Presence].Presence"
ATTEMPTS["E1-072"] = dict(
    label="complete", source="v2 encoding",
    label_reason="Same presence-transition snapshot as v1; the time guards read Sun.IsDaylight instead of literal hours.",
    history=["v1: guards on Clock.Hour with literal 18 and 6 (kept; rerun on the new history below).",
             "v2 (below): guards on the platform daylight input."],
    automations=[dict(name="main", ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "cycle", "until": None, "period": "0 MSEC", "body": [
            {"op": "read", "var": "p_prev", "src": _P},
            {"op": "wait", "cond": f"{_P} != $p_prev", "edge": "none"},
            {"op": "if", "cond": f"{_P} == true and Sun[Sun_Env].IsDaylight == false",
             "then": [{"op": "call", "target": "Switch[Light1,Light2].On", "args": {}}]},
            {"op": "if", "cond": f"{_P} == false and Sun[Sun_Env].IsDaylight == true",
             "then": [{"op": "call", "target": "Switch[Light1,Light2,Light3].Off", "args": {}}]},
        ]}]})],
)

# v1 encodings rerun on histories added in v2, as audit evidence of what the adjudication changed
V1_EVIDENCE = {"E1-099": ["motion_at_deadline_instant"],
               "E1-034": ["C_confirm_restart_then_no_response"],
               "E1-072": ["later_sunrise_from_environment"]}
