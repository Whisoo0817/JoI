# 생성·검사·시뮬레이션 연구 원문 대조

검토일: 2026-09-09. 현재 VETS 계약과 비교하며, 구 OVLA의 bounded/on-device 주장을 그대로 가져오지 않는다. 아래의 ‘차이’는 확인한 연구 절차와의 비교다. 기능의 구현 불가능성이나 문헌 전체의 부재를 뜻하지 않는다. 정량 성능은 재분석하지 않았다.

## ChatIoT (IMWUT 2024)

- 출처: [논문 DOI](https://doi.org/10.1145/3678585), 로컬 `etc/related_works/ChatIoT.pdf` 원문 §3.1.2–3.2, Fig. 2–4, pp. 7–10 확인.
- 명세/표현: NL→ChatIoT-TAP(`trigger`, `condition`, `action`)→플랫폼 형식. 즉 **중간 표현도 이미 있다**. Fig. 3의 문법은 property 비교, Boolean 조건 조합, action assignment를 명시한다.
- 검사: Preprocessor가 부족한 정보를 사용자에게 질의한다. 별도 LLM Evaluator는 형식뿐 아니라 요청/context 대비 기기·service·operator·value의 적절성을 검사·수정한다.
- 차이: 명시된 절차는 LLM의 TAP 판단이다. 사용자 확정 실행 기준과 최종 플랫폼 코드의 모든 허용 이력에 대한 timed ACTION 동등성을 인증하는 절차는 제시하지 않는다. HA backend의 표현력을 ChatIoT-TAP 문법과 혼동하지 않는다.
- 수정할 구문: ‘요청 충족을 검사하지 않는다’, ‘format checking에서 끝난다’, ‘IR이 없다’는 모두 부정확하다.

## AutoIoT, Cheng et al. (arXiv 2411.10665v1, 2024)

- 출처: [원문](https://arxiv.org/html/2411.10665v1), §IV-A–D.
- 명세/표현: device tuple, trigger/action JSON 규칙, 환경 요인과 상태 전이를 모델링한다. LLM이 규칙과 formal verification용 코드를 생성하며 adapter가 Maude 코드 작성을 돕는다.
- 검사: state/environment conflict와 두 cascading conflict 유형을 형식화하고 Maude로 검사한다. 결과로 규칙을 수정한다.
- 후속 산출물 확인(§V-C): Mi Home 앱에 수동 등록할 NL 규칙과 `python-miio` 기반 Python 스크립트의 두 출력을 제시하며, 후자는 Raspberry Pi에서 실행한다. 따라서 검증용 Maude 모델만 생성한다고 분류하지 않는다. [IR/실행 비교](automation_ir_execution_matrix.md).
- 차이: LLM 생성 IoT 자동화에 formal verification을 붙이는 선행 사례다. 확인한 검증 질문은 conflict 정의에 대한 분석이며, 별도 요청별 실행 명세와 배포 코드의 timed trace 일치 판정이 아니다. formal model 생성 자체의 신뢰 경계도 비교해야 한다.
- 이름 주의: 다음 AutoIOT(MobiCom)는 **다른 논문**이다.

## AutoIOT, Shen et al. (MobiCom 2025)

- 출처: [원문](https://arxiv.org/html/2503.05346v1), §3–4, 특히 §4.3 Code Improvement. 로컬 MobiCom PDF도 확보되어 있다.
- 명세/표현: AIoT 요구의 지식 검색·분해와 코드 조각 합성. 예제 입출력과 알고리즘별 성능 목표를 사용한다.
- 검사: 생성 프로그램을 실행하고 compiler/interpreter feedback으로 debugging과 optimization을 반복한다. 사용자 추가 지시도 받을 수 있다.
- 차이: 실제 실행과 기능 성능 개선을 하므로 ‘syntax만 확인’으로 줄이지 않는다. 실행 피드백 기반 생성과, 확정 reactive spec에 대한 모든 허용 입력 이력의 동등성 인증은 다른 계약이다.

## GPIoT (SenSys 2025)

- 출처: [arXiv](https://arxiv.org/abs/2503.00686), 로컬 `sensys_gpiot_ko_overleaf/GPIoT.txt` 원문 §3, §5–6의 모델 분해·IoTBench·pass@k 설명 확인.
- 명세/표현: task decomposition, requirement transformation, code generation을 특화한 small language models. 주 대상은 IoT signal-processing/ML 코드다.
- 검사: benchmark test cases의 실행 통과, 코드 품질 분석과 사람 평가를 사용한다.
- 차이: 요구→spec→code의 분해와 실행 검사는 기존 기여다. VETS에서는 지속적으로 변하는 입력 이력에서 요청별 기대 ACTION을 계산하고 생성 구현과 대조하는 계약이 필요하다. GPIoT의 spec이 존재하지 않는다고 쓰지 않는다. 현재 VETS의 핵심 비교를 모델 크기나 on-device 여부에 두지 않는다.

## TaskSense (SenSys 2025)

- 출처: [저자 원문 PDF](https://yanzhenyu.com/assets/pdf/TaskSense-SenSys25.pdf), [DOI](https://doi.org/10.1145/3715014.3722070), §4 Sensor Language, §5.2–5.4 확인.
- 명세/표현: 도구를 vocabulary, data/control dependency를 grammar로 정의하고 NL sensor query를 실행 plan DAG로 번역한다.
- 검사: solvability는 LLM checker, grammar correctness는 DAG subgraph matching이다. 실행 중 data 품질과 결과를 보고 대안 경로로 바꾼다.
- 차이: 실행 가능성과 도구 의존성의 검사다. 결과 table→NL 단계는 질문의 답을 만드는 절차이며 plan을 역번역해 의미를 인증하는 절차가 아니다. DAG의 data dependency는 실제 특징이므로 ‘값 관계가 없다’고 쓰지 않는다. sensor QA의 결과와 지속 자동화의 ACTION history를 비교 단위로 구분한다.

## LACE (arXiv 2505.23835v1, 2025)

- 출처: [원문](https://arxiv.org/html/2505.23835v1), §IV-A Step-II, §IV-B.
- 명세/표현: subject/resource/action/effect/conditions의 정책 tuple. 시간대와 동적 context 조건도 다룬다.
- 검사: 정책을 정형 문장으로 재구성하고 NLI 모델로 원 요청과 semantic consistency를 판단한다. **별도로 SMT conflict 검사와 OPA 정책 집행/결정 검증도 있다.**
- 차이: 요청과의 semantic consistency 판정은 NLI이며, formal 부분은 정책 충돌/정책 준수다. concrete reactive implementation과 실행 명세의 timed ACTION 관계 인증과 구별한다. 정책을 단순 ‘시간 없는 static rule’, 시스템 전체를 ‘LLM judge만’으로 요약하지 않는다.

## IoTGPT (arXiv 2601.04680v1, 2026)

- 출처: [원문](https://arxiv.org/html/2601.04680v1), §IV-A–B, §V, §VII.
- 명세/표현: decompose/derive/refine, task/subtask/context DAG memory, parameter personalization.
- 검사: 실제 배포 전 가상 환경에서 명령을 실행해 API 위반·runtime failure를 검사하고 수정한다. 이후 필요하면 설명과 사용자 feedback을 받는다. 논문 평가에서는 ground-truth command와 extra/missing command도 측정한다.
- 차이: 운영 중 자동 correction과 논문 평가 oracle을 구분해야 한다. 자동 검사 기준이 요청별 실행 명세의 전칭적 시간 행동 보존인 것은 아니다. ‘행동 평가 자체가 없다’는 문구는 사용하지 않는다.

## Giudici et al., Generating Home Assistant Automations (arXiv 2505.02802, 2025)

- 출처: [arXiv](https://arxiv.org/abs/2505.02802), 로컬 `Generating_HomeAssitant_Automations.pdf` §3.2–4 확인.
- 명세/표현: NL chatbot에서 Home Assistant automation JSON 생성.
- 검사: 자동 JSON validity metric은 HA API에 제출해 framework 응답을 확인한다. 논문은 이외에 요구·기기 관련 정확도, relevance 등 사람 분석도 포함한다.
- 차이: 자동 validity 통과를 보편적 timed behavior correctness로 읽을 수 없다. 전체 평가를 JSON parse 하나로 줄이는 것도 부정확하다.

## DS-IA (arXiv 2603.16207v1, 2026)

- 출처: [원문](https://arxiv.org/html/2603.16207v1), §III-A–D, Eq. 3–5.
- 명세/표현: room/device/function/parameter action tuple, intent routing, mixed-intent filtering.
- 검사: deterministic cascade가 room 존재, 해당 room의 device 존재, device capability 지원을 순서대로 확인한다.
- 차이: grounding된 command 실행 가능성에 관한 기준이다. 시간 조건을 위반하지 않고 명세의 action을 빠짐없이 내는지의 전 history 관계와 다르다. VETS에서도 device binding은 필요하므로 상호 보완적이다.

## SimuHome (arXiv 2509.24282v3; 기존 corpus의 ICLR 2026 항목)

- 출처: [v3 원문](https://arxiv.org/html/2509.24282v3), §3–4.3. 이 검토는 v3를 기준으로 하며 구 버전의 agent 수/측정값을 섞지 않는다.
- 명세/표현: 시간 가속과 환경 dynamics를 가진 simulator. episode는 initial state, structured goal, prerequisite tool calls, query로 구성한다.
- 검사: device/environment goal과 prerequisite 호출 이력을 검사한다. scheduling task는 **목표 시각**으로 진행시킨 뒤 상태를 검사한다. ‘최종 상태만 확인’은 불충분한 요약이다.
- 차이: benchmark episode의 task completion을 평가한다. 요청별 생성 프로그램과 확정 spec의 모든 허용 입력 이력에 대한 동등성 인증과는 다른 평가 단위다. 환경 물리 모델은 현 VETS보다 넓은 부분이다.

## 일반 코드 생성의 비교: CodeT, Self-Debug, Spider

- [CodeT](https://arxiv.org/abs/2207.10397), [ICLR 2023 원문](https://openreview.net/pdf?id=ktrw68Cmu9c): **LLM이 test도 생성**하고 실행 일치로 code 후보를 고른다. ‘이 계열은 외부에서 주어진 oracle이 항상 있다’는 OVLA 문구의 반례다. abstract/원문 도입부와 저자 [repository](https://github.com/microsoft/CodeT) 확인.
- [Self-Debug](https://arxiv.org/abs/2304.05128), ICLR 2024: 실행 결과와 code explanation으로 self-debugging하며, unit test가 없는 Spider 설정도 다룬다. abstract 확인. 따라서 ‘unit test가 주어지므로 검증 가능’ 하나로 정리하지 않는다.
- [Spider](https://aclanthology.org/D18-1425/), EMNLP 2018: text-to-SQL benchmark/reference query의 배경. benchmark gold와 실제 사용자 요청별 운영 oracle을 구분한다. 공식 abstract/metadata 확인.
- 공통 비교: 생성 test/실행 피드백은 유용하지만, 선택한 입력에서의 성공을 선언 모델의 모든 reactive history에 대한 certificate로 바꾸지는 않는다. 이들은 주 closest-work보다 배경 인용에 적절하다.

## 배경 유지: Sasha와 SAGE

- [Sasha](https://arxiv.org/abs/2305.09802), IMWUT 2024: 목표 지향 스마트홈 reasoning의 기존 인용. DOI 직접 접근은 403으로 실패했지만 arXiv v3 primary abstract에서 underspecified command로부터 action plans와 automation routines를 만드는 목표 및 사용자 평가를 확인했다. 상세 기능 부재 주장은 재사용하지 않는다.
- [SAGE](https://arxiv.org/abs/2311.00772), v2 2024: primary abstract가 dynamic prompt tree, user interaction, API reading, **persistent state monitoring**을 명시한다. ‘단발 동작만’이라는 분류는 틀리다. 이번에는 abstract 수준의 배경 비교에 한정한다.

## 접근 기록

OpenCite 검색은 Semantic Scholar 등 일부 provider에서 rate limit/error가 났지만 arXiv/OpenAlex 결과를 반환했다. 원문 접근은 저자 PDF, arXiv HTML, 기존 로컬 원문으로 보완했다. 로컬 번역 LaTeX만으로 핵심 기능을 판정하지 않았다. 임시 원문 변환은 `/tmp/vets-related-20260909`에 두며, 이 파일의 영구 근거는 URL·원문 절 번호·기존 로컬 PDF 경로다. 원문 공개판의 권리 확인 없이 PDF를 새 연구 기록에 복제하지 않았다.
