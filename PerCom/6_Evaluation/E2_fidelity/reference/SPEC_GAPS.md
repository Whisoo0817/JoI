# SPEC_GAPS — points the specifications do not determine, and what the reference does

Rule applied (task brief §4): use a decision already written in PROTOCOL_DRAFT §1.4/§7, a text in an allowed source, or
return REF-UNSUPPORTED. Each entry: what is missing · documents checked · choice. "→ unsupported" means the construct
yields `status: "unsupported"`. Entries marked **[choice]** adopt a reading that is not literally written; they are the
first candidates for author review.

## Selection and binding

**G1 Selector tag matching. — SUPERSEDED by B1 (author decision whisoo, 2026-09-14, BINDING_DECISION_2026-09-14.md)
for runs that pass the IR binding (`run_joi(..., binding=, ir=)`). The text below is kept because runs without the
binding keyword (the frozen results) still follow it.**
JOI_SPEC §1.3 ("devices carrying the tags", `(#A #B)` intersection) and FRONTEND §3
(B(T) = tag-set match in inventory order) do not say whether `category` or the device ID also match a tag.
**Author decision (whisoo, 2026-09-14, first):** match the `tags` list only, exact case. To select a device by its ID, the
ID must be present as a tag on that device. Consequences: E1-095 JoI v3 `(#Pool_Report #Pool)` →
unsupported (`Pool_Report` is an ID, not a tag); candidate C08_032 `(#Hall_Light_1)` → unsupported.

**B1/B2 Binding and selectors — author decision (whisoo, 2026-09-14).** Source: `E2_fidelity/BINDING_DECISION_2026-09-14.md`
(authoritative). Opt-in API so the frozen results stay reproducible: `run_joi(..., binding=<pair binding, may be None>,
ir=<pair IR>)`, `run_ir(..., binding_decision=True)`, `compare(a, b, device_sets=...)`, `device_sets(ir, binding)`.
- B0 device sets (`common.parse_binding_slots`, `run.device_sets`): one per binding slot (quantifier removed, kept
  aside); plus, for every explicit `Svc[d,...]` site of the IR found by the same compile walk that grounds it
  (`IrProgram.collect_explicit_sites`), one set per site (pairs with `binding: null`, E1 depth form).
- B1 (`JoiProgram.selector_service`, `bound_devices`, `match`, `_operand`, `do_action`): S in the binding with one
  distinct set → that set; several → tag/ID/category match M, then the set equal to M, else the unique set ⊇ M, else
  M. Calls (B1.3, revised): the tag/ID/category match M when non-empty and ⊆ the chosen set, else every device of the
  chosen set (also for singular selectors; `any(...)` outside a condition is a syntax error since G35). Reads (B1.4, revised): one device → that device; several →
  the JoI quantifier (`all`, `any`, `op|`) when written, else the IR slot quantifier. S not in the binding: previous
  rules (S6, `all` fan-out, `any` action refused) with the new tag match: a selector tag matches if it equals one of
  the device's `tags`, its ID, or one of its `category` entries.
- B2 (`common.b2_normal_form`, `compare_b2`): within one instant the calls of all call groups are read in order; a
  maximal run of consecutive calls with equal (service, method, typed args, `val_eq`) whose devices all lie in one
  device set D of that service with |D| ≥ 2 becomes one unit {kind: set, devices, order ignored} (revised): devices =
  that binding set when exactly one such set holds every called device, else the called devices; the unit is
  repeated k times, k = most calls received by one device in the run. Other
  calls stay in their original call group (split only where a set unit was taken out); times, typed arguments and
  unit order are compared as before. Applied to both traces with the same sets.
Points the decision text leaves open, and the choice made (**[choice]**):
- **[choice]** Which service a selector names: `service_member` prefix → that service; unprefixed name → the binding
  services declaring the member; if several, narrowed to categories of the tag-matched devices; still several →
  unsupported[selector-service-ambiguous]. Tag, ID and category comparisons are exact-case.
- **[choice]** Several distinct sets and M empty: every set contains the empty M, so none is unique → M → unsupported
  [selector-no-device].
- **[choice]** Slots with the same device set but different quantifiers (`any` and `all`) and no JoI quantifier →
  unsupported[read-quantifier]. A slot without quantifier next to one with a quantifier on the same set: the named
  quantifier is used.
- **[choice]** Several devices, no JoI quantifier and no IR slot quantifier (plain singular selector), or a
  multi-device read outside a direct comparison operand → unsupported[read-quantifier] (same as IR G9). `op|` on a
  singular selector that B1 binds to several devices counts as a JoI quantifier (OR); `any(...) op|` stays refused.
  B1.3's M restriction is applied to calls only (the text says 호출); reads use the chosen set.
- **[choice]** B2 "same device set D": the set must belong to the call's service (case-insensitive), and membership is
  by device ID only. If sets of one service overlap, a run continues while some D ⊇ all devices of the run exists; a
  device in both a |D| ≥ 2 set and a one-device set is treated by membership (so calls on it can merge with calls on
  the larger set). A single call whose device is in such a D is also a set unit (its target the unique containing
  set, else itself), on both sides alike. "Exactly one such set" counts distinct (service, device set) pairs, so two
  slots with the same devices count once. k copies of the unit are compared as k consecutive units.
- Symbolic-argument clause of B2 does not arise: the reference only has concrete values.
- **Corrections (author decision whisoo, 2026-09-14, relayed by the coordinator; B1.3/B1.4 now in the decision file):**
  (1) B1.3 first version called the whole chosen set from every line, creating artificial duplicate calls; now only
  M ⊆ set. (2) B1.4 first version preferred the IR slot quantifier, which flips `not (any(#S).m == true)` written
  for IR `{"all": [a,b]}` with `m == false`; now the JoI quantifier wins. (3) B2 first version used the set of called
  devices with duplicates removed; now target = the unique containing binding set, multiplicity k kept, so a
  duplicated call is a difference and naming part of the bound devices is not.

**B5 Several binding device sets for one service — author decision (whisoo, 2026-09-14, added).** Source:
BINDING_DECISION_2026-09-14.md §B5. Which device set a JoI selector means is a binding question: the pair is equal if
SOME assignment gives equal traces, different only if EVERY assignment differs, otherwise undecided. The harness loops
over histories and assignments; the reference provides:
- `selector_space(block, devices, binding, ir, catalog_path=None) -> {"domains": [n_i], "tag_choice": [c_i]}`
  (`run.py`, `JoiProgram.assignable_occurrences`, `selector_space`, `tag_choice`). Occurrences: source selector
  nodes (one per occurrence however often executed) whose service has ≥ 2 distinct device sets, in source order —
  statements in order; `if` cond, then, else; `loop` cond, body; `wait` cond; an action's selector before its
  arguments; a comparison's left operand before its right; arithmetic left before right. Clock selectors never count.
- Device-set index order (`DeviceSets.distinct`): the service's binding slots by slot number (`S` = #1, `S#2`, …,
  independent of JSON key order, G8), then explicit IR `S[d,...]` sites in IR compile-walk order; a set equal to an
  earlier one is not repeated. `c_i` = B1.2 index (set equal to M, else the unique set ⊇ M, else 0).
- `run_joi(..., binding=, ir=, selector_assignment=[a_1..a_k])`: occurrence i uses set a_i; B1.3 (call M if M ⊆
  set, else the set), B1.4 (JoI quantifier, else the slot's) and B2 apply unchanged. Without `selector_assignment`,
  B1.2 as before. Wrong length / out-of-range index → status error, category `selector-assignment`.
- **[choice]** An occurrence whose service cannot be decided (selector-service-ambiguous) is not listed; the run
  is REF-UNSUPPORTED under every assignment. On a JoI that cannot be parsed, `selector_space` returns empty lists
  plus `status`/`detail`.
- Test (ii) of the coordinator: IR reads slot 1 (L) and calls slot 2 (T); JoI reads and calls `(#Lamp)`; with the
  assignment [L set, T set] B1.3 calls every device of {T} because M = {L} is not a part of it, so the traces match.

**G2 `(#Clock)`.** JOI_SPEC §1.4 says time conditions read the Clock service; VERIFICATION_CONTRACT says
`clock.hour/minute/weekday/timestamp` are functions of logical time, `clock.isholiday` is a BOOL input. Inventories
normally have no Clock device. **Author decision (whisoo, 2026-09-14):** `(#Clock)` is the built-in S11 clock; no
Clock device is needed; IsHoliday stays an input. Implementation: a selector whose tag list is exactly `Clock`, or a member name with the
`clock_` prefix, reads the built-in S11 clock; `IsHoliday` is input key `Clock.IsHoliday`. Clock Day/Month/Year/
Second/Date/Datetime/Time → unsupported (S11). Quantified Clock and Clock functions (`Delay`) → unsupported.

**G8 IR binding slots.** FRONTEND §3: "`Service#2`는 JSON key 나열 순서와 무관하게 두 번째 자리. 단일 자리의 모든 등장
재사용 규칙은 유지"; SERVICE_MODEL §1: "binding의 원래 등장 순서로 접지"; "사용 중인 자리 수 불일치" is refused.
The exact walk order is not written. **Author decision (whisoo, 2026-09-14): confirmed as written here.** Occurrences of a service counted in IR document order: steps
pre-order, fields in their JSON key order, left to right inside an expression or template, a call's target at its key
position. One slot → every occurrence. k > 1 slots → i-th occurrence ↔ slot i; count mismatch → unsupported.
Version note: the first draft matched slots to *distinct members*; the 388 smoke run showed 15 dataset rows binding two
occurrences of the same member to `#1`/`#2` (e.g. C06#1 `TemperatureSensor.Temperature >= 28 or
TemperatureSensor.Temperature >= 30`). "등장" (occurrence) covers these, so the rule was changed before any E2 pair
was run. E1 C16 gives the same grounding under both readings.

**G9 IR binding shapes.** dataset.csv uses `["d1", …]`, `{"any": […]}`, `{"all": […]}`. FRONTEND §3 defines any → OR,
all → AND for comparisons and refuses "불명확한 quantifier". Choice: `{"any"/"all"}` quantifies a read that is a direct
operand of a comparison; the same binding in any other position (read op, arithmetic, bare condition, template), a
multi-device list used as a read, or a quantified binding on a call → unsupported. A list on a call → fan-out.
E1 explicit form `Svc[d1,d2].Member` (depth_attempts*.py) → that device list (fan-out for calls; single device only
for reads).

**G28 Member collisions.** SERVICE_MODEL §1 refuses "concrete input member 충돌". Choice: reading a member whose name
exists in two categories of the same device → unsupported; an unprefixed JoI name found in two categories →
unsupported.

**G29 Singular selector.** S6 applied: unique `Main` tag, else first in `connected_devices` order. No match →
unsupported. Capability not declared as a category of the chosen device → unsupported (SERVICE_MODEL §1).

## Values and expressions

**G3 Equality and ordering across types.** Only ACTION-argument equality is written (VERIFICATION_CONTRACT: 1 == 1.0,
true != 1, "1" != "1.0"). Choice: `==`/`!=` within BOOL, number, STRING; `None` equals only `None` (the probe
`missing_query` expects `w == "rain"` false for a missing result; HANDOFF/E1 IRs use `$t != null`). Any other mixed
equality → unsupported. `< > <= >=` only number/number or string/string (SERVICE_MODEL §3 lexical string intervals);
otherwise → unsupported. **Author decision (whisoo, 2026-09-14):** an ordered comparison (`>`, `<`, `>=`, `<=`) in
which either operand is a missing value (None) evaluates to **false**, in both the IR and the JoI interpreter
(VERIFICATION_CONTRACT includes None in non-BOOL input domains, but no document said how it compares). Equality is
unchanged: None == None true, None == other false, `!=` the negation. Previously → unsupported[ordered-compare-type].

**G4 Null arithmetic. — SUPERSEDED for the JoI side by R14 (author decision whisoo, 2026-09-16,
`uninitialized-arith-v1`, RUNTIME_CONTRACT.md).** Using a variable that has never been assigned as an operand of an
arithmetic operation is a **runtime error**: the instance stops there for good, the ACTIONs issued before it stay in
the trace, and the stop itself is observable, so a side that ends this way differs from a side that runs on. The
reference returns `status: "runtime-error"`, category `uninitialized-arith` (`joi_ref.JoiProgram.check_assigned`,
`common.RefRuntime`). The rule covers variables only: `+` with a STRING operand is S8 concatenation, not arithmetic,
and a missing non-BOOL *input* read (R10, value None) keeps the old treatment. IR arithmetic is unchanged (None as
0). Candidate C24_003 (`n = n + 1` with `n := 0` only inside a branch not taken in the first iteration) is the one
program in the E2 population the rule reaches; a definite-assignment check over all 142 frozen pairs finds no other.
The text below is the pre-decision reading.

**G4 Null arithmetic (pre-decision text).** HANDOFF: "미초기화 변수는 null 이고 null 산술은 0 으로 강제된다. 현재 검증 계약에 명세돼 있지
않다" — stated for the Timeline IR executor only. Choice: IR arithmetic, unary minus and abs/min/max treat `None` as
integer 0; JoI arithmetic on `None` → unsupported (no JoI text). Ordered comparison with `None` → false in both
(author decision 2026-09-14, see G3); arithmetic rules unchanged, so in IR `$x - 1 > 0` with `$x` None compares
`-1 > 0` (coercion happens in the arithmetic first) while `$x > 0` is false.
Candidate C24_003 (`n + 1` with `n := 0` only inside a branch not taken in the first iteration) is affected.

**G5 Text conversion.** S8 fixes numbers. VERIFICATION_CONTRACT (symbolic value-flow note) "converting None to text
yields empty text, while passing raw None to a required STRING ACTION remains REFUSED". Choice: None → "", raw None
ACTION argument → unsupported; BOOL → text is not specified → unsupported; a float whose shortest repr needs an
exponent → unsupported.

**G6 IR `call.args` string values.** extractor: "The expression grammar applies inside cond … and read-derived arg
expressions"; joi_common lowers `"Channel": "$Television.Channel - 1"` (INTEGER) inline as an expression and
`"Text": "Current $t degrees"` (STRING) as concatenation. Nothing states the general rule. **Author decision (whisoo,
2026-09-14): confirmed as written here.** By catalog
argument type: INTEGER/DOUBLE/BOOL given as a JSON string → parsed as an expression (E1-095 `"($ph1 + …) / 5"`, E1 C07
`"$b0"`); STRING/ENUM containing `$` → template with references `$name`, `$Svc.Attr`, `$Svc[dev].Attr` (ASCII
identifier characters, so `$Hour시` reads `Hour`); a template that is exactly one reference passes the raw value (then
type-checked); other strings are literals; non-string JSON values are literals. BINARY/LIST arguments → unsupported.

**G11 IR functions and `%`.** extractor lists `abs(x)`; lists `min`/`max` as forbidden, while joi_common defines them
("min(a, b) → result is the SMALLER of a and b") and dataset IRs use them. Choice: abs/min/max implemented for numbers.
`%` (used in extractor D7c) defined only for integers a ≥ 0, b > 0; other operands → unsupported.
**JoI `%` — author decision (whisoo, 2026-09-14):** the deployment grammar `lowering/parser/JOILang.g4` has no `%`;
the reference accepts it as integer remainder (following files/joi_cycle.md Ex5 `n % 2 == 0`). Implemented by a
copy of the grammar in `reference/grammar/JOILang.g4` with `('*'|'/'|'%')` in `arithmetic_expression` (same
precedence as `*` and `/`, left-associative) and a `MODULO : '%'` token, regenerated with
antlr-4.13.2-complete.jar (Python3 target) into `reference/grammar/`; `joi_ref.py` uses that parser. Same operand
restriction as IR `%` (no allowed spec says more). The deployment grammar is not modified, so a script using `%` is
accepted by the reference but still rejected by the deployment parser.

**G12 IR lexical points.** `null` literal accepted (E1 IRs, HANDOFF); a bare identifier is a local variable (extractor
R1.2); `&&`, `||`, `!` → unsupported (extractor forbids them, although its D7 table prints `||`); double-quoted strings
without backslashes only; chained comparisons → unsupported. Precedence per FRONTEND §2.

**G13 JoI quantifiers.** JOI_SPEC §1.3–1.4 and S5 define `all`/`any` in comparisons and `all` fan-out for actions.
Choice → unsupported: `any(...)` outside a condition (now unsupported[syntax] at parse time, G35); `all/any(...).m` used anywhere except as a direct operand of a
comparison (FRONTEND §3 "미지원 집합값 사용은 거절"); `op|` with anything but `all(...)`; both comparison operands
quantified; `x = all(...).query()` (`any` there: syntax, G35).

**G16 Conditions must be BOOL.** No truthiness rule is written. Bare condition atoms, `not`, `and`, `or` operands that
are not BOOL → unsupported. Both operands of and/or are evaluated (FRONTEND §2 "양쪽을 평가한다").

**G22 JoI and/or precedence.** JOILang.g4 puts `and` and `or` on one left-recursive level; FRONTEND §2 gives `and`
tighter than `or`. Choice: the parse chain is flattened and re-associated per FRONTEND §2. `not` applies to one
condition_atom (grammar).

**G18/G19.** JoI string escapes → unsupported (FRONTEND §2). Division by zero, non-finite results, negative delay →
unsupported. `/` is real division (S7).

**G23 ACTION argument equality.** Numeric equality is used, so `0.0 == -0.0`; the contract only states `1 == 1.0`.

## Time and control

**G7 IR `wait.timeout` / `on_timeout`.** Not in extractor.md. Sources used: E1 irs.py header "E-TIMEOUT-ABORT: a wait
with timeout and a NON-empty on_timeout ends the current iteration … With an EMPTY on_timeout the program continues
past the wait" and FRONTEND §4 "break/timeout: … cycle 출구/회차 끝". Choice: on expiry run `on_timeout`; if it is empty
continue after the wait; if non-empty, after it completes jump to the end of the current iteration of the nearest
cycle (count increment, period, until check); outside any cycle this ends the automation; a `break` inside
`on_timeout` exits the nearest cycle. Expiry and condition at the same instant: condition first (S4). `for` and
`timeout` together are both honoured.

**G35 `any(...)` only inside a condition — author decisions (whisoo, 2026-09-14).** Sources: the author decisions
relayed by the coordinator (first: `any(...)` on a call statement is invalid; second, same day, replacing the earlier
[choice] on query assignments: `any(...)` may appear only inside a condition); `handoff_timer/e2_population.json`
(exclusion of C03_008/llm, category `invalid_syntax`: "any selector in ACTION position is forbidden by the
user-approved language rule; parse-time rejection").
Rule: `any(...)` is valid only inside a condition. Condition positions in JOILang.g4 are exactly the operands of a
`condition_list`: the condition of `if` (an `else if` is `else` followed by an `if_statement`, so it is covered), of
`wait until(...)`, and of `loop(...)` (the grammar has no `while`; `loop (cond)` is its conditional loop). Everywhere
else `any(...)` is a syntax error: a call statement (`any(#S).m()`, ACTION position), the right-hand side of `=` or `:=`
(`x = any(#S).v`, `x := any(#S).v`, `x = any(#S).q()`, also inside arithmetic), and call arguments. (`x = any(#S).v ==
true` is already a grammar error because `==` is not arithmetic; `for (x : ...)` only allows `all(...)` and `for` is
excluded anyway.) `all(...)` is not affected.
Effect: `joi_ref.conv_stmt` / `conv_arith` raise unsupported[syntax] with the message "any selector outside a
condition: <position>: ..." while building the AST, so `run_joi` returns status "unsupported", category "syntax", no
ACTION, with or without the binding keywords, and `selector_space` returns empty lists with status "unsupported".
Before, a bound `any(...)` call followed B1.3 (C03_008/llm ran as REF-EQUIV-CHECKED), an unbound one was refused at run
time as unsupported[any-action], and `x = any(...).q()` was unsupported[multi-device-query] unless B1 bound one device;
those run-time branches are now unreachable for `any`. Programs with this construct are invalid input and leave the E2
behavioral population (142 → 140 with C20_011/llm).

**G10 IR `break` outside a cycle.** extractor: "exit nearest cycle". Choice: ends the automation (as R13 for JoI).

**G14 JoI local store across period iterations.** VERIFICATION_CONTRACT includes the local store in the state and
starts it empty only at `Init`. Choice: variables persist across iterations; `:=` is skipped after the first logical
iteration (R8).

**G15 Durations.** IR: `"<integer> <HOUR|MIN|SEC|MSEC>"` (extractor); anything else → unsupported. JoI `DAY` (grammar
token only) = 86 400 000 ms.

**G24 Evaluation instants.** A blocked wait is re-evaluated at every input change, at its own deadlines (sustain,
timeout), and — if its condition reads the clock — at every absolute 1 s boundary. Inputs (R2) and S11 clock values
are constant between these instants, so this equals evaluation at every 1 ms (R3).

**G27 Timestamp.** S11 `Timestamp = t // 1000` (integer) is used although the catalog declares DOUBLE with a
fractional part.

**G30 IR structure.** `start_at` must be the first top-level step, anchor `now` or `cron` (erased, one window);
unknown ops or fields (e.g. `bind`), `edge` outside none/rising/null, missing `cycle.period` → unsupported.

**G31 Horizon.** ACTIONs at relative times ≤ `horizon_ms` are reported.

**G33 JoI `loop` / `for`.** `for` → unsupported statically (§7). `loop` per L1; more than 200 000 statements at one
logical time → reference error ("reaction does not finish").

**G34 JoI block.** `period` must be a non-negative integer number of ms; `cron` erased (one window); `script` or
`code` key.

## Services and inputs

**G17 Read-role calls.** SERVICE_MODEL §2: statement-position call of a reviewed read function → unsupported; return
assignment of any other function (incl. VOID) → unsupported; FRONTEND/VERIFICATION_CONTRACT: dynamic query arguments →
unsupported (only literal arguments form a key).

**G21 Catalog checks.** Unknown service/member, function used as a property, value called as a function, argument
count/type/range/ENUM violation (checked at execution, SERVICE_MODEL §1/§3) → unsupported. The E1 default-history
smoke run therefore reports e.g. `SetChannel(Channel - 1)` with Channel 0 as `arg-range`.

**G26 Input keys and validity.** Keys `Device.Member` and `Device.Member(<Python literals>)`; argument types are part
of the key (3 ≠ 3.0); a zero-argument query shares the property key (FRONTEND §1). Missing non-BOOL → None. Missing
BOOL, or BOOL not true/false → reference error (invalid history, R10). `MenuProvider.GetMenu` missing/None → reference
error (VERIFICATION_CONTRACT non-null STRING).

**G32 History validity.** First event at t=0; change times on the 100 ms grid (R2), else reference error. DOUBLE
0.1-grid and ENUM membership of input values are not checked.

**G25 E1 fault injection (T7).** Implemented as optional `faults=[{service, method, device, after_ms}]` on
`run_ir`/`run_joi`: the ACTION is recorded; from `issue time + after_ms` on, the instance takes no further step.
