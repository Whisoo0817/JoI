# E1 — 경계 표 중심의 외부 요구 표현 적합성 사례 연구

시작 2026-09-12. **Stage A(12건): B 의미 감사(whisoo, 2026-09-12) 완료·반영. 논문 결과가 아니다.** 결과 표: `results.md`. 감사 전 결과 보존: `runs/e1_stageA_before_audit.json`, `runs/results_before_audit.md`.
설계 배경과 결정은 세션 논의(2026-09-12)에 따른다. 상위 계획: `../confirmed_ir_evaluation_2026-09-10.md`, `../e1_ir_adequacy_design_2026-09-10.md`
(두 문서의 "완전 표현 비율" 지표는 이 문서의 경계 표로 대체 예정 — whisoo 확정 후 갱신).

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

- repo commit: `0356601b597d7c1e5c66d2652f62bd5cab3bef62` (2026-09-12 12:04 +0900), 작업 트리 변경 없음(`PerCom/` 미추적 제외).
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
- `irs.py` 의 encoding 수정 이력은 각 항목의 `history` 필드에 남긴다(C01 v1→v3, C03 v1→v2, C07 v1→v3, C09 v1→v2, C20 v1→v2, 감사 후 C05 v2·C19 v2). 실행기·계약은 바꾸지 않았다.
- 감사 후 `cases.py` 변경: C01 가정 문구(“새로운 motion off→on 재트리거마다”), C11 메모, C19 이력 2개 추가(`already_present_at_start_no_mail`, `arrive_0900_30_no_mail`), C20 `elements` 에서 B3 제거(순서형 문장만 사례로 확정).
- 실행기 의미나 tolerance 를 결과에 맞춰 바꾸지 않는다. 수정이 필요하면 전후와 영향을 이 문서에 기록한다.

관측 계약: `explorer/docs/model/VERIFICATION_CONTRACT.md` 그대로. 입력 100 ms 격자, 만료 1 ms 정확, 같은 시각은 입력 먼저, edge 는 wait 평가 시점에만, period 는 회차 종료 후 대기, 단일 시나리오. Clock 은 t=0 = 월요일 00:00 에서 파생(`interp.clock_state`).

이미 확인한 계약 사이의 차이(결과와 무관하게 기록):
- 참조 실행기는 `wait.timeout/on_timeout` 을 지원하고 논문 Timeline 절도 timeout 을 언급하지만, `files/timeline_ir/extractor.md`(LLM 에 주는 문법) 에는 없다. `timeline_ir.validate_ir` 는 모르는 필드·중첩 cycle 을 거절하지 않고 통과시킨다(구조 검사만).
- 실행기는 `start_at.anchor == "cron"` 을 거절한다(`ir_step.compile_ir`). 실행 확인은 `gate.prepare_pair` 와 같은 방식으로 앵커를 소거하고 한 발화 창만 재생했다.
- `cycle.period` 는 회차 종료 후 대기다. 따라서 "매 N" cadence 를 원하면 회차 시간을 빼야 한다(C05: 100 ms/회차 누적, 1 초 허용 안; C07: blink 를 맞추기 위해 timeout 400 ms 사용).
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
| C20 | Brackenbury CHI'19 Table 1 | R1 R2 B3 B1 | ★ |

Stage B 후보(미착수): C02 C06 C08 C10 C12 C13 C14 C17.

## 6. 파일

- `cases.py` — 출처·원문·해석·가정·binding·기대 trace (IR 없음).
- `irs.py` — 사례별 Timeline IR 후보와 encoding 메모.
- `run_e1.py` — A-frontend / C / D / E 열 자동 채움 → `runs/e1_stageA.json`, 표 출력.
- `results.md` — 경계 표와 사례별 판정(감사 열은 whisoo 가 채움).
