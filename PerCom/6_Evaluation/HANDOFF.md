# Evaluation handoff

상태: **E1 종료(2026-09-13), E2 완료(2026-09-14, 140쌍 모집단). 원고 E1·E2 초안은 whisoo 검토 대기. E3 탐색적 완료(2026-09-15, Qwen 382건). Feedback 루프 설계 중, E4 는 feedback 실험 후.**

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
  - 판정 130 = 정답기 확인 129(이력에서 EQUIV 55 + DIVERGE 66, 반례 재생 8) + 확인 불가 1(C24_003). 어긋남 0.
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
  - `0e76584`(바인딩된 `any` 동작 허용)은 2026-09-14 whisoo 결정으로 되돌렸다. `any` 는 조건문 안에서만 쓸 수 있고, Explorer 파서와 정답기(SPEC_GAPS G35) 모두 조건문 밖의 `any`(ACTION·대입·인자)를 구문 오류로 거절한다.
- Timeline IR 절·Limitations 절로 보낼 E2 항목은 각 절 HANDOFF 에 적었다.

## E3 — `E3_application/`

- **E3 application 최신 Qwen 평가(2026-09-15 완료).** 상세: `E3_application/E3_QWEN_382_RESULT.md`.
  - 모델 `Hyper-AI/Qwen3.5-9B-fp8`, 실행 시 endpoint `http://localhost:8002/v1`. 확정 `ir_gt`와 `binding_gt`를 직접 주입하여 자연어 service mapping/selector 추론을 우회한다.
  - 원본 388행은 보존하고 timeout/on_timeout이 포함된 C26_001–006 전체를 E3 범위에서 제외했다. 현재 분모는 382건이다.
  - 후보 tag `qwen3_5-9b-fp8-e3-prefix-fixed-v2`: 기존 325건을 payload 일치 및 byte hash 확인 후 재사용하고, prefix 영향 56건과 C05_015(drying) 1건을 신규 생성했다. 신규 57건의 raw trace를 보존했으며 부분 재생성 시 프롬프트는 바꾸지 않았다.
  - B1/B2/B5 binding, `selector_binding=True`, `H=None`, bounded fallback 없음. 전체 382건: EQUIV-FIXPOINT 307 / DIVERGE_CONFIRMED 70 / REFUSED 3 / UNKNOWN 2. 판정 완료율 377/382(98.69%)이며 정확도가 아니다. 생성·capability·문법·arity 오류는 이 실행에서 0건이다.
  - 70건 모두 replay 확인, 평가 중 source/candidate hash 연속성 확인. REFUSED는 C01_015(BINARY 반환값), C03_003(무경계 산술), C11_006(대규모 조도 도메인). UNKNOWN은 C11_001·C11_005(SMT query timeout)이며 제한 변경이나 재탐색 없이 남겼다. C05_015는 EQUIV다.
  - 근거: 저장소 루트 `explorer/eval/results/e3_prefix_fixed_382_20260915_*`의 lineage, candidates, protocol, manifest 및 `_run/summary.json`, `_run/case_outcomes.jsonl`.
  - 혼합 출처·익숙한 과제의 탐색적 평가다. protocol snapshot은 후보 생성 후·평가 전에 기록했으므로 신규 382건 생성이나 confirmatory replication으로 쓰지 않는다. DIVERGE 원인은 개별 감사하지 않았고 독립 실기기 검증도 아니다.
  - 과거 Gemma 388건 결과는 `E3_application/RESULTS.md`에 이력으로 보존한다. prefix 버그가 포함된 이전 Qwen 388건 집계는 철회됐으며 최신 논문 수치로 쓰지 않는다. feedback 시험 결과는 폐기했고 현재 결과에 포함하지 않는다.

## 공통

- E1–E4 번호는 최신 계획대로 고정한다. 구 문서의 E1/E2 번호를 가져오지 않는다.
- 구 fixed-horizon 평가와 그에 종속된 pair 수·transition 감소율·latency 수치는 현재 PerCom 원고에서 제거했다. 이는 과거 audit 기록으로만 보존한다.
- E3는 위 최신 H=None 결과와 탐색적 범위로 보고한다. E4는 동일 검증 계약의 closure/completion 조건에 맞춰 별도 실행·작성한다.
- Motivation pilot과 LLM-judge experiment는 Fig2/동기 근거로 별도 취급하고 E2/E3에 조용히 합치지 않는다.
- E1·E2·E3의 현재 근거를 Methods–Results에 반영하고, 미착수 E4 scale/ablation 및 별도 확증 평가와 구분한다.
- 모든 refusal/error/incomplete를 전체 분모에 남긴다.
- transition reduction을 runtime speedup으로 바꿔 쓰지 않는다.
