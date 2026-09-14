# Evaluation handoff

상태: **E1 Stage A 완료(2026-09-12), E2–E4 미착수**.

- 실험의 방식·코드·데이터·결과는 이 폴더의 실험별 하위 폴더에 둔다. E1: [`E1_adequacy/`](E1_adequacy/README.md) (README = protocol·결정·버전 고정, `cases.py` = 출처·해석·기대 trace, `irs.py` = IR, `run_e1.py`/`make_results.py` = 실행·표, `results.md` = 결과, `runs/` = 원본·감사 전 보존본).
- E1 Stage A: 12건 완전 12/12, exact 41/41, whisoo B 감사 반영. C05·C07·C19 수정 전후 보존. B3·B4 는 Stage A 사례에 없었고, 아래 경계 probe P1–P3 로 따로 시험했다(언어·실행기 통과, Explorer 만 거절). C20 unordered variant 는 probe P1.
- **E1 breadth corpus(2026-09-13 가져옴, pre-audit).** `E1_adequacy/breadth/` — 100건(출처 다양 corpus: official 25 / research 26 / elicited 24 / community 25, 층별 고정 할당 주장 안 함), 선별 기록 150건, 새 depth 8건의 IR 없는 frozen case(해시 `FREEZE_MANIFEST.md`). 출처 감사 완료(`audit/PROVENANCE_AUDIT.md`): URL 36/36 접속, 원문 전부 확인, locator 60행·제목 26행 교정. C15 는 research 로 재분류(whisoo 결정). **저자 1인 수동 선별 완료(2026-09-13, `audit/AUTHOR_SCREENING_2026-09-13.md`): IN_SCOPE 92 / AMBIGUOUS 6 / OUT_OF_SCOPE 2 / UNMATCHED 0, 남긴 중복 없음.** 두 번째 코더·κ 사용 안 함. **R/B 코딩 완료(2026-09-13, `audit/AUTHOR_RB_CODING_2026-09-13.md`)**: IN_SCOPE 92건만 분모, 나머지 8건 N/A. 건수 R1 65 / R2 14 / R3 13 / R4 3 / R5 8 / R6 23 / R7 5 / R8 3 / R9 28 / R10 2 / B1 6 / B2 5 / B3 2 / B4 0 / B5 1.
- **E1 depth 8건 — 저자 의미 감사 반영 v2(2026-09-13).** `E1_adequacy/breadth/depth/RESULTS.md`, 결정 기록 `depth/AUTHOR_ADJUDICATION_2026-09-13.md`. v1(frozen·전사·시도·실행)은 그대로 보존하고 v2 기록을 해시 커밋 후 재실행.
  8건 모두 참조 실행 정확 일치(이력 12개). 판정: E1-092 `complete via multi-Timeline decomposition`(단일 Timeline v1 은 0/1 로 기록 유지; 독립 흐름 두 개를 Timeline 두 개로 배포, 주입 실패는 Alexa 자동화만 멈춤) / E1-095 `complete for fixed-cardinality aggregation` / E1-028 `complete for the fixed bound of two` / E1-099·034·072·062·086 `complete`.
  **선별·R/B 수치는 저자 값으로 확정됐다(두 번째 코더·κ 없음).** 통합 표: `E1_adequacy/E1_SUMMARY.md` (depth 20건, 이력 53/53 정확, 판정 전부 complete 계열). Explorer 는 분자·분모 밖 보조 결과. extractor 문법 관찰·실행기 시계 문제는 결과가 아니라 `depth/ENGINEERING_NOTES.md`.
- E1 원고 절은 `PerCom_version.md`에 **2026-09-13 초안으로 다시 썼다(whisoo 검토 대기)**. 근거는 `E1_adequacy/E1_SUMMARY.md`: corpus 100(출처 25/26/24/25, 선별 92/6/2/0, 중복 0, R/B 코딩), depth 20건 이력 53/53 정확, 범위 붙은 판정 3건, probe P1–P3. extractor 문법·Clock.Second 는 넣지 않았고 finite-state·일반 누적·병렬 과장 문장을 뺐다.
- E1 계약 사실(period 회차 후 대기, 초기 참 edge, latch 미반영, cron 소거, timeout 문법 부재, **미초기화 변수 = null**)은 3_Timeline_IR HANDOFF에도 반영해야 한다.
- **경계 probe(2026-09-12 추가).** Stage A 는 성공 사례뿐이라 경계를 말할 수 없었다. B3·B4 를 사전 지정 요구 3건으로 따로 시도했다(성공 분모와 분리, `probes.py` 해시 후 `probe_attempts.py` 작성).
  - **세 후보 모두 언어 경계가 아니었다**(시험 전 예상과 반대). P1·P2(도는 중 이벤트 기억) 각 4/4 정확, P3(가변 간격) 3/3 정확.
    P3 는 duration 피연산자가 리터럴이라 `delay "$d MIN"` 은 거절되지만 `cycle(until "k >= $n", count "k"){ delay "1 단위" }` 로 펼치면 된다. 단위 = 해상도 = 상태 수.
    B3 는 두 가지로 나눠 쓴다. (가) 켜지기 전 과거 = **서비스/카탈로그 문제**(SensorHistory 류 서비스를 만들면 `read` 한 줄. "Timeline 이 못 한다" 고 쓰지 말 것). (나) 도는 중 과거 = 가능.
  - **실제 구속은 검증기다.** probe 3건 전부 Explorer 거절, 사유가 같은 종류(실행 중 값끼리 비교하는 joint-guard). E2·E4 의 핵심 입력.
  - ~~구조적으로 남는 언어 한계 3가지(유한 상태·대입 없음·단일 제어 흐름)~~ — **2026-09-13 저자 감사로 대체.** 쓸 수 있는 문장은 `../3_Timeline_IR/HANDOFF.md` "쓸 수 있는 것"(Timeline 하나에 병렬 branch 없음 → 독립 흐름만 분해, 고정 개수 집계·고정 한도 2, 일반 누적은 backend 위임). "고정 프로그램이라 finite-state" 는 쓰지 않는다.
  - B2 진짜 중첩 인스턴스는 probe 없이 실행 계약(단일 제어 흐름) 근거로 한계 보고. C11 은 "두 흐름 지원" 이 아니라 단일 흐름 환원으로 표기.
- A-extractor 문법 열(Stage A 12건 중 4건이 `extractor.md` 밖 구성)은 **E1 결과·한계가 아니다**(2026-09-13 whisoo, Limitations 항목 삭제). 기록은 E1 README 에만 둔다. extractor 문법 확장 여부는 E3 시작 전에 따로 정한다.
- **E2 validation fidelity (2026-09-14 착수).** `E2_fidelity/PROTOCOL_DRAFT.md`(동결 전). 결정: 독립 정답기 (b) — Explorer 코드를 공유하지 않는 IR·JoI 두 실행기를 명세 문서만으로 작성(Explorer 코드를 본 적 없는 별도 에이전트가 작성, 읽은 파일 기록); 쌍 = E1 20건 IR 기반 올바른 대안·오류 유형별 직접 작성 + 388 후보 표본(Explorer 판정과 무관하게 추출); 이력 = 원래 시간 척도의 경계 중심 구조 이력; JoI 문법 전체(`for` 제외, `loop` 은 L1 정의); Explorer 버그는 고정판 결과 보고 + 수정판 재실행. S1–S11 의미 확정.
  **동결 `649cb9c` (2026-09-14):** 정답기(E1 기대 trace Stage A 41/41·depth 12/12·JoI probe 15/15, 명세 공백 결정 G1 tags만·G2 내장 Clock·G6·G8·JoI `%` 허용), 쌍 142(E1 기반 올바른 21 + 오류 81, 388 표본 40), 이력 11,577, `run_e2.py`(Explorer 는 gate_pair 단계에 시작 시각 일치). 해시 `E2_fidelity/FREEZE_MANIFEST.md`. 실행 결과 `E2_fidelity/runs/`.
  **실행 완료(2026-09-14, `191c87a`):**
  - 표는 `E2_fidelity/RESULTS.md`, 쌍별 확인은 `INSPECTION_2026-09-14.md`에 있다.
  - Explorer 판정(142쌍): DIVERGE 68 / EQUIV 36 / REFUSED 25 / TIMEOUT 13.
  - 정답기는 두 판으로 재계산했다: 동결판 `649cb9c`, 현재판(None 순서 비교 = false).
  - 현재판 기준 일치: AGREE-EQUIV 36 / AGREE-DIVERGE 58 / 반례로 확인됨 8 / 정답기 미지원 반례 2 / 거절 25 / 시간 초과 13. 거짓 EQUIV는 두 판 모두 0, Explorer 오류는 찾지 못함(D4 해당 없음).
  - 약점: 정답기 이력의 시작 상태가 사실상 1개이고 이력 상한이 300개라, 정답기가 "같음"으로 본 59쌍 중 8쌍을 놓쳤다.
  - 보강 이력(프로토콜 §9, whisoo 결정, `193203c`, 39,245개)은 정답기를 돌리기 전에 커밋했다. 보강 실행 결과: 거짓 EQUIV는 여전히 0건이다. 시작 상태 때문에 놓쳤던 llm 5쌍은 정답기 이력에서도 차이가 잡혔다. 합친 일치 수는 AGREE-EQUIV 36 / AGREE-DIVERGE 63 / 반례로 확인됨 3(E1-086 오류 3쌍: 유일한 시작 이력이 301초에 취소하고 두 프로그램 모두 거기서 끝나, 첫 작동을 더 길게 하는 이력이 규칙상 생기지 않음) / 정답기 미지원 반례 2 / 거절 25 / 시간 초과 13이다. E1 남은 72건 depth 는 보류(`E1_adequacy/breadth/TODO_DEPTH_REMAINING_72.md`).
  **바인딩 결정과 재실행(2026-09-14, 진행 중):**
  - whisoo 결정: E2 는 시간·상태·로직만 본다. 셀렉터·태그·ID·category·기기 수·any/all 은 판정에 넣지 않는다. IR 에 따로 적힌 호출의 순서는 지킨다.
  - 규칙은 `E2_fidelity/BINDING_DECISION_2026-09-14.md` (B1 셀렉터 → 바인딩 기기, B2 한 자리 안에서 나뉜 호출은 한 묶음, 중복 호출은 여전히 다름).
  - 정답기: 별도 에이전트가 반영했다(옵션 인자, 없으면 동결 동작). 확인 42건 통과, conformance·independence 그대로.
  - Explorer: `ground.py`·`observation.py`·`gate.py`(`selector_binding` 스위치)·`timed/relational/product` 에 반영했다. 회귀 전부 통과. 셀렉터 정답성을 보던 옛 시험 9개는 `selector_binding(False)` 로 동결 의미를 유지한다. 새 시험은 `explorer/tests/test_binding_decision.py`.
  - 재실행: `run_binding_v1.py` → `runs/e2_run.binding-v1.jsonl`. `run_e2.py` 는 `E2_BINDING_DECISION=1` 일 때만 새 규칙이고, 기본은 동결 의미다.
  - 남은 판단: C21_003 은 JoI 가 `#Bedroom` 을 두 번 읽고 거실을 안 읽는다. 자리가 둘인 서비스라 규칙상 DIVERGE 가 남는다. target 오류 2쌍은 "범위 밖(바인딩)" 으로 표시할 것.
  - 타이머 이산화는 다른 AI 에게 인계했다: `E2_fidelity/handoff_timer/README.md`.
- C20 은 C20-O(ordered)로 개명했다. 짝을 이루는 unordered 문장은 probe P1 이며, 성공 분모에서 뺀 것이 아니라 별개 요구로 분리해 시도했다.
- Limitations 절에 넣을 것: 12/12 는 선정 사례 중의 건수(coverage 아님), B2 중첩 인스턴스 미평가, B5 중첩 반복은 C07 한 건, Explorer 미인증 경계.

- E1–E4 번호는 최신 계획대로 고정한다. 구 문서의 E1/E2 번호를 가져오지 않는다.
- 구 fixed-horizon 평가와 그에 종속된 pair 수·transition 감소율·latency 수치는 현재 PerCom 원고에서 제거했다. 이는 과거 audit 기록으로만 보존한다.
- 최종 E3/E4는 현재 H=None 검증 계약의 closure/completion 조건에 맞춰 새로 작성한다.
- Motivation pilot과 LLM-judge experiment는 Fig2/동기 근거로 별도 취급하고 E2/E3에 조용히 합치지 않는다.
- E1 외부 corpus, E2 독립 oracle, E3 동결 생성 평가, E4 scale/ablation을 실행한 후 Methods–Results 병렬 구조로 전면 개정한다.
- 모든 refusal/error/incomplete를 전체 분모에 남긴다.
- transition reduction을 runtime speedup으로 바꿔 쓰지 않는다.
