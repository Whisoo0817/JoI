# E2 hand inspection (2026-09-14)

**Reading guide (2026-09-14).** The reported numbers use the 140-pair population (`handoff_timer/e2_population.json`:
`C03_008/llm` and `C20_011/llm` are invalid inputs) and are in the last section, "Final version". The sections before
it are development records written at each stage on the 142 frozen pairs; their counts and pair lists (for example
the 8 witness-confirmed pairs of the frozen stage) are not the final ones.

Inputs: `runs/e2_run.ref-frozen.jsonl`, `runs/e2_run.ref-current.jsonl` (tables in `RESULTS.md`). Every pair whose
agreement is not a plain AGREE / EXPLORER-REFUSED / EXPLORER-TIMEOUT, and every pair the reference does not
support, was inspected. Explorer verdicts were not changed; the reference was not changed.

## Summary

- FALSE-EQUIV-CANDIDATE: **0** with both reference versions.
- FALSE-DIVERGE-CANDIDATE: 1 with the frozen reference (C05_014/llm), 0 with the current reference. The frozen
  reference refused the witness on `None <= 18`; with the author decision (None ordered comparison = false) the
  witness diverges on the reference.
- EXPLORER-DIVERGE-CONFIRMED-BY-REF-ON-WITNESS: 8 (current). In each, the reference found no difference on its own
  histories (REF-EQUIV-CHECKED), and the Explorer witness, replayed on the reference, shows a difference. The
  pairs are really different; the reference histories missed the input. None is an Explorer error.
- Frozen vs current: 9 pairs differ, all witness replays refused by the frozen reference on a None ordered
  comparison (C03 ×3, C11 ×3, C20-O ×2, C05_014). Reference outcomes on the pairs' own histories are identical.
- REF-UNSUPPORTED: 3 LLM JoI programs outside the reference's supported inputs (below).
- **No Explorer error was found.** D4 (fixed-version rerun) is not triggered.

## Witness-confirmed divergences missed by the reference histories

| pair | difference (from the witness replay) | why the histories missed it |
|---|---|---|
| E1-086/fault2 (timing) | Zone 2 opens at 630 s in IR, not in JoI (gap 60 s instead of 30 s) | needs the first run of the switch held past 630 s; the only seed cancels at 301 s (see the supplement section) |
| E1-086/fault3 (order) | cancel at 630.1 s: Close order Zone1, Zone2 vs Zone2, Zone1 | same: no history cancels inside zone 2 |
| E1-086/fault4 (guard) | cancel at 600.1 s during the gap: IR closes both valves, JoI does not | same: no history cancels inside the 30 s gap |
| C05_014/llm | start state Living presence true, Bedroom temp −40, Living temp None: IR (binding Bedroom sensor) sets both ACs, JoI `(#TemperatureSensor)` reads Living sensor | one-shot program; one start state (all defaults) |
| C05_028/llm | start state dust 100, mode auto: JoI `all(#Speaker)` speaks on every speaker, IR on Warehouse speaker | one-shot program; one start state |
| C16_007/llm | presence true at 22:00: IR switches three lights, JoI `all(#LevelControl)` one | one-shot program; one start state |
| C16_011/llm | Phone charger fullyCharged, Main charger None: JoI `all(...) ==|` (any) turns off both, IR checks the bound Main charger | pulses vary only IR-compared values (Main charger) |
| C21_003/llm | start state Living motion true, Bedroom false: IR speaks, JoI checks `#Bedroom` twice | one-shot program; one start state |

## Reference-unsupported pairs

| pair | Explorer | reference detail | note |
|---|---|---|---|
| C08_032/llm | DIVERGE | `selector-no-device: (#Hall_Light_1)` | JoI names devices absent from the inventory; witness replay IR ok, JoI unsupported |
| C24_003/llm | DIVERGE | — (resolved by R14, see below) | top-level `n = n + 1` on an uninitialized variable |
| C20_011/llm | REFUSED | `capability: LivingRoom_TV lacks category Charger` | both sides refuse |

### C24_003/llm after R14 (author decision 2026-09-16)

The script initializes `n` with `n := 0` only inside a branch it does not take on the first iteration, then runs
`n = n + 1` at the top level. The specification said nothing about arithmetic on a variable that has no value, so the
reference returned REF-UNSUPPORTED and this pair was the one decided verdict no independent run confirmed. The
execution contract now states (RUNTIME_CONTRACT R14) that such an arithmetic operation is a runtime error: the
instance stops there for good and the stop is observable. Both tools follow the rule.

On every one of the 301 reference histories the JoI stops at the first period tick while the IR keeps running and
speaks at 600 s, 720 s and 840 s, so the reference now reports REF-DIVERGE with an ACTION difference, not only the
error itself. The Explorer verdict is DIVERGE before and after the rule; the agreement moves from
`DIVERGE-WITNESS-ir:ok joi:unsupported` to `AGREE-DIVERGE`. A definite-assignment check over all 142 frozen pairs
finds no other program that can reach the rule, and an A/B rerun of the reference over the frozen histories (old
code vs R14 code) leaves every other pair's outcome unchanged. The 382 E3 inputs contain no program that reaches it
either, so the E3 numbers are untouched.

## Other checked rows

- C09/fault4 (edge-at-start): EQUIV on both sides; the fault is unobservable by construction (analysed when the
  fault was written).

## Weakness of the reference EQUIV side (to report)

REF-EQUIV-CHECKED means "no difference on the generated histories", not a proof. 8 of 59 REF-EQUIV-CHECKED pairs
were shown different by an Explorer witness. Two causes, both in the history generator, not in the interpreters:

1. **One start state.** Almost every case has a single t=0 state (all defaults). One-shot programs evaluate their
   condition once at start, so a condition is exercised only under the default state. Among the 36
   AGREE-EQUIV-ON-CHECKED pairs, 5 are one-shot `if` programs checked this way (C03_027, C05_021, C06_007,
   C07_027, C07_029); their EQUIV agreement is weak.
2. **Seed-bound pulses, pulse cap and IR-only compared values.** Pulses add one excursion to a seed, so a behaviour
   the seeds never enter (E1-086: a first run longer than 301 s) is not reached. At most 300 pulse histories per case
   are kept (e.g. 300 of 98,544 for C07). Pulses vary only the values the IR compares, not the other devices a JoI
   selector may read.

## Supplementary histories (PROTOCOL_DRAFT §9, run 2026-09-14 after the frozen run)

The current reference was rerun on 39,245 supplementary histories (start-state assignments and uncapped pulses)
for the 59 pairs that were REF-EQUIV-CHECKED on the frozen histories. Explorer verdicts unchanged.

- **FALSE-EQUIV-CANDIDATE: still 0.** All 36 Explorer-EQUIV pairs stay EQUIV on the supplementary histories.
- 5 pairs now diverge on the reference's own histories: C05_014, C05_028, C16_007, C16_011, C21_003 (all
  llm, all Explorer DIVERGE). They move from EXPLORER-DIVERGE-CONFIRMED-BY-REF-ON-WITNESS to AGREE-DIVERGE. Each is the
  start-state gap named above.
- C03_008/llm: the reference refuses the JoI on the supplementary start states (REF-UNSUPPORTED-JOI, 3 histories);
  the Explorer refused the pair too.
- E1-086 fault2/3/4 stay EQUIV on the supplement (1,206 more pulses, all that the pulse rule generates).
  - Why the histories miss them: the only seed turns the switch on at 1 s and off at 301 s. Both programs stop at
    that cancel (`break`). A pulse cannot lengthen that first run without overlapping the seed's own change, and it
    is skipped when it would.
  - Measured: the first on-stretch is at most 301.0 s in every frozen and supplementary history. Later stretches
    reach 1,199.9 s, but they come after both programs have ended.
  - These 3 remain EXPLORER-DIVERGE-CONFIRMED-BY-REF-ON-WITNESS. The pair difference is real (confirmed on the
    reference with the Explorer witness), but this history rule cannot reach it.
- Combined agreement (142 pairs): AGREE-EQUIV 36, AGREE-DIVERGE 63, confirmed by witness 3, witness on
  reference-unsupported JoI 2, Explorer REFUSED 25, TIMEOUT 13.
- Run note: the first supplementary run stopped with the session after 57 of 59 pairs, before writing its output.

## Binding decision rerun (BINDING_DECISION_2026-09-14.md, after the frozen and supplementary runs)

whisoo decided that E2 checks time, state and logic only: selectors, tags, device IDs/categories, device counts and
any/all must not decide a verdict (B1/B2), and when one service has several binding device sets a pair is equal if
some selector assignment is equal (B5). Both tools were changed (reference by the separate agent from the decision
text; Explorer by the session author). Tables: `RESULTS.md` "Binding decision"; rows: `runs/e2_run.binding-final.jsonl.gz`.

- **FALSE-EQUIV-CANDIDATE 0, FALSE-DIVERGE-CANDIDATE 0.**
- Explorer: DIVERGE 57 / EQUIV 48 / REFUSED 24 / TIMEOUT 13. Agreement: AGREE-EQUIV 48, AGREE-DIVERGE 50, confirmed by
  witness 6, witness on reference-unsupported JoI 1 (C24_003; AGREE-DIVERGE after R14), REFUSED 24, TIMEOUT 13.
- 16 pairs changed. Each change was checked against the pair's code:
  - B1/B2 (selector only, logic identical): C03_008 (`any(#Speaker).speaker_stop()`), C05_014, C05_028, C12_013
    (`all(#Siren)` also hits the floor-2 siren), C15_019 (`all(#WindowCovering)` also opens the bedroom curtain),
    C16_003 (`all(#RobotVacuumCleaner)` also starts the bedroom vacuum), C16_007, C16_011 → EQUIV on both tools.
  - C08_032: the reference now runs the JoI (device-ID selectors) and confirms the Explorer witness. The remaining
    difference is timing, not binding: the IR reacts to the door at 100 ms, the JoI polls every 1 s.
  - B5 (one selector points at another bound slot): C21_003 (JoI reads `#Bedroom` twice), C16/fault1 (turns off the
    light instead of the TV), E1-062/fault3 (turns off B instead of A), E1-086/fault3 (Close order of two different
    valves swapped; whisoo accepted this as a binding difference) → EQUIV on both tools. The three fault pairs are
    reported as **out of scope: binding**, not as missed faults.
  - C16/fault2–4: under two of the four selector assignments the JoI reads the TV switch, which the IR never reads, so
    the histories give it no value and the reference cannot run those assignments (REF-UNSUPPORTED-JOI). The
    Explorer witness is confirmed on the reference.
- Pre-measurement on the 22 pairs with selector assignments (Explorer, all assignments): every logic fault
  (E1-062 f1·f2·f4, C16 f2–f4, E1-072 f1–f4, E1-086 f1·f2·f4) is DIVERGE under every assignment (E1-086 f2: all 1,024).
- Run note: the combined run shared the machine with two other jobs. C05/fault2 and C05/fault3 reached the 120 s wall
  budget (TIMEOUT) instead of the 400,000-state cap; rerun alone they are REFUSED at the state cap as in the frozen run.
  The recorded rows use the quiet rerun and keep the loaded result as `explorer_under_load`.

Run note (supplementary histories): `run_supplement.py` was changed to save each finished pair and was rerun in full;
its outcomes on the 57 pairs match the first run's log (`runs/run_supplement.log`).

## Final version: exploration optimizations + binding contract (140 pairs; the reported numbers)

Explorer from the merged timer branch (Codex: semantics-preserving exploration optimizations; merged `24d7b1a`)
with B1/B2/B5 on, same budget. The reference code did not change, so its outcomes are reused from the
binding-contract run; every new Explorer witness was replayed on the reference. Rows: `runs/e2_run.timer-binding.jsonl.gz`.
Population: 140 pairs (`handoff_timer/e2_population.json`).

- **Excluded inputs (not in any count):** `C03_008/llm` uses `any(...)` in ACTION position. By author decision
  (2026-09-14) `any(...)` is allowed only inside a condition (`if`, `loop`, `wait until`), so this is a syntax error. A parser change in `0e76584` had accepted it for bound services; that change was withdrawn and
  both the Explorer parser and the reference (SPEC_GAPS G35) now reject it. `C20_011/llm` reads a Charger capability the
  TV does not declare (invalid service mapping); both tools refuse it.
- **FALSE-EQUIV-CANDIDATE 0, FALSE-DIVERGE-CANDIDATE 0.** Explorer: DIVERGE 75 / EQUIV 55 / REFUSED 5 / TIMEOUT 5.
- Decided 130 = confirmed 130 (AGREE-EQUIV 55, AGREE-DIVERGE 67, confirmed by witness 8). C24_003/llm is in
  AGREE-DIVERGE since the R14 decision of 2026-09-16 (see above); before it the reference could not run that JoI.
- Before the optimizations the same Explorer decided 104 of the 140 pairs under the same budget and binding contract.
  26 pairs moved from undecided to decided (C01/fault2, C05/fault2–3, C13_006, C14_003, C15 correct/fault1,
  C18/correct, C19/correct, C20-O correct/fault1, E1-028 ×5, E1-034 ×5, E1-095 ×5); all agree with the reference, and
  none of the 104 earlier verdicts changed.
  - C14_003/llm: DIVERGE confirmed by witness. The JoI increments its counter every tick instead of every press; the
    reference histories never changed the button value (history-generator gap noted above).
  - C15/fault1 (`h < 6` → `h <= 6`): DIVERGE confirmed by witness; the reference histories never pass 06:xx.
- The 8 witness-confirmed pairs: C08_032, C14_003, C15/fault1, E1-086/fault2·4 (no reference history reaches the
  diverging input) and C16/fault2–4 (the JoI reads a device value the histories do not supply, so the reference
  cannot run it on its histories).
- Undecided (10): C07 ×5 (TIMEOUT at the 120 s budget: nested repetition and timers), E1-099 ×5 (REFUSED: deadline
  `t_on + 300 + 120·k` grows with the number of motion episodes).
- Of 75 fault pairs with an observed difference (reference histories or witness), the Explorer gives DIVERGE for 69,
  EQUIV for none, and leaves 6 undecided (C07 f1–f4, E1-099 f1·f3). The other 6 fault pairs show no difference on
  either side: C09/fault4, C16/fault1, E1-062/fault3, E1-086/fault3, E1-099/fault2·4.
