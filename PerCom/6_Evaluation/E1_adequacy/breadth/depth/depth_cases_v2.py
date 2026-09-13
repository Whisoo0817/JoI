"""E1 depth additions — v2 case records after the author semantic audit. NO TIMELINE IR, NO JoI.

Source of the changes: AUTHOR_ADJUDICATION_2026-09-13.md. Written and hashed before any v2 encoding.
`depth_cases.py` (v1) is imported read-only and never edited; rules T1–T7 there apply unchanged.

What changes relative to v1
  E1-092  history and expected trace unchanged; only the encoding changes (two independent automations).
  E1-099  interpretation adds "motion first at the same instant"; history `motion_at_deadline_instant` added.
  E1-034  interpretation becomes the repeating policy; history `C_confirm_restart_then_no_response` added.
  E1-072  interpretation reads a platform daylight input; every history supplies `Sun_Env.IsDaylight`;
          history `later_sunrise_from_environment` added (sunrise 07:30 in that run).
  others  identical to v1 (records copied, not re-derived).
"""
import copy

import depth_cases as v1
from depth_cases import S, M, H, T0, dev, act

CASES = [copy.deepcopy(c) for c in v1.CASES]
BY_ID = {c["id"]: c for c in CASES}


def _note(cid, text):
    BY_ID[cid].setdefault("v2_changes", []).append(text)


# ─────────────────────────────────────────────────────────────────────────────
# E1-092 — unchanged record; encoding changes only
_note("E1-092", "record unchanged; v2 encodes two independent automations (author adjudication)")

# ─────────────────────────────────────────────────────────────────────────────
# E1-099 — motion first when motion and deadline coincide
c = BY_ID["E1-099"]
c["spec"] += (" If a motion event and the current deadline fall on the same instant, the motion is handled first: the "
              "deadline is extended by two minutes and the automation continues. Reaching the extended deadline later "
              "without further motion turns the light off.")
c["transcription"] = c["transcription"] + [
    "'no motion during the preceding two minutes' counts motion onsets in (deadline - 2 min, deadline]; an onset "
    "exactly 2 min before the deadline is outside. This follows from the adjudication: each motion extends the "
    "deadline by exactly 2 min, and the extended deadline reached without later motion must turn the light off."]
c["histories"].append(dict(
    name="motion_at_deadline_instant", kind="boundary", step_ms=100, horizon=T0 + 10 * M,
    events=[(0, {"Hall_Light.Switch": False, "Hall_Motion.Motion": False}),
            (T0, {"Hall_Light.Switch": True}),
            (T0 + 5 * M, {"Hall_Motion.Motion": True}), (T0 + 5 * M + S, {"Hall_Motion.Motion": False})],
    expected=[act(T0 + 7 * M, "Switch.Off", [], "Hall_Light")]))
_note("E1-099", "added same-instant history; motion-first interpretation")

# ─────────────────────────────────────────────────────────────────────────────
# E1-034 — repeating policy
c = BY_ID["E1-034"]
c["spec"] = ("Repeating policy. After the oven has been on for four hours, send a confirmation alert. If no "
             "ContinueConfirmed input arrives within one minute, turn the oven off. If it arrives, keep the oven on, "
             "restart the four-hour timer from that moment, and repeat.")
c["transcription"] = c["transcription"] + [
    "`ContinueConfirmed` is the platform-delivered button event, i.e. the E1 stub input Notify.ConfirmContinue",
    "the restarted four-hour period is measured from the confirmation instant",
    "histories A and B are v1's; under the repeating policy their expected traces within the horizon are unchanged"]
c["histories"].append(dict(
    name="C_confirm_restart_then_no_response", kind="boundary", step_ms=1000, horizon=T0 + 8 * H + 2 * M + 30 * S,
    events=[(0, {"Kitchen_Oven.State": False, "Owner_Phone.ConfirmContinue": False}),
            (T0, {"Kitchen_Oven.State": True}),
            (T0 + 4 * H + 30 * S, {"Owner_Phone.ConfirmContinue": True}),
            (T0 + 4 * H + 31 * S, {"Owner_Phone.ConfirmContinue": False})],
    expected=[act(T0 + 4 * H, "Notify.OvenOverrun", [], "Owner_Phone"),
              act(T0 + 8 * H + 30 * S, "Notify.OvenOverrun", [], "Owner_Phone"),
              act(T0 + 8 * H + M + 30 * S, "Oven.Off", [], "Kitchen_Oven")]))
_note("E1-034", "repeating policy; added confirm -> restart -> no response history")

# ─────────────────────────────────────────────────────────────────────────────
# E1-072 — platform daylight input instead of literal clock hours
c = BY_ID["E1-072"]
c["spec"] = ("On transition to HOME, turn on light1 and light2 only when it is not daylight (between sunset and "
             "sunrise). On transition to AWAY, turn off light1, light2 and light3 only when it is daylight (between "
             "sunrise and sunset). Daylight is a platform-provided environment input; sunrise and sunset times are "
             "values of a particular run, not part of the automation.")
c["stubs"] = c["stubs"] + ["Sun.IsDaylight (BOOL environment input, fixture_v2.py)"]
c["devices"] = {**c["devices"], **dev("Sun_Env", "Sun", "Home")}
c["transcription"] = [t for t in c["transcription"] if not t.startswith("sunrise 06:00")] + [
    "Sun_Env.IsDaylight is the platform daylight flag; history `night_home_then_day_away` sets sunrise 06:00 and "
    "sunset 18:00 as that run's environment values"]
h = c["histories"][0]                               # Mon 18:59:59 start; Tue 06:00 = T0 + 11 h
h["events"] = [(t, {**u, "Sun_Env.IsDaylight": False}) if t == 0 else (t, u) for t, u in h["events"]]
h["events"].append((T0 + 11 * H, {"Sun_Env.IsDaylight": True}))
h["events"].sort(key=lambda e: e[0])
c["histories"].append(dict(
    name="later_sunrise_from_environment", kind="boundary", step_ms=1000, horizon=T0 + 13 * H + M,
    events=[(0, {"Home_Presence.Presence": False, "Sun_Env.IsDaylight": False}),
            (T0 + 12 * H, {"Home_Presence.Presence": True}),            # Tue 07:00 HOME, still dark
            (T0 + 12 * H + 30 * M, {"Sun_Env.IsDaylight": True}),       # sunrise 07:30 in this run
            (T0 + 13 * H, {"Home_Presence.Presence": False})],          # Tue 08:00 AWAY, daylight
    expected=[act(T0 + 12 * H, "Switch.On", [], "Light1"), act(T0 + 12 * H, "Switch.On", [], "Light2"),
              act(T0 + 13 * H, "Switch.Off", [], "Light1"), act(T0 + 13 * H, "Switch.Off", [], "Light2"),
              act(T0 + 13 * H, "Switch.Off", [], "Light3")]))
_note("E1-072", "daylight environment input; added later-sunrise history")

CASE_BY_ID = BY_ID
