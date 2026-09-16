"""E1 depth additions — encoding attempts (current Timeline IR, unchanged) and JoI fallbacks.

Written after depth_cases.py and fixture.py were hashed and committed (commit 6f2c040).
Device atoms are written `Svc[Dev,...].Member`; run_depth.lower() turns them into plain IR plus the
binding table. `history` keeps every attempt in order, including refused or diverging ones.
JoI fallbacks are written only for cases whose Timeline result is partial or impossible.
"""

ATTEMPTS = {}

# ─────────────────────────────────────────────────────────────────────────────
# E1-092 independent parallel shutdown flows
# ─────────────────────────────────────────────────────────────────────────────
ATTEMPTS["E1-092"] = dict(
    lang="impossible",
    lang_reason=("Timeline IR has one control flow. Both command sequences must be interleaved in that flow, so the "
                 "injected failure of Alexa.AnnounceNews ends the only instance and with it the house-shutdown "
                 "commands still to come. The language has no parallel composition and, by decision, no "
                 "error-handling or availability construct may be added."),
    history=["v1 (below): the two sequences interleaved step by step at their frozen 1 s spacing."],
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "wait", "cond": "House[House_Hub].ShutdownRequested == true", "edge": "rising"},
        {"op": "call", "target": "Alexa[Echo].AnnounceTasks", "args": {}},
        {"op": "call", "target": "Lights[Downstairs_Lights].Off", "args": {"Area": "downstairs"}},
        {"op": "delay", "duration": "1 SEC"},
        {"op": "call", "target": "Alexa[Echo].AnnounceNews", "args": {}},
        {"op": "call", "target": "Locks[Door_Locks].Lock", "args": {"Doors": "front, back"}},
        {"op": "delay", "duration": "1 SEC"},
        {"op": "call", "target": "Alexa[Echo].AnnounceAlarmSettings", "args": {}},
        {"op": "call", "target": "Alarm[Alarm_Panel].Set", "args": {"Mode": "armed"}},
    ]},
    joi=dict(
        note=("Two JoI blocks deployed side by side, both started by the same request. JoI scripts have no in-script "
              "parallel construct either; independence comes from the platform running two automation instances, "
              "and the injected failure ends only the instance that issued the failing command."),
        blocks=[
            dict(name="alexa_flow", period=0, script=(
                "wait until((#Home #House).ShutdownRequested == true)\n"
                "(#LivingRoom #Alexa).AnnounceTasks()\n"
                "delay(1 SEC)\n"
                "(#LivingRoom #Alexa).AnnounceNews()\n"
                "delay(1 SEC)\n"
                "(#LivingRoom #Alexa).AnnounceAlarmSettings()")),
            dict(name="house_flow", period=0, script=(
                "wait until((#Home #House).ShutdownRequested == true)\n"
                "(#Downstairs #Lights).Off(\"downstairs\")\n"
                "delay(1 SEC)\n"
                "(#Entrance #Locks).Lock(\"front, back\")\n"
                "delay(1 SEC)\n"
                "(#Home #Alarm).Set(\"armed\")")),
        ]),
)

# ─────────────────────────────────────────────────────────────────────────────
# E1-095 internal accumulation of a daily average
# ─────────────────────────────────────────────────────────────────────────────
_READS = []
for i in range(1, 6):
    _READS += [{"op": "read", "var": f"ph{i}", "src": "PoolPH[Pool_PH].Value"},
               {"op": "read", "var": f"cl{i}", "src": "PoolChlorine[Pool_Chlorine].Value"},
               {"op": "delay", "duration": "1 HOUR"}]

ATTEMPTS["E1-095"] = dict(
    lang="partial",
    lang_reason=("The required mechanism, internal sum += value and count += 1, cannot be written: Timeline IR has no "
                 "assignment, and `read` only copies a catalog attribute into a variable. The fixed five-sample window "
                 "can be expressed by unrolling five pairs of reads and averaging them in the call argument, which "
                 "reproduces the frozen trace but depends on the sample count being a literal; it is not accumulation."),
    history=["attempt A: accumulate with `read` whose source is an expression over the running sum (kept below as a "
             "refused attempt, compiled by run_depth.py so the refusal is reproduced).",
             "v1 (below): five unrolled reads, one daily cycle, mean computed in the call arguments.",
             "JoI v1 used device-id selectors `(#Pool_PH)`; the catalog check refused it before execution "
             "(`unknown catalog value: pool_ph.value`: JoI takes the service from the last selector tag). "
             "JoI v2 ended each selector with the category tag and sampled on `Minute == 0 and Second == 0`. It executed "
             "but reported nothing (0/1): the reference executor's clock (explorer.runtime.interp.clock_state) provides "
             "timestamp, hour, minute and weekday only, so `(#Clock).Second` is null although the catalog lists it. "
             "This is a reference-runner gap, not a JoI language limit.",
             "JoI v3 (below) samples once per hour with a persistent `last_hour` slot instead of Clock.Second."],
    refused_attempts=[dict(label="A_read_expression_as_accumulator", ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "read", "var": "sum_ph", "src": "$sum_ph + PoolPH[Pool_PH].Value"},
    ]})],
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "cycle", "until": None, "period": "0 MSEC", "body": [
            {"op": "wait", "cond": "Clock.Hour == 10", "edge": "none"},
            *_READS,
            {"op": "call", "target": "Pool[Pool_Report].ReportDailyQuality",
             "args": {"MeanPH": "($ph1 + $ph2 + $ph3 + $ph4 + $ph5) / 5",
                      "MeanChlorine": "($cl1 + $cl2 + $cl3 + $cl4 + $cl5) / 5"}},
            {"op": "wait", "cond": "Clock.Hour != 15", "edge": "none"},
        ]}]},
    joi=dict(
        note=("Ordinary JoI mutable variables: `:=` slots persist across ticks and are updated with `=`. The block "
              "runs every second and accumulates the reading taken at each full hour from 10 to 14, then reports "
              "sum/count at 15:00 and resets. No history or statistics service is used."),
        blocks=[dict(name="accumulate_and_report", period=1000, script=(
            "sum_ph := 0\n"
            "sum_cl := 0\n"
            "count := 0\n"
            "last_hour := -1\n"
            "h = (#Clock).Hour\n"
            "if (h >= 10 and h <= 14 and h != last_hour) {\n"
            "    sum_ph = sum_ph + (#Pool #PoolPH).Value\n"
            "    sum_cl = sum_cl + (#Pool #PoolChlorine).Value\n"
            "    count = count + 1\n"
            "    last_hour = h\n"
            "}\n"
            "if (h == 15 and count > 0) {\n"
            "    (#Pool_Report #Pool).ReportDailyQuality(sum_ph / count, sum_cl / count)\n"
            "    sum_ph = 0\n"
            "    sum_cl = 0\n"
            "    count = 0\n"
            "}"))]),
)

# ─────────────────────────────────────────────────────────────────────────────
# E1-086 cancelable sequential sprinklers
# ─────────────────────────────────────────────────────────────────────────────
_RUN = "Switch[Sprinkler_Run].Switch"
_CANCEL = [{"op": "call", "target": "Valve[Zone1_Valve].Close", "args": {}},
           {"op": "call", "target": "Valve[Zone2_Valve].Close", "args": {}},
           {"op": "break"}]

ATTEMPTS["E1-086"] = dict(
    lang="complete",
    lang_reason="E-TIMEOUT-ABORT: each timed stage is a wait for the off condition with the stage length as timeout.",
    history=["v1 (below)."],
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "cycle", "until": None, "period": "0 MSEC", "body": [
            {"op": "wait", "cond": f"{_RUN} == true", "edge": "rising"},
            {"op": "call", "target": "Valve[Zone1_Valve].Open", "args": {}},
            {"op": "wait", "cond": f"{_RUN} == false", "edge": "none", "timeout": "10 MIN"},
            {"op": "if", "cond": f"{_RUN} == false", "then": list(_CANCEL)},
            {"op": "call", "target": "Valve[Zone1_Valve].Close", "args": {}},
            {"op": "wait", "cond": f"{_RUN} == false", "edge": "none", "timeout": "30 SEC"},
            {"op": "if", "cond": f"{_RUN} == false", "then": list(_CANCEL)},
            {"op": "call", "target": "Valve[Zone2_Valve].Open", "args": {}},
            {"op": "wait", "cond": f"{_RUN} == false", "edge": "none", "timeout": "10 MIN"},
            {"op": "if", "cond": f"{_RUN} == false", "then": list(_CANCEL)},
            {"op": "call", "target": "Valve[Zone2_Valve].Close", "args": {}},
            {"op": "break"},
        ]}]},
)

# ─────────────────────────────────────────────────────────────────────────────
# E1-099 manual light with motion extension
# ─────────────────────────────────────────────────────────────────────────────
_DEADLINE = "Clock.Timestamp >= $t_on + 300 + 120 * $k"

ATTEMPTS["E1-099"] = dict(
    lang="complete",
    lang_reason=("E-STAMP + named counter: the deadline is t_on + 300 s + 120 s x (motions so far); the inner cycle's "
                 "counter k counts motion iterations, so each motion extends the existing deadline instead of "
                 "restarting a timer."),
    history=["v1 (below)."],
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "cycle", "until": None, "period": "0 MSEC", "body": [
            {"op": "wait", "cond": "Switch[Hall_Light].Switch == true", "edge": "rising"},
            {"op": "read", "var": "t_on", "src": "Clock.Timestamp"},
            {"op": "cycle", "until": None, "period": "0 MSEC", "count": "k", "body": [
                {"op": "wait", "cond": f"MotionSensor[Hall_Motion].Motion == true or {_DEADLINE}", "edge": "none"},
                {"op": "if", "cond": _DEADLINE,
                 "then": [
                     {"op": "if", "cond": "$t_m == null or Clock.Timestamp - $t_m >= 120",
                      "then": [{"op": "call", "target": "Switch[Hall_Light].Off", "args": {}}]},
                     {"op": "break"}],
                 "else": [
                     {"op": "read", "var": "t_m", "src": "Clock.Timestamp"},
                     {"op": "wait", "cond": "MotionSensor[Hall_Motion].Motion == false", "edge": "none"}]},
            ]},
        ]}]},
)

# ─────────────────────────────────────────────────────────────────────────────
# E1-028 rolling-window feeder limit
# ─────────────────────────────────────────────────────────────────────────────
_ROOM = ("$ta == null or Clock.Timestamp - $ta >= 14400 or "
         "$tb == null or Clock.Timestamp - $tb >= 14400")

ATTEMPTS["E1-028"] = dict(
    lang="complete",
    lang_reason=("Only the two most recent dispenses matter for 'fewer than two in the window'. They are kept in two "
                 "timestamp slots written alternately by the parity of the dispense counter (E-STAMP, E-NULL), so the "
                 "slot not being overwritten always holds the other recent dispense. No assignment is needed."),
    history=["v1 (below)."],
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "cycle", "until": None, "period": "0 MSEC", "count": "n", "body": [
            {"op": "cycle", "until": None, "period": "0 MSEC", "body": [
                {"op": "wait", "cond": "Feeder[Pet_Feeder].DispenseRequested == true", "edge": "rising"},
                {"op": "if", "cond": _ROOM, "then": [{"op": "break"}]},
            ]},
            {"op": "call", "target": "Feeder[Pet_Feeder].Dispense", "args": {"Portion": "one_bowl"}},
            {"op": "if", "cond": "$n % 2 == 0",
             "then": [{"op": "read", "var": "ta", "src": "Clock.Timestamp"}],
             "else": [{"op": "read", "var": "tb", "src": "Clock.Timestamp"}]},
        ]}]},
)

# ─────────────────────────────────────────────────────────────────────────────
# E1-034 oven overrun confirmation
# ─────────────────────────────────────────────────────────────────────────────
ATTEMPTS["E1-034"] = dict(
    lang="complete",
    lang_reason="Sustained wait for four hours, then a confirmation wait whose timeout branch turns the oven off.",
    history=["v1 (below)."],
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "wait", "cond": "Oven[Kitchen_Oven].State == true", "edge": "none", "for": "4 HOUR"},
        {"op": "call", "target": "Notify[Owner_Phone].OvenOverrun", "args": {}},
        {"op": "wait", "cond": "Notify[Owner_Phone].ConfirmContinue == true", "edge": "none", "timeout": "1 MIN",
         "on_timeout": [{"op": "call", "target": "Oven[Kitchen_Oven].Off", "args": {}}]},
    ]},
)

# ─────────────────────────────────────────────────────────────────────────────
# E1-072 home and away lighting
# ─────────────────────────────────────────────────────────────────────────────
_P = "PresenceSensor[Home_Presence].Presence"

ATTEMPTS["E1-072"] = dict(
    lang="complete",
    lang_reason="E-PREV snapshot detects either transition in one flow; each rule keeps its own clock guard.",
    history=["v1 (below)."],
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "cycle", "until": None, "period": "0 MSEC", "body": [
            {"op": "read", "var": "p_prev", "src": _P},
            {"op": "wait", "cond": f"{_P} != $p_prev", "edge": "none"},
            {"op": "if", "cond": f"{_P} == true and (Clock.Hour >= 18 or Clock.Hour < 6)",
             "then": [{"op": "call", "target": "Switch[Light1,Light2].On", "args": {}}]},
            {"op": "if", "cond": f"{_P} == false and Clock.Hour >= 6 and Clock.Hour < 18",
             "then": [{"op": "call", "target": "Switch[Light1,Light2,Light3].Off", "args": {}}]},
        ]}]},
)

# ─────────────────────────────────────────────────────────────────────────────
# E1-062 bidirectional light synchronization
# ─────────────────────────────────────────────────────────────────────────────
_A, _B = "Switch[LightA].Switch", "Switch[LightB].Switch"

ATTEMPTS["E1-062"] = dict(
    lang="complete",
    lang_reason="E-PREV snapshot tells which light changed; the four source rules become four guarded branches.",
    history=["v1 (below)."],
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "cycle", "until": None, "period": "0 MSEC", "body": [
            {"op": "read", "var": "a_prev", "src": _A},
            {"op": "read", "var": "b_prev", "src": _B},
            {"op": "wait", "cond": f"{_A} != $a_prev or {_B} != $b_prev", "edge": "none"},
            {"op": "if", "cond": f"{_A} == true and $a_prev == false and {_B} == false",
             "then": [{"op": "call", "target": "Switch[LightB].On", "args": {}}]},
            {"op": "if", "cond": f"{_A} == false and $a_prev == true and {_B} == true",
             "then": [{"op": "call", "target": "Switch[LightB].Off", "args": {}}]},
            {"op": "if", "cond": f"{_B} == true and $b_prev == false and {_A} == false",
             "then": [{"op": "call", "target": "Switch[LightA].On", "args": {}}]},
            {"op": "if", "cond": f"{_B} == false and $b_prev == true and {_A} == true",
             "then": [{"op": "call", "target": "Switch[LightA].Off", "args": {}}]},
        ]}]},
)
