# E1 — 경계 표 중심의 외부 요구 표현 적합성 사례 연구

시작 2026-09-12, **E1 종료 2026-09-13**. 최종 결과는 `E1_SUMMARY.md`(depth 20건 + corpus 100), 원고는 `../PerCom_version.md` E1 절이다.
이 README 는 Stage A(12건) 절차·결정·경계 probe 의 기록이다. Stage A 결과 표: `results.md`. 감사 전 결과 보존: `runs/e1_stageA_before_audit.json`, `runs/results_before_audit.md`.
설계 배경과 결정은 세션 논의(2026-09-12)에 따른다. 상위 계획: `../../../skill_result/05_experiment_plan/confirmed_ir_evaluation_2026-09-10.md`(E1 절은 이 문서의 경계 표 설계로 갱신됨, 2026-09-12). 원고 반영: `../PerCom_version.md`, `../HANDOFF.md`.
작업 공간은 2026-09-12에 `skill_result/05_experiment_plan/e1_adequacy_2026-09-12/`에서 이곳으로 옮겼다(git mv, 내용 동일).

## 0. 결론 (이 폴더를 처음 여는 사람용; 2026-09-14 갱신)

**말할 수 있는 것(최종).** 외부 요구 corpus 100건(IN_SCOPE 92) 중 depth 20건(Stage A 12 + 추가 8)을 Timeline IR 로 표현했고,
사전 등록한 53개 입력 이력이 모두 기대 ACTION 과 정확히 일치했다(53/53). **20/20 은 선정 사례 중의 건수이며 coverage 가 아니다.**
Stage A 12건(41/41)에서는 감사가 인코딩 결함 3건(C05·C07·C19)을 잡았고 수정 전 결과를 보존했다. 표는 `E1_SUMMARY.md`.

**경계를 찾으려고 따로 시험한 것.** 성공 사례만으로는 경계를 말할 수 없어, Stage A 가 닿지 않은
경계 후보를 사전 등록 요구 3건(P1 P2 P3)으로 시도했다. **세 후보 모두 언어의 경계가 아니었다.**
가변 간격은 카운터 반복 + 단위 delay 로, 도는 중 이벤트 기억은 시계 스냅샷으로 표현됐고 전부 정확히 일치했다.

**실제로 찾은 경계는 언어가 아니라 검증기다.** probe 3건이 모두 언어·실행기를 통과하고 Explorer 만 거절했다.
거절 사유는 두 종류다 — P2·P3 은 실행 중 값끼리 비교하는 guard(joint-guard), P1 은 범위가 정해지지 않은 관측값(입력 domain 필요).
따라서 E1 의 결론은 "IR 이 어디까지 표현하나" 가 아니라 **"표현되는 것 중 어디까지 인증되나"** 로 옮겨간다.

**언어 한계(2026-09-13 저자 의미 감사로 확정).** 옛 논증 "유한 상태 / 대입 연산 없음 / 단일 제어 흐름" 은 **대체됐다**.
쓸 수 있는 문장은 `../../05_Timeline_IR/HANDOFF.md` "쓸 수 있는 것": Timeline 하나에 병렬 branch 없음(독립 흐름만 분해, E1-092),
고정 개수 집계(E1-095)·고정 한도 2(E1-028), 일반 누적·동적 집계는 backend 위임. **"고정 프로그램이라 finite-state" 는 쓰지 않는다.**

**언어 문제가 아닌 것.** 자동화가 켜지기 전의 과거는 서비스·카탈로그 문제다. 기기별 변경 시각을 주는
서비스를 JoI 에 두면 IR 은 `read` 한 줄로 쓴다. **"Timeline 은 못 한다" 고 쓰면 안 된다.**

상세는 §6 경계 probe, 표는 `results.md`. 파일 역할은 §7.

## 목적과 주장 경계

확인하는 것: 고정된 Timeline IR로 **외부의 구체적인 reactive-temporal 요구**를 표현할 수 있는지,
표현된 요구의 시간·상태·행동 의미가 유지되는지, 한계가 어디인지.

주장하지 않는 것: 전체 스마트홈 coverage, JoI 전체에 대한 표현 완전성, LLM의 NL→IR 정확도,
일반 사용자 확인 성공률. 일부 trace의 일치는 전체 의미 동치 증명이 아니다.

## 선례와 차이

- AutoTap (ICSE 2019 §III·IV·VI): 71명의 자유서술 요구를 7 template로 분류, 나머지는 out-of-scope/ambiguous로 분리. Study 2의 14 task는 Study 1 기반이라 표현 가능한 쪽으로 편향됐다고 저자가 명시.
- Dwyer et al. (ICSE 1999 §3): 35+출처 555건을 패턴/scope에 대응, 미매칭 44건은 UNKNOWN으로 보존, 자체 작성(304) vs 외부(251) 분리.
- 두 연구 모두 수집 자료가 표현 체계의 설계·보완에 쓰였다. **held-out 평가 선례로 인용하지 않는다.**
- 우리가 추가하는 절차: 요구 해석과 입력별 기대 ACTION trace를 IR 작성 전에 고정하고, IR 실행 결과와 비교한다.

## 1. 범위 (사용자 행동 기준)

포함: 한 개의 자동화로서, 기기·시간 입력 이력이 주어지면 서비스 호출의 시각·대상·인자·횟수·순서가 정해지는 요구.

| 요소 | 뜻 | | 경계 후보 | 뜻 |
|---|---|---|---|---|
| R1 | 즉시 반응 | | B1 | 진행 중 즉시 취소·재시작 |
| R2 | 지연 후 호출 | | B2 | 독립 두 흐름 / 여러 인스턴스 |
| R3 | 지속 조건 + 끊기면 다시 셈 | | B3 | 이벤트 기억·시간창(look-back) |
| R4 | 사건 한 번 / 다시 무장 | | B4 | 가변 간격 반복 |
| R5 | 저장값이 나중 호출에 흐름 | | B5 | 중첩 반복 |
| R6 | 순차·분기 | | | |
| R7 | 조건까지 반복(주기) | | | |
| R8 | 고정 횟수 반복 | | | |
| R9 | 시계 앵커·시간대 조건 | | | |
| R10 | 정해진 시각 vs 사건 경쟁 | | | |

제외(분모에 넣지 않음): 호출을 정하지 않는 안전 속성, 여러 자동화 간 우선순위·충돌, 판단이 필요한 fuzzy trigger·새 기능 요청, 물리 과정의 완료.

## 2. 절차 (열 순서 = 작업 순서)

| 단계 | 열 | 담당 | 내용 |
|---|---|---|---|
| 1 | 원문·출처·접근일 | 작성자 | `cases.py` |
| 2 | 해석 확정 | 작성자 → 감사 | 초기 상태, 평가 시점, reset, 종료, 재진입, 허용 오차. 원문에 없는 항목은 `[가정]` |
| 3 | 기대 trace | 작성자 → 감사 | 이력 2~4개, `(시각, Service.Method, 인자, 대상)`. **IR 작성 전 고정** |
| 4 | A. IR 작성 | 작성자 | 완전 / 부분(빠진 요소) / 불가(문법·의미 근거) / 보류. A-언어(논문 Timeline 계약) 와 A-frontend(`timeline_ir.validate_ir`) 를 나눠 기록 |
| 5 | B. 의미 감사 | **whisoo** | IR이 2단계 해석을 보존/변경/누락 |
| 6 | C. 실행 일치 | 기계 | 참조 IR 실행기로 3단계 이력 재생, n/m 일치, 1초 허용(정확 일치 별도) |
| 7 | D. 참조 실행기 지원 | 기계 | 컴파일 거절 여부. cron 앵커는 실행기가 거절 → 앵커 소거 후 한 창만 실행하고 기록 |
| 8 | E. Explorer 지원(참고) | 기계 | IR×IR 자기 product 결과. **E1 정답이 아님** |
| 9 | F. binding 계약 | 작성자 | `Service.Method`당 selector 하나로 되는가 |
| 10 | G. JoI 구현 가능성 | 작성자 | 불가/부분 사례만 손으로 JoI 시도. 나머지 "미확인". 단일/여러 자동화 조건 구분 |

판정: **완전** = A 완전 ∧ B 보존 ∧ C 전부 일치. **부분** = 요소 삭제 또는 시간·재진입 의미 변경(무엇을 바꿨는지 명시).
**불가** = 조합 시도 후 빠진 실행 기능 명시. **보류** = 해석이 갈리고 출처가 정하지 않음(가정으로 확정한 경우와 구분).
D·E 결과는 A 판정을 바꾸지 못한다.

## 3. 결정 기록 (whisoo, 2026-09-12)

- 감사자: whisoo. LLM 합의만으로 독립 감사라 부르지 않는다.
- 기대 trace 비교: 1초 허용(정확 일치는 별도 기록).
- AutoTap 속성→자동화 변환 허용(해당 사례에 `[연구자 변환]` 표시).
- 커뮤니티 글 사용: URL·게시일·접근일 기록. 본문 대표 사례는 공식/논문 출처 우선.
- C06 "any of N doors" 는 B2 로 판정하고 binding 경계와 분리.
- horizon 은 사례별(마지막 기대 ACTION + 요구 시간 단위).

## 4. 버전 고정

- **실행 시점 repo commit**(실행기·frontend·catalog 이 이 상태였다): `0356601b597d7c1e5c66d2652f62bd5cab3bef62` (2026-09-12 12:04 +0900). 아래 sha256 네 개가 그 상태를 고정한다.
- **결과 artifact commit**(이 폴더의 자료가 기록된 커밋, 실행기 상태와 구분한다):
  - `9b01ec9` — Stage A 12건 + whisoo B 감사 반영(감사 전 결과 보존 포함).
  - `7d989c3` — 작업 공간을 `skill_result/05_experiment_plan/e1_adequacy_2026-09-12/` 에서 `PerCom/08_Evaluation/E1_adequacy/` 로 이동(내용 동일).
  - `4a43629` — 경계 probe P1·P2·P3 추가, A-extractor 문법 열, C20→C20-O 분리, 감사 전 문구 정리.
- `explorer/runtime/ir_step.py` sha256 `c21875d7…ecc21d`
- `timeline_ir/timeline_ir.py` sha256 `6cab4f2c…b00598`
- `explorer/verification/gate.py` sha256 `6e2e9696…3280f1`
- `explorer/runtime/interp.py` sha256 `9de49eab…364a671`
- **`cases.py` (해석·기대 trace, IR 없음) sha256 `83ba687eb67943d9d82f5f9904e1f198c9094b285aaa32c02c5a69f80e7fdab4`** — `irs.py` 는 이 해시 기록 후 작성.
  - 해시 후 수정 3건(해석·기대 trace 의 뜻은 바꾸지 않음, 파일 안에 주석으로 표시):
    1. C16 binding `{"Switch": [light, tv]}` → `{"Switch": [light], "Switch#2": [tv]}` (읽기/호출 메서드별 자리 분리; 처음 표기는 fan-out 한 자리로 읽힘).
    2. C07 `closes_during_first_blinking` 닫힘 시각 903.25 s → 903.2 s (입력 100 ms 격자 위로 이동).
    3. C11 enum 값 `cleaning`/`stop` → catalog 실제 멤버 `running`/`idle` (이름만 교체).
  - 수정 후 sha256 `ce657f9b88c699afa58b0595998bfa4c5659633d0a2d357f7718605fd04afb53`.
- `irs.py` 의 encoding 수정 이력은 각 항목의 `history` 필드에 남긴다(C01 v1→v3, C03 v1→v2, C07 v1→v3, C09 v1→v2, C20-O v1→v2, 감사 후 C05 v2·C19 v2). 실행기·계약은 바꾸지 않았다.
- 감사 후 `cases.py` 변경: C01 가정 문구(“새로운 motion off→on 재트리거마다”), C11 메모, C19 이력 2개 추가(`already_present_at_start_no_mail`, `arrive_0900_30_no_mail`), C20-O `elements` 에서 B3 제거(순서형 문장만 사례로 확정).
- 실행기 의미나 tolerance 를 결과에 맞춰 바꾸지 않는다. 수정이 필요하면 전후와 영향을 이 문서에 기록한다.

관측 계약: `explorer/docs/model/VERIFICATION_CONTRACT.md` 그대로. 입력 100 ms 격자, 만료 1 ms 정확, 같은 시각은 입력 먼저, edge 는 wait 평가 시점에만, period 는 회차 종료 후 대기, 단일 시나리오. Clock 은 t=0 = 월요일 00:00 에서 파생(`interp.clock_state`).

이미 확인한 계약 사이의 차이(결과와 무관하게 기록):
- 참조 실행기는 `wait.timeout/on_timeout` 을 지원하고 논문 Timeline 절도 timeout 을 언급하지만, `files/timeline_ir/extractor.md`(LLM 에 주는 문법) 에는 없다. `timeline_ir.validate_ir` 는 모르는 필드·중첩 cycle 을 거절하지 않고 통과시킨다(구조 검사만).
  이 차이는 메모로 두지 않고 **A-extractor 문법 열**로 사례마다 측정한다(`grammar_check.py`). Stage A 12건 중 8건은 문법 안, 4건(C01 C05 C07 C20-O)은 `wait.timeout` 을 쓰고, 그중 C01·C05·C07 은 중첩 cycle, C05·C07 은 `period 0 MSEC` 도 쓴다. **현재 NL→IR 경로로는 이 4건의 encoding 이 생성되지 않는다.** 이는 언어 표현력의 결함이 아니라 frontend 문법의 미반영이며, 문법 확장은 E3 입력을 바꾸므로 E3 시작 전에 따로 결정한다.
- 실행기는 `start_at.anchor == "cron"` 을 거절한다(`ir_step.compile_ir`). 실행 확인은 `gate.prepare_pair` 와 같은 방식으로 앵커를 소거하고 한 발화 창만 재생했다.
- `cycle.period` 는 회차 종료 후 대기다. 따라서 "매 N" cadence 를 원하면 회차 시간을 빼야 한다. 감사 전 C05 v1 은 이 때문에 회차마다 100 ms 씩 밀려 정확 일치 0/4 였고, C07 v2 는 blink 를 400 ms timeout 으로 보정하려다 복원이 최대 100 ms 늦었다. **둘 다 감사 후 inner `period: "0 MSEC"` 로 바꿔 현재는 각각 4/4 정확 일치이며, 위 두 보정은 더 이상 쓰지 않는다**(수정 전후는 `results.md` 와 `runs/*_before_audit.*`).
- edge 대기는 처음 평가 시 조건이 이미 참이면 발화한다(초기 참 발화). "사건" 의미가 필요하면 선행 level 대기를 둔다(C03, C09). 다른 대기 중 일어난 edge 는 latch 에 반영되지 않는다(C01 v1/v2 실패 원인).
- `cycle.period: "0 MSEC"` 은 body 가 반드시 wait/timeout 으로 block 하는 event-driven loop 에서만 쓴다(무한 즉시 loop 허용이 아님). period 가 회차 종료 후 대기이므로, body 의 timeout 이 이미 cadence 를 담당하면 0 이 맞다(감사 결정, C05·C07). 실행기 `parse_duration` 과 frontend `parse_duration_to_ms` 모두 0 을 받는다.
- 실행기 입력 키는 속성명을 전부 소문자로 쓴다(`carbondioxide`). 파일럿의 첫 글자만 소문자 규칙은 한 단어 속성에서만 우연히 맞았다.

## 5. Stage A 사례 (12)

| ID | 출처 | 요소 | 경계 의도 |
|---|---|---|---|
| C01 | HA 공식 blueprint motion_light | R1 R3 R7 B1 | ★ |
| C03 | TAPInspector §V-D IFTTT | R1 R2 | |
| C04 | TAPInspector §V-D IFTTT | R9 R2 | |
| C05 | HA 커뮤니티 520305 | R3 R7 | |
| C07 | HA 커뮤니티 783900 | R9 R3 R5 R8 B5 B1 | ★ |
| C09 | AutoTap §III (g) [연구자 변환] | R1 R4 | |
| C11 | AutoTap §VI Task 11 | R1 B2 | ★ |
| C15 | Ur CHI'14 참가자 | R4 R7 R9 | |
| C16 | Ur CHI'14 Task I | R9 R6 | |
| C18 | Huang & Cakmak '15 Q3 | R1 R9 R2 | |
| C19 | Huang & Cakmak '15 P3 | R10 R9 | |
| C20-O | Brackenbury CHI'19 Table 1 (ordered 문장) | R1 R2 B1 | ★ |

Stage B 후보(C02 C06 C08 C10 C12 C13 C14 C17)는 진행하지 않았다. 2026-09-13 에 breadth corpus 의 depth 추가 8건
(E1-092 E1-095 E1-086 E1-099 E1-028 E1-034 E1-072 E1-062, `breadth/depth/`)이 그 자리를 대신했다.

## 6. 경계 probe (성공 분모와 분리)

Stage A 12건은 요소 R1–R10 과 경계 B1·B2 만 건드렸고 B3·B4 에는 사례가 없었다. 성공 사례만으로는
"경계가 어디인가" 에 답할 수 없으므로, 경계 후보를 **미리 지정한 별도 요구**로 시도했다.

규칙:
- probe 는 12건 성공 분모에 들어가지 않는다. 성공률을 만들기 위해 사례를 뺀 것이 아니라, 애초에 다른 요구다.
- 요구·해석·가정·기대 trace 를 인코딩 시도 전에 `probes.py` 에 고정하고 해시했다. sha256 `9ffee57593f6731e3216b6b23af1792c7a59ff86c1ad87b9b754ac4a5b219e1c`. 시도는 그 뒤 `probe_attempts.py` 에 쓴다.
  - 해시 후 수정 1건: P3 `interval_changed_to_10` 의 기대 ACTION 8개 → 9개. horizon 60분에서 마지막 On 을 빠뜨렸었다.
    요구 원문("start the next cycle exactly I minutes after this cycle's On")에서 직접 재유도해 확인했고, 인코딩을 보고 고친 것이 아니다.
    이 수정 뒤에도 attempt B 는 여전히 1/3 이다. 수정 후 sha256 `5833ef3eb1ea258cbaf345376083681fff8866491f6fb8977ee33325c6197f40`.
- **시도하지 않고 불가로 적지 않는다.** 실패한 시도도 `history` 에 남기고, 요구대로 쓴 encoding 이 거절되면 그 메시지를 실행기에서 재현해 기록한다.
- probe 가 "완전" 으로 끝나는 것도 정상 결과다. 경계 후보가 사실은 표현 가능했다는 뜻이며, 그대로 보고한다.

| ID | 경계 | 출처 | 결과 |
|---|---|---|---|
| P1 | B3 이벤트 기억(순서 없는 짝) | Brackenbury CHI'19 Table 1 의 unordered 문장 (C20-O 의 짝) | **완전** 4/4 정확. Explorer 거절 |
| P2 | B3 이벤트 기억(이동 시간창) | HA 커뮤니티 363863 "door opened within the last x minutes" | **완전** 4/4 정확. Explorer 거절 |
| P3 | B4 가변 간격 | HA 커뮤니티 541232 "repeat every n minutes where n is variable" | **완전(단위 해상도)** 3/3 정확. Explorer 거절 |

**세 후보 모두 언어의 경계가 아니었다.** 시험 전 예상과 반대다.

- **B4 가변 간격.** duration 피연산자 자체는 컴파일 시점 리터럴이라 `delay "$d MIN"` 은 거절된다
  (`Unsupported: duration format: '$d_min MIN'`, attempt A). 그러나 `cycle.until` 은 변수와 산술을 받으므로
  `cycle(until "k >= $d_min", count "k"){ delay "1 MIN" }` 로 **가변 길이 대기를 펼쳐서** 만들 수 있다(attempt C, 3/3 정확).
  대가는 단위당 회차 1개이므로 단위(1 MIN·1 SEC·100 MSEC)가 곧 해상도이자 상태 수다.
- **B3 도는 중 이벤트 기억.** `Clock.Timestamp` 스냅샷 + `$t != null` 로 표현된다(P1·P2 각 4/4 정확).
- **켜지기 전의 과거.** 이건 언어 문제가 아니라 **서비스/카탈로그 문제**다. JoI 에 `GlobalVariable` 처럼
  기기별 변경 시각을 주는 서비스를 두면 IR 은 `read` 한 줄로 쓴다. "Timeline 은 못 한다" 고 쓰면 안 된다.
  현재 catalog 에 그 서비스가 없다는 사실만 기록한다.

**실제로 확인된 구속은 언어가 아니라 검증기다.** probe 3건 모두 언어·실행기는 통과하고 Explorer 만 거절했다.
거절 사유는 두 종류다 — P2·P3 은 실행 중 값끼리 비교하는 guard, P1 은 범위가 정해지지 않은 관측값(입력 domain 필요).

| probe | Explorer 거절 사유 |
|---|---|
| P1 | `explicit input domain required for observable large/unbounded catalog value` |
| P2 | `미지원 무늬(fail-closed): joint-guard: ((clock.timestamp - $t_open) <= 600)` |
| P3 | `미지원 무늬(fail-closed): joint-guard: ($k >= $d_min); joint-guard: ($j >= ($i_min - $d_min))` |

**[대체됨 2026-09-13] 아래 세 항목은 저자 의미 감사 전의 논증이다. 결론으로 쓰지 않는다.** 확정 문장은 §0 과
`../../05_Timeline_IR/HANDOFF.md` "쓸 수 있는 것"(병렬 branch 없음·독립 흐름 분해, 고정 개수 집계·고정 한도 2, 일반 누적은 backend 위임)을 따른다.
특히 "유한 상태" 는 금지 문장이다.

**구조적으로 남는 한계(감사 전 논증, 보존용).**

1. **유한 상태.** IR 은 고정된 유한 프로그램이고 변수는 `read`/`count` 로 작성 시점에 정해진다.
   겹치는 인스턴스 수·기억할 사건 수가 입력에 따라 무한히 늘어나는 요구는 불가. 상한 k 가 정해지면 k 칸으로 가능.
2. **계산 결과를 변수에 저장할 수 없다.** 대입 연산이 없다(`_STEP_OPS = {start_at, wait, delay, read, call, if, cycle, break}`).
   변수는 `read` 스냅샷이나 `call` 반환값만 받는다. 누적합·평균 같은 집계는 IR 안에서 유지할 수 없다.
   `GlobalVariable` 로 우회하면 그 쓰기가 관측 ACTION 에 찍히므로(`globalvariable#G.setinteger('n', 1)`) 검증 대상 trace 자체가 바뀐다.
3. **단일 제어 흐름.** 병렬은 폴링으로 수동 인터리브해야 하고, 그러면 blocking `delay`/`wait.for` 를 쓸 수 없으며
   동시 활동 수가 작성 시점에 고정된다(1 번과 같은 뿌리).

B2(진짜 중첩 인스턴스)는 probe 를 만들지 않았다. 단일 제어 흐름이라는 실행 계약에서 곧바로 따라오는 한계이므로
계약 근거로 보고하고, C11 의 B2 는 "두 흐름 지원" 이 아니라 **단일 흐름으로 환원된 특수 사례**로 표기한다.

## 7. 파일

- `cases.py` — 출처·원문·해석·가정·binding·기대 trace (IR 없음).
- `irs.py` — 사례별 Timeline IR 후보와 encoding 메모.
- `run_e1.py` — A-frontend / C / D / E 열 자동 채움 → `runs/e1_stageA.json`, 표 출력.
- `probes.py` — 경계 probe 의 요구·해석·기대 trace (시도 없음, 해시 대상).
- `probe_attempts.py` — probe 의 시도한 encoding 과 시도 이력.
- `run_probes.py` — probe 실행 → `runs/e1_probes.json`.
- `grammar_check.py` — `files/timeline_ir/extractor.md` 문법 밖 구성 판별(A-extractor 열).
- `results.md` — 경계 표와 사례별 판정(감사 열은 whisoo 가 채움).
- `breadth/` — 100건 breadth corpus 와 새 depth 8건의 frozen case (2026-09-13 가져옴; 같은 날 출처 감사·저자 선별·R/B 코딩·depth 감사 완료).
  `E1_CORPUS_PROTOCOL.md`·`CLAUDE_E1_HANDOFF.md` 가 절차, `FREEZE_MANIFEST.md` 가 가져온 파일과 frozen case 의 해시,
  `audit/PROVENANCE_AUDIT.md` 가 출처 감사 결과, `audit/AUTHOR_SCREENING_2026-09-13.md` 가 저자 수동 선별(확정)이다.
  `audit/AUTHOR_RB_CODING_2026-09-13.md` 가 저자 R/B 코딩(확정, IN_SCOPE 92건 분모)이다.
- `E1_SUMMARY.md` — depth 20건(Stage A 12 + depth v2 8)과 corpus 분포·R/B 건수를 한 곳에 모은 표.
  `make_e1_summary.py` 가 기록된 결과만 읽어 만든다(재실행 없음).
