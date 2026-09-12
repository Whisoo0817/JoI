# E1 Stage A 결과 (기계 열 자동 채움; B·G 열은 whisoo)

생성: `python make_results.py`. 근거: `runs/e1_stageA.json`, `cases.py`, `irs.py`. **논문 결과가 아니다.**

## 사례별

| ID | 요소 | 경계 | A-언어 | A-frontend | A-extractor 문법 | B 감사(whisoo) | C 실행 일치 (정확) | D 실행기 | E Explorer(참고) | F binding | G JoI | 최종 | 메모 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C01 | R1 R3 R7 B1 | ★ | full | accepted | **밖**: nested cycle, wait.timeout | **보존** — 새 motion off→on 재트리거는 종료 대기를 취소하고 On 재호출, 마지막 no-motion 후 120 s Off. HA 는 인스턴스 재시작·IR 은 내부 반복이지만 action trace 동일 | 4/4 (4/4) | compiled | EQUIV (EQUIV-FIXPOINT) | selector/Service.Method 1 ✓ | 미확인(불가/부분 없음) | 완전 | encoding 수정 이력 있음(irs.py) |
| C03 | R1 R2 |  | full | accepted | 안 | **보존** — ≤1000→>1000 에 On, 정확히 15분 후 Off, 종료 뒤 다음 crossing 에 새 실행. 진행 중 재교차 무시는 원문 미정 부분의 명시적 [가정]으로 승인 | 4/4 (4/4) | compiled | EQUIV (EQUIV-FIXPOINT) | selector/Service.Method 1 ✓ | 미확인(불가/부분 없음) | 완전 | encoding 수정 이력 있음(irs.py) |
| C04 | R9 R2 |  | full | accepted | 안 | **보존** — 'At noon' = 매일 12:00. cron→On→15 min→Off 가 직접 보존. 실행기는 cron 소거 후 한 창만 재생(단서 유지) | 1/1 (1/1) | compiled (cron anchor erased; one firing window executed) | EQUIV (EQUIV-FIXPOINT) | selector/Service.Method 1 ✓ | 미확인(불가/부분 없음) | 완전 |  |
| C05 | R3 R7 |  | full | accepted | **밖**: nested cycle, period 0 MSEC, wait.timeout | **수정 후 보존** — 2분 연속 열림에 첫 SMS, 열린 동안 정확히 60 s 마다, 닫히면 즉시 종료. inner period 100 MSEC 가 회차마다 100 ms 누적 → 0 MSEC 로 수정(E-ZERO-PERIOD) | 4/4 (4/4) | compiled | EQUIV (EQUIV-FIXPOINT) | selector/Service.Method 1 ✓ | 미확인(불가/부분 없음) | 완전 | encoding 수정 이력 있음(irs.py) |
| C07 | R9 R3 R5 R8 B5 B1 | ★ | full | accepted | **밖**: nested cycle, period 0 MSEC, wait.timeout | **수정 후 보존** — 22:00 이후 10분 열림→B0 snapshot→(blink 10·restore·5분 pause)×≤7 승인. 500+400+period 100 구조는 닫힘 뒤 복원이 최대 100 ms 늦음 → 500+500, inner period 0 MSEC 로 수정 | 4/4 (4/4) | compiled | UNKNOWN (INCONCLUSIVE) | selector/Service.Method 1 ✓ | 미확인(불가/부분 없음) | 완전 | encoding 수정 이력 있음(irs.py) |
| C09 | R1 R4 |  | full | accepted | 안 | **보존 [연구자 변환]** — 원문은 안전 속성 → '귀가 absent→present 순간 Lock' 자동화로 구체화해 평가. 초기 absence 확인 후 각 신규 arrival 에 Lock. 원문 속성 자체를 검증했다고 쓰지 않음 | 3/3 (3/3) | compiled | EQUIV (EQUIV-FIXPOINT) | selector/Service.Method 1 ✓ | 미확인(불가/부분 없음) | 완전 | encoding 수정 이력 있음(irs.py) |
| C11 | R1 B2 | ★ | full | accepted | 안 | **보존** — 두 독립 TAP rule 을 직전 snapshot(E-PREV)으로 한 흐름에서 판별. 이 사례는 delay·중첩 인스턴스·되먹임이 없어 trace 가 두 rule 과 같다고 감사에서 확인. 이 사례 한정이며 snapshot 이 병렬 rule 을 일반적으로 대체한다는 주장이 아님 | 4/4 (4/4) | compiled | EQUIV (EQUIV-FIXPOINT) | selector/Service.Method 1 ✓ | 미확인(불가/부분 없음) | 완전 |  |
| C15 | R4 R7 R9 |  | full | accepted | 안 | **보존** — 밤 22:00–06:00, 입·퇴실 = presence 변화. 밤 입실에만 On, 06:00 이후 퇴실도 Off. 밤 시작 시 이미 재실이면 On 없음. IR·3 이력이 정확히 보존 | 3/3 (3/3) | compiled | UNKNOWN (INCONCLUSIVE) | selector/Service.Method 1 ✓ | 미확인(불가/부분 없음) | 완전 |  |
| C16 | R9 R6 |  | full | accepted | 안 | **보존** — 'if it is 10:00pm' = 매일 22:00 정각 한 번 검사. 그 순간 문 닫힘·조명 Off 일 때만 TV Off. Switch binding slot 분리 확인. cron 한 회차 단서 유지 | 2/2 (2/2) | compiled (cron anchor erased; one firing window executed) | EQUIV (EQUIV-FIXPOINT) | selector/Service.Method 1 ✓ | 미확인(불가/부분 없음) | 완전 |  |
| C18 | R1 R9 R2 |  | full | accepted | 안 | **보존** — '3:00 pm' = 15:00–15:59 창, 진행 중 재누름 무시로 구체화([가정] 유지, 원 논문도 해석이 갈림). 새 버튼 사건에 즉시 Unlock, 정확히 10 s 뒤 Lock 보존 | 3/3 (3/3) | compiled | UNKNOWN (INCONCLUSIVE) | selector/Service.Method 1 ✓ | 미확인(불가/부분 없음) | 완전 |  |
| C19 | R10 R9 |  | full | accepted | 안 | **수정 후 보존** — '분 단위 과허용' 설명은 오류(race 가 09:00 에 끝나므로 09:00:30 은 통과 안 함). 실제 결함은 시작 시 이미 present 를 arrival 로 오인 → wait(absent) 선행, 마지막 if 단순화, 이력 2개 추가 | 5/5 (5/5) | compiled (cron anchor erased; one firing window executed) | UNKNOWN (INCONCLUSIVE) | selector/Service.Method 1 ✓ | 미확인(불가/부분 없음) | 완전 | encoding 수정 이력 있음(irs.py) |
| C20-O | R1 R2 B1 | ★ | full | accepted | **밖**: wait.timeout | **보존 — ordered variant 만** — 'AND AFTERWARDS … WITHIN 2 hours' 문장만 사례로 확정. 퇴장이 창을 끝내고 재입장이 새 창 → 재시작 의미와 같은 trace. paired unordered variant requires look-back event memory and is excluded from this ordered-variant case | 4/4 (4/4) | compiled | UNKNOWN (INCONCLUSIVE) | selector/Service.Method 1 ✓ | 미확인(불가/부분 없음) | 완전 | encoding 수정 이력 있음(irs.py) |

## 요소 × 사례 (경계 표)

| 요소 | 뜻 | 사례 | C 통과/전체 | 비고 |
|---|---|---|---|---|
| R1 | 즉시 반응 | C01 C03 C09 C11 C18 C20-O | 6/6 |  |
| R2 | 지연 후 호출 | C03 C04 C18 C20-O | 4/4 |  |
| R3 | 지속 조건+reset | C01 C05 C07 | 3/3 |  |
| R4 | 사건 한 번/재무장 | C09 C15 | 2/2 |  |
| R5 | 저장값 흐름 | C07 | 1/1 |  |
| R6 | 순차·분기 | C16 | 1/1 |  |
| R7 | 조건까지 반복(주기) | C01 C05 C15 | 3/3 | C05 v1 은 정확 일치 0/4(period 가 회차 종료 후 대기라 100 ms 누적) → 감사에서 inner period 0 MSEC 로 수정, 현재 4/4 |
| R8 | 고정 횟수 반복 | C07 | 1/1 |  |
| R9 | 시계 앵커·시간대 | C04 C07 C15 C16 C18 C19 | 6/6 | cron 앵커 3건(C04 C16 C19)은 실행기가 거절 → 앵커 소거 후 한 창만 실행. Clock.Hour/Minute 은 분 단위, Clock.Timestamp 는 초 단위 |
| R10 | 시각 vs 사건 경쟁 | C19 | 1/1 |  |
| B1 | 즉시 취소·재시작 | C01 C07 C20-O | 3/3 | C07 v3: 닫힘 시각에 B0 복원(감사 후 정확 일치). C01/C20-O: 재시작·취소를 timeout+break 조합으로 표현 |
| B2 | 독립 두 흐름/인스턴스 | C11 | 1/1 | C11 한 건뿐이고, 두 흐름을 만든 것이 아니라 **단일 흐름으로 환원**한 것이다. 이 사례에는 delay·중첩 인스턴스·action→trigger 되먹임이 없어 직전 snapshot 판별이 두 TAP 규칙과 같은 trace 를 낸다(감사 확인). 진짜 중첩 인스턴스가 필요한 요구는 Stage A·probe 모두에서 **미평가**이며, 실행 계약상 단일 제어 흐름이라는 한계로 보고한다 |
| B3 | 이벤트 기억·look-back | (Stage A 없음) | - | 두 가지를 나눠야 한다. **(가) 자동화가 켜지기 전의 과거**는 불가 — 실행 모델이 t=0 에 현재 값만 주므로 이력으로 쓸 수조차 없다(Timeline 표현력이 아니라 관측 모델의 경계. HA 는 플랫폼의 `last_changed` 로 답한다). **(나) 도는 중에 놓친 과거**는 가능 — probe P1·P2 가 각각 4/4 정확 일치. 단 Explorer 는 둘 다 거절한다(아래 probe 절) |
| B4 | 가변 간격 반복 | (Stage A 없음) | - | Stage A 에는 사례가 없었고 **probe P3 로 시도**했다. duration 이 컴파일 시점 리터럴이라 표현되지 않는다(아래 probe 절) |
| B5 | 중첩 반복 | C07 | 1/1 |  |

최종 판정: 완전 12/12 (완전 = A full ∧ B 보존 ∧ C 모든 이력 일치). 선정한 12건 중의 건수이며 coverage 비율이 아니다.

Explorer 참고 열: IR×IR 자기 product, 120 s 예산. UNKNOWN 은 표현 실패가 아니라 탐색 미완(cap)이며 A 판정을 바꾸지 않는다.

## 감사 후 수정 전후 (exact 열)

| 사례 | 수정 | 전 (match/exact) | 후 (match/exact) |
|---|---|---|---|
| C05 | inner cycle period 100 MSEC → 0 MSEC | 4/4 / 0/4 | 4/4 / 4/4 |
| C07 | half-blink 500+400 → 500+500, inner period 0 MSEC | 4/4 / 3/4 | 4/4 / 4/4 |
| C19 | wait(absent) 선행, branch 단순화, 이력 +2 | 3/3 / 3/3 | 5/5 / 5/5 |

## 경계 probe (성공 분모와 분리)

Stage A 가 건드리지 못한 경계 B3·B4 를 **따로 지정한 요구**로 시도한 결과다. 요구와 기대 trace 는 인코딩 시도 전에 `probes.py` 에 고정하고 해시했다(README §6). 이 표는 12건 성공 분모에 들어가지 않으며, probe 가 '완전' 로 끝나는 것도 정상적인 결과다 — 경계 후보가 사실은 표현 가능했다는 뜻이다.

| ID | 경계 | 출처 요구 | A-언어 | A-extractor 문법 | C 실행 일치 (정확) | D 실행기 | E Explorer | 판정 |
|---|---|---|---|---|---|---|---|---|
| P1 | B3 | IF Sally enters the bedroom AND the sun sets WITHIN 2 hours THEN turn on the bed… | full | **밖**: Clock.Timestamp, null operand, period 0 MSEC | 4/4 (4/4) | compiled | REFUSED: Unsupported: explicit input domain required for observable large/unbou | **완전** |
| P2 | B3 | I have an automation which sends a notification along with a camera capture for … | full | **밖**: Clock.Timestamp, null operand, period 0 MSEC | 4/4 (4/4) | compiled | REFUSED: Unsupported: 미지원 무늬(fail-closed): joint-guard: ((clock.timestamp - $t_ | **완전** |
| P3 | B4 | turn on a GPIO at a repeatable interval where the interval is configurable via a… | partial | 안 | 1/3 (1/3) | compiled | EQUIV | **부분** |

### probe 세부

**P1 (B3) — Brackenbury et al., How Users Interpret Bugs in TAP (CHI 2019), Table 1 (unordered member of the pair)**

원문: IF Sally enters the bedroom AND the sun sets WITHIN 2 hours THEN turn on the bedroom lights.

왜 probe 인가: C20-O covers only the ordered reading. The unordered reading requires remembering that one event happened while the flow may be occupied elsewhere, and re-testing on every later event of the other kind.

해석: Two event kinds: ENTRY = bedroom presence changes absent->present; SUNSET = outdoor brightness changes from >=50 to <50. On each ENTRY, if a SUNSET occurred at most 2 hours earlier, call Switch.On at the instant of the ENTRY. On each SUNSET, if an ENTRY occurred at most 2 hours earlier, call Switch.On at the instant of the SUNSET. Order does not matter and the rule re-arms: every new event is tested against the most recent event of the other kind, so the same SUNSET may pair with several later ENTRYs. Before the first event of a kind, no pairing exists. Never ends.

가정: [가정] 해넘이 = LightSensor.Brightness 가 50 아래로 떨어지는 사건 (C20-O 와 동일) / [가정] '가장 최근의 반대편 사건' 과만 짝짓는다. 더 오래된 사건은 덮어쓴다 / [가정] 같은 사건이 여러 번 짝지어질 수 있다(원문의 WITHIN 2 hours 에 1회 제한이 없음)

시도한 encoding: E-PREV + E-STAMP + E-NULL. One polling flow wakes on any change of either input, records the timestamp of whichever event just occurred, and tests it against the stored timestamp of the other event kind. Symmetric, so order does not matter, and the stored timestamp is not consumed, so one sunset can pair with several later entries.

시도 이력: v1 (race encoding) was written first: wait for the rising edge of `Presence == true or Brightness < 50`, branch on whichever is true, then wait for the other with a 2 HOUR timeout. Executed: 3/4 histories. It fails `one_sunset_two_entries` — after the first pairing the disjunction is still true (it is still dark), so the loop's rising edge never fires again and the second entry at 6600 s produces no ACTION. v2 replaces the edge wait with the snapshot pattern below, which holds no latch.

Explorer: REFUSED: 'explicit input domain required for observable large/unbounded catalog value'. Reading the raw DOUBLE brightness into $b_prev makes the value itself observable, so the Explorer fail-closes instead of certifying. The language and the reference runner accept the encoding; the verifier does not.

extractor 문법 밖 구성: `Clock.Timestamp` (extractor.md documents Clock.Hour/Minute/Day/Month; Timestamp is not among them); `null operand` (extractor.md uses JSON null only as cycle.until; null is not a condition operand); `period 0 MSEC` (extractor.md §D7b requires a period and prescribes 1 SEC / N UNIT values)

| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |
|---|---|---|---|---|---|---|
| entry_then_sunset | nominal | ✓ | ✓ | 1 | 1 |  |
| sunset_then_entry | boundary | ✓ | ✓ | 1 | 1 |  |
| one_sunset_two_entries | boundary | ✓ | ✓ | 2 | 2 |  |
| gap_too_large | boundary | ✓ | ✓ | 0 | 0 |  |

**P2 (B3) — Home Assistant Community thread 363863 (2021-12-06), original post**

원문: I have an automation which sends a notification along with a camera capture for when motion is detected near my front door, which is also equipped with a sensor. ... I wanted to create a condition for the automation, such that this will only get triggered if and only if the door sensor has been triggered (i.e., state changed to "open") within the previous x minutes. Note that within these x minutes, the automation should be able to run as many times as needed/triggered.

왜 probe 인가: The condition is a past event, not a current level, and the rule must fire on every motion inside the window. No Stage A case needed a remembered event time.

해석: x is fixed at 10 minutes. On each motion no-motion->motion change, call MessageSender.SendSms at that instant if and only if the front door changed to open at some time in the preceding 10 minutes (inclusive). Several motion changes inside the same window each send. Motion before the first door opening never sends. Never ends.

가정: [가정] Contact == false 가 '열림'(C05 와 같은 규약). '문이 열림으로 바뀜' = Contact true->false / [가정] 알림 = MessageSender.SendSms 고정 인자. 카메라 캡처는 호출 열을 정하지 않으므로 범위 밖 / [가정] 창은 문이 열린 순간부터 10분(닫힘 시각과 무관)

시도한 encoding: Same E-PREV + E-STAMP + E-NULL pattern. The door-open timestamp is overwritten by each new opening, which is what the requirement's sliding window needs, and the motion branch re-tests it on every motion, so several motions inside one window each send.

시도 이력: v1 measured the window with a `wait(motion rising, timeout "10 MIN")` restarted per motion inside the door-open loop. Executed: 3/4 histories. It measures ten minutes from the previous motion rather than from the opening, because a wait's timeout restarts with the wait and the remaining time cannot be computed (durations are compile-time literals, see P3). On `open_then_motions_in_and_out` it emits a third SMS at 960 s, which is 11 min after the opening but only 4 min after the previous motion. v2 uses the timestamp test below.

**판정 범위 제한: This covers only openings the automation observes WHILE RUNNING. The execution model gives t=0 the current value of each input and has no way to state that the door opened before t=0, so an opening inside the ten minutes preceding start is invisible and cannot even be written as a history. Home Assistant answers that case because the platform stores each entity's last_changed independently of any automation, which is how the thread's own reply solves it (`as_timestamp(states.cover.garage_door.last_changed)`). So the verdict is: remembering events that happen during the run is expressible; pre-start history is outside the model, not merely outside Timeline.**

Explorer: REFUSED: 'joint-guard: ((clock.timestamp - $t_open) <= 600)' is listed fail-closed as an unsupported pattern. The look-back window that makes this requirement expressible is outside the fragment the Explorer certifies.

extractor 문법 밖 구성: `Clock.Timestamp` (extractor.md documents Clock.Hour/Minute/Day/Month; Timestamp is not among them); `null operand` (extractor.md uses JSON null only as cycle.until; null is not a condition operand); `period 0 MSEC` (extractor.md §D7b requires a period and prescribes 1 SEC / N UNIT values)

| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |
|---|---|---|---|---|---|---|
| open_then_motions_in_and_out | nominal | ✓ | ✓ | 2 | 2 |  |
| motion_without_any_open | boundary | ✓ | ✓ | 0 | 0 |  |
| three_motions_inside_one_window | boundary | ✓ | ✓ | 3 | 3 |  |
| second_open_opens_new_window | boundary | ✓ | ✓ | 1 | 1 |  |

**P3 (B4) — Home Assistant Community thread 541232 (2023-02-27), original post**

원문: turn on a GPIO at a repeatable interval where the interval is configurable via a home assistant input number. Once turned on, then the GPIO needs to stay on for a period of time depending on the value of a second home assistant input number, then turn off. ... I thought I could use 'interval.interval' but it seems that the it's not templatable and will only take fixed numbers.

왜 probe 인가: No Stage A case needed a repetition interval or an on-time that is read from a device at run time.

해석: Repeat forever. At the start of each cycle read I = Interval_Setting.CurrentLevel and D = OnTime_Setting.CurrentLevel, both in minutes. Call Switch.On at the start of the cycle, call Switch.Off exactly D minutes later, and start the next cycle exactly I minutes after this cycle's On. A change to either setting takes effect from the next cycle that starts after the change.

가정: [가정] input_number 두 개 = LevelControl.CurrentLevel 두 대(분 단위). 원문 ESPHome GPIO = Switch / [가정] I > D 이며 값은 회차 시작에 읽는다(회차 중 변경은 그 회차에 영향 없음) / [가정] 첫 회차는 t_start 에 시작

시도한 encoding: Attempt B below fixes the two settings at their initial values (20 min interval, 5 min on-time) and therefore reproduces the requirement only while the settings do not change. The body takes 5 min and cycle.period is waited after the body, so period 15 MIN gives a 20 min cadence.

시도 이력: Attempt A writes the durations as variables, exactly as the requirement states them. The reference runner refuses it at compile time with `Unsupported: duration format: '$d_min MIN'`; run_probes.py reproduces the message rather than quoting it. Attempt C, enumerating the possible settings with nested `if` branches and a literal delay per branch, is not written out: LevelControl.CurrentLevel is typed DOUBLE in the service catalog, so the branch set is not finite. Attempt B is the closest encoding that compiles.

**빠진 실행 기능: a duration operand that is read at run time. `delay.duration`, `wait.for`, `wait.timeout` and `cycle.period` are all resolved by explorer.runtime.ir_step.parse_duration at compile time and accept only a literal number or '<n> <UNIT>' string.**

요구대로 쓴 attempt A 에 대한 실행기 응답: `refused: Unsupported: duration format: '$d_min MIN'`

Explorer: EQUIV-FIXPOINT on attempt B. A constant-cadence loop is inside the certified fragment; the refusal is in the language, not in the verifier.

| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |
|---|---|---|---|---|---|---|
| constant_20_5 | nominal | ✓ | ✓ | 6 | 6 |  |
| interval_changed_to_10 | boundary | ✗ | ✗ | 8 | 7 | {'index': 6, 'expected': [3000000, 'switch', 'on', [], ['Hydro_Pump']], 'actual': [3600000, 'switch', 'on', [], ['Hydro_ |
| ontime_changed_to_10 | boundary | ✗ | ✗ | 7 | 8 | {'index': 5, 'expected': [3000000, 'switch', 'off', [], ['Hydro_Pump']], 'actual': [2700000, 'switch', 'off', [], ['Hydr |


## 실행 세부 (이력별)

### C01 — Home Assistant core, blueprints/motion_light.yaml

원문: description: "Turn on a light when motion is detected." / no_motion_wait: "Time to leave the light on after last motion is detected." / mode: restart / actions: light.turn_on -> wait_for_trigger(motion on->off) -> delay(no_motion_wait) -> light.turn_off

가정: [가정] no_motion_wait 기본값 120초 사용 / [가정] HA restart 모드를 문자 그대로 해석: 새로운 motion off→on 재트리거마다 turn_on을 다시 호출한다(중복 On 호출도 관측 ACTION) / [가정] 시작 시 이미 motion=true면 사건이 아니므로 On을 내지 않는다

encoding: Restart mode as one flow. Outer: rising motion -> On. Inner cycle: wait no-motion; wait motion with a 2-minute timeout -> on timeout Off and `break` out of the inner cycle (E-TIMEOUT-ABORT + break); motion returned in time -> explicit On and back to 'wait no-motion'. After the break the outer loop-top rising wait observes the false level and re-arms for the next pass.

수정 이력: v1 (2026-09-12): single cycle, no explicit On after the timeout-wait -> 3/4; the On for motion returning inside the window was missing because the loop-top rising wait's latch is not updated while other waits run. v2: added explicit On at the end of the body -> still 3/4; after that On the loop-top rising wait stayed latched and the flow never returned to 'wait no-motion', so the final Off was missing. v3: inner cycle with break on timeout (this version).

| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |
|---|---|---|---|---|---|---|
| single_pass | nominal | ✓ | ✓ | 2 | 2 |  |
| remotion_during_wait_restarts | boundary | ✓ | ✓ | 3 | 3 |  |
| motion_stays_long | boundary | ✓ | ✓ | 2 | 2 |  |
| second_pass_after_off | boundary | ✓ | ✓ | 4 | 4 |  |

### C03 — TAPInspector (arXiv 2102.01468v2) §V-D, IFTTT applet

원문: Turn on fan for 15 minutes when CO₂>1000ppm

가정: [가정] 15분 진행 중 재교차는 무시(single 실행). 대안 해석(15분 재시작)은 채택하지 않음 / [가정] 시작 시 이미 >1000이면 교차 사건이 아니므로 시작하지 않음

encoding: Rising crossing -> On, fixed delay, Off. Re-crossings during the delay are unobserved (ignored). History 'already_high_at_start' tests the initial-true edge policy of the contract against the requirement.

수정 이력: v1 (2026-09-12): no leading wait -> On at t=0 in 'already_high_at_start' (initial-true edge fires). v2 adds wait(<= 1000) before the cycle.

| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |
|---|---|---|---|---|---|---|
| one_crossing | nominal | ✓ | ✓ | 2 | 2 |  |
| recross_during_run_ignored | boundary | ✓ | ✓ | 2 | 2 |  |
| second_run_after_off | boundary | ✓ | ✓ | 4 | 4 |  |
| already_high_at_start | boundary | ✓ | ✓ | 0 | 0 |  |

### C04 — TAPInspector (arXiv 2102.01468v2) §V-D, IFTTT applet

원문: At noon turn your fan on for 15 minutes

가정: [가정] 매일 반복(cron '0 12 * * *'). 실행 확인은 한 번의 발화 창(12:00~12:15)만 검사

encoding: Calendar anchor + delay. Reference runner rejects the cron anchor; executed with anchor erased at 12:00.

| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |
|---|---|---|---|---|---|---|
| noon_window | nominal | ✓ | ✓ | 2 | 2 |  |

### C05 — Home Assistant Community thread 520305 (2023-01-18)

원문: set notification if door is left open for 2 minutes and if not closed after that it should send notifications each minute

가정: [가정] Contact=false 가 '열림' / [가정] 알림 = MessageSender.SendSms 고정 인자 / [가정] 닫힌 뒤 다시 열리면 알림 간격 중이었더라도 2분 지속부터 다시 셈

encoding: Sustain 2 min, then an inner cycle: send; wait up to 60 s for the door to close (E-TIMEOUT-ABORT with empty block = just continue). Inner `until` checks closed at each iteration start; a close during the 60 s makes the wait succeed at once, so the next until-check exits without sending. Nested cycle: frontend may refuse.

수정 이력: v1 (2026-09-12): inner period 100 MSEC -> match 4/4 but exact 0/4 (100 ms added per iteration: 130.0, 190.1, 250.2, ...). B audit: the body's 60 s timeout already carries the cadence, so v2 sets the inner period to 0 MSEC (E-ZERO-PERIOD). Verified after v2: match 4/4, exact 4/4.

| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |
|---|---|---|---|---|---|---|
| open_then_close_at_400 | nominal | ✓ | ✓ | 5 | 5 |  |
| closed_before_2min_restarts | boundary | ✓ | ✓ | 2 | 2 |  |
| reopen_after_close | boundary | ✓ | ✓ | 4 | 4 |  |
| brief_close_between_notifications | boundary | ✓ | ✓ | 7 | 7 |  |

### C07 — Home Assistant Community thread 783900 (2024-10-20)

원문: trigger: "garage door is left open after 22:00 for more than 10 minutes"; "Blink the kitchen lights by dimming up and down 10 times in quick succession"; "pause for 5 minutes"; "Repeat the cycle up to 7 times"; "If at any point during the blinking cycles, the garage door is closed, stop the automation immediately"; "Ensure the kitchen lights return to their original state ... after the automation ends or during the pauses"

가정: [가정] '깜빡임' = MoveToBrightness(10)/(100) 를 0.5초 간격, Rate=0 / [가정] 원상태 = 시작 시 읽은 밝기 B0 하나 (색 등은 제외) / [가정] 22:00 이후 조건과 문 열림의 지속 10분은 둘이 동시에 성립한 시각부터 셈 / [가정] 자동화는 한 번 실행되고 끝남(다음 날 재시작은 범위 밖) / [가정] Contact=false 가 '열림'

encoding: Sustained conjunction (clock >= 22 and open) for 10 min; snapshot B0; outer cycle (count c, period 5 MIN = pause after the body) with until 'c >= 7 or closed'; inner blink cycle (count k, until 'k >= 10 or closed'). Each half-blink delay is a wait-for-close with 500 ms timeout, so a close interrupts at the exact instant and the following restore(B0) is emitted then. After the inner loop the restore is emitted once; a close during the pause exits at the next until-check with no ACTION. Nested cycles and count/until on the same cycle: frontend may refuse.

수정 이력: v1 (2026-09-12): both half-blink timeouts 500 ms -> 1/4; each blink iteration took 1.1 s because cycle.period is waited AFTER the body, so 10 blinks drifted 1 s and the next cycle started 1.1 s late. v2 sets the second timeout to 400 ms so body + period = 1.0 s -> match 4/4, exact 3/4: the restore after a close during blinking was up to 100 ms late because the inner period ran after the body. B audit: v3 uses 500 ms + 500 ms and inner period 0 MSEC (E-ZERO-PERIOD), so blink cadence stays 1 s and a close is answered at its own instant. Verified after v3: match 4/4, exact 4/4.

| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |
|---|---|---|---|---|---|---|
| stays_open_all_7_cycles | nominal | ✓ | ✓ | 147 | 147 |  |
| closes_during_second_pause | boundary | ✓ | ✓ | 42 | 42 |  |
| closes_during_first_blinking | boundary | ✓ | ✓ | 8 | 8 |  |
| closed_before_10min_no_run | boundary | ✓ | ✓ | 0 | 0 |  |

### C09 — AutoTap (ICSE 2019) §III, Event-Event Conditional sample

원문: My smart door lock should always lock after I come in.

가정: [연구자 변환] 원문은 안전 속성; '들어오면 잠근다' 자동화로 바꿈 / [가정] 잠금 시각 = 도착 순간(지연 없음) / [가정] 시작 시 이미 present 면 사건이 아님

encoding: Rising presence -> Lock, forever. The contract fires a rising-edge wait when its condition is already true at first evaluation, so an initial wait for absence is needed to make 'present at start' a non-event.

수정 이력: v1 (2026-09-12): no leading wait -> Lock at t=0 in 'present_at_start' (initial-true edge fires). v2 adds wait(absent).

| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |
|---|---|---|---|---|---|---|
| one_arrival | nominal | ✓ | ✓ | 1 | 1 |  |
| two_arrivals | boundary | ✓ | ✓ | 2 | 2 |  |
| present_at_start_is_not_arrival | boundary | ✓ | ✓ | 1 | 1 |  |

### C11 — AutoTap (ICSE 2019) §VI-A Task 11 and authors' rule explanation

원문: "IF Roomba becomes on WHILE the curtain is open, THEN close the curtain; IF curtain becomes open WHILE Roomba is on, THEN turn off Roomba" (property: "Roomba is on should NEVER be active WHILE curtain is open")

가정: [가정] Roomba on = OperatingState == 'running'; 끄기 = SetRobotVacuumCleanerRunMode('idle') (2026-09-12 해시 후 수정: 처음 쓴 'cleaning'/'stop' 은 catalog enum 에 없음 — 값 이름만 바꿈, 행동 해석 불변) / [가정] 커튼 열림 = CurrentPosition > 0 / [가정] 동시 변화면 (a) 다음 (b) 순서로 둘 다 호출 / [메모] 이 사례의 두 rule 에는 delay·중첩 인스턴스·action→trigger 되먹임이 없어 직전 snapshot 판별이 두 독립 rule 과 같은 trace 를 낸다. 일반적으로 snapshot 이 병렬 rule 을 대체한다는 주장이 아님(감사 2026-09-12) / [가정] 자동화의 ACTION 이 만든 상태 변화(커튼 닫힘 등)는 입력 이력에 명시된 시점에만 반영

encoding: Two reactions in one flow via E-PREV: poll every 100 ms; the previous iteration's snapshots decide which input changed. Both `if`s may fire in one iteration (both changed together), in the required order. Does not spawn two flows: the audit confirmed that this case has no delay, no overlapping instance and no action->trigger feedback, so the single-flow trace equals the two rules' trace. That is a statement about this case, not a general claim that snapshots replace concurrent rules (B2).

| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |
|---|---|---|---|---|---|---|
| vacuum_starts_while_open | nominal | ✓ | ✓ | 1 | 1 |  |
| curtain_opens_while_cleaning | nominal | ✓ | ✓ | 1 | 1 |  |
| both_change_together | boundary | ✓ | ✓ | 2 | 2 |  |
| sequence_of_both_directions | boundary | ✓ | ✓ | 2 | 2 |  |

### C15 — Ur et al., Practical Trigger-Action Programming in the Smart Home (CHI 2014), participant quote

원문: When I get up at night, I would want my lights to turn on and off as I enter and exit the room.

가정: [가정] 밤 = Clock.Hour >= 22 또는 < 6 / [가정] 밤에 들어와 켠 뒤 06:00 이후에 나가도 Off 는 낸다 / [가정] '방' = 침실 하나, 사람 감지 = PresenceSensor

encoding: Rising presence, then branch on the night window; only then On / wait absent / Off. Putting the clock inside the rising condition would fire at 22:00 for someone already in the room, which the contract rejects.

| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |
|---|---|---|---|---|---|---|
| two_visits_at_night | nominal | ✓ | ✓ | 4 | 4 |  |
| entry_before_night_ignored | boundary | ✓ | ✓ | 2 | 2 |  |
| in_room_when_night_starts | boundary | ✓ | ✓ | 0 | 0 |  |

### C16 — Ur et al. (CHI 2014) Table 1, Task I

원문: If it is 10:00pm and my bedroom door is closed and the lights are off, turn the television off.

가정: [가정] '10:00pm' = 22:00 정각 한 번 검사 (창 아님) / [가정] Contact=true 가 '닫힘'; TV 끄기 = TV 기기의 Switch.Off

encoding: Cron anchor + one-shot branch. Two Switch binding slots (read on light, call on TV). Executed with anchor erased at 22:00.

| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |
|---|---|---|---|---|---|---|
| conditions_hold | nominal | ✓ | ✓ | 1 | 1 |  |
| light_on_no_action | boundary | ✓ | ✓ | 0 | 0 |  |

### C18 — Huang & Cakmak, Supporting Mental Model Accuracy in TAP (UbiComp 2015), Table 5 Q3

원문: If the doorbell rings and the time is 3:00 pm, then unlock the front door for 10 seconds

가정: [가정] '3:00 pm' = 15시 한 시간 창 (원 논문이 순간/창 해석이 갈린다고 보고한 항목) / [가정] 벨 = Button 값이 'pushed' 로 바뀌는 사건; 같은 값이 유지되는 것은 새 사건이 아님 / [가정] 10초 진행 중 재누름 무시

encoding: Rising 'pushed' event, hour-window branch, unlock/delay/lock. Presses during the delay are unobserved.

| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |
|---|---|---|---|---|---|---|
| press_in_window | nominal | ✓ | ✓ | 2 | 2 |  |
| press_before_and_after_window | boundary | ✓ | ✓ | 0 | 0 |  |
| double_press_ignored | boundary | ✓ | ✓ | 2 | 2 |  |

### C19 — Huang & Cakmak (UbiComp 2015), Table 4 P3

원문: Your work starts at 9:00 am. On days when you get to work on time, you want to send an email to yourself saying "I got to work on time!"

가정: [가정] 감시 시작 06:00 (cron '0 6 * * *'); 실행 확인은 하루 창만 / [가정] '정시' = 09:00:00 이하 (같음 포함) / [가정] 도착 = PresenceSensor 가 present 로 바뀜

encoding: Wait for absence first (a presence already true at 06:00 is not an arrival), then race arrival against 09:00 as a disjunctive wait. The race itself enforces the deadline: at 09:00:00 the wait fires with the clock, so a later arrival never reaches the branch; the branch only needs 'present'. Cron anchor erased at 06:00.

수정 이력: v1 (2026-09-12): no leading absence wait; branch 'Hour < 9 or (Hour == 9 and Minute == 0)' claimed as a minute-resolution approximation (lang=partial), match 3/3. B audit: that explanation was wrong (the race already ends at 09:00:00, so 09:00:30 never passes); the real defect was treating a presence already true at start as an arrival. v2 adds wait(absent) first, simplifies the branch to 'present', lang=full; two histories added to cases.py.

| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |
|---|---|---|---|---|---|---|
| arrive_0800 | nominal | ✓ | ✓ | 1 | 1 |  |
| arrive_0930_no_mail | boundary | ✓ | ✓ | 0 | 0 |  |
| arrive_exactly_0900 | boundary | ✓ | ✓ | 1 | 1 |  |
| already_present_at_start_no_mail | boundary | ✓ | ✓ | 0 | 0 |  |
| arrive_0900_30_no_mail | boundary | ✓ | ✓ | 0 | 0 |  |

### C20-O — Brackenbury et al., How Users Interpret Bugs in TAP (CHI 2019), Table 1

원문: IF Sally enters the bedroom AND AFTERWARDS the sun sets WITHIN 2 hours THEN turn on the bedroom lights.

가정: [가정] 해넘이 = LightSensor.Brightness 가 50 아래로 떨어지는 사건 / [가정] 창 안 재입장은 창을 다시 시작(restart) / [감사 2026-09-12] 이 사례는 CHI'19 Table 1 의 순서형 문장(AND AFTERWARDS)만을 대상으로 확정한다. 짝을 이루는 unordered 문장은 별개의 요구이므로 경계 probe P1 (probes.py) 로 분리해 따로 시도·실행했다. 성공 분모에서 뺀 것이 아니다

encoding: The case is the ordered 'AND AFTERWARDS' sentence (B audit 2026-09-12); the paired unordered sentence is probe P1. Rising entry opens the window; then wait (rising) for 'dark or left' with a 2 h timeout (E-TIMEOUT-ABORT). Leaving ends the window; a later re-entry opens a new one, which coincides with 'restart on re-entry' for entries that require a leave first. 'Dark already before entry' must NOT fire: relies on the edge latch not firing on an initially-true condition. The unordered sentence is encoded separately in probe_attempts.py (P1).

수정 이력: v1 (2026-09-12): no guard -> On at the entry instant when it was already dark (initial-true edge fires). v2 guards the window with 'bright at entry'.

| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |
|---|---|---|---|---|---|---|
| enter_then_sunset_in_window | nominal | ✓ | ✓ | 1 | 1 |  |
| sunset_after_window_expired | boundary | ✓ | ✓ | 0 | 0 |  |
| sunset_before_entry_ordered_no_fire | boundary | ✓ | ✓ | 0 | 0 |  |
| reentry_restarts_window | boundary | ✓ | ✓ | 1 | 1 |  |
