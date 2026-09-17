# Related Work 문단 흐름 — SenSys ↔ PerCom

왼쪽은 [SenSys 원문](SenSys_version.md)의 R1–R8 순서다. 오른쪽은 [PerCom 초안](PerCom_version.md)의 P0–P4 대응과 수정 이유다. P 번호는 작업용이며 본문에는 넣지 않았다.

기준: [Intro](../01_Intro/PerCom_version.md), [HANDOFF](HANDOFF.md), [Writing Style](../WRITING_STYLE.md), [Guardrails](../WRITING_GUARDRAILS.md).

| SenSys — 원문 순서와 역할 | PerCom — 초안 반영 및 이유 |
| --- | --- |
| **R1. 도입** — 기존에는 reference가 있었지만 LLM 생성으로 사라졌다는 배경. 검증 reference를 중심으로 문헌 분류. | **P0의 분류 문장만 유지.** reference 확보·확인이라는 authoring 기여로 기대를 유도하는 배경은 삭제. 검증 대상과 기준을 비교하며 Intro의 문제 설명을 반복하지 않음. |
| **R2. 기존 자동화 검증** — AutoTap, TAPInspector, TAPFixer, iRuler/Soteria, HAWatcher. 고정 property를 검사하므로 별도 intent reference가 필요 없다는 결론. | **P1에 연구 설명 유지하고 IoTSan 추가.** IoTSan의 앱 코드→Promela→Spin 경로를 소개. HAWatcher도 runtime 사례로 같은 문단에 둠. 첫 문장은 TAP보다 넓은 property 기반 자동화 검증으로 수정. 마지막은 선택한 속성·충돌 정의·불변식이라는 검증 기준만 정리하고 VETS 비교는 삭제. 시간·활성·사용자 속성 및 관계적 검증을 기존 기법이 다루지 못한다는 주장은 하지 않음. |
| **R3. 실행 oracle이 있는 코드 생성** — GPIoT, SQL, CodeT, Self-Debug를 이미 reference가 주어진 계열로 묶음. | **GPIoT를 P2에 압축 반영.** 실행 테스트 사례로 소개하고 다음의 모델 판정 사례와 구분. SQL은 Intro와 중복, CodeT·Self-Debug는 지면상 생략. 모든 계열에 테스트가 미리 주어진다는 일반화 삭제. |
| **R4. Reactive automation의 reference와 primitive/idiom 차이** — TAP는 primitive를 실행하고 JoI 코드는 상태·조건·tick으로 구현. | **P4에 핵심 설명 재사용.** 플랫폼이 temporal primitive를 구현하는 경우와 현재 JoI에서 LLM이 idiom을 만드는 경우를 구분. 표현력 우열, 오류 가시성, DSL 산출물 자체를 차별점으로 삼지 않음. |
| **R5. 생성 결과의 기존 검사** — AutoIoT, DS-IA, TaskSense, AgentSpec을 소개하고 사용자 행동은 reference가 아니라고 결론. | **AutoIoT를 P1에 유지.** LLM이 만든 규칙의 conflict 검사도 속성·충돌 검증 묶음에 포함. DS-IA·TaskSense·AgentSpec 개별 설명은 생략. 사용자 행동은 결코 reference가 아니라는 일반화 삭제. |
| **R6. 생성과 사용자 확인** — ChatIoT, Giudici et al., IoTGPT, AwareAuto. 기존 검사가 format/API 등에서 끝난다고 주장하고 렌더링을 비교. | **ChatIoT는 P2, AwareAuto는 P3에 유지.** 연구 설명 문장은 보존. Giudici et al.·IoTGPT는 생략. AwareAuto의 panel은 기능 설명으로 유지하되 deterministic rendering 비교와 goes furthest 삭제. |
| **R7. 의도 관련 검사** — LACE·SimuHome를 소개하고 model-judged intent 검사를 비판. | **LACE 설명을 P2에 복원.** NLI 약어를 풀고 별도 SMT 충돌 검사도 명시. Moon et al.과 연결하되 그 연구가 LACE·ChatIoT를 직접 평가한 것으로 쓰지 않음. SimuHome 사례와 자기 인증·100% correctness 비판은 생략. |
| **R8. OVLA의 위치** — LACE와 AwareAuto를 가장 가까운 연구로 제시하고 user confirmation, rendering, on-device, 최초성을 강조. | **P4 마지막에서 VETS의 위치 설명.** P1은 기존 연구의 검증 기준, P3는 명세 확정의 전제, P4는 명세–구현 보존 검증을 설명. authoring·렌더링·on-device·최초성 차별화 삭제. |
| **추가: 자연어 요구의 명세화** | **P3에 nl2spec·ARTEMIS.** 사용자 의도의 명세화·확인을 지원하는 인접 연구로 인정. VETS의 명세 확정 가정을 분명히 하고 확인 용이성이나 NL→IR 정확도 기여를 주장하지 않음. |
| **추가: 구현 행동 보존** | **P4는 AutoTap·TAPInspector·IoTSan의 검증 질문을 받아 VETS와 비교.** 속성 만족과 확정 명세의 timed action trace 보존을 구별하고 imperative idiom 설명으로 연결. Murphy et al.과 translation validation은 이번 초안에서 제외하고 deterministic compiler는 미평가 대안으로 인정. |
| **추가: LLM code judge 선행** | **P2에 Moon et al.** 모델 기반 요청 충족 판정만으로 실행 행동 보존이 확립되지는 않는다는 점에서 시작해, 표면 변화에 따른 평가 편향과 §3의 reactive-temporal 코드에 대한 LLM 판정 일관성 조사로 연결. 앞서 소개한 시스템들의 오류를 입증했다는 뜻으로 쓰지 않으며 결과·수치는 반복하지 않음. |

## 현재 PerCom 순서

P0 분류 기준 → P1 속성·충돌 검증 → P2 생성 코드·정책 평가 → P3 의도 명세화·확인 → P4 구현 행동 보존 및 VETS의 위치.

네 묶음은 비교할 연구 질문에 따른 배치다. 한 시스템이 여러 검사·확인 방식을 함께 지원할 수 있으며, 분류를 해당 시스템 전체 기능의 한계로 읽지 않는다. 현재 초안에서 제외한 연구도 기능 부재나 열등함의 근거가 아니다.
