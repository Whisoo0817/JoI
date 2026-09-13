# E2 — Validation fidelity: protocol draft (2026-09-14, not frozen)

Question: when the Explorer says EQUIV or DIVERGE for a Timeline IR / JoI pair, does an independent reference agree?

Decisions so far (whisoo 2026-09-14):
- Reference = option (b): a separate executable semantics for **both** Timeline IR and JoI that shares no code with
  the Explorer.
- Pairs = correct alternative JoI implementations + hand-written faulty implementations per fault family + real LLM
  errors from the 388 candidates (no "development" label needed; provenance still stated).
- The remaining 72 E1 depth cases are on hold.

## 1. Independent reference (option b)

### 1.1 Independence rules

- Written only from the specification documents in §1.2. Explorer runtime/verification source (`explorer/runtime/*`,
  `explorer/verification/*`, `explorer/analysis/*`) is not read while writing the reference.
- No imports from `explorer`, `timeline_ir`, or `lowering` except the ANTLR-generated deployment grammar parser
  (`lowering/parser/generated/JOILang*.py`, from `JOILang.g4`), which Explorer's own `runtime/joi_parser.py` does
  not use. The catalog JSON is read directly.
- An import check (test) fails if any forbidden module is imported.
- Its own history enumerator and trace comparison; `explorer/tests/oracles/exact_*` are not used (they share the
  one-step runners).
- The reference is frozen (commit + hash) before any pair is run through it and the Explorer. A later fix to the
  reference is a new version with a written reason taken from the spec, never from an Explorer result.

### 1.2 Specification sources (the reference follows these)

| Source | Covers |
|---|---|
| `explorer/docs/model/RUNTIME_CONTRACT.md` R1–R13 | input grid, timers, wait position, period, tie order, edge latch, `:=`, reads, ACTION, termination |
| `explorer/docs/model/VERIFICATION_CONTRACT.md` (time/reaction, ACTION observation, inputs) | trace definition, fan-out normal form, number/string equality, BOOL two values, DOUBLE 0.1 grid |
| `explorer/docs/model/SERVICE_MODEL.md` | read-role functions, argument order/type/range, return domains |
| `docs/JOI_SPEC.md`, `files/joi_common.md` cheat-sheet | JoI selectors (`(#A #B)` intersection, `all`, `any`), quantifier operators `op|`, `delay`, `wait until`, string concat |
| `lowering/parser/JOILang.g4` | JoI syntax |
| `files/timeline_ir/extractor.md` "Step Grammar" and D-rules | Timeline IR ops and fields |
| `PerCom/3_Timeline_IR/HANDOFF.md` "E1 에서 확정된 실행 의미" | period after body, initial-true edge fires, no latch during other waits, cron erased, uninitialised = null |
| `files/service_list_ver2.0.7.json` (+ E1 fixture stubs) | catalog |
| `explorer/docs/proof/FRONTEND_CORRECTNESS.md` §1–§3 | query vs ACTION position, expression precedence, fixed binding meaning: inventory-order device list, `any`/`all`/`op|`, fan-out, `Service#2` slots |
| `docs/VETS_verification_contract_decisions_2026-09-07.md` D1–D9 | fan-out order, edge at start, fixed binding, termination is not an ACTION |

### 1.3 Scope

Both interpreters cover the constructs that occur in the E2 pairs, not the whole of JoI:

- Timeline IR: `start_at`, `wait` (`edge`, `for`, `timeout`, `on_timeout`), `delay`, `read`, `call` (incl. `var`),
  `if`, `cycle` (`until`, `period`, `count`), `break`. (These eight ops are all that the 388 dataset and the E1 IRs use.)
- JoI: assignment `=` / `:=`, action calls with `(#tags)`, `all(...)`, `any(...)`, `if`/`else`, `wait until`,
  `delay`, `break`, arithmetic `+ - * /` (and `%` if a pair uses it), comparisons incl. `op|`, `and/or/not`,
  string concat, Clock reads, `period` and `cron` in the block. In the 388 candidates: `loop` and `for` do not occur;
  the reference refuses them.
- Anything else → the reference reports `REF-UNSUPPORTED` for that pair (kept in the denominator, reported apart).

### 1.4 Points the specifications leave open (proposed answer; confirm before coding)

| # | Point | Proposed answer | Basis |
|---|---|---|---|
| S1 | IR `cycle`: order of `until` check and `period` | body → wait `period` → check `until` → next body; first `until` check before the first body | extractor "until exits before each iteration"; R5 period from body completion |
| S2 | IR `cycle.count`: value in the first body, when incremented | 0 in the first body, +1 after each body | extractor D7c "tick-index 0/1/2" |
| S3 | IR `wait.for` + `edge: rising` | rising edge starts the sustain timer; a false resets it and requires a new rising edge | extractor D5.5 re-arming form |
| S4 | IR `wait.timeout` expiry vs condition true at the same instant | condition first (input snapshot applied first, R6) | R6 |
| S5 | JoI `all(#X).Attr op v` without `|` | true iff every matching device satisfies it; with `|` true iff at least one does; `any(#X).Attr op v` = `all(#X).Attr op| v` | JOI_SPEC 1.4 |
| S6 | JoI `(#A)` matching several devices | unique `Main` tag if present, else the first device in `connected_devices` order | VERIFICATION_CONTRACT "Main, 아니면 정해진 첫 후보" (order = inventory order is our reading) |
| S7 | JoI `/` on two integers | real division (DOUBLE result) | not stated; to confirm |
| S8 | Number → string in concat | integers without decimal point, DOUBLE in shortest decimal form (`23.5`, `1.0`) | VERIFICATION_CONTRACT keeps `1` vs `1.0` distinct |
| S9 | JoI top-level `break` in a `period > 0` script | terminates the instance (R13) | R13 |
| S10 | JoI `wait until` in a `period > 0` script | blocks at its position across ticks (R4); no abort-tick | R4 |

## 2. Pairs

| Source | What | Label |
|---|---|---|
| Correct alternatives | a JoI implementation of a confirmed IR in a different idiom (flag vs previous/current, `:=` counter vs loop shape, etc.) | reference result |
| Hand-written faults | one change per fault family: missing/extra call, timing, snapshot value, order, sustain reset, edge re-arming, repetition state | reference result (a fault that turns out to be unobservable is reported as such, not relabelled) |
| Real LLM candidates | sample from the 388 `gemma4-26b-contract-v1-fresh-v4` candidates **without using the Explorer verdict** (e.g. random per category among generated scripts) | reference result |

Base IRs: see open decision D2.

## 3. Histories and bounds

The reference answers only on the histories it runs; see open decision D1. Reference EQUIV means "no difference on
the checked histories", never an unbounded certificate. Reference DIVERGE on a history inside the Explorer's input
model is a real difference in that model.

## 4. Outcomes and metrics

Per pair: Explorer verdict (EQUIV / DIVERGE / REFUSED / INCONCLUSIVE / error) × reference result (EQUIV-on-checked /
DIVERGE with witness / REF-UNSUPPORTED / reference error). Reported separately:
- false EQUIV (Explorer EQUIV, reference DIVERGE) — each one investigated and shown with its history;
- false DIVERGE (Explorer DIVERGE, reference EQUIV on the Explorer's own witness history);
- refusals, incomplete, errors — never counted as false verdicts;
- per fault family detection table; one history-dependent counterexample in the paper.

## 5. Freeze and change policy

- Explorer commit fixed before the run. See open decision D4 for what happens if a disagreement is an Explorer bug.
- Pair set, histories and reference frozen (hash) before running either tool on them.

## 6. Decisions D1–D4 (whisoo 2026-09-14)

- **D1 histories: boundary-structured histories at the original time scale.** Inputs change only a few times; the
  change instants are taken around every literal duration and threshold crossing (just before, at, just after, on the
  100 ms grid), and all combinations of those instants and input values are run. No time scaling.
- **D2 base IRs: E1 depth 20 + a sample of the 388.** Correct alternatives and hand-written faults are built on the
  E1 20 IRs; real LLM errors come from the 388 sample with their dataset IRs.
- **D3 reference scope: the whole JoI grammar** (`JOILang.g4`), including `loop` and `for`. §1.3's "constructs in the
  pairs" restriction is withdrawn. Constructs whose meaning no spec states need an author definition first (§1.4).
- **D4 Explorer bug: report the frozen-version result as found, and also rerun a fixed version**, reporting both.

## 7. Reference semantics decisions (whisoo 2026-09-14)

- **S1–S10: confirmed as proposed** in §1.4.
- **S11 calendar origin:** logical `t = 0 ms` is Monday 00:00:00; `Hour = (t // 3600000) % 24`, `Minute = (t // 60000) % 60`,
  `Weekday = ["monday", …, "sunday"][(t // 86400000) % 7]`, `Timestamp = t // 1000`, no DST (E1 `cases.py` header uses
  the same origin). Day/Month/Year are not defined by any spec; the reference refuses them.
- **L1 `loop (cond) stmt` / `loop () stmt`** (defined from whisoo's two examples):
  - `cond` is evaluated before every iteration on the current input snapshot; an empty condition is always true.
  - `break` exits the nearest enclosing `loop` (or the script when there is none, R13).
  - `delay` / `wait until` inside the body block at their position (R3/R4); later iterations see later snapshots.
  - Iterations with no blocking statement continue at the same logical time; if one reaction does not finish
    (iteration cap), the reference reports an error for that history rather than a trace.
  - In a `period > 0` script, a `loop` still running blocks the next period tick (R5, no overlap).
- **`for (x : list)`: excluded.** The reference reports REF-UNSUPPORTED (whisoo: `for` exists to iterate `all(...)`
  devices and is not used now).

## 8. Author independence

The session author (Claude) has read Explorer runtime code in earlier sessions. The reference interpreters are therefore
written by a separate agent that is given only the §1.2 specification files, this protocol and the E1 case records
(IR-free expected traces), and is told not to open `explorer/runtime`, `explorer/verification`, `explorer/analysis`,
`timeline_ir/*.py`, or `lowering/*.py` other than the generated parser. The agent logs every file it opens; the log is
kept with the reference. Independence is claimed at the level of code and author, not of the specification: the
reference and the Explorer follow the same written contract, so a wrong contract is not detected by E2.
