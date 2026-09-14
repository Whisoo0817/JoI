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

### Run definition (`run_e2.py`)

- **Histories:** `histories/make_e1_histories.py` (E1 20: seeds = author-audited E1 histories without E1-092
  fault injection; ±100 ms shifts; single-input pulses at IR-derived instants; same-instant two-input flips;
  ≤ 300 pulses per case, seeded) → 4,597 histories. `histories/make_388_histories.py` (40 sample: default seed from
  the reference smoke test, same pulse rules, horizon max(10 s, 3 × longest IR duration + 10 s) ≤ 6 h) → 6,980.
  Both read IR literals and seed histories only.
- **Reference outcome per pair:** REF-DIVERGE if any history with both sides ok differs; REF-EQUIV-CHECKED if every
  history ran ok on both sides with equal traces; otherwise REF-UNSUPPORTED/REF-ERROR with the side named.
- **Explorer verdict per pair:** the steps of `gate_pair` (prepare_pair → timed_product with `horizon_ms=None` →
  replay_divergence → fold_verdict), with `t0_ms = 2,419,200,000 + t_start_ms` so both tools start at the same
  clock time (gate_pair has no start-time argument); 120 s budget per pair (TIMEOUT); exceptions folded to REFUSED
  as in gate_pair. Depth IR device atoms are lowered with the E1 tool `run_depth.lower`.
- **Explorer witness:** for DIVERGE, the first confirmed witness path is converted to reference events and run on the
  reference.
- **Agreement:** AGREE-EQUIV-ON-CHECKED; AGREE-DIVERGE; FALSE-EQUIV-CANDIDATE (Explorer EQUIV, REF-DIVERGE);
  FALSE-DIVERGE-CANDIDATE (Explorer DIVERGE whose witness is equal on the reference and REF-EQUIV-CHECKED);
  EXPLORER-DIVERGE-CONFIRMED-BY-REF-ON-WITNESS (the histories missed a real difference); EXPLORER-REFUSED/TIMEOUT/
  ERROR and REF-UNSUPPORTED/ERROR kept apart. Every candidate false verdict is inspected by hand before it is
  reported as an Explorer error (it may be a reference error or a spec disagreement).

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

### Scale (whisoo 2026-09-14)

- E1 20 base IRs: one correct JoI implementation each + 3–4 single-fault JoI variants each (about 80–100 pairs).
  Fault families are spread so that each family (missing/extra call, timing, snapshot value, order, sustain reset,
  edge re-arming, repetition state) occurs on several cases; a family that does not apply to a case is not forced.
- 388 sample: 40 candidates with a generated script, chosen **without reading any Explorer outcome**: fixed seed
  20260914, up to 1 per task category (`C01`…`C26`), then the remainder uniformly at random from the rest
  (`pairs/select_388_sample.py`, output `pairs/sample_388.json`). Each is paired with its dataset IR and binding.
  (The first version said "up to 2 per category"; it failed before producing any sample because 23 categories have
  a generated script and 23 × 2 > 40. Changed to 1 per category; no candidate content or verdict was looked at.)
- All pairs and histories are frozen (hash, commit) before either the reference or the Explorer runs on them.

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

### Decisions on the reference's spec gaps (whisoo 2026-09-14; `reference/SPEC_GAPS.md`)

- **G1 selectors match `tags` only.** To select a device by its ID, that ID must be present as a tag on the device.
  (Binding and selection are fixed inputs of the experiment, not something E2 measures.)
- **G2 `(#Clock)` is the built-in clock** of S11; no Clock device is needed; `IsHoliday` stays an input.
- **G6** IR `call.args` string values by catalog argument type (number/BOOL → expression; STRING/ENUM with `$` → template)
  and **G8** binding slots `Service#k` by occurrence order in the IR: accepted as written in SPEC_GAPS.
- **Ordered comparison with a missing value (after freeze, 2026-09-14):** `>`, `<`, `>=`, `<=` with a None operand
  evaluate to false in both interpreters; equality unchanged (None equals only None). Found when Explorer witnesses
  with a missing numeric sensor value could not be replayed on the reference (C03 faults). New reference version;
  reference outcomes are recomputed and both versions are reported.
- **JoI `%` is allowed as integer remainder** in the reference, following the lowering documents (`joi_cycle.md` Ex5),
  although `JOILang.g4` has no `%`. The grammar/document mismatch is recorded as a finding.

## 8. Author independence

The session author (Claude) has read Explorer runtime code in earlier sessions. The reference interpreters are therefore
written by a separate agent that is given only the §1.2 specification files, this protocol and the E1 case records
(IR-free expected traces), and is told not to open `explorer/runtime`, `explorer/verification`, `explorer/analysis`,
`timeline_ir/*.py`, or `lowering/*.py` other than the generated parser. The agent logs every file it opens; the log is
kept with the reference. Independence is claimed at the level of code and author, not of the specification: the
reference and the Explorer follow the same written contract, so a wrong contract is not detected by E2.

## 9. Supplementary histories (after the frozen run; whisoo 2026-09-14)

**Why.** The hand inspection of the frozen run (`INSPECTION_2026-09-14.md`) found 8 pairs whose reference outcome on
the frozen histories was REF-EQUIV-CHECKED although an Explorer witness, replayed on the reference, showed a real
difference. Two causes apply to every case: almost every case has a single start state (one-shot programs test their
condition only in the default state), and at most 300 pulse histories are kept per case. whisoo decided to add a
supplementary history set and report it separately. The frozen results stay as reported.

**Rule** (fixed before generation; committed with the generated histories before any reference run on them;
`histories/make_supplement.py` → `histories/supplement_histories.json`, 39,245 histories):
- It is the same for every case. It reads only the frozen history files and the pairs' base IR, binding, devices and
  start time. It never reads a JoI script, a fault, an Explorer verdict or a witness.
- **Start states:**
  - Keys are the IR-compared inputs plus the same member on other devices of the case that share a category.
  - Values are both BOOLs; for numbers, the seed start value and each compared literal v as v − s, v and v + s; for
    strings, the seed start value and the compared literals. None is not used.
  - A seed's t = 0 values are replaced by every assignment when there are at most 200 per seed. Otherwise every
    single-key change is used, plus seeded random joint assignments up to 200.
- **More pulses:** the frozen pulse rules are rerun without the cap. Pulses already in the frozen set are removed,
  and up to 1,500 more are sampled per case (seed `20260914-supp`).
- **Self-check:** rerunning the frozen generator from the same inputs must reproduce the frozen histories exactly.

**Run** (`run_supplement.py`):
- Only pairs with REF-EQUIV-CHECKED under the current reference are rerun, with the current reference. Explorer
  verdicts and witness replays are unchanged.
- The combined outcome is REF-DIVERGE if the supplement diverges; otherwise it is the frozen-history outcome.
- Output: `runs/e2_run.ref-current-supp.jsonl`.

**Reporting:**
- The frozen-history agreement and the supplementary agreement are reported side by side, and the supplement is
  labelled as added after the run.
- A new FALSE-EQUIV-CANDIDATE is inspected like any other.
- Supplementary histories on which the reference is unsupported are counted apart.
