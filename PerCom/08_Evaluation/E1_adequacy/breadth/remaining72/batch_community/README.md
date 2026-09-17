# Remaining community cases: 17 requests, 52 frozen histories

Agent interpretation and reference execution, 2026-09-17. These decisions were inferred autonomously from the source records and the prior20 conventions under the author's explicit instruction. They have not received a new independent author semantic audit.

The source-linked interpretation, assumptions, alternatives/possible favorable bias, raw inputs, and expected timed actions are in `cases.py` and `frozen_cases.json`. `FREEZE.json` hashes `cases.py` before `attempts.py` was created. The final run reproduces52/52 frozen histories exactly under the unchanged reference executor and legacy T5 same-time multiset comparison. This is finite trace evidence for the declared interpretations, not a proof of all-input behavior.

Run from repository root:

```sh
/home/gnltnwjstk/temp/bin/python PerCom/08_Evaluation/E1_adequacy/breadth/remaining72/run_batch.py batch_community
```

`runs/results.json` retains lowered IR, bindings, frontend/grammar results, expected/actual traces and exact/tolerance comparisons. `archive/` retains the initial encoding and failed first run; changes fix the encoding or honor an already-frozen per-history clock origin, without changing any expected action. `ENCODING_REVISIONS.md` records those repairs. `runs/archive/` additionally keeps previous run outputs on rerun.

## Material interpretation qualifications

- E1-078: the opening post's prohibition on turning on after HA turns off is underspecified. The chosen conservative reading latches a lockout until manual light-on, consistent with the source thread's helper-state suggestion. This blocks even genuine later motion until manual rearm. It is not a generic inference of which lux changes were caused by the lamp. The final author reply in the thread instead adjusted the lux threshold and timer configuration; that later variant is not substituted for the corpus's opening request.
- E1-081: the first reminder is five minutes after arrival, not immediate. Departure at the deadline cancels the reminder.
- E1-084: daily schedule edges are expressed by Clock.Weekday/Hour comparisons. Three histories use different declared absolute origins (Monday, Friday, Sunday). No cron is erased. No startup reconciliation is requested.
- E1-089: the source's final YAML controls startup and threshold crossings with overlapping numeric thresholds. Its startup branch order is preserved; this is source fidelity, not a claim that the source's astronomy policy is unambiguous or universally correct.
- E1-093/094/097: independent flows are multiple deployed Timelines, following prior E1-092. This supports fixed independent flows only. E1-094's fade is a declared stepped sequence, not a simulation of physical continuous fading.
- E1-096: two sensors and one selected notification device instantiate a fixed selected set. Unknown status is a raw availability observation; the IR checks threshold/availability itself. No fixture performs a battery-history query, dynamic discovery or aggregate formatting.
- All other unspecified constants, branch conditions and timing/re-entry choices are explicit in `cases.py`; they are agent assumptions rather than externally measured facts.

## Source checks during interpretation

The corpus supplies the source URL and opening-post locator for all cases. Four original pages were reread to resolve substantial questions before freezing: [E1-078](https://community.home-assistant.io/t/combination-of-motion-and-illuminance-sensor-to-control-light-bulb/995590), [E1-079](https://community.home-assistant.io/t/trigger-automation-every-minute-unless-it-has-been-triggered-by-something-else/864628), [E1-089](https://community.home-assistant.io/t/evolution-of-an-automation-turn-a-light-on-off-at-sunset-sunrise/302465), and [E1-090](https://community.home-assistant.io/t/turn-something-on-for-a-set-time/670621). The frozen record stores the corpus normalization, not a falsely labeled verbatim quote.

## Measurement limits

Typed leaf fixtures expose raw states/events and atomic output commands. Timing, counts, threshold combinations and retries remain in the IR. Commands do not automatically change an observed state; feedback histories explicitly list such changes. No Explorer certification or hardware behavior is measured. JoI fallback is unnecessary for these successfully encoded, explicitly qualified interpretations.

## Later parent-review sensitivity checks

Four separately frozen histories exposed gaps in a candidate that had passed all52 initial histories. The prior candidate fails all4; IR repairs pass all4 and retain52/52 on the initial set. The additional checks cover initial-true edge rearming, startup inside a calendar window, a button held longer than its off deadline, and startup midway through a scheduled minute. The before/after traces and freeze are kept separately and do not inflate the original52 denominator. This illustrates the limitation of finite examples; no all-input correctness result is inferred.
