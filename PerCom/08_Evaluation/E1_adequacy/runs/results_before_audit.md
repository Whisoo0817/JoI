# E1 Stage A 결과 (기계 열 자동 채움; B·G 열은 whisoo)

생성: `python make_results.py`. 근거: `runs/e1_stageA.json`, `cases.py`, `irs.py`. **논문 결과가 아니다.**

## 사례별

| ID | 요소 | 경계 | A-언어(작성자 주장) | A-frontend | B 감사 | C 실행 일치 (정확) | D 실행기 | E Explorer(참고) | F binding | G JoI | 메모 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C01 | R1 R3 R7 B1 | ★ | full | accepted |  | 4/4 (4/4) | compiled | EQUIV (EQUIV-FIXPOINT) | selector/Service.Method 1 ✓ |  | encoding 수정 이력 있음(irs.py) |
| C03 | R1 R2 |  | full | accepted |  | 4/4 (4/4) | compiled | EQUIV (EQUIV-FIXPOINT) | selector/Service.Method 1 ✓ |  | encoding 수정 이력 있음(irs.py) |
| C04 | R9 R2 |  | full | accepted |  | 1/1 (1/1) | compiled (cron anchor erased; one firing window executed) | EQUIV (EQUIV-FIXPOINT) | selector/Service.Method 1 ✓ |  |  |
| C05 | R3 R7 |  | full | accepted |  | 4/4 (0/4) | compiled | EQUIV (EQUIV-FIXPOINT) | selector/Service.Method 1 ✓ |  |  |
| C07 | R9 R3 R5 R8 B5 B1 | ★ | full | accepted |  | 4/4 (3/4) | compiled | UNKNOWN (INCONCLUSIVE) | selector/Service.Method 1 ✓ |  | encoding 수정 이력 있음(irs.py) |
| C09 | R1 R4 |  | full | accepted |  | 3/3 (3/3) | compiled | EQUIV (EQUIV-FIXPOINT) | selector/Service.Method 1 ✓ |  | encoding 수정 이력 있음(irs.py) |
| C11 | R1 B2 | ★ | full | accepted |  | 4/4 (4/4) | compiled | EQUIV (EQUIV-FIXPOINT) | selector/Service.Method 1 ✓ |  |  |
| C15 | R4 R7 R9 |  | full | accepted |  | 3/3 (3/3) | compiled | UNKNOWN (INCONCLUSIVE) | selector/Service.Method 1 ✓ |  |  |
| C16 | R9 R6 |  | full | accepted |  | 2/2 (2/2) | compiled (cron anchor erased; one firing window executed) | EQUIV (EQUIV-FIXPOINT) | selector/Service.Method 1 ✓ |  |  |
| C18 | R1 R9 R2 |  | full | accepted |  | 3/3 (3/3) | compiled | UNKNOWN (INCONCLUSIVE) | selector/Service.Method 1 ✓ |  |  |
| C19 | R10 R9 |  | partial | accepted |  | 3/3 (3/3) | compiled (cron anchor erased; one firing window executed) | EQUIV (EQUIV-FIXPOINT) | selector/Service.Method 1 ✓ |  |  |
| C20 | R1 R2 B3 B1 | ★ | partial | accepted |  | 4/4 (4/4) | compiled | UNKNOWN (INCONCLUSIVE) | selector/Service.Method 1 ✓ |  | encoding 수정 이력 있음(irs.py) |

## 요소 × 사례 (경계 표)

| 요소 | 뜻 | 사례 | C 통과/전체 | 비고 |
|---|---|---|---|---|
| R1 | 즉시 반응 | C01 C03 C09 C11 C18 C20 | 6/6 |  |
| R2 | 지연 후 호출 | C03 C04 C18 C20 | 4/4 |  |
| R3 | 지속 조건+reset | C01 C05 C07 | 3/3 |  |
| R4 | 사건 한 번/재무장 | C09 C15 | 2/2 |  |
| R5 | 저장값 흐름 | C07 | 1/1 |  |
| R6 | 순차·분기 | C16 | 1/1 |  |
| R7 | 조건까지 반복(주기) | C01 C05 C15 | 3/3 | C05: 정확 일치 0/4 — period 가 회차 종료 후 대기라 회차마다 100 ms 누적(1초 허용 안) |
| R8 | 고정 횟수 반복 | C07 | 1/1 |  |
| R9 | 시계 앵커·시간대 | C04 C07 C15 C16 C18 C19 | 6/6 | cron 앵커 3건(C04 C16 C19)은 실행기가 거절 → 앵커 소거 후 한 창만 실행. Clock 은 분 단위(C19 근사) |
| R10 | 시각 vs 사건 경쟁 | C19 | 1/1 |  |
| B1 | 즉시 취소·재시작 | C01 C07 C20 | 3/3 | C07: 취소가 100 ms 격자에서 감지(정확 일치 1건 실패, 1초 허용 안). C01/C20: 재시작·취소를 timeout+break 조합으로 표현 |
| B2 | 독립 두 흐름/인스턴스 | C11 | 1/1 | C11: 두 흐름을 만들지 않고 이전 회차 snapshot(read)으로 '무엇이 바뀌었나'를 판별. 두 TAP 규칙과 같은 행동인지는 감사 판단 |
| B3 | 이벤트 기억·look-back | C20 | 1/1 | C20 은 순서 있는 변형만 통과. 순서 없는(look-back) 변형은 **작성하지 않음** — B3 자체는 Stage A 에서 미평가 |
| B4 | 가변 간격 반복 | (Stage A 없음) | - | Stage B 후보 필요 |
| B5 | 중첩 반복 | C07 | 1/1 |  |

Explorer 참고 열: EQUIV-FIXPOINT 8건, UNKNOWN 4건(C07·C20 transition cap, C15·C18 state cap — 120 s 예산 안, IR×IR 자기 product). UNKNOWN 은 표현 실패가 아니라 탐색 미완이며 A 판정을 바꾸지 않는다.

## 실행 세부 (이력별)

### C01 — Home Assistant core, blueprints/motion_light.yaml

원문: description: "Turn on a light when motion is detected." / no_motion_wait: "Time to leave the light on after last motion is detected." / mode: restart / actions: light.turn_on -> wait_for_trigger(motion on->off) -> delay(no_motion_wait) -> light.turn_off

가정: [가정] no_motion_wait 기본값 120초 사용 / [가정] HA restart 모드를 문자 그대로 해석: 재감지마다 turn_on을 다시 호출한다(중복 On 호출도 관측 ACTION) / [가정] 시작 시 이미 motion=true면 사건이 아니므로 On을 내지 않는다

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

| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |
|---|---|---|---|---|---|---|
| open_then_close_at_400 | nominal | ✓ | ✗ | 5 | 5 |  |
| closed_before_2min_restarts | boundary | ✓ | ✗ | 2 | 2 |  |
| reopen_after_close | boundary | ✓ | ✗ | 4 | 4 |  |
| brief_close_between_notifications | boundary | ✓ | ✗ | 7 | 7 |  |

### C07 — Home Assistant Community thread 783900 (2024-10-20)

원문: trigger: "garage door is left open after 22:00 for more than 10 minutes"; "Blink the kitchen lights by dimming up and down 10 times in quick succession"; "pause for 5 minutes"; "Repeat the cycle up to 7 times"; "If at any point during the blinking cycles, the garage door is closed, stop the automation immediately"; "Ensure the kitchen lights return to their original state ... after the automation ends or during the pauses"

가정: [가정] '깜빡임' = MoveToBrightness(10)/(100) 를 0.5초 간격, Rate=0 / [가정] 원상태 = 시작 시 읽은 밝기 B0 하나 (색 등은 제외) / [가정] 22:00 이후 조건과 문 열림의 지속 10분은 둘이 동시에 성립한 시각부터 셈 / [가정] 자동화는 한 번 실행되고 끝남(다음 날 재시작은 범위 밖) / [가정] Contact=false 가 '열림'

encoding: Sustained conjunction (clock >= 22 and open) for 10 min; snapshot B0; outer cycle (count c, period 5 MIN = pause after the body) with until 'c >= 7 or closed'; inner blink cycle (count k, until 'k >= 10 or closed'). Each half-blink delay is a wait-for-close with 500 ms timeout, so a close interrupts at the exact instant and the following restore(B0) is emitted then. After the inner loop the restore is emitted once; a close during the pause exits at the next until-check with no ACTION. Nested cycles and count/until on the same cycle: frontend may refuse.

수정 이력: v1 (2026-09-12): both half-blink timeouts 500 ms -> 1/4; each blink iteration took 1.1 s because cycle.period is waited AFTER the body, so 10 blinks drifted 1 s and the next cycle started 1.1 s late. v2 sets the second timeout to 400 ms so body + period = 1.0 s. This is encoding to the declared period semantics, not a change of the contract; note that 'every N' cadences need the body time subtracted (see C05 exact-time column).

| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |
|---|---|---|---|---|---|---|
| stays_open_all_7_cycles | nominal | ✓ | ✓ | 147 | 147 |  |
| closes_during_second_pause | boundary | ✓ | ✓ | 42 | 42 |  |
| closes_during_first_blinking | boundary | ✓ | ✗ | 8 | 8 |  |
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

가정: [가정] Roomba on = OperatingState == 'running'; 끄기 = SetRobotVacuumCleanerRunMode('idle') (2026-09-12 해시 후 수정: 처음 쓴 'cleaning'/'stop' 은 catalog enum 에 없음 — 값 이름만 바꿈, 행동 해석 불변) / [가정] 커튼 열림 = CurrentPosition > 0 / [가정] 동시 변화면 (a) 다음 (b) 순서로 둘 다 호출 / [가정] 자동화의 ACTION 이 만든 상태 변화(커튼 닫힘 등)는 입력 이력에 명시된 시점에만 반영

encoding: Two reactions in one flow via E-PREV: poll every 100 ms; the previous iteration's snapshots decide which input changed. Both `if`s may fire in one iteration (both changed together), in the required order. Does not spawn two flows; whether this is 'the same behavior' as two TAP rules is the audit's call (B2).

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

encoding: Race between arrival and 09:00 as a disjunctive wait, then a branch. The clock has minute resolution in the model, so 'at or before 09:00:00' is encoded as 'before 09:01:00' (over-inclusive by <60 s). Cron anchor erased at 06:00.

| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |
|---|---|---|---|---|---|---|
| arrive_0800 | nominal | ✓ | ✓ | 1 | 1 |  |
| arrive_0930_no_mail | boundary | ✓ | ✓ | 0 | 0 |  |
| arrive_exactly_0900 | boundary | ✓ | ✓ | 1 | 1 |  |

### C20 — Brackenbury et al., How Users Interpret Bugs in TAP (CHI 2019), Table 1

원문: IF Sally enters the bedroom AND AFTERWARDS the sun sets WITHIN 2 hours THEN turn on the bedroom lights. (unordered variant: IF Sally enters the bedroom AND the sun sets WITHIN 2 hours THEN ...)

가정: [가정] 해넘이 = LightSensor.Brightness 가 50 아래로 떨어지는 사건 / [가정] 창 안 재입장은 창을 다시 시작(restart) / [가정] 실행 확인은 순서 있는 변형만; 순서 없는 변형은 look-back 기억이 필요해 B3 로 기록

encoding: ORDERED variant only. Rising entry opens the window; then wait (rising) for 'dark or left' with a 2 h timeout (E-TIMEOUT-ABORT). Leaving ends the window; a later re-entry opens a new one, which coincides with 'restart on re-entry' for entries that require a leave first. 'Dark already before entry' must NOT fire: relies on the edge latch not firing on an initially-true condition. The UNORDERED (look-back) variant is not encoded: B3.

수정 이력: v1 (2026-09-12): no guard -> On at the entry instant when it was already dark (initial-true edge fires). v2 guards the window with 'bright at entry'.

| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |
|---|---|---|---|---|---|---|
| enter_then_sunset_in_window | nominal | ✓ | ✓ | 1 | 1 |  |
| sunset_after_window_expired | boundary | ✓ | ✓ | 0 | 0 |  |
| sunset_before_entry_ordered_no_fire | boundary | ✓ | ✓ | 0 | 0 |  |
| reentry_restarts_window | boundary | ✓ | ✓ | 1 | 1 |  |
