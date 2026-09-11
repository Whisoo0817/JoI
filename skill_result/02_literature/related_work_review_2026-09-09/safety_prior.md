# IoT verification and runtime enforcement: primary-source check

검토일: 2026-09-09. 논문 흐름에서의 용도: Introduction의 문제·차별성 및 Related Work의 formal verification/runtime enforcement 단락. 아래 비교는 VETS의 제한된 고정 모델에서 요청별 executable reference와 생성 구현의 timed ACTION trace equality를 비교 대상으로 삼는다. 선행 도구를 실행하거나 동일 태스크를 이식한 결과가 아니다. `차이`는 읽은 검증 계약에 대한 비교 해석이며 표현 불가능성의 증명이 아니다.

## TAPInspector — TIFS 2022

- **원문/접근:** [arXiv v2 PDF](https://arxiv.org/pdf/2102.01468v2), §III-A, §IV-A–C, §V-A, PDF pp. 4, 7–10. Primary PDF의 모델 및 검증 본문 확인. [출판 DOI](https://doi.org/10.1109/TIFS.2022.3214084).
- **표현:** 실제 SmartApps/IFTTT 앱에서 TAP rules를 추출하고 latency-sensitive rules, timer, extended action, immediate/tardy physical attributes와 연결 관계를 FSM으로 변환한다. Trigger-to-action delay 및 실행 중 지연을 별도 timer/subrule로 표현한다. Rule-dependency slicing과 수치 상태 압축을 사용한다. Cyber time은 규칙에 등장하는 시점들을 압축하며 tardy attribute와 concurrent event에는 추가 고려가 필요하다고 명시한다.
- **검증 관계:** 모델이 LTL/CTL safety 및 liveness properties를 만족하는지 NuSMV로 검사하고 counterexample을 반환한다. §IV-C/Table II는 긍정적 response, extended action 종료, timeout 전 실행 금지까지 포함한다. 총 67개 속성을 정의한다.
- **차이/위험:** “시간을 모델링하지 않는다”, “실제 코드를 안 본다”, “금지 조건만 검사한다”는 대비는 틀리다. VETS의 차이 후보는 동일 허용 입력 이력에 대한 요청별 reference와 구현의 정확한 action 발생 관계이다. TAPInspector의 동시 다중 규칙·물리 상호작용 범위는 현재 VETS보다 넓다. 현재 본문에서 reference–implementation trace equality 계약은 확인되지 않았다.
- **중복 실행 질문 후속 확인:** Table I의 T1은 같은 trigger와 양립 가능한 조건의 두 규칙이 동시에 같은 action을 수행하는 Action Duplication이다. 본문은 반복 알림·반복 거래를 예로 든다. 따라서 “기존 TAP 검증은 중복 호출을 못 잡는다”는 주장은 틀리다. §IV-A Eq.(8)은 이전 trigger attribute를 기억해 조건이 계속 참일 때 FSM이 매 step 실행하지 않도록 한다. 이 선언된 edge 모델의 올바른 규칙 분석과, 실제 생성 DSL의 잘못된 반복 코드가 reference를 보존하는지의 비교는 별도 문제다. 후자를 이 모델 추출기가 놓친다는 결론은 실제 이식 없이 내리지 않는다.

## TAPFixer — USENIX Security 2024

- **원문/접근:** [공식 PDF](https://www.usenix.org/system/files/usenixsecurity24-yu-yinbo.pdf), §4.1–4.4, §5.2–5.4, pp. 4948–4953; primary 본문 확인. [공식 페이지](https://www.usenix.org/conference/usenixsecurity24/presentation/yu-yinbo).
- **표현:** HA profile/rule, device metadata, physical configuration에서 property-specific finite automaton을 구성한다. 명시/암시 rule delay, 물리 변화 지연, 플랫폼의 센서 업데이트 지연 및 nondeterminism을 모델링한다. 수치·predicate abstraction과 refinement를 repair 탐색에 사용한다.
- **검증 관계:** `Mφ ⊨ φ`의 LTL correctness checking, 위반 state/event counterexample, negated-property reasoning을 통한 patch 생성이다. §4.3은 사용자 정의 correctness properties와 NL templates→LTL을 명시한다. 상태 유지뿐 아니라 “조건이면 다음 event가 일어나야 한다” 같은 positive event obligation 및 timer-bound property도 있다. §5.3은 local/global feasibility를 확인하고 새로운 violation도 재검사한다.
- **차이/위험:** 사용자 요구 명세, 시간 모델, 검증, repair, 사용자 확인 모두 선행된다. 다만 최종 산출물은 rule-syntax patches이고 플랫폼 프로그램 수정은 수작업으로 남긴다고 §5.4에 명시한다. 요청별 전체 observable behavior의 독립 생성 코드 보존과는 계약이 다르다. Numeric delay 변경이 의도를 깨뜨릴 수 있어 피한다는 설계도 있어 “의도 보존을 전혀 고려 안 함”은 틀리다.

## IoTSan — CoNEXT 2018

- **원문/접근:** [저자 arXiv PDF](https://arxiv.org/pdf/1810.09551), §1–2, §4, §6–8의 목표·구성·translation 설명 확인; PDF pp. 1–4 및 관련 본문. [DOI](https://doi.org/10.1145/3281411.3281440).
- **표현:** 앱 source, configuration, device/environment와 app dependency를 함께 분석한다. Groovy 코드를 변환해 Promela system model을 만들고 dependency 분석 등으로 상태 폭발을 줄인다. 따라서 IR/모델과 실제 앱 코드 분석이 이미 존재한다.
- **검증 관계:** 기본 속성과 **사용자 정의** safety properties를 대상으로 앱 간 상호작용 및 device/communication failure가 unsafe states를 만드는지 Spin으로 검사한다. Counterexample과 원인 attribution을 제공한다. §2는 실제 사용한 BITSTATE hashing이 approximate하며 complete verification을 제공하지 않는다고 명시한다.
- **차이/위험:** 차이는 사용자 명세 유무가 아니라 어떤 명세에 대한 어떤 계약을 확인하느냐이다. IoTSan은 위험 상태의 도달 가능성을 분석하며 VETS는 선택한 reference의 timed action을 구현이 보존하는지 검사한다. VETS를 더 일반적인 IoT safety 분석으로 표현하면 반박받는다. IoTSan의 failure/multi-app 범위와 VETS의 제한된 모델을 함께 밝혀야 한다.

## Soteria — USENIX ATC 2018

- **원문/접근:** [공식 PDF](https://www.usenix.org/system/files/conference/atc18/atc18-celik.pdf), Abstract, §4.1–4.4, pp. 150–154 부근의 IR·property·validation 본문 확인. [공식 서지](https://www.usenix.org/conference/atc18/presentation/celik).
- **표현:** platform-specific IoT source code→IR→state model. IR은 permission/device, event/action, event handler, app lifecycle 및 call graph를 담고 source path/state change를 분석한다. 이는 생성 전에 기대 동작을 확정하는 VETS reference와 달리 분석할 구현에서 추출한 표현이다.
- **검증 관계:** safety, security, **functional** properties를 temporal formula로 정의하고 모델 검사를 수행한다. §4.3은 general 및 app-specific properties, use/misuse case 기반 속성 도출을 설명한다. 환경에 맞게 property discovery를 조정해야 한다고 인정한다.
- **차이/위험:** “IR을 만들고 검증하는 최초 접근”은 성립하지 않는다. 기능 요구를 검증하지 않는다는 설명도 부정확하다. 차이는 구현 추출 모델이 선택된 속성을 만족하는지와, 구현보다 먼저 확정한 executable behavior reference에 대한 timed action equivalence이다. 충분한 속성으로 더 상세한 요구를 표현할 가능성을 배제하지 않는다.

## iRuler / Charting the Attack Surface of Trigger-Action IoT Platforms — CCS 2019

- **원문/접근:** [저자 PDF](https://people.cs.umass.edu/~pdatta/publication/iruler/iruler.pdf), §5.1–5.3, pp. 1442–1445; primary method 확인. [DOI](https://doi.org/10.1145/3319535.3345662).
- **표현:** rule representation은 trigger event/constraint와 action의 condition, subject, command, arguments를 포함한다. Deployment/device metadata와 함께 event-based transition system을 만들고 rewriting logic/Maude로 검사한다. Time을 증가 변수로 모델링하며 timer trigger와 physical environment의 discrete changes를 지원한다. 필요한 규칙의 값으로 time/environment 상태 공간을 줄인다.
- **검증 관계:** inter-rule vulnerabilities를 탐색하며, 본문은 built-in LTL로 **다른 properties도** 검사할 수 있다고 명시한다. NLP는 서비스 설명에서 숨겨진 rule interaction에 필요한 정보를 얻는 역할이다.
- **차이/위험:** argument, time, IR, formal checking 자체는 차별점이 아니다. 논문의 중심은 설치할 규칙들의 상호작용 attack surface이며, NL 요청에서 확정한 executable reference와 별도 생성 구현의 일치 계약과 다르다. §5.2는 실시간 연속 환경의 dynamic laws/time delays를 완전히 모델링하는 일은 범위 밖이라고 제한한다. 이 특정 제한을 모든 시간 표현 부재로 일반화하면 안 된다.

## HAWatcher — USENIX Security 2021

- **원문/접근:** [공식 초록 및 서지](https://www.usenix.org/conference/usenixsecurity21/presentation/fu-chenglong), pp. 4223–4240. **Primary abstract 확인 수준**; PDF 다운로드 실패로 shadow execution 세부 semantics는 이번 카드에서 검증하지 않았다.
- **표현:** 실제 event logs와 app/device/relation/location semantics에서 hypothetical correlations를 만들고 로그로 확인한다. 설치된 앱에서 추출한 correlations로 보정해 정상 행동 모델을 만든다.
- **검증 관계:** Shadow Execution이 예측한 정상 device states와 실제 runtime states의 불일치를 anomaly로 보고한다. 따라서 실행 가능한 정상 행동 모델과 actual-vs-expected 비교를 이미 사용한다.
- **차이/위험:** VETS가 “예상 행동과 실제 행동을 비교한다”만 주장하면 겹친다. 확인된 구분은 로그·설치 앱에 기반한 정상성 모델의 runtime anomaly detection과, 요청별 reference에 대한 생성 구현의 모든 허용 이력 검증이다. HAWatcher가 어떤 정확도의 시간 또는 값 추적을 제공하지 않는다는 주장은 초록만으로 하지 않는다. 물리 장치의 실제 관측 anomaly detection은 현재 VETS certificate의 보장 범위 밖이다.

## AgentSpec — ICSE 2026 / arXiv 2025

- **원문/접근:** [arXiv 2503.18666v3](https://arxiv.org/abs/2503.18666v3), [저자 ICSE PDF](https://cposkitt.github.io/files/publications/agentspec_llm_enforcement_icse26.pdf), §2–4의 problem, DSL, semantics, implementation 확인. ID/title 일치 및 ICSE 2026 acceptance는 arXiv metadata에서 확인했다.
- **표현:** trigger, predicates, enforcement sequence로 구성된 user-customizable DSL. LLM이 rule을 생성해 사용자 review/approval을 받을 수 있다. §3.3은 current trajectory 및 rule activation/enforcement에 대한 formal semantics를 정의한다.
- **검증 관계:** 실행 전 action, observation 후, task finish 등의 지점에서 규칙을 검사하고 stop, user inspection, predefined action, LLM self-examination으로 개입한다. 사람 확인과 LLM 대응이 포함되므로 모두를 결정적 formal proof라고 묶지 않는다.
- **차이/위험:** “사용자가 확인한 명세로 LLM 실행을 제한한다”는 workflow 자체가 새로운 것은 아니다. VETS의 후보 차이는 runtime behavior를 수정하는 policy enforcement 대신, 확정 reference와 이미 생성된 automation 구현의 모델 내 모든 허용 입력 이력에 대한 timed action equivalence를 검사한다는 것이다. AgentSpec에 formal semantics가 없다는 설명은 틀리며, trajectory를 전혀 못 본다는 단정도 피한다.

## VIGIL — arXiv June 2026, 신규 발견

- **원문/접근:** [arXiv 2606.26524v1](https://arxiv.org/abs/2606.26524v1), [HTML 본문](https://arxiv.org/html/2606.26524v1), §III-B–D, IV-B, V-A–C 확인. 현재 확인한 서지는 preprint이다.
- **표현:** NL skill specifications에서 정책을 만들고 실제 tool calls를 action, named arguments, status, output의 typed finite trace로 추상화한다. 정책 언어는 precedence, response, bounded response, until, absence와 **cross-call value binding**을 제공한다. 여기서 bounded response는 wall-clock deadline이 아니라 다음 ℓ개 event 이내이다.
- **검증 관계:** `τ ⊨ P`를 finite observed trace/prefix에 대한 SMT 질의로 판단하고 위반 invocation/witness를 제시한다. Pending call을 차단하며 미래 obligation은 run 종료 시 판단한다. 전체 입력 이력에 대한 프로그램 검증 계약은 아니다.
- **차이/위험:** “NL→행동 명세→독립 검증”, “시간 순서/값 흐름 관계”만으로는 차별성이 부족하다. VETS는 정해진 환경의 모든 허용 이력에서 특정 실행 reference와 구현의 timed ACTION을 비교한다. 반면 VIGIL의 계약은 관측된 실행의 policy satisfaction이다. 세부 timer 표현의 차이를 모든 temporal semantics 부재로 과장하면 안 된다.

## 이 strand에서 바로 수정할 비교 표현

- 폐기: “기존 IoT 검증은 고정된 safety 금지 조건만 검사한다.” TAPInspector는 liveness/positive response, TAPFixer·IoTSan은 사용자 정의 properties, Soteria는 functional/app-specific properties, iRuler는 additional LTL을 포함한다.
- 폐기: “기존 IR은 time/arguments/value flow가 없다.” 개별 모델별 기능이 다르고 VIGIL은 temporal dependency와 value binding을 명시적으로 제공한다.
- 폐기: “기존은 실제 코드를 검증하지 않는다.” Soteria/IoTSan/TAPInspector는 실제 코드에서 모델을 추출한다.
- 유지 가능한 좁은 비교: “이 문헌들의 주된 검증 계약은 모델 또는 관측 실행의 property satisfaction / violation repair이다. VETS는 확정한 executable reference에 대해, 지원하는 고정 모델의 모든 허용 입력 이력에서 생성 구현의 관측 action trace가 보존되는지를 묻는다.” 단, 이것만으로 새로운 formal technique이 입증되지는 않으며 translation validation/reactive synthesis strand와 추가 비교해야 한다.
- 기능 유무의 부정은 본문 명시적 제한 또는 구현 이식 실험 없이는 `미확인`으로 남긴다. A/B 오류도 알맞은 property를 쓰면 기존 모델 checker로 발견할 수 있으므로 “기존 도구가 못 찾는다”는 실험 없는 단정은 금지한다.
