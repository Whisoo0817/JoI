# VETS / New OVLA — PerCom 2027 프로젝트 컨텍스트

최종 정리: **2026-09-07 (KST)**. 이 README는 새 에이전트 세션이 논문의 배경, 합의된 방향, 구현·실험의 현재 상태와 다음 작업을 이어받기 위한 진입점이다. 파일의 존재, advisor의 `PASS`, 초록의 완료형 표현을 구현·증명의 완료로 해석하지 않는다.

## 1. 현재 프로젝트를 먼저 이해하기

SenSys 2027에 제출한 OVLA 논문이 reject되어, 리뷰를 바탕으로 논문의 주장과 검증 방법을 보완해 **PerCom 2027 main conference**에 제출하는 프로젝트다. 현재 초록 초안의 시스템 이름은 **VETS**다. OVLA는 이전 논문 및 설계·코드에 남은 이름이며, VESTA는 중간에 사용했던 이름이다.

논문의 중심 질문은 **“LLM이 생성한 스마트홈 자동화 코드가 구현해야 하는 행동을 어떻게 검증할 것인가?”**다. Timeline IR의 문법이나 결정론성 자체를 독립적인 언어 연구처럼 전면에 두지 않는다. Timeline IR은 생성 코드와 비교할 실행 가능한 기준 행동을 제공하기 위해 필요한 수단이다.

현재 확보한 결과는 **동결된 유한 입력 모델과 32단계 실행 범위에서, 평가 가능한 311개 IR–코드 쌍에 대한 Explorer와 완전 열거기의 판정 일치**다. 이후 발견한 Speaker 반례와 아직 완료하지 않은 증명 때문에, 이를 Explorer 전체의 formal guarantee로 확대할 수는 없다. 다음 핵심 작업은 입력 추상화를 보완하고 그 탐색 범위를 증명하는 것이다.

## 2. 반드시 읽을 문서 — 이 순서대로

사용자가 지정한 지식 순서다. 대소문자와 경로는 아래 실제 파일명을 사용한다.

| 순서 | 문서 | 읽는 목적 / 지위 |
| --- | --- | --- |
| 1 | [JOI_SPEC.md](docs/JOI_SPEC.md) | **최우선 도메인 지식.** JoI DSL의 반복 실행, 지속 변수, 셀렉터, 시간 연산, 생성 파이프라인을 먼저 이해한다. 파이프라인 경로·일부 설명은 과거 구조이므로 현재 코드와 대조한다. |
| 2 | [OVLA_SenSys2027.pdf](docs/OVLA_SenSys2027.pdf) | 실제 reject된 이전 제출본. motivation, Figure 1, 이전 시스템·평가·보장 범위를 파악한다. 신규 구현의 성능 근거로 재사용하지 않는다. |
| 3 | [review.txt](docs/review.txt) | 사용자 확인 가정, bounded 검증, compiler 대안, 일반화, on-device 동기와 재현성에 대한 원래 지적을 읽는다. |
| 4 | [New_OVLA_Timeline_IR_Design_and_Verification.md](docs/New_OVLA_Timeline_IR_Design_and_Verification.md) | PerCom용 재설계의 논리와 형식화 방향. GPT와의 논의에서 나온 설계안이며, 모든 세부 문법·의미론·증명이 최종 확정되거나 구현됐다는 뜻은 아니다. 이후 교수님·사용자 피드백과 함께 읽는다. |
| 5 | [abstract_draft.txt](docs/abstract_draft.txt) | **확정본이 아닌 최신 초록 초안.** 현재 제목·이름·서사의 출발점이다. `formally verifies`, 시간 경계 최적화, 수치 표현은 아래 현재 근거 범위와 대조해야 한다. |
| 6 | [VETS_formal_verification_scope_and_explorer_revision.md](docs/VETS_formal_verification_scope_and_explorer_revision.md) | 실험 완료 → formal claim 검토 → Speaker 반례 → 32단계와 fixpoint 논의 → 구현·증명·재실험 계획을 연결한 최신 기술 인계 문서. **보완 계획을 완료 기록으로 읽지 않는다.** |

문서가 충돌하면 주제별로 판단한다. DSL 이해는 `JOI_SPEC.md`에서 시작하고, 실제 동작은 해당 코드·테스트와 대조한다. 연구 범위는 최신 사용자·교수님 합의가 이전 advisor 제안보다 우선한다. 수치는 동결된 결과·감사 기록을 따르되, 이후 발견된 반례와 제한도 함께 적용한다. 초록 문구가 보장 범위를 결정하지 않는다.

## 3. 제출 일정과 프로젝트 진행 경과

등록과 최종 제출 마감은 각각 **1주 연기**되었다. 2026-09-07에 [공식 Call for Papers](https://percom.org/call-for-papers/)에서 확인했다.

| 마일스톤 | 기존 마감 | 변경된 마감 | 한국 시간 환산¹ |
| --- | --- | --- | --- |
| Paper registration | 2026-09-04 AoE | **2026-09-11 AoE** | 2026-09-12 20:59:59 KST |
| 논문 최종 제출 | 2026-09-11 AoE | **2026-09-18 AoE** | 2026-09-19 20:59:59 KST |

¹ AoE 날짜의 23:59:59, UTC−12 기준 환산이다. 제출 작업은 여유 있게 끝내고 실제 [HotCRP](https://percom2027.hotcrp.com/) 화면의 마감을 마지막으로 확인한다. 여기서 registration은 논문 등록이며 학회 참석 등록이 아니다. 실제 등록 완료 여부는 이 저장소에서 확인되지 않았다. 사용자는 등록 이후 제목 수정이 불가능하고 abstract는 최종 제출 때 수정 가능하다는 전제로 논의했다. 제출 화면에서 최종 확인할 항목이다.

공식 분량은 기술 내용 최대 9쪽(10pt, IEEE 2단; 그림·표·부록 포함)과 참고문헌 전용 최대 1쪽이며 double-blind다. 기존 [venue 요건 문서](skill_result/02_literature/percom/official_scope_and_requirements.md)의 9/4·9/11 마감은 연기 전 기록이다.

| 시점 / 단계 | 진행 내용 | 현재 의미 |
| --- | --- | --- |
| 이전 SenSys 제출·reject | OVLA 제출본과 리뷰 3건 확보 | 새 논문의 출발점. 리뷰 세 건 모두 weak reject이며 reject 사실은 사용자 제공 맥락이다. |
| 이후 방향 논의 | 사용자 확인을 명세 확정 경계로 설정; 코드의 행동 동치로 주장 재정립 | end-to-end 의도 정확성에서 confirmed IR 대비 구현 정확성으로 보장 범위를 명확히 함 |
| 7–9월 Explorer 개발 기록 | BFS, 상태 병합, 입력 분할, 시간 점프, 단편 검사, 반례 재생 등 개발 | 과거 실행 기록은 [explorer/README.md](explorer/README.md), [runs/](explorer/runs/)에 있음. 일반 soundness 증명과는 별개 |
| 2026-09-04 advisor·workspace 정리 | 선행연구, 주장, 형식 설계, E1–E4 계획과 코드 구조 정리 | `skill_result/`의 주요 문서 생성; 계획 단계 상태가 남아 있음 |
| 2026-09-04 A/B 실험 | 개발 sweep → v1 생성 실패 → v2 감사·보완 → 새 v3 held-out 평가 | 311쌍, H=32의 최종 기록 확보 |
| 2026-09-04 초록·명칭 | VESTA 초록 커밋 후 후속 논의에서 VETS 초안 사용 | 과거 “finalized” 파일명·커밋 메시지가 현재 확정을 뜻하지 않음 |
| 2026-09-05 후속 검토 문서 | Speaker 반례, formal claim 조건, 32단계 제한과 fixpoint 보완 계획 정리 | 보완·증명·재측정은 남아 있음 |
| 2026-09-07 현재 | 본 README로 지식·상태·TODO 연결; 연기된 마감 반영 | 아래 우선순위로 재개 |

주요 커밋: `67ce1e2`(구조 정리), `91a1b39`(bounded 차등 평가 구현), `95b1525`(held-out 결과), `132bbf5`(당시 VESTA 초록). 현재 작업 브랜치는 `paper`다.

## 4. 지금까지 합의한 논문 방향

### 문제와 해결 흐름

스마트홈 자동화는 입력 변화, 유지되는 상태, 시간 조건에 따라 여러 시점에 걸쳐 행동한다. 같은 행동을 이전/현재 값 비교, flag, state machine 등 서로 다른 코드로 구현할 수 있고, 표면적으로 그럴듯한 코드가 잘못된 반복 동작을 만들 수도 있다. 이전 논문 Figure 1의 rising-edge와 level-trigger 예시가 이 논리를 설명한다.

```text
자연어 요청 → Timeline IR 후보 → 사용자 확인 → 기준 명세 확정
                                             ├→ 코드 생성
                                             └→ 기준 행동 실행
같은 모델링된 초기 환경·입력 이력으로 IR과 코드를 실행 → 행동 비교·반례
```

Timeline IR은 자연어에 암묵적인 event·state·time 의미를 명시적인 연산자로 나타내는 authoring surface이자 실행 가능한 명세다. 사용자 확인 이후 이를 authoritative specification으로 삼는다. IR과 코드의 내부 변수나 상태 표현까지 같다고 가정하지 않는다. 각자 상태를 전개하고 외부에서 관찰되는 행동을 비교한다.

### 교수님 피드백과 범위 결정

- **Determinism이 Timeline IR의 핵심 성질이다.** 고정된 IR, 초기 상태, timed input sequence에 대해 행동이 유일하게 정의되어야 한다. 여러 환경 입력에 따른 여러 trace의 존재는 nondeterminism 오류가 아니다.
- **표현력은 지원 의미 공간으로 설명한다.** 문법·연산자·합성 규칙과 대표 자동화를 통해 표현 가능한 행동과 제외 범위를 제시한다. 유한한 자동화 N개가 모든 자동화의 전체 집합은 아니므로 “일반적인 자동화의 X%를 표현한다”는 수치를 주장하지 않는다.
- **결정론성은 증명, 구현 적합성은 실험으로 다룬다.** 문법 구조에 대한 귀납으로 primitive와 합성 연산자의 one-step determinism을 보이고, 입력 길이에 대한 귀납으로 unique trace를 얻는 계획이다. 여러 테스트를 통과했다고 언어 전체의 결정론성이 증명되는 것은 아니다.
- **논문의 주인공은 행동 검증이다.** 문법·실행 의미·합성·결정론성은 검증 기준이 필요하다는 문제에서 도출한다.
- **현재 표현 범위는 smart-home automation이다.** 스마트팜·오피스·팩토리 확장 가능성을 논의했지만, 새 도메인·다른 DSL에서의 일반화는 현재 입증되지 않았다.
- **On-device나 로컬 LLM은 핵심 전제가 아니다.** 현재 주장의 성립을 특정 모델 크기·배포 위치에 제한하지 않는다. frontier 모델도 플랫폼 지식과 복잡한 행동 구현에서 오류를 낼 수 있다는 논의가 배경이다.
- **User study는 진행하지 않는 방향이다.** 사용자 확인은 자연어 의도와 구현 정확성을 분리하는 명시적 가정이다. 의도 해석의 정확성, 비전문가의 확인 성공률, usability를 보장하지 않는다.
- **LLM lowering의 필연성을 주장하지 않는다.** deterministic compiler는 가능한 대안이다. 현재 연구는 생성된 코드의 독립적인 행동 검사에 초점을 두며 compiler 우열 비교는 완료된 근거가 아니다.
- **Abstract는 간결하게 유지한다.** 세부 의미론과 증명 전개는 본문에서 다루고, 마지막에는 실제 측정한 검증 판정 일치와 비용 감소를 정확한 범위로 요약한다. 초안 자체는 아직 확정되지 않았다.

### 이전 리뷰를 새 논문과 연결하기

| 이전 지적 | 현재 대응 방향 | 남아 있는 책임 |
| --- | --- | --- |
| 어려운 의도 판단을 사용자에게 넘겼음 | 확인된 명세 대비 코드 검증으로 주장 경계 명시 | 사용자 확인이 실제 의도 정확성을 보장한다는 인상을 주지 않기 |
| 왜 deterministic compiler를 쓰지 않는가 | lowering 방식과 검증 기준을 분리 | compiler가 불가능하거나 LLM이 필수라고 주장하지 않기 |
| bounded scenario 검사인데 formal verification인가 | 실행 의미·관찰 관계·탐색 포괄성의 정리와 증명 마련 | Speaker 반례 수정, 구현 대응, bounded/fixpoint 판정 구분 |
| 한 플랫폼 결과에 비해 일반화가 과함 | smart-home/JoI 및 지원 모델 범위 명시 | 다른 backend·실제 물리 동작의 정확성으로 확대하지 않기 |
| on-device 동기와 LLM 추세 주장이 과함 | 모델·배포 위치보다 검증 문제를 중심에 둠 | 기존 접근에 대한 넓은 문장은 실제 선행연구로 확인 |
| 재현성과 누락 오류 분석 부족 | manifest·소스 버전·오류·반례·전체 분모 보존 | 새 구현 재실험과 독립 의미론 적합성 평가 완료 |

## 5. 구현을 읽기 전에 필요한 기술 지식

| 개념 | 이 프로젝트에서의 의미 |
| --- | --- |
| JoI 실행 | `{cron, period, code/script}` 구조. `period > 0`이면 반복 실행, `0`이면 one-shot. `:=`는 최초 초기화 후 유지, `=`는 실행 시 재평가·갱신 |
| 장치 선택·grounding | 태그를 실제 장치 집합에 연결한다. 다중 태그는 교집합이며 group action과 existence condition의 수량 의미를 구분한다. `all(...).Attr OP\| value`는 존재 조건으로 사용됨 |
| Trace / observation | 시간에 따라 발생한 action 기록. target·operation·argument·중복 횟수·순서가 중요하며 최종 장치 상태만 비교해서는 반복 호출을 놓칠 수 있음 |
| Input determinism | 같은 입력과 상태에 대한 다음 결과의 유일성. NL→IR 생성이 항상 같은 결과를 낸다는 의미가 아님 |
| Product state | 함께 실행 중인 IR 상태와 코드 상태, 환경·시간 등 미래 행동에 필요한 정보를 묶은 탐색 노드 |
| BFS + memoization | 짧은 입력 이력부터 탐색하고 같은 미래를 갖는 상태의 중복 탐색을 줄임. IR 상태만 같다고 노드를 합치면 코드 내부 오류를 놓칠 수 있음 |
| 유한 입력 모델 | 평가에 허용한 센서값·이벤트·초기 상태 등의 명시적 범위. 현실의 모든 실수값·장치·환경을 뜻하지 않음 |
| H=32 | 입력을 받고 양쪽 실행 상태를 전개하는 과정을 최대 32단계까지 검사. 32초도, 동일 상태를 32번 기다리는 병합 기준도 아님 |
| Fixpoint | 미래 행동을 보존하는 유한 상태 표현에서 더 이상 새 reachable state가 나오지 않는 상태. 그래프가 닫혔다는 근거가 있어야 길이 제한 없는 결론을 낼 수 있음 |
| False accept / reject | 완전 열거는 비동치인데 Explorer는 동치이면 A; 완전 열거는 동치인데 Explorer는 비동치이면 B. 미지원·생성 실패·미완료는 별도 결과 |

**H=32 bounded 평가와 기존 시간 점프 모드를 혼동하지 않는다.** 이번 A/B에서는 구체 상태와 깊이를 유지하고 한 tick씩 전진한다. 서로 다른 깊이를 추상적으로 합치거나 긴 시간 구간을 점프하지 않는다. 기존 Explorer의 zone 정규화·stutter 기반 시간 점프는 별도 경로이며 추가 증명이 필요하다. 따라서 73.4% 감소를 “시간 경계 점프의 효과”로 설명할 수 없다.

## 6. 완료한 것과 확보된 결과

### 완료·부분 완료 상태

| 작업 | 상태 | 근거 / 한계 |
| --- | --- | --- |
| 이전 논문·리뷰·신규 방향 정리 | 완료 | 핵심 문서 1–4 |
| Advisor의 논리·선행연구·주장·형식 설계·E1–E4 계획 | 계획 산출물 완료 | `skill_result/`; 증명·실험의 완료와 구분 |
| Explorer, IR/code 실행기, 지원 단편 검사, bounded 완전 열거·A/B 도구 | 구현 존재 | `explorer/`; 일반 soundness와 모든 advisor 의미론 구현은 미확립 |
| 독립 구현과의 E1 pilot | **개발 평가 6/6 통과** | 이전 SenSys 실행기와 공통 부분집합 비교. 최종 E1 아님 |
| 개발 sweep 및 v1/v2 실패·보완 추적 | 완료 | [experiment-tracker.md](skill_result/05_experiment_plan/experiment-tracker.md) |
| 동결된 v3 H=32 평가·감사 | 완료 | 아래 수치; 제한된 search-layer 경험적 근거 |
| Speaker 보완·bounded theorem·fixpoint theorem | **TODO** | 최신 보완 문서에 계획만 기록 |
| 최종 초록·PerCom 본문·신규 전체 E1–E4 | 미완료 | 초록은 초안, 기존 문서의 `PASS`는 완료 증거가 아님 |

### v3 held-out 수치 — 변경 전 구현의 기준 기록

결과 원본: [summary.json](skill_result/05_experiment_plan/results/E3/heldout-gemma-v3-h32/summary.json), [case_outcomes.jsonl](skill_result/05_experiment_plan/results/E3/heldout-gemma-v3-h32/case_outcomes.jsonl). 해석 범위: [결과 감사](skill_result/05_experiment_plan/results-audit/results-audit.md), [초록용 결과 설명](skill_result/05_experiment_plan/results/E3/heldout-gemma-v3-h32/abstract-result-wording.md).

| 항목 | 결과 | 정확한 분모·범위 |
| --- | --- | --- |
| 사전 선정 생성 시도 | 388 | Gemma-4-26B held-out v3 |
| 평가 가능한 READY 쌍 N | 311 | 전체의 80.15% |
| 비평가 결과 | 생성 오류 61, 미지원 15, 준비 오류 1 | 삭제하거나 A/B 분모로 섞지 않음 |
| 판정 완료·일치 | 311/311 | READY 쌍의 100%; 전체 시도의 100%가 아님 |
| 완전 열거 판정 | bounded-equivalent 231, divergent 80 | 동결 입력 모델, H=32 |
| A: false accept | 0/80 | 관측치; Wilson 95% 상한 4.58% |
| B: false reject | 0/231 | 관측치; Wilson 95% 상한 1.64% |
| R: pair-transition 평가 감소 | 73.448% (초록 반올림 73.4%) | **동치 231쌍만**: 427,685 → 113,558 |
| T: Explorer 실행 시간 | median 0.65 ms, p95 52.09 ms, max 280.12 ms | 311쌍; LLM 생성·준비·완전 열거·파일 I/O 등 제외 |

[측정 환경](skill_result/05_experiment_plan/results/E3/heldout-gemma-v3-h32/environment.md): Intel Core i9-11900K, Linux, Python 3.8.10, 단일 평가 프로세스. 평가기 커밋 `91a1b393e6ba6845d99d974ba94a06d7be33e861`. 이전 논문의 Mac mini M4 수치와 섞지 않는다.

완전 열거기와 Explorer는 **동일한 IR/code one-step 실행기를 공유**한다. 따라서 이 결과는 해당 모델에서 검색 축소의 판정 일치를 확인한 것이며, 실행 의미 자체의 정확성·모든 프로그램의 검증 정확도 100%를 입증하지 않는다. E1 pilot은 targets, grounding, reentry, cancellation, cron, missing values, timer ties, merge laws 등을 충분히 다루지 않았다.

v2 감사 때 입력 축 누락을 고친 뒤 새로운 v3를 생성·동결·평가했다. 그러나 그 수리가 아래의 **조건에 사용되면서 동시에 action argument로 흐르는 값**까지 해결했다는 뜻은 아니다. 두 보완 사건을 구분한다. 예전 대화의 `27 unsupported`는 개발 H=8 결과이며 현재 v3의 미지원 수는 15다. SenSys의 382개와 이번 388회 생성 시도도 서로 다른 분모다.

## 7. Formal verification을 위해 남은 핵심 문제

### Speaker 반례와 입력 분할

후속 검토에서 기록한 최소 반례는 다음과 같다.

```text
IR:   temperature < 10이면 speak(temperature)
Code: temperature < 10이면 speak(9)

대표값 9, 10에서는 동일해 보임.
허용 도메인에 9.9가 있으면 speak(9.9)와 speak(9)가 달라짐.
```

조건의 참·거짓이 같다는 것만으로 출력까지 같지는 않다. 현재의 경계 대표값 선택이 지원 단편 전체에서 안전하다는 주장은 이 반례로 유지할 수 없다. 기존 [SUPPORTED_FRAGMENT.md](explorer/SUPPORTED_FRAGMENT.md)의 “항등 전달은 정확하다”는 설명도 이 제한과 함께 읽어야 한다.

합의한 보완 방향은 IR과 코드 양쪽의 **transitive data flow**를 분석하는 것이다. 조건 판단에만 쓰이고 같은 다음 상태·행동을 보장하는 입력은 동치 구간의 대표값을 사용한다. action 인자·target·횟수·순서·미래 상태·timer에 직접 또는 간접 영향을 주는 값은 **선언된 유한 도메인의 모든 값**을 열거한다. 분석 불가·미지원이면 fail-closed한다. 이는 현실의 모든 연속 센서값을 전수조사한다는 뜻이 아니다.

### Formal claim과 32단계 제한

Bounded model checking도 formal verification이다. 문제는 `bounded`라는 단어 자체가 아니라, 실행 의미·trace equality·입력 포괄성·상태 병합·구현 대응에 대한 근거가 있는가다. Timeline IR determinism만으로 Explorer의 탐색 완전성이 증명되지는 않는다.

현재는 `systematically checks` 또는 `bounded behavioral verification`이 근거에 맞는다. 보완과 증명이 완료되면 `bounded formal verification`을 쓰고 지원 문법·유한 입력 모델·실행 범위를 명시할 수 있다. 초안에 `formally verifies`가 이미 있어도 증명 완료로 취급하지 않는다.

H=32는 개발에서 H=4, 8, 32로 늘린 후 실험 전에 동결한 실용적 한도이며 semantic completeness bound가 아니다. `count`에서 동적 H를 구하는 것만으로 해결되지 않는다. delay·duration·중첩 반복과 코드가 새로 도입한 counter도 고려해야 한다.

실행 길이 제한을 제거하려면 미래 행동을 보존하는 유한 product state와 상태/시간 추상화를 정의·증명하고 fixpoint까지 탐색해야 한다. 권장 결과 구분은 `DIVERGE`, `EQUIV-BOUNDED(H)`, `EQUIV-FIXPOINT`, `INCONCLUSIVE`다. **이 명칭과 보장은 보완 목표이며 현 API 전체에 이미 구현된 계약이 아니다.** 시간·메모리·상태 한도에 걸린 것을 동치로 판정하지 않는다.

## 8. 다음 작업 — 의존 순서와 완료 기준

마감까지의 작업 순서다. 각 항목의 완료 날짜나 소요 시간은 아직 확정하지 않았다. 이번 README 작성은 아래 구현·실험의 실행 완료를 의미하지 않는다.

| 우선순위 | TODO | 완료 기준 |
| --- | --- | --- |
| P0: 등록 전 | 제목·이름·초록 문구 점검 및 등록 상태 확인 | `abstract_draft.txt`를 기준으로 이름을 정리하고, 현재 근거보다 강한 문장·수치 분모를 수정한 등록 문안 확보 |
| P1: 검증 계약 | 실제 지원 IR/JoI 문법, observation, 초기 상태, 유한 입력 모델, 시간·동시성 규칙 정합화 | advisor 설계와 구현의 차이 목록 및 지원 범위 고정; 실패·미완료 판정 명시 |
| P1: Speaker 보완 | 최소 반례 회귀 테스트 → 양쪽 transitive value-flow 분석 → observable-flow 전수조사·fail-closed | 9.9 반례 및 간접 변수 전달·상태·timer 사례에서 누락 없음. 입력 manifest와 Explorer 도메인의 대응 확인 |
| P1: 형식화 | 문법·well-formedness·실행 의미와 결정론성 증명 완성 | expression/primitive/merge/constructor, progress·termination, one-step 및 unique-trace 정리 |
| P1: bounded Explorer 증명 | 시간 점프 없는 탐색부터 input partition, successor coverage, exact state merge, bounded theorem 정리 | `EQUIV-BOUNDED(H)`가 선언 범위의 모든 입력 시퀀스에 대한 동치를 뜻함을 증명하고 코드와 대응 |
| P1: E1 확대 | 독립적인 의미론 기반 expected trace·boundary oracle 작성 | 현재 6개 pilot 밖의 시간·순서·취소·재진입·장치 target·missing-value 등 지원 항목 검사, 의도적 실행기 오류 검출 |
| P1: E3 재평가 | 수정 구현·입력 모델 동결 후 완전 열거 차등 검사와 새 held-out 평가 | A/B, 전체 실패·미지원·미완료, 반례, 버전·manifest·감사 기록. 기존 v3는 개발 회귀 자료로 보존 |
| P1: 표현 범위 정리 | E2를 교수님 피드백에 맞춰 재정렬 | 문법·연산자·합성에 따른 지원/제외 행동과 사례 provenance 제시. 전체 자동화 coverage 비율로 주장하지 않음 |
| P1: E4·최종 수치 | 입력·상태·timer·규칙 수에 따른 시간·메모리·완료 경계 측정 | 최적화별 효과와 비용, median/p95/max, 실패·timeout까지 기록. R/T를 수정된 버전으로 재측정 |
| P2: fixpoint 확장 | future-relevant key, 상태/시간 추상화·stutter 보존 증명 및 탐색 | 닫힌 그래프와 bounded·미완료를 구분하고 완료율·비용 측정. 완료된 범위에서만 길이 제한 제거 |
| 제출 전 | 본문·실험 표·초록·claim 기록·익명 artifact 정합화 | 같은 버전·같은 분모·같은 보장 범위 사용, 관련연구 최종 점검, 페이지·익명성 확인 |

P2는 sound bounded 검증 이후의 강화 경로다. fixpoint가 어려운 사례 때문에 무조건 전부 무제한 검증으로 바꾸지 않는다. 복잡도가 증가하면 탐색이 지수적으로 커질 수 있으며 비용은 측정해야 한다. 결과에 맞춰 사례를 사후 제거해 A/B를 좋게 만들지 말고, 지원 범위를 사전에 선언한 뒤 제외·실패를 모두 보존한다.

## 9. `skill_result/`에서 선별해서 읽을 것

모든 파일을 읽을 필요는 없다. 다음은 현재 작업에 직접 연결되는 문서다. `confirmed`는 당시 주장·순서 합의, `PASS`는 해당 계획 게이트의 통과일 수 있으며 실험·증명의 완성을 뜻하지 않는다.

| 읽을 상황 | 선별 문서 | 역할 / 주의점 |
| --- | --- | --- |
| advisor 전체 맥락 | [PHASE_0_4_ADVISOR_SUMMARY.md](skill_result/PHASE_0_4_ADVISOR_SUMMARY.md) | 논리·문헌·형식 설계·E1–E4의 압축 요약. “실험 없음”은 작성 당시 상태 |
| 논문 논리·주장 | [논리 Map](skill_result/01_intake/new_ovla_logic_map.md), [Contribution](skill_result/03_claims/confirmed_contribution.md), [Anti-claims](skill_result/03_claims/anti_claims.md) | C1 행동 검증 → C2 실행 기준 → C3 결정론적 의미 → C4 탐색 → C5 평가의 연결과 범위 |
| 리뷰 대응 | [Reviewer objection register](skill_result/01_intake/reviewer_objection_register.md) | 원래 리뷰 지적을 주장·증거 작업에 매핑 |
| novelty·관련연구 | [SOTA gap map](skill_result/02_literature/synthesis/sota_gap_map.md) | 생성 시스템, IoT property checker, 사용자 상호작용, 형식 방법을 구분. 선정 문헌 내 분석이며 보편적 “최초” 증명 아님 |
| PerCom 서사·분량 | [Venue alignment](skill_result/02_literature/percom/new_ovla_venue_alignment.md), [Paper pattern map](skill_result/02_literature/percom/percom_paper_pattern_map.md) | pervasive 문제·구현·현실 사례·검증·비용을 연결. 7편의 관찰 경향을 공식 규칙으로 쓰지 않음 |
| 의미론 확정 | [Grammar](skill_result/04_formal_design/grammar.md), [Well-formedness](skill_result/04_formal_design/well_formedness.md), [Operational semantics](skill_result/04_formal_design/operational_semantics.md), [Observation](skill_result/04_formal_design/observation_model.md) | 제안된 syntax와 snapshot–evaluate–merge–commit, 시간 경계·취소/만료·재진입·관찰 규칙 |
| 증명·알고리즘 | [Explorer model](skill_result/04_formal_design/explorer_model.md), [Proof obligations](skill_result/04_formal_design/proof_obligations.md), [Proof sketch](skill_result/04_formal_design/proof_sketch.md) | PO-01–PO-17 및 귀납 구조. 최신 보완 문서의 입력 분할·시간 점프 의무 추가 필요 |
| 실험 재개 | [Experiment plan](skill_result/05_experiment_plan/experiment-plan.md), [Tracker](skill_result/05_experiment_plan/experiment-tracker.md), [A/B protocol](skill_result/05_experiment_plan/ab-evaluation-protocol.md), [E1 status](skill_result/05_experiment_plan/e1-conformance-status.md) | 설계와 실제 완료 이력을 구분. 최신 진행 상태는 tracker와 결과 폴더를 함께 확인 |
| 수치·claim 감사 | [results-audit.md](skill_result/05_experiment_plan/results-audit/results-audit.md), [results-audit.json](skill_result/05_experiment_plan/results-audit/results-audit.json) | v3의 제한된 confirmatory claim과 공유 실행기 한계. Speaker 후속 반례도 반드시 함께 적용 |

세부 claim·run을 변경할 때만 [candidate_claim_register.md](skill_result/03_claims/candidate_claim_register.md), [claim-map.json](skill_result/05_experiment_plan/claim-map.json), [run-blocks.json](skill_result/05_experiment_plan/run-blocks.json)을 추가로 읽고 동기화한다. 문헌의 구체 근거가 필요하면 `02_literature/collection/`의 해당 paper card·원문 및 [references.bib](skill_result/02_literature/references.bib)로 내려간다. 과거 제목 후보는 [title_candidates_and_abstract.md](skill_result/06_manuscript/title_candidates_and_abstract.md)에 있지만 현재 초안보다 우선하지 않는다.

### 특히 주의할 오래된 상태·설계 차이

- `skill_result/README.md`, advisor summary, experiment plan, candidate register에는 실험 전 상태가 남아 있다. v3 완료 여부는 tracker·결과·감사를 기준으로 읽는다.
- 기존 E2의 비율·annotation 제안은 최신 교수님 피드백에 맞춰 수정해야 한다. “전체 자동화 표현률”을 새로 만들지 않는다.
- advisor `explorer_model.md`는 기본 exact BFS를 제안했지만 실제 Explorer에는 입력 축소·상태 추상화·시간 점프가 존재한다. 모드별 구현과 증명을 따로 연결해야 한다.
- advisor observation은 독립적인 병렬 action의 우연한 순서를 제거하고 명시적 causal order를 보존한다. 현재 `SUPPORTED_FRAGMENT.md`는 tick 내 액션 **시퀀스 순서도 관찰**한다. 이미 같은 의미론이라고 가정하지 말고 지원 범위와 관찰 계약을 맞춰야 한다.
- `JOI_SPEC.md`에 남은 `joi/generate.py`, `files/ir_extractor.md` 등은 과거 경로다. 현재 주요 모듈은 아래와 같다. 문서의 “mechanically/lossless lowering” 설명만으로 생성 코드의 correctness를 이미 보장한다고 해석하지 않는다.
- `docs/VESTA_abstract_en.md`는 사용자가 오래된 버전이라 삭제했다. 복원하지 않는다. 현재 초록은 `docs/abstract_draft.txt`이며 확정본이 아니다.

## 10. 코드·데이터 위치와 재개 방법

| 위치 | 역할 |
| --- | --- |
| [timeline_ir/](timeline_ir/) | IR 파싱·검사·렌더링·장치 mapping. 주요 진입점 `timeline_ir.py`, `ir_renderer.py`, `mapping/` |
| [files/](files/) | 생성 prompt·JoI 설명·장치 hints. IR 추출 prompt는 [files/timeline_ir/extractor.md](files/timeline_ir/extractor.md) |
| [lowering/run_local_ir.py](lowering/run_local_ir.py) | IR에서 JoI 후보를 생성하는 로컬 LLM 평가 경로 |
| [explorer/](explorer/) | 현재 탐색·실행·동치 비교 패키지. 구현 안내는 [README](explorer/README.md), 지원 제한은 [SUPPORTED_FRAGMENT](explorer/SUPPORTED_FRAGMENT.md) |
| [explorer/ir_step.py](explorer/ir_step.py), [interp.py](explorer/interp.py), [runner.py](explorer/runner.py) | IR/JoI one-step 실행과 실행기 인터페이스 |
| [explorer/explore.py](explorer/explore.py), [product.py](explorer/product.py), [gate.py](explorer/gate.py) | 입력 축·상태·탐색, IR×code 비교, 준비·외부 판정 |
| [explorer/exact_tick.py](explorer/exact_tick.py), [ab_eval.py](explorer/ab_eval.py), [differential_sweep.py](explorer/differential_sweep.py) | bounded 완전 열거, A/B 집계, corpus 차등 평가 |
| [explorer/domain_manifest.py](explorer/domain_manifest.py), [domain_audit.py](explorer/domain_audit.py) | 입력 모델·hash 동결 및 입력 읽기 감사 |
| [dataset.csv](dataset.csv), [explorer/candidates/](explorer/candidates/) | IR·binding·장치 정보와 생성 후보. 기존 Qwen 후보는 개발 자료, Gemma v3는 당시 held-out 자료 |
| [snapshots/](skill_result/05_experiment_plan/snapshots/), [results/](skill_result/05_experiment_plan/results/) | 동결 manifest와 버전별 원시 결과. 새 실행은 새 디렉터리에 기록 |
| [sensys/](sensys/) | 이전 논문의 실행기·실험·근거 보존. 신규 결과와 혼용하지 않음 |
| [etc/smt/](etc/smt/) | 별도 SMT 탐색·교차 확인 자료. 현재 Explorer의 형식 증명이 완료됐다는 근거가 아님 |
| [docs/ovla0606.tex](docs/ovla0606.tex), [docs/refs.bib](docs/refs.bib) | 이전 논문 소스·참고문헌. PerCom 완성 원고로 취급하지 않음 |

과거 IDE 맥락의 `app.py`는 현재 `paper` 브랜치 루트에 없다. 서비스 개발 경로를 추정해서 다른 프로젝트를 수정하지 말고, 이 저장소의 논문·탐색 패키지에서 작업을 시작한다.

새 세션의 시작 확인:

```bash
cd /home/gnltnwjstk/joi
git status --short
git branch --show-current
git log -5 --oneline
```

탐색 구현을 변경할 때의 기존 회귀 테스트 진입점:

```bash
python3 -m explorer.tests.test_exact_tick
python3 -m explorer.tests.test_soundness
python3 -m explorer.tests.test_mapping_response
```

v3 동결 입력을 현재 구현에서 회귀 실행하는 명령 예시다. 새 임시 결과 디렉터리를 사용하며 이전 결과를 덮어쓰지 않는다. 구현이 바뀐 후의 실행은 과거 수치의 재현이나 새로운 held-out 결과와 자동으로 동일시할 수 없다.

```bash
eval_run_dir=$(mktemp -d /tmp/vets-v3-regression.XXXXXX)
python3 -m explorer.differential_sweep \
  --candidates explorer/candidates/gemma4-26b-heldout-v3 \
  --domain-manifest skill_result/05_experiment_plan/snapshots/E3_heldout_input_manifest_v3_h32.json \
  --require-frozen \
  --output-dir "$eval_run_dir"
```

입력 축 계약 자체를 변경하면 과거 manifest와 맞지 않아 `MANIFEST_MISMATCH`가 날 수 있다. 이를 숨기거나 옛 manifest를 덮어쓰지 말고 새 모델 버전과 개발/held-out 구분을 기록한다. 과거 52.1 ms의 재현에는 위에 기록한 평가기 버전·환경도 필요하다.

## 11. 다음 에이전트에게 전달할 작업 규칙

- 먼저 핵심 문서 1–6을 읽고, 요청된 작업에 필요한 advisor 문서·구현만 추가로 읽는다.
- 연구 주장, 제안 설계, 현재 구현, 실험 결과, 완성된 증명을 구분한다. 이 README의 TODO를 이미 완료한 것으로 바꾸지 않는다.
- 핵심 합의는 **smart-home 코드의 행동 검증 / confirmed IR 경계 / input determinism / 표현 범위의 명시 / 정확한 탐색 범위**다.
- Speaker와 H=32 문제를 이미 해결했다고 가정하지 않는다. 초안의 `formally verifies`와 311·73.4%·52.1 ms는 새 구현 이후 다시 검토·측정한다.
- 이전 기록은 보존하고 새 run ID·manifest·결과·감사를 만든다. 완료한 하위 작업마다 tracker와 필요한 문서·README의 상태를 업데이트해 다음 세션이 이어갈 수 있게 한다.
- 사용자 작업을 보존한다. 2026-09-07 확인 시 `docs/abstract_draft.txt`, 최신 보완 문서, 과거 v1/v2 후보 디렉터리, `skill_result/06_manuscript/new_ovla_abstract_draft.md`는 untracked이며 VESTA 초록 삭제도 미커밋이다. untracked라고 임시 파일로 판단해 삭제하거나 일괄 커밋하지 않는다.
- 이 README는 인계 문서다. 등록·제출 완료나 원격 커밋·푸시 완료를 대신하지 않는다.
