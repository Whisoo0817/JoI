# SPEC_GAPS — points the specifications do not determine, and what the reference does

Rule applied (task brief §4): use a decision already written in PROTOCOL_DRAFT §1.4/§7, a text in an allowed source, or
return REF-UNSUPPORTED. Each entry: what is missing · documents checked · choice. "→ unsupported" means the construct
yields `status: "unsupported"`. Entries marked **[choice]** adopt a reading that is not literally written; they are the
first candidates for author review.

## Selection and binding

**G1 Selector tag matching.** JOI_SPEC §1.3 ("devices carrying the tags", `(#A #B)` intersection) and FRONTEND §3
(B(T) = tag-set match in inventory order) do not say whether `category` or the device ID also match a tag.
**[choice]** Match the `tags` list only, exact case. Consequences: E1-095 JoI v3 `(#Pool_Report #Pool)` →
unsupported (`Pool_Report` is an ID, not a tag); candidate C08_032 `(#Hall_Light_1)` → unsupported.

**G2 `(#Clock)`.** JOI_SPEC §1.4 says time conditions read the Clock service; VERIFICATION_CONTRACT says
`clock.hour/minute/weekday/timestamp` are functions of logical time, `clock.isholiday` is a BOOL input. Inventories
normally have no Clock device. **[choice]** A selector whose tag list is exactly `Clock`, or a member name with the
`clock_` prefix, reads the built-in S11 clock; `IsHoliday` is input key `Clock.IsHoliday`. Clock Day/Month/Year/
Second/Date/Datetime/Time → unsupported (S11). Quantified Clock and Clock functions (`Delay`) → unsupported.

**G8 IR binding slots.** FRONTEND §3: "`Service#2`는 JSON key 나열 순서와 무관하게 두 번째 자리. 단일 자리의 모든 등장
재사용 규칙은 유지"; SERVICE_MODEL §1: "binding의 원래 등장 순서로 접지"; "사용 중인 자리 수 불일치" is refused.
The exact walk order is not written. **[choice]** Occurrences of a service counted in IR document order: steps
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
otherwise → unsupported.

**G4 Null arithmetic.** HANDOFF: "미초기화 변수는 null 이고 null 산술은 0 으로 강제된다. 현재 검증 계약에 명세돼 있지
않다" — stated for the Timeline IR executor only. Choice: IR arithmetic, unary minus and abs/min/max treat `None` as
integer 0; JoI arithmetic on `None` → unsupported (no JoI text). Ordered comparison with `None` → unsupported in both.
Candidate C24_003 (`n + 1` with `n := 0` only inside a branch not taken in the first iteration) is affected.

**G5 Text conversion.** S8 fixes numbers. VERIFICATION_CONTRACT (symbolic value-flow note) "converting None to text
yields empty text, while passing raw None to a required STRING ACTION remains REFUSED". Choice: None → "", raw None
ACTION argument → unsupported; BOOL → text is not specified → unsupported; a float whose shortest repr needs an
exponent → unsupported.

**G6 IR `call.args` string values.** extractor: "The expression grammar applies inside cond … and read-derived arg
expressions"; joi_common lowers `"Channel": "$Television.Channel - 1"` (INTEGER) inline as an expression and
`"Text": "Current $t degrees"` (STRING) as concatenation. Nothing states the general rule. **[choice]** By catalog
argument type: INTEGER/DOUBLE/BOOL given as a JSON string → parsed as an expression (E1-095 `"($ph1 + …) / 5"`, E1 C07
`"$b0"`); STRING/ENUM containing `$` → template with references `$name`, `$Svc.Attr`, `$Svc[dev].Attr` (ASCII
identifier characters, so `$Hour시` reads `Hour`); a template that is exactly one reference passes the raw value (then
type-checked); other strings are literals; non-string JSON values are literals. BINARY/LIST arguments → unsupported.

**G11 IR functions and `%`.** extractor lists `abs(x)`; lists `min`/`max` as forbidden, while joi_common defines them
("min(a, b) → result is the SMALLER of a and b") and dataset IRs use them. Choice: abs/min/max implemented for numbers.
`%` (used in extractor D7c) defined only for integers a ≥ 0, b > 0; other operands → unsupported.

**G12 IR lexical points.** `null` literal accepted (E1 IRs, HANDOFF); a bare identifier is a local variable (extractor
R1.2); `&&`, `||`, `!` → unsupported (extractor forbids them, although its D7 table prints `||`); double-quoted strings
without backslashes only; chained comparisons → unsupported. Precedence per FRONTEND §2.

**G13 JoI quantifiers.** JOI_SPEC §1.3–1.4 and S5 define `all`/`any` in comparisons and `all` fan-out for actions.
Choice → unsupported: `any(...)` in action position; `all/any(...).m` used anywhere except as a direct operand of a
comparison (FRONTEND §3 "미지원 집합값 사용은 거절"); `op|` with anything but `all(...)`; both comparison operands
quantified; `x = all/any(...).query()`.

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
