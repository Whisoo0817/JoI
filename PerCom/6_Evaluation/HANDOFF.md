# Evaluation handoff

상태: **E1 종료(2026-09-13), E2 완료(2026-09-14, 140쌍). E3 최종(2026-09-15, 382건). Feedback 1·2라운드와 반례 없는 대조군 완료(2026-09-16). Table 1 동기 실험 완료(2026-09-16, judge 3개, Fig2 제외 — `1_Intro/motivation_judge/` 로 이동). E4 완료(2026-09-17, 합성 30개 프로그램, 270회). 원고 E1·E2·E4 초안은 whisoo 검토 대기.**

- 실험의 방식·코드·데이터·결과는 이 폴더의 실험별 하위 폴더에 둔다.

## E1 — `E1_adequacy/`

- **최종 표:** `E1_adequacy/E1_SUMMARY.md` (`make_e1_summary.py`, 기록된 결과만 읽음).
  - corpus 100건(출처 official 25 / research 26 / elicited 24 / community 25, 고정 할당 주장 안 함).
    저자 1인 수동 선별 IN_SCOPE 92 / AMBIGUOUS 6 / OUT_OF_SCOPE 2 / UNMATCHED 0, 남긴 중복 없음(`breadth/audit/AUTHOR_SCREENING_2026-09-13.md`).
    R/B 코딩은 IN_SCOPE 92건만 분모(`breadth/audit/AUTHOR_RB_CODING_2026-09-13.md`). 두 번째 코더·κ 없음.
  - depth 20건(Stage A 12 + 추가 8), 이력 53/53 정확(Stage A 41/41, 추가 v2 12/12). 20/20 은 선정 사례 중의 건수이며 coverage 가 아니다.
  - 범위 붙은 판정: E1-092 `complete via multi-Timeline decomposition`, E1-095 `complete for fixed-cardinality aggregation`,
    E1-028 `complete for the fixed bound of two`. 결정 기록 `breadth/depth/AUTHOR_ADJUDICATION_2026-09-13.md`, 결과 `breadth/depth/RESULTS.md`.
  - Explorer 열은 분자·분모 밖 보조 결과다. 출처 감사 `breadth/audit/PROVENANCE_AUDIT.md`.
- **Stage A 기록:** `E1_adequacy/README.md`(절차·결정·버전 고정), `cases.py`·`irs.py`·`run_e1.py`·`make_results.py` → `results.md`.
  감사가 C05·C07·C19 를 고쳤고 수정 전 결과를 `runs/*_before_audit.*` 에 보존한다. C20 은 C20-O(ordered)로 개명했고, 짝인 unordered 문장은 probe P1 이다.
- **경계 probe P1–P3** (성공 분모와 분리, `probes.py` 해시 후 `probe_attempts.py` 작성).
  - 세 후보 모두 언어 경계가 아니었다. P1·P2(도는 중 이벤트 기억) 각 4/4 정확, P3(가변 간격) 3/3 정확.
    P3 는 duration 피연산자가 리터럴이라 `delay "$d MIN"` 은 거절되지만 `cycle(until "k >= $n", count "k"){ delay "1 단위" }` 로 펼치면 된다.
  - **실제 구속은 검증기다.** 세 probe 모두 Explorer 가 거절했다. 사유는 두 종류다: P2·P3 은 실행 중 값끼리 비교하는 guard(joint-guard),
    P1 은 범위가 정해지지 않은 관측값(입력 domain 필요).
  - B3 는 두 가지로 나눠 쓴다. (가) 켜지기 전 과거 = **서비스/카탈로그 문제**("Timeline 이 못 한다" 고 쓰지 말 것). (나) 도는 중 과거 = 가능.
- **언어 한계 문장**은 `../3_Timeline_IR/HANDOFF.md` "쓸 수 있는 것" 만 쓴다(Timeline 하나에 병렬 branch 없음 → 독립 흐름만 분해,
  고정 개수 집계·고정 한도 2, 일반 누적은 backend 위임). "고정 프로그램이라 finite-state" 는 쓰지 않는다.
  B2 진짜 중첩 인스턴스는 probe 가 없고, C11 은 "두 흐름 지원" 이 아니라 단일 흐름 환원으로 표기한다.
- **E1 계약 사실**(period 회차 후 대기, 초기 참 edge 발화, 다른 대기 중 edge latch 미반영, 실행기는 cron 앵커를 거절 → 실험에서 소거 후 한 창 재생,
  **미초기화 변수 = null**)은 `../3_Timeline_IR/HANDOFF.md` 에 있고 Timeline 절 본문에 아직 반영되지 않았다.
- A-extractor 문법 열(Stage A 12건 중 4건이 `extractor.md` 밖 구성)은 **E1 결과·한계가 아니다**(2026-09-13 whisoo). 기록은 E1 README 에만 둔다.
  extractor 문법 확장 여부는 E3 시작 전에 따로 정한다.
- **원고 E1 절:** `PerCom_version.md`, 2026-09-13 초안, 2026-09-14 사실 정정(P1 거절 사유, cron 앵커, 인코딩 수정 4건 + 해석 변경 3건,
  AutoTap 문장 변환, 해시 기록 범위, validator → Explorer). whisoo 검토 대기.
- 남은 corpus 72건의 depth 는 보류(`E1_adequacy/breadth/TODO_DEPTH_REMAINING_72.md`).

## E2 — `E2_fidelity/`

- **요약** `E2_fidelity/E2_SUMMARY.md`, **표** `E2_fidelity/RESULTS.md`(`make_e2_results.py`, `.jsonl` 또는 `.jsonl.gz` 입력),
  **쌍별 확인** `E2_fidelity/INSPECTION_2026-09-14.md`, **원고 계획** `E2_fidelity/E2_WRITING_PLAN.md`(§0 이 최신 결정).
- **모집단 140쌍** (`E2_fidelity/handoff_timer/e2_population.json`): 동결 142쌍에서 `C03_008/llm`(ACTION 위치 `any` = 구문 오류)과
  `C20_011/llm`(잘못된 service mapping)을 뺐다. 실행 파일의 142행은 그대로 둔다.
- **최종 결과:**
  - 판정 130 = 정답기 확인 130(이력에서 EQUIV 55 + DIVERGE 67, 반례 재생 8). 어긋남 0.
  - 관찰된 차이가 있는 오류 75쌍 → DIVERGE 69 / EQUIV 0 / 판정 못 함 6.
  - LLM 후보 38/38. 직접 만든 쌍 92/102, 요구 18/20.
  - 판정 못 함 10쌍: C07 5쌍(시간 예산 초과), E1-099 5쌍(사건 수에 따라 늘어나는 시한, 거절).
- **탐색 최적화:** 같은 예산에서 판정 104 → 130(+26). 기존 104개 판정 변화 0. 바인딩 계약은 개선 수치에 넣지 않는다(바인딩 전후 모두 104).
- **원고 E2 절:** `PerCom_version.md`, 140쌍 기준 초안, whisoo 검토 대기. 표 하나, §0 최적화 문장 사용.
  구현 기법 이름, 최적화 전 수치, 바인딩 규칙, 제외한 2쌍은 원고에 쓰지 않는다.
- **개발 기록(논문 수치 아님, `RESULTS.md` "Development records"):**
  - 동결 `649cb9c`: 정답기(E1 기대 trace 41/41·12/12, JoI probe 15/15), 쌍 142, 이력, `run_e2.py`. 해시 `FREEZE_MANIFEST.md`.
  - None 순서 비교 결정(현재판 정답기), 보강 이력 §9(`193203c`, 정답기 실행 전에 커밋).
  - 바인딩 계약 `BINDING_DECISION_2026-09-14.md`(B1/B2/B5, `3b728e4`): 두 도구에 반영, 재실행 `run_binding_v1.py`·`run_binding_b5.py` → `runs/e2_run.binding-final.jsonl`.
  - 탐색 최적화(Codex, `timer-regions-20260914`, 병합 `24d7b1a`) → `run_timer_binding.py` → `runs/e2_run.timer-binding.jsonl`. 인계 기록 `E2_fidelity/handoff_timer/`.
  - R14 미초기화 변수 산술(whisoo 결정 2026-09-16, `explorer/docs/model/RUNTIME_CONTRACT.md`): 한 번도 대입되지 않은 변수를
    산술에 쓰면 runtime error이고, 인스턴스는 멈추며 그 멈춤이 관찰 대상이다. Explorer(`runtime/interp.py`)와 정답기
    (`reference/joi_ref.py`, `common.RefRuntime`, `run.py` status `runtime-error`) 양쪽에 넣었다. C24_003/llm 이 "정답기가
    실행 못 함"에서 "정답기가 확인한 DIVERGE"로 바뀐 것이 전부다: 142쌍 definite-assignment 검사로 이 규칙에 닿는 다른 쌍이
    없음을 확인했고, 정답기 A/B 재실행에서도 다른 쌍의 결과는 그대로였다. E3 382 입력도 닿는 코드가 없어 수치가 그대로다.
  - `0e76584`(바인딩된 `any` 동작 허용)은 2026-09-14 whisoo 결정으로 되돌렸다. `any` 는 조건문 안에서만 쓸 수 있고, Explorer 파서와 정답기(SPEC_GAPS G35) 모두 조건문 밖의 `any`(ACTION·대입·인자)를 구문 오류로 거절한다.
- Timeline IR 절·Limitations 절로 보낼 E2 항목은 각 절 HANDOFF 에 적었다.

## E3 — `E3_application/`

- **E3 최종(2026-09-15, 브랜치 e3-b5-rerun-20260915 → paper).** 상세: `E3_application/E3_QWEN_382_FINAL_2026-09-15.md`.
  - EQUIV-FIXPOINT 309 / DIVERGE_CONFIRMED 68 / REFUSED 3 / UNKNOWN 2, 판정 377/382. 생성·준비 오류 0.
  - whisoo 결정(09-15): 382건 범위 확정, B5 를 E3 평가기에도 적용, C21_001 정답 or→and, 동작 자리에 any 를 단 정답 binding 5건은 한정자 없는 기기 하나로. lowering 프롬프트는 맞을 수도 틀릴 수도 있다는 전제이며 이 결과가 feedback 실험의 baseline(DIVERGE 68).
  - 병합 후 E2 회귀 53쌍 판정 변화 0. 아래 항목은 직전 307/70 기록이다.
- **(이전 기록) E3 application Qwen 평가 307/70/3/2.** 상세: `E3_application/E3_QWEN_382_RESULT.md`.
  - 모델 `Hyper-AI/Qwen3.5-9B-fp8`, 실행 시 endpoint `http://localhost:8002/v1`. 확정 `ir_gt`와 `binding_gt`를 직접 주입하여 자연어 service mapping/selector 추론을 우회한다.
  - 원본 388행은 보존하고 timeout/on_timeout이 포함된 C26_001–006 전체를 E3 범위에서 제외했다. 현재 분모는 382건이다.
  - 후보 tag `qwen3_5-9b-fp8-e3-prefix-fixed-v2`: 기존 325건을 payload 일치 및 byte hash 확인 후 재사용하고, prefix 영향 56건과 C05_015(drying) 1건을 신규 생성했다. 신규 57건의 raw trace를 보존했으며 부분 재생성 시 프롬프트는 바꾸지 않았다.
  - B1/B2/B5 binding, `selector_binding=True`, `H=None`, bounded fallback 없음. 전체 382건: EQUIV-FIXPOINT 307 / DIVERGE_CONFIRMED 70 / REFUSED 3 / UNKNOWN 2. 판정 완료율 377/382(98.69%)이며 정확도가 아니다. 생성·capability·문법·arity 오류는 이 실행에서 0건이다.
  - 70건 모두 replay 확인, 평가 중 source/candidate hash 연속성 확인. REFUSED는 C01_015(BINARY 반환값), C03_003(무경계 산술), C11_006(대규모 조도 도메인). UNKNOWN은 C11_001·C11_005(SMT query timeout)이며 제한 변경이나 재탐색 없이 남겼다. C05_015는 EQUIV다.
  - 근거: 저장소 루트 `explorer/eval/results/e3_prefix_fixed_382_20260915_*`의 lineage, candidates, protocol, manifest 및 `_run/summary.json`, `_run/case_outcomes.jsonl`.
  - 혼합 출처·익숙한 과제의 탐색적 평가다. protocol snapshot은 후보 생성 후·평가 전에 기록했으므로 신규 382건 생성이나 confirmatory replication으로 쓰지 않는다. DIVERGE 원인은 개별 감사하지 않았고 독립 실기기 검증도 아니다.
  - 과거 Gemma 388건 결과는 `E3_application/RESULTS.md`에 이력으로 보존한다. prefix 버그가 포함된 이전 Qwen 388건 집계는 철회됐으며 최신 논문 수치로 쓰지 않는다. feedback 시험 결과는 폐기했고 현재 결과에 포함하지 않는다.

## Feedback — `joi/self_feedback/` (2026-09-16, 1라운드·2라운드·대조군 실행 완료)

- 09-15 구현(c8b020d 까지)은 오류로 whisoo 가 reset. 다시 만든 판은 `joi/self_feedback/README.md` 부터.
- 설계(whisoo 09-16): E3 DIVERGE 68건에 반례로 **한 번** 수정 → EQUIV-FIXPOINT 몇 건인지. 반례 없는 대조군은 처음엔 빼기로 했다가 09-16 에 추가 실행(맨 아래).
- 프롬프트: `prompts/repair.md`(v5, 유형별 정답 JoI 예제 A–G + 모양 체크리스트). 68건이 아닌 새 dev set 14건으로 골랐다(`DEV_NOTES_2026-09-16.md`, 13/14, thinking off·temperature 0).
- 프로토콜: `PROTOCOL_E3_FEEDBACK_2026-09-16.md` / `protocol_e3_feedback_v1.json`(prompt·후보·baseline 해시, 모델 설정, 평가기 = E3 최종과 같은 snapshot).
- 하네스 점검: 수정 전 68건을 같은 파이프라인으로 평가 → 68/68 DIVERGE_CONFIRMED 재현(`runs/harness_check_20260916/`).
- **본실행 결과(09-16, `runs/e3_feedback_68_20260916`, 기록 `RESULTS_E3_FEEDBACK_2026-09-16.md`)**: 68건 → **EQUIV-FIXPOINT 36 (52.9%)**, DIVERGE 26, 평가기 TIMEOUT 5, MODEL_ERROR 1(반례 이력 96k 토큰으로 컨텍스트 초과). 유형별: 이벤트 대기 15/31, 지속 1틱 21건 중 15, 범위·종료 2/5, 지속·주기 1/4, 첫 회차 0/3, 값 대체 2/2, abs 1/1, 문자열 0/1. 비용: 건당 완성 토큰 중앙값 368, 유효 5.9 s/건, 평가 중앙값 0.06 s.
- 실패 32건 원인(새 반례 판독 + 기계적 재작성 재검증, `runs/.../failure_cause_diagnostic.json`): **조건식을 다시 쓰면서 JoI 의 존재 양화 연산자 `OP|`(`==|`,`<|` …)를 떨어뜨린 것이 12건**(C07_024·C08_018·020·021·022·024·026·027·029·032·C10_003·C12_007, C14_006 포함 시 13). `OP|` 를 쓰던 후보 13건 중 11건이 이를 잃었고 그 11건은 전부 실패, 지킨 채 실패한 건 0. 재무장을 `not (조건)` 이 아니라 대수적 보수(`>= 50`)로 쓴 것도 같이 겹침(null 판독에서 영구 대기). `OP|` 유지 + 재무장 `not(조건)` 두 규칙만 기계적으로 되돌리면 edge 10건 전부 EQUIV, C10_003·C12_007 은 `OP|` 만으로 EQUIV. `prompts/repair.md` 에 `OP|` 설명이 0회라 프롬프트 공백이 원인이고, 반례 형식 문제는 아니다(반례 입력에 판별 조합이 대개 들어 있었다).
- 나머지: 틱 산술 ×10·period 4, 다중 블록 구조 5, 선행동작+cycle(phase) 3, 과단순화 1, 검증기 상태 폭발 5(C14 산술 인자; 600 s 를 줘도 40만 상태 한도에서 INCONCLUSIVE), 컨텍스트 초과 1.
- **v2 프롬프트 시도 후 폐기(09-16)**: `OP|` 와 `not (C)` 재무장을 가르치는 v6a/v6b/v6 세 판을 만들어 dev set 14건 × 4회로 비교했더니 전부 v5 보다 낮았다(평균 12.25/11.75/11.50 vs v5 12.75). 손대지 않은 유형에서 새 실패가 났고 파서가 거부하는 문법까지 나왔다. dev set 에 `{"any": [...]}` 슬롯이 없어 이득은 측정되지 않고 손해만 보이는 구조이기도 하다. **결정(whisoo): v5 유지.** 따라서 이 실행의 36/68 은 측정된 그대로다. `prompts/repair.md` 는 `repair_v5.md` 와 동일(sha 3acaf6b4…, 프로토콜과 일치). 기록은 `DEV_NOTES_2026-09-16.md`.
- **2라운드(09-16, 26건 대상)**: 1라운드에서 DIVERGE 로 남은 26건만 재실행(EQUIV 36 은 종료, TIMEOUT 5·MODEL_ERROR 1 은 새 반례가 없어 제외). 두 갈래 — **r2a: 프롬프트 v5 그대로 → 4/26, 2라운드 누적 40/68(58.8%)**. r2b: `OP|`·재무장 규칙을 넣은 프롬프트 → 6/26, 누적 42/68(프롬프트가 이 케이스들의 1라운드 실패에서 도출된 사후 판). 기록 `RESULTS_E3_FEEDBACK_ROUND2_2026-09-16.md`, 프로토콜 `protocol_e3_feedback_r2a.json`/`r2b.json`.
- 2라운드의 발견: 새 반례를 받으면 모델이 any/all 문제를 **정확히 진단**한다(진단문에서 양화 언급 r2a 6건·r2b 12건, 1라운드 0건). 그런데 JoI 로 못 적는다 — 동작 자리에 `any(...)`(문법 금지), `> 30|` 처럼 `|` 를 값 뒤에 붙임, `all(#A, #B)` 같은 없는 셀렉터. 1라운드엔 문법·형식 실패가 0 이었는데 2라운드엔 5(r2a)·9(r2b) 발생. 즉 병목은 반례도 개념도 아니고 JoI 표기 지식이다.
- r2b 프롬프트 결함: 체크리스트에 리터럴 `{"any": [...]}` 를 넣어 모델이 진단 문자열에 그대로 복사 → JSON 깨짐 6건. 프롬프트에 큰따옴표 든 JSON 리터럴 금지.
- **반례 없는 대조군 실행 완료(09-16, `protocol_e3_feedback_ablation.json`)**: 같은 68건·같은 설정·같은 평가기, 반례 대신 "IR 과 동등하지 않음, 위치는 알려주지 않음"만 전달. 프롬프트는 v5 에서 증거 읽는 절과 F1–F4 언급만 제거(수정 규칙·체크리스트·예제 A–G 는 바이트 동일). **결과 31/68(45.6%) vs 반례 있을 때 36/68.** 쌍 비교: 둘 다 성공 26, 반례로만 10, 반례 없을 때만 5, 둘 다 실패 27. **McNemar 양측 p = 0.30, 유의하지 않음.**
- 관찰: 반례 없이 '틀렸다'만 듣고도 68건 중 31건을 다시 제대로 낮춘다. 반례의 순효과는 5건이고 일방적이지도 않다(10건 살리고 5건 죽임). 죽이는 기전이 보인다 — 프롬프트가 '증거가 뒷받침하는 최소 수정'을 지시하므로 반례가 가리킨 곳만 고치고 나머지 오류를 보존한다(C20_014 는 threshold 만 고치고 period 0 방치, C24_005 는 반복 본문을 최상위에 붙임; 반례 없는 쪽은 IR 기준으로 블록을 다시 써서 통과). 1라운드 실패 분석의 `OP|` 누락도 같은 기전.
- 세 실험이 같은 지점을 가리킨다: 2라운드에서 모델은 결함을 정확히 진단하고도 JoI 로 못 적었고, 대조군은 반례 없이도 31건을 고쳤다. 기록 `RESULTS_E3_FEEDBACK_ABLATION_2026-09-16.md`.
- **동결된 수치 네 가지**: 1라운드 36/68(52.9%, protocol v1), 2라운드 누적 40/68(58.8%, r2a), 2라운드 사후 프롬프트 42/68(r2b), 반례 없는 대조군 31/68(45.6%, ablation). 넷 다 동결 프로토콜과 평가기 기록이 있다. 원고에 무엇을 어떻게 쓸지는 나중에 whisoo 가 정한다.


## Table 1 동기 실험

`PerCom/1_Intro/motivation_judge/` 로 옮겼다(09-16). 설계·수치·원고 규칙은 [1_Intro/HANDOFF.md](../1_Intro/HANDOFF.md) 에 있다.

## E4 — 비용·규모 (2026-09-17)

위치 `E4_cost/`. 설계·진단은 [E4_cost/README.md](E4_cost/README.md), 수치는 [E4_cost/RESULTS.md](E4_cost/RESULTS.md).

- 합성 프로그램 30개(센서 수 W 1–7, 단계 B 1–6, 대기 T 100 ms–4 h, 반복 K 1–200; 축별 단독 + 대각선), 3회 반복, 1회당 120 s(E2와 같음). 판정 정답 여부는 보지 않는다(E2 몫).
- 결정(whisoo 09-16): 메커니즘 ablation 제외(silent-time elision 에 스위치 없음) → horizon 유무 비교로 대체. 원고는 속도가 아니라 판정 범위로 쓴다. 원고 그림은 대각선 한 칸(`figs/e4_cost.pdf`).
- 결과: H=None 28/30 프로그램(84/90회). 프로그램별 3회 중 가장 느린 값 기준 1 s 미만 19개, 5 s 이내 24개, 21 s 이내 28개(판정 회차 median 0.48 s / p95 17.8 s, ≤44 MB). 고정 H=10 s 7/30, 대기를 덮는 고정 H 2/30.
- 미판정 2개(W6B6K50, W7B6K100)는 지원 거절이 아니다. timer-zone 증명의 30 s 벽시계 한도에서 포기했다. 한도 해제 진단 시 전자는 242 s 에 EQUIV, 후자는 전이 상한 2,000,000 에 도달했다.
- **주의: 30 s 한도가 벽시계 기준이라 H=None 판정 여부가 서버 부하에 따라 바뀐다.** 12개 동시 실행(`runs/e4_run.jsonl`, 미보고)에서는 80/90이었다. H=None 은 반드시 1개씩 돌린다.
- 원고 서술 규칙(whisoo 09-17): 내부 30 s 한도는 원고에 쓰지 않는다. timeout 은 사용자가 정하는 파라미터로 서술하고(E4 는 E2 와 같은 120 s), 미판정 2개는 "지원 거절이 아니라 시간 예산 초과"로 쓴다. "거의 일정" 같은 수치 없는 표현은 쓰지 않는다.
- `n_steps` 는 IR·코드 걸음을 따로 세므로 전이 수는 `n_steps // 2`.
- Abstract 의 E4 문장은 가정치(70%, 50 ms)를 버리고 whisoo 선택안으로 교체했다(09-17): "decided 28, 19 of them in under a second, whereas fixed-horizon search decided at most 7". 1초 미만 19개는 3회 중 가장 느린 값 기준. 그림은 후보 A/B(`E4_cost/figs/options/`) 중 whisoo 선택 대기.

## 공통

- E1–E4 번호는 최신 계획대로 고정한다. 구 문서의 E1/E2 번호를 가져오지 않는다.
- 구 fixed-horizon 평가와 그에 종속된 pair 수·transition 감소율·latency 수치는 현재 PerCom 원고에서 제거했다. 이는 과거 audit 기록으로만 보존한다.
- E3는 위 최신 H=None 결과와 탐색적 범위로 보고한다. E4는 동일 검증 계약의 closure/completion 조건에 맞춰 별도 실행·작성한다.
- Motivation pilot과 LLM-judge experiment는 Table 1/동기 근거로 별도 취급하고 E2/E3에 조용히 합치지 않는다.
- E1–E4의 현재 근거를 Methods–Results에 반영하고, 별도 확증 평가와 구분한다.
- 모든 refusal/error/incomplete를 전체 분모에 남긴다.
- transition reduction을 runtime speedup으로 바꿔 쓰지 않는다.
