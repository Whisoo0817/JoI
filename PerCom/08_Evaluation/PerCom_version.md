# Evaluation — PerCom working draft

상태: 2026-09-18 E1을 범위 내 92건 전체 평가로 갱신. 사용자 검토 전. E1–E4 각 표 하나. Counterexample은 수정에 필요한 행동 차이 정보로만 사용하며 대조군 비교나 인과적 개선 주장은 본문에 넣지 않는다. 근거·검증 메모는 `DRAFT_NOTES.md` 참조.

Our evaluation asks four questions: Can Timeline IR express externally sourced automation requests (E1)? Do Explorer verdicts agree with a separately implemented reference (E2)? What errors appear in generated code (E3)? How does checking cost change with automation size and timing (E4)?

**Setup.** All code evaluations use JoI and the execution model in Sections V and VI. E1 evaluates expression and reference execution, E2 checks verdict fidelity, E3 evaluates generated candidates, and E4 measures completion and cost. Refusals, incomplete searches, and errors remain in each evaluation's denominator. LLM generation is separate from behavioral checking.

## Timeline IR Adequacy

E1 tests whether Timeline IR operators can be combined to express externally sourced automation requests. We collected 100 requests from four sources (Table E1). One author screened them against the reactive-temporal scope: 92 were in scope, six were ambiguous, and two were out of scope. We encoded and tested all 92 in-scope requests.

For each request, we recorded a concrete interpretation and expected actions and timestamps before encoding it. The initial 20 interpretations were reviewed by the author; LLM agents derived the remaining 72 using those precedents. The agents also prepared their expected traces, so these were not independent judgments of intent. We replayed the input histories on the reference IR runner and compared actions and timestamps, treating simultaneous actions as an unordered group. We report final encodings and retain failed attempts in the experiment records.

**Table E1. Timeline IR execution results by request source.**

| Request source | Collected | Evaluated | Exact histories |
| --- | ---: | ---: | ---: |
| Official platform examples | 25 | 25 | 97/97 |
| Research examples | 26 | 24 | 74/74 |
| Published participant responses | 24 | 20 | 58/58 |
| Community requests | 25 | 23 | 65/65 |
| **Total** | **100** | **92** | **294/294** |

All 92 final encodings reproduced the expected traces on all 294 input histories (Table E1). The cases exercise combinations of operators: a door alert waits for sustained opening and then repeats reminders; a garage alert nests blinking cycles within repeated checks and restores a saved light setting; and a sprinkler combines stored timestamps, conditions, and repetition to limit watering to ten minutes in any 48-hour window. Seventeen additional diagnostic histories also matched and are reported separately from the table.

These results depend on the recorded interpretations and assumptions. Examples include fixed-size averages, specified pulse waveforms, and separate Timelines for independent automations. The sprinkler encoding uses one-second units and assumes no prior watering. The results demonstrate expression and execution on these finite histories; they do not establish correctness for every input, coverage of every operator combination, or Explorer support for every encoding.

## Validation Fidelity

To evaluate Explorer's verdicts, we compared them with a Timeline runner and JoI interpreter implemented from the specification without access to Explorer code. Before use, the reference reproduced the 53 traces from the initial 20 E1 requests and 15 JoI conformance probes. The population contains 21 correct implementations and 81 single-fault variants of those 20 E1 requirements, plus 38 valid generated candidates sampled from the 388-request development set. Faults span 12 families, including action omission, timing, guards, stored values, order, and repetition. The reference compared both programs on 48,990 input histories and replayed Explorer's counterexamples. Explorer used 120 s, 400,000 states, and 2,000,000 transitions per pair. Semantics-preserving reductions of repetitive temporal and state exploration allowed 26 additional pairs to be decided under the same budgets, without changing earlier verdicts.

**Table E2. Reference checks of Explorer verdicts.**

| Assessment | Pairs |
| --- | ---: |
| Semantic verdicts issued | 130/140 |
| Equivalent: no difference on reference histories | 55 |
| Divergent: difference on reference histories | 67 |
| Divergent: confirmed by witness replay | 8 |
| Verdicts contradicted by reference checks | 0 |
| Fault variants with an observed difference | 75 |
| Divergent / equivalent / undecided (fault variants above) | 69 / 0 / 6 |
| Generated candidates decided | 38/38 |
| Hand-built pairs decided | 92/102 |
| Undecided: time budget / unsupported relation | 5 / 5 |

None of the 130 verdicts contradicted the reference checks (Table E2). For eight divergences, the reference histories alone did not expose the difference, but replaying Explorer's witness did. For equivalent verdicts, agreement on these finite histories is empirical evidence rather than a proof of equivalence. Among fault variants with an observed difference, Explorer left six undecided and accepted none. The ten undecided pairs belong to two requirements: nested blinking cycles with long pauses exceeded the time budget, and an event-extended deadline required an unsupported arithmetic relation. Thus, all pairs for 18 of the 20 hand-built requirements were decided. Fault variants from the same requirement are related cases rather than independent samples.

## Generated-Code Validation

To evaluate generated candidates, we supplied confirmed IRs and bindings to Qwen3.5-9B-FP8, bypassing natural-language service and selector inference. Generation used temperature 0.1, a 512-token limit, and thinking disabled. The evaluated set contains 382 requests, excluding six timeout-handler requests from the source set of 388. It includes 63 regenerated candidates after input and service-prefix corrections and 319 byte-identical reused candidates. Evaluation ran with Python 3.12.11 on an Intel Core i9-11900K Linux host, with a 20 s process budget, 200,000 states, 500,000 transitions, and a 1 s limit per SMT query.

**Table E3. Outcomes on generated JoI candidates.**

| Outcome | Candidates | Share |
| --- | ---: | ---: |
| Equivalent | 309 | 80.89% |
| Divergent (replay-confirmed) | 68 | 17.80% |
| Unsupported | 3 | 0.79% |
| Inconclusive | 2 | 0.52% |
| Total | 382 | 100.00% |

Explorer issued a semantic verdict for 377 candidates (Table E3), a completion rate rather than an accuracy estimate. All 68 divergences were confirmed by its concrete replay. For example, a request turns off a power strip after 30 s without motion. The generated code increments a counter at the initial evaluation and every second thereafter, so it reaches 30 and turns the strip off at 29 s. At that instant the IR emits no action. The unsupported cases involved a binary return assignment, unbounded temperature arithmetic, and a large illuminance domain. Both inconclusive cases hit the SMT query limit. These familiar-task, mixed-provenance results are exploratory and relative to the confirmed IR and binding, not measurements of natural-language intent accuracy or physical-device behavior.

**Counterexamples for repair.** A counterexample supplies the input history and expected and actual actions at a mismatch to inform code revision. With the IR and binding fixed, we allowed one repair call per divergent candidate using the same model at temperature 0 with a 4,096-token limit, and checked the revised code again. The resulting outcomes were 36 equivalent, 26 divergent, five checking timeouts, and one model context error out of 68 cases.

## Validation Cost and Scale

To evaluate checking cost as automations grow, we generated 30 equivalent IR–code pairs from one parameterized family. We varied Boolean sensors (1–7), sequential wait–call stages (1–6), wait length (100 ms–4 h), and repetitions (1–200), both individually and in combined settings. Each program ran three times with a 120 s budget per run. The baseline disables timer zones but retains the same semantic executors, next-event jumps, and exact-state reuse. Both methods require completed exploration for an equivalence result. Explorer ran serially, while the baseline used four concurrent workers on an eight-core host. The reported times therefore describe these configurations, not a matched-load speedup.

**Table E4. Checking cost on selected scale settings.**

| Program | Explorer (s) | Explicit (s) |
| --- | ---: | ---: |
| Base | 0.24 | 47.2 |
| Sensors: 7 | 9.21 | timeout |
| Stages: 6 | 0.71 | timeout |
| Wait: 0.1 s | 0.05 | 0.06 |
| Wait: 4 h | 0.25 | timeout |
| Repeats: 200 | 18.0 | timeout |
| Combined: 7 sensors, 6 stages, 100 repeats | timeout | timeout |
| Programs decided (all settings) | 28/30 | 12/30 |

Base: 2 sensors, 2 stages, 2 min wait, 5 repeats. Each row changes only the named parameters. Times are the slowest of three runs. A program counts as decided only if all three runs complete.

Explorer decided 28 programs, including 19 in under one second and all 28 within 21 s (Table E4). Peak memory for completed Explorer runs was below 44 MiB. Across the wait-length sweep, checking took 0.05–0.35 s. Increasing sensors instead increased the input combinations checked per step: the seven-sensor case retained 52 states but explored 31,832 paired transitions. The two unfinished programs combined six or seven sensors, six stages, and 50 or 100 repetitions. Both exhausted the allotted resources rather than being refused as unsupported. These measurements characterize completion and cost for this synthetic family, not verdict correctness or cost for arbitrary generated code.
