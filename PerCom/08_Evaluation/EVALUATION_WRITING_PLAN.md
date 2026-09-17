# Evaluation 집필 계획

작성: 2026-09-17. 상태: 사용자 검토 전 계획. Motivation부터 이후 원고 전체도 피드백 전이다.

## 최신 사용자 결정 및 작성 결과

아래 최초 계획보다 이 절이 우선한다.

- E1과 E3에도 작은 표를 넣는다. E1–E4 각각 하나로 총 네 개다.
- Counterexample은 입력 이력과 기대/실제 행동 차이를 알려주는 repair 보조 수단으로 설명한다. 반례 없는 대조군과 비교 통계는 본문에 넣지 않는다. 반례 자체의 수정 성능 개선·인과 효과도 주장하지 않는다. 기존 대조군 실험과 기록은 삭제하지 않는다.
- 사용자가 작성 및 push를 요청하여 `PerCom_version.md`와 Overleaf `sections/evaluation.tex`에 초안을 작성했다. 실험은 재실행하지 않았다. Motivation부터 이후 원고는 여전히 사용자 피드백 전이다.
- E2/E3/E4 핵심 집계를 원 실행 파일에서 재확인했다. E4는 직렬 Explorer와 4-worker baseline이라는 측정 조건을 본문에 밝히고 matched-load speedup을 주장하지 않는다.
- 네 표 포함 Evaluation은 현재 배치 약 1.7페이지, 전체 PDF는 참고문헌·부록 포함 11페이지다. 앞부분 축소와 Limitations/Conclusion 작성은 남아 있다.
- 아래는 최초 계획을 보존한 기록이다. '표 두 개', '대조군 본문 포함', '이번 턴 작성·push하지 않음'은 위 결정으로 대체됐다. 최신 집필·검증 기록은 `DRAFT_NOTES.md`에 둔다.

## 최초 계획 (아래 기록 보존)

## 1. 목적과 분량

논문의 중심은 확정 Timeline IR/binding 아래에 생성 코드의 행동 검사를 붙이는 workflow다. Evaluation은 그 기준을 표현할 수 있는지, 검사 결과를 신뢰할 근거가 있는지, 실제 생성 코드에 적용되는지, 검사 비용이 얼마인지 순서대로 보여준다.

새 실험을 대량 추가하는 계획이 아니라 기존 E1–E4를 본문에 맞게 압축하는 standalone 집필 계획이다. 아래 숫자는 기존 보고서의 집필 후보이며 이번 작업이 새 결과 감사나 논문 사용 승인을 부여하지 않는다. 실행을 추적하는 새 experiment pack은 만들지 않는다.

목표는 표 포함 2–2.2페이지다. 현재 본문 앞부분의 축소와 별도로 이 공간을 확보해야 하며, 기존 9페이지 PDF에 그대로 추가해도 된다는 뜻이 아니다. Limitations/Conclusion과 참고문헌·부록 공간은 별도로 남긴다. 현재 실험 번호 E1–E4를 유지하고, 별도 Implementation 절은 되살리지 않는다.

| 구성 | 담당 질문 | 목표 분량 |
| --- | --- | --- |
| Setup | 무엇을 어떤 조건에서 평가했는가 | 0.15쪽 |
| A. Timeline IR Adequacy (E1) | 실제 출처의 요구를 표현하고 기대 trace를 재현하는가 | 0.35쪽 |
| B. Validation Fidelity (E2) | Explorer 판정이 별도 reference 실행과 일치하는가 | 0.55쪽 |
| C. Generated-Code Validation (E3) | 생성 후보에서 어떤 결과와 오류가 나타나는가 | 0.50쪽 |
| D. Validation Cost and Scale (E4) | 규모가 커질 때 검사 완료와 비용은 어떤가 | 0.55쪽 |

각 소절은 목적·설계 → 결과 → 해당 결과의 범위 순서로 쓴다. 핵심 주장은 두 개로 제한한다: (P1) 확정 명세 기준의 행동 검사가 생성 오류를 드러낸다(E2/E3, E1은 기준 표현의 보조 근거), (P2) 평가한 합성 프로그램군에서 검사 비용과 완료 범위를 측정할 수 있다(E4). NL 의도 정확도, 사용자 가독성, 실기기 안전성, 일반적 model checker 우위는 주장하지 않는다.

## 2. Setup

- JoI backend, 확정 IR/binding, 공통 입력·시간·ACTION 계약은 Methods를 참조하고 다시 설명하지 않는다.
- E1의 corpus/depth, E2의 프로그램 쌍, E3의 생성 후보, E4의 합성 프로그램은 서로 다른 모집단이다. 하나의 총 표본 수로 합치지 않는다.
- 실행 당시 CPU/RAM/OS, Python/solver 버전, 평가기 snapshot, 실험별 예산을 원래 manifest/프로토콜에서 확인한다. 현재 서버 사양으로 과거 실행 환경을 대체하지 않는다.
- 모델은 E3에만 해당한다. 모델 식별자와 생성 설정, 확정 입력을 주었다는 점을 기재한다. 검사는 LLM 추론 비용과 분리한다.
- E2의 120초/400,000 states/2,000,000 transitions와 E4의 반복·시간 예산은 원 기록을 사용한다. 실험별 설정 차이가 있으면 공통 설정이라고 묶지 않는다.

## 3. E1: Timeline IR Adequacy

**본문 구성: 두 문단, 별도 표 없음.**

1. 공식 문서·연구·elicited·community 출처의 100건을 수집했고 저자 선별상 in-scope 92, ambiguous 6, out-of-scope 2였음을 짧게 설명한다. 92건 전체를 인코딩한 실험은 아니다.
2. 심층 20건에 대해 기대 timed trace를 정하고 인코딩·의미 검토·reference replay를 수행한 결과, 최종 53개 이력이 정확히 일치했다는 보고를 사용한다. 17건 일반 판정과 세 가지 조건부 성공(독립 자동화 분해, 고정 개수 집계, 고정 상한 2)을 함께 명시한다.
3. 별도 boundary probe 3건은 20건 분모 밖이다. 표현 가능성과 Explorer 인증 가능성은 다르다는 결론으로 연결한다. 현재 인증 범위는 최신 실행 기준과 구분하고 과거 E1 보조 판정을 최신 구현의 한계로 단정하지 않는다.

**남길 한계:** 선정 사례 연구, 단일 저자 코딩, 사용자 실험 없음. 20/20을 스마트홈 요구 coverage 100%로 쓰지 않는다. 사전 기록 후 수정된 해석/인코딩도 있어 모든 결과를 untouched preregistered success로 묘사하지 않는다. 수정 이력은 아티팩트에 보존한다.

근거: `E1_adequacy/E1_SUMMARY.md`, `breadth/depth/RESULTS.md`, `breadth/audit/PROVENANCE_AUDIT.md`(뒤 두 경로는 E1_adequacy 아래).

## 4. E2: Validation Fidelity

**본문 구성: 설계 한 문단 + 표 EV-T1 + 결과·미판정 한 문단. 가장 우선하여 보존한다.**

- 모집단 140쌍 = 수작업 correct 21 + fault 81 + 유효 LLM 후보 38. 입력 부적합 2건은 모집단 구성 단계에서 분리한 기록을 남기며, 나머지 refusal/timeout은 분모에 유지한다.
- 별도 reference 구현, E1 trace와 JoI conformance 점검, 48,990개 입력 이력 및 Explorer witness 재생을 짧게 설명한다. 별도 구현이라는 사실과 완전한 조직적 독립성은 구별한다.
- 표에는 전체 판정 130/140, EQUIV 55, DIVERGE 75, 미판정 10을 넣는다. EQUIV는 유한 reference 이력에서 차이 없음, DIVERGE는 reference 이력 67 + witness 재생 8로 구분한다.
- 추가 표 행으로 관찰된 차이가 있는 **fault 쌍 75개**의 결과 69 DIVERGE / 0 EQUIV / 6 미판정을 넣는다. 전체 DIVERGE 75와 이 fault 모집단 75는 서로 다른 수치다.
- 미판정은 nested repetition/time budget 5와 event-dependent growing deadline/refusal 5로 설명한다.

**해석:** 검사한 근거에서 판정과 모순되는 사례를 찾지 못했다. EQUIV 55건의 reference 시험은 전칭 동등성 증명이 아니다. '정확도 100%'라고 쓰지 않는다. 동일 요구의 mutant는 독립 표본으로 취급하지 않는다.

근거: `E2_fidelity/RESULTS.md`의 Final version, `E2_fidelity/E2_WRITING_PLAN.md`, `E2_fidelity/runs/e2_run.timer-binding.jsonl.gz` 및 reference 재생 기록. 과거 최적화 audit만으로 최종 130개 reference 확인을 대신하지 않는다.

## 5. E3: Generated-Code Validation

**본문 구성: 설정·분포 한 문단 + 오류 사례 한 문단 + feedback 짧은 문단. 별도 대형 표 없음.**

- `Hyper-AI/Qwen3.5-9B-fp8`, 확정 IR/binding을 직접 제공한 382건. 원본 388건에서 timeout/on_timeout 6건을 제외한 범위임을 명시한다.
- 현재 보고: EQUIV 309, DIVERGE 68, REFUSED 3, UNKNOWN 2. 판정 완료 377/382는 정확도가 아니다. 68건은 Explorer replay로 확인됐으며 E2의 별도 reference 확인과 혼동하지 않는다.
- 63건 재생성 + 319건 byte-identical 재사용을 포함한 익숙한 과제의 탐색적 결과임을 짧게 밝힌다. 새 382건 독립 생성이나 NL→IR end-to-end 평가로 쓰지 않는다. 일부 확정 binding은 원 NL의 'all'과 다르므로 사용자 의도 충족률을 주장하지 않는다.
- 오류는 '지속 조건이 counter로 풀리면서 너무 이른 행동을 냄', 'edge를 level polling으로 바꾸어 재실행함' 같은 실제 timed ACTION 차이로 설명한다. 집필 전 원 후보/반례를 확인한 1–2개 사례만 쓴다. 전체 68건 유형별 빈도는 전수 분류 감사 전까지 넣지 않는다.

**Feedback 문단:** 한 번의 수정 후 36/68이 EQUIV였고, 동일 repair 설정에서 반례를 숨긴 대조군은 31/68이었다는 결과를 함께 제시한다. 기존 보고의 paired exact McNemar p=0.30을 유지하되 반례의 유의한 개선 효과로 쓰지 않는다. 36건 성공 외 DIVERGE 26, timeout 5, model error 1도 분모에 남긴다. 두 arm 모두 원 생성보다 보강된 repair prompt를 사용하므로 원 생성 대비 차이를 반례만의 효과로 해석하지 않는다. repair loop가 연결 가능하다는 보조 증거까지다.

2라운드 40/68과 사후 prompt 42/68, 상세 실패 유형·프롬프트 개발 이력은 아티팩트에 둔다. 본문에서 best-of 결과를 고르지 않는다. 분량 부족 시 feedback 전체를 줄이되 대조군과 한계만 지우지 않는다.

근거: `E3_application/E3_QWEN_382_FINAL_2026-09-15.md`, `../../../explorer/eval/results/e3_single_binding_382_20260915_run/`, `E3_application/feedback/RESULTS_E3_FEEDBACK_2026-09-16.md`, `E3_application/feedback/RESULTS_E3_FEEDBACK_ABLATION_2026-09-16.md`.

## 6. E4: Validation Cost and Scale

**본문 구성: 설계·비교 대상 한 문단 + 표 EV-T2 + 결과·한계 한 문단.**

- 합성 30개, 각 3회. 센서 수/단계 수/대기 길이/반복 수를 각각 변화시키고 대각선 조합도 포함한다. 모든 프로그램을 동등하도록 구성한 비용 실험이며 정답 판정 정확도의 근거로 재사용하지 않는다.
- 주 비교는 timer-zone 단계가 없는 명시적 상태 탐색이다. 공통 실행기, 다음 사건 점프, 정확한 상태 재사용을 갖는 구현 내 비교로 소개한다. 별도 NuSMV/UPPAAL와 비교한 결과로 쓰지 않는다.
- 보고 후보는 완료 28/30 대 12/30, Explorer에서 19개가 1초 미만, 완료한 28개가 모두 21초 이내다. 프로그램별 세 번 모두 완료해야 완료로 세고 시간은 가장 느린 회차로 요약한다. 미완료 2개는 분모에 유지한다.
- EV-T2는 기존 `e4_table.md`의 축별 선택을 보존하되 약 7–8행으로 압축한다: base, sensors 7, stages 6, wait 0.1s, wait 4h, repeats 200, 어려운 diagonal, 전체 완료. 열은 프로그램/Explorer 시간/explicit 시간 중심, 상태 수는 핵심 사례만 본문에 쓴다. 선택 행은 사전 정의 축의 끝점으로 고르며 전체 30개 기록을 보존한다.
- 표는 기존 사용자 선택대로 유지하고 새 대형 figure는 만들지 않는다. 시간 추론은 기존 기법의 적용이며 새로운 zone 알고리즘이라고 쓰지 않는다.

**집필 전 점검:** Explorer는 직렬, baseline은 4개 동시 실행이었다. 각 방법의 자원·부하와 내부 시간 제한 차이를 확인해야 공정한 같은 조건 비용 비교로 쓸 수 있다. 확정 전에는 같은 예산이라는 이유만으로 정확한 speedup을 주장하지 않는다. 보고 시간의 process startup/timeout cleanup 포함 여부도 확인한다. 동일 조건 비교를 핵심 주장으로 유지하려면 serial 기준 matched 재실행을 우선 고려한다(이번 계획에서는 실행하지 않음).

고정 100ms 시뮬레이션의 유한 구간 결과는 무제한 완료와 같은 인증이 아니다. 공간상 본문에서 빼는 것을 기본으로 하며, 넣더라도 유한 구간 시험이라는 조건을 명시한다. 과거 H=10s 비교를 부활시키지 않는다.

근거: `E4_cost/RESULTS.md`, `E4_cost/e4_table.md`, `E4_cost/README.md`, `E4_cost/runs/e4_free_serial.jsonl`, `E4_cost/runs/e4_explicit_w4.jsonl`.

## 7. 집필 전 순서와 중단 조건

1. **필수: 최신 근거 연결.** E1–E4별 모집단·평가기 버전·최종 행·제외·실패를 대조한다. `E3_application/results-audit-final/`은 이름과 달리 철회된 388건 실행을 다루므로 최신 382건의 승인 근거로 사용하지 않는다. E2 `handoff_timer/results-audit/`도 개발 최적화 감사이며 이후 reference 확인과 범위가 다르다. 최신 결과를 정식 claim binding으로 승격할 때는 해당 scope의 감사 기록을 먼저 갱신한다.
2. **필수: E2 의미 구분.** EQUIV의 checked-history 일치와 DIVERGE witness 확인을 구분한 EV-T1을 만든다. reference와 충돌하는 판정이 발견되면 fidelity 주장을 멈추고 원인을 해결하거나 결과를 제한한다.
3. **필수: E4 공정성 확인.** 공통 자원/실행 조건 차이가 결과를 좌우하는지 확인한다. 불확실하면 조건별 기술 통계로 한정하고 비교 우위 문구를 보류한다. 필요 시 matched 재실행 계획을 별도 동결한다. baseline도 작은 대기 사례에서는 완료할 수 있어야 하며, 실패하도록 설정하지 않는다.
4. **필수: E3 사례 검토.** 제시할 후보와 trace만 최소 검토하고, 전체 유형 빈도가 필요할 때만 전수 분류한다. 원인 분류가 불확실하면 사례 설명도 제거하고 판정 분포만 쓴다.
5. **그다음 집필.** E2 → E3 → E4 → E1 → Setup 순으로 작성하되 최종 독서 순서는 E1–E4다. 표 두 개와 함께 2–2.2페이지에 맞춘다. 이번 턴에서는 실행·원고 수정·push하지 않는다.

선택 작업은 matched E4 재측정(비교 주장 유지 시 필수로 승격), 추가 모델 또는 held-out E3 반복이다. 후자는 일반화 주장이 필요할 때만 별도 동결 모집단으로 수행한다. 이미 본 과제를 다시 돌린 것만으로 confirmatory evidence로 올리지 않는다. 사용자 연구, HA/openHAB backend, compiler baseline, 실기기 실험은 이번 집필의 선행 조건으로 추가하지 않는다.

## 8. 압축 우선순위

먼저 E1 전체 분류표·사례 나열, E3 생성 수정 이력, repair 2라운드, E4 진단 실행을 본문 밖 로컬 아티팩트로 보낸다. 별도 supplementary 제출이 허용된다고 가정하지 않는다. 그래도 길면 E4 상태 수 열과 E3 사례 수를 줄인다. E2의 판정 근거 차이, 각 모집단 분모, 미판정 결과, E3 탐색적 범위와 feedback 대조군은 압축 중에도 유지한다.

계획에는 research-paper-plan의 주장·근거·분량 연결, research-experiment-plan의 최소 비교/중단 조건, research-results-auditor의 최신 scope·실패·독립성 구분 원칙을 적용했다. 새 실험 실행이나 완전한 결과 감사는 수행하지 않았다.
