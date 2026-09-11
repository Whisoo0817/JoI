# Authoring / feedback strand — factual paper cards

검토일: 2026-09-09. 논문의 **Introduction motivation을 Related Work와 대조하는 자료**. 범위: AwareAuto, CASPER journal/workshop, TAP-Debug, Trace2TAP, SENSATION. 논문별 사실과 VETS에 대한 비교 해석을 분리했다. 전 분야 novelty 결론은 이 strand만으로 내리지 않는다.

접근: 기존 OVLA catalog는 후보 발견에만 사용하고 원문을 재확인했다. opencite skill 지침을 읽었으며, 부모 작업에서 보고된 API rate limit 때문에 primary-source web/PDF로 대체했다. PDF 원본·텍스트는 `/tmp/authoring_*.pdf[.txt]`에만 두었다. CASPER journal은 출판사 직접 요청 403, 검색 도구가 제공한 출판사 본문 캐시에서 §1, §5.1–5.4, §7.4를 읽었다. 다른 다섯 자료는 PDF 전문 확보 후 관련 방법·결과·한계 부분을 읽었다. 전문을 줄마다 읽었다는 뜻은 아니다.

표기: **확인**은 논문에 명시된 내용, **미확인**은 이번 원문 검토로 확정할 수 없는 내용이다. 미확인은 미지원과 다르다. 논문의 플랫폼이 Home Assistant라는 이유만으로 모든 HA 문법을 해당 논문의 IR가 지원한다고 보지도 않는다.

## AP-01 — AwareAuto

- **서지:** Yingtian Shi, Xiaoyi Liu, Chun Yu, Tianao Yang, Cheng Gao, Chen Liang, Yuanchun Shi. *Bridging the gap between natural user expression with complex automation programming in smart homes*. arXiv:2408.12687 (2024), 검토판 v1. PDF의 임시 conference header를 출판 venue로 인용하지 않는다.
- **원문:** [HTML](https://arxiv.org/html/2408.12687v1), [PDF](https://arxiv.org/pdf/2408.12687).
- **문제·입력:** 모호하거나 불완전한 multimodal 표현을 상황에 맞는 실행 가능한 자동화로 변환. 자연어 규칙을 사용자에게 보여주고 수정하도록 함.
- **IR 확인:** §4.2–4.3, pp10–13. TA-pair; trigger `target-interface-condition-mode`; event/state 구분; `state(10mins)` 지속시간; action `target-interface-parameter`; timer를 action sequence에 삽입; trigger 집합에 action 그룹을 연결해 branch 표현. §3.2에는 퇴실 후 10분이라는 A와 가까운 예제가 있음.
- **검사 확인:** §4.3–4.4는 grounding의 device/interface/parameter feasibility와 오류 피드백. §5.1–5.3, pp15–17는 intent-consistency·feasibility 평가; grounding 단계 평가 전에 NL 규칙을 수동 보정함. 설명된 pipeline에 lowered code와 고정 spec의 전 입력 timed-trace equivalence 절차는 나타나지 않음.
- **미확인:** interruption 시 timer 취소·재시작, 동시 사건 우선순위, 저장값 lifetime의 형식 의미. `state(10mins)`만으로 A 미지원이라고 주장할 수 없음. dynamic parameter 지원을 B의 snapshot/read 의미와 동일시하지 말 것.
- **VETS 비교 해석:** NL→구조화된 temporal rule→사용자 수정→실행형으로 변환은 이미 겹침. 남겨둘 비교 질문은 **그 규칙을 executable reference로 고정하고 lowering 결과의 행동 보존을 어떤 범위에서 검사하는가**.

## AP-02 — CASPER, journal

- **서지:** Simone Gallo, Sara Maenza, Andrea Mattioli, Fabio Paternò. *CASPER: an interactive IoT automation management environment combining visual and conversational support*. **Behaviour & Information Technology**, online 2026-05-28. [DOI / 출판사 원문](https://doi.org/10.1080/0144929X.2026.2679590). Workshop와 저자 목록·제목이 다름.
- **접근:** 출판사 본문 검색 캐시. [출판사 PDF](https://www.tandfonline.com/doi/pdf/10.1080/0144929X.2026.2679590)는 직접 다운로드 403; 검색 도구에서 pp13,15 일부 확인.
- **명세·사용자 확인:** §5.1, p13. Conversational Manager가 모호한 event/condition/action과 시간·threshold를 질문하고 Event–Condition(s)–Action(s) 형식의 structured NL로 정리. 사용자가 만족하면 별도 Automation Generator LLM에 전달. 생성·검사·수정 후 승인·HA 배포.
- **검사 확인:** §5.1 entity-ID를 HA 환경과 대조. §5.2–5.3은 action incompatibility, event 관계, condition overlap에 따른 충돌 및 direct/indirect activation chain 분석. §5.4는 action→환경변수 knowledge base, 현재 환경의 fuzzy goal 평가, missing revert 점검. 해결안 제시는 LLM 활용. **검증이 없다는 서술은 틀림.**
- **미확인:** 독립 reference operational semantics, spec–code timed-trace 등가 판정, 전 입력·무한시간 soundness theorem, timer cancellation·snapshot의 IR 문법. 명시된 검사는 해당 보장을 제시하지 않음. §7.4는 지식모델이 수작업으로 구성된 부분집합이라고 한정함.
- **VETS 비교 해석:** **명세화·clarification·승인·생성 후 검사**까지 겹친다. 차이는 검사 유무가 아니라 **검사 기준과 관측 대상**: 관계/goal 분석과 confirmed reference의 정확한 timed ACTION 보존은 서로 다른 판단 문제. CASPER의 다중 자동화·환경 goal 분석은 현 VETS 단일 시나리오 계약보다 넓은 측면도 있음.

## AP-03 — CASPER, AutomationXP26 workshop (보조 자료)

- **서지:** Simone Gallo, Andrea Mattioli, Fabio Paternò. *An Interactive IoT Automation Management Environment Supporting Transparency and Human Control*. AutomationXP26 workshop at CHI 2026, paper의 표기일 2026-04-14, 7 pages. [저자/워크숍 PDF](https://matthiasbaldauf.com/automationxp26/papers/AutomationXP26_paper_1464.pdf).
- **확인:** §2, pp2–4. Main Agent가 Automation Generator, Issue Explainer, Solutions Generator를 조정. NL을 structured TAP로 변환한 뒤 conflict, direct/indirect chain, goal inconsistency를 분석하고 설명·해결안을 visual/conversational UI에 제시. §3.2, pp5–6에서 변경은 사용자 선택으로 적용한다고 명시.
- **연구 초점:** §3은 transparency와 human control에 관한 두 사용자 연구를 논의. 예측되는 행동·대안 이해를 돕는다는 motivation이 VETS의 사용자 중심 표현과 겹침.
- **미확인/주의:** journal의 세부 알고리즘을 이 짧은 workshop에 소급 인용하지 않는다. 여기서도 code–spec equivalence theorem은 제시되지 않음. 이 문서를 journal과 별도 독립 시스템처럼 세어도 안 됨.
- **VETS 비교 해석:** 승인 단계나 시각적 설명만으로 사용자 통제의 독창성을 주장하기 어렵다. 현 VETS는 사용자 이해도 향상을 입증한 연구로 취급하지 않는다.

## AP-04 — TAP-Debug / Helping Users Debug Trigger-Action Programs

- **서지:** Lefan Zhang, Cyrus Zhou, Michael L. Littman, Blase Ur, Shan Lu. *Helping Users Debug Trigger-Action Programs*. **IMWUT 6(4), Article 196**, December **2022**, 32 pages; UbiComp 2023 발표와 연도 구분. [DOI](https://doi.org/10.1145/3569506), [저자 PDF](https://www.blaseur.com/papers/imwut22-debuggingtap.pdf).
- **명세 확인:** §2–3, pp4–8. `IF event WHILE conditions THEN action`; 사용자 피드백으로 과거의 잘못 발생한 action과 발생했어야 할 action/time을 지정. explicit·implicit 두 경로; 수정 후보를 ranking하고 counterfactual history로 보여줌. Fig6 p5에는 **motion 없음이 정확히 5분 지속**하는 trigger 예가 있음.
- **검사/보장 확인:** §4.1–4.5, pp9–11. symbolic TAP patch를 기록된 trace에서 재실행하고 Z3로 목표 constraint를 만족하는 수정안을 합성. 목표는 보고된 오류 중 threshold 비율 수정(연구 설정 0.3). under-automation은 기준시각 −10분/+5분 범위. 부수효과는 hard constraint가 아닌 ranking factor. 형식 기법과 제한된 보장은 분명히 존재함.
- **한계/미확인:** 목표는 모든 입력 이력에서 독립 spec과 구현의 exact ACTION 일치가 아님. B의 저장값 lifetime 문법은 미확인. 사용자 선택은 실패할 수 있음(§6.3.2).
- **VETS 비교 해석:** user intent·trace·자동 검사/수정·후보 설명을 기존에 안 했다고 할 수 없음. 차이는 **과거 예제에 대한 피드백 constraint**와 **고정 실행명세에 대한 모델 범위 전체의 구현 등가성**. “human-authored vs LLM-generated”만으로 차별화하지 않는다.

## AP-05 — Trace2TAP

- **서지:** Lefan Zhang, Weijia He, Olivia Morkved, Valerie Zhao, Michael L. Littman, Shan Lu, Blase Ur. *Trace2TAP: Synthesizing Trigger-Action Programs from Traces of Behavior*. **IMWUT 4(3), Article 104** (2020), 26 pages. [DOI](https://doi.org/10.1145/3411838), [저자 PDF](https://hewj.info/papers/trace2tap.pdf), [artifact](https://github.com/zlfben/trace2tap).
- **문제·명세:** 사용자 수동 행동·sensor trace에서 여러 plausible TAP를 합성하고 선택하게 함. §4–5, pp7–13에 event/condition 구분과 symbolic `executeTrace`가 있음. §5.2.4 p13은 조건이 true로 바뀐 후 계속 true인 지속시간 trigger를 명시. **A의 연속 N분은 기존 문법에 존재**.
- **검사/보장:** §5.2.2–5.2.3 pp12–13. 기록 trace의 episode에서 action 효과가 나타나는 규칙을 SAT로 합성; 시간허용구간 기본 −10분/+5분, action-instance coverage threshold 0.3. universe는 선택된 template/변수/관측 trace. 정적 “문법 검사뿐”이 아님.
- **후보 선택:** §6 pp14–16. 관측 action을 자동화하는지 bitvector로 표시하고 Hamming distance/K-modes clustering, feature ranking, prospective trace visualization. clustering은 전 입력 semantic equivalence 판정이 아님.
- **미확인:** B 같은 action 간 저장값 재사용의 일반 문법, 임의 lowered implementation의 refinement proof. §5.2.4의 time 값은 symbolic으로 탐색하지 않고 미리 정함.
- **VETS 비교 해석:** 후보 발견·행동별 묶기·실행 예상·user choice가 이미 있음. VETS는 이 기능을 현재 기여로 계상하지 않는다.

## AP-06 — SENSATION

- **서지:** Giuseppe Desolda, Francesco Greco, Francisco Guarnieri, Nicole Mariz, Massimo Zancanaro. *SENSATION: An Authoring Tool to Support Event–State Paradigm in End-User Development*. **INTERACT 2021**, LNCS 12933. [DOI](https://doi.org/10.1007/978-3-030-85616-8_22), [저자 preprint](https://arxiv.org/abs/2109.02382), [PDF](https://arxiv.org/pdf/2109.02382).
- **문제·명세 확인:** §1, §3, pp1–4. 사용자가 event와 state를 혼동하는 문제를 해결하기 위한 guided authoring. `DO action WHEN event WHILE state specifications`; WHEN은 정확히 하나의 event, WHILE은 optional state conjunction, DO는 action 하나 **또는 sequence**. UI가 선택 가능한 action/event/state를 필터링하며 세 질문으로 규칙 구성을 유도.
- **검사 확인:** §4, pp4–8은 사용자 작성 정확도·완료시간·사용성 평가, 규칙 성공은 수작업 평가. code–spec universal verification 알고리즘은 기술되지 않음.
- **미확인:** sustain-for-duration, delay/timer, arbitrary branch, 저장값 lifetime의 일반 문법 및 완전 operational semantics. action sequence는 명시적으로 존재하므로 “TAP authoring은 sequencing조차 없다”는 서술 금지. WHEN/WHILE을 구분한다는 이유만으로 연속시간 sustain 지원이라고 추론할 수도 없음.
- **VETS 비교 해석:** 행동을 구체적인 event/state 형식으로 만들고 사용자에게 선택을 안내하는 것은 기존 문제와 기여. VETS의 차이는 event/state 표기 자체보다 동일 실행명세가 생성 지침과 검증 reference로 연결되는 역할에서 검토해야 함. 이 논문의 사용자 연구 결과를 VETS interface의 이해 가능성 증거로 대체하지 않는다.

## 이 strand에서 원문 대조로 발견한 catalog 수정 후보

아래는 원본을 수정한 것이 아니라 부모 synthesis에 전달할 검토 결과다.

- `etc/related_works/related_works.md`의 “T6 is empty across the field”는 이 bounded strand로 지지할 수 없는 전 분야 부재 주장. 이미 user feedback와 formal execution/synthesis를 함께 쓰는 AP-04/05가 있다.
- `etc/related_works/flow_userstudy_analysis.md`의 “Absent across ALL TAP papers …” 같은 보편적 문법 부재 주장 대신 논문·지원 문법·의미 단위로 한정해야 한다. AP-05에 명시적 sustain trigger, AP-01에 state(duration)/timer/branch, AP-06에 action sequence가 있다.
- AP-01을 “IR·확인만 있고 의미가 전혀 없다”라고 낮추면 안 된다. 실행 규칙 형식과 intended semantics가 있고, 별도 formal preservation check의 유무가 비교 지점이다.
- AP-02 때문에 “NL authoring 계열의 검사는 schema/grounding에서 끝난다”는 범주 전체 서술을 재검토해야 한다. 충돌·chain·goal analysis를 정당하게 인정한 뒤 exact trace conformance와 구별한다.
- AP-04를 “implicit feedback”만으로 설명하면 Explicit-Feedback 핵심을 누락한다. 후보 합성은 명시적인 SAT goal에 대한 보장을 주지만, 그 goal이 제한적이다.
- A/B는 **검증 대상 의미차를 설명하는 예제**로 계속 유효하다. 이 자료만으로 A/B가 기존 IR에 표현 불가능하다는 주장은 성립하지 않는다. 특히 A는 AP-05의 duration trigger와 직접 겹친다.

후속 원문 확인 질문: AwareAuto interruption/retrigger 및 data-value semantics는 공개 artifact에서 추가 확인할 수 있는가; CASPER structured NL/HA abstraction의 완전 문법은 제공되는가; 각각을 VETS IR으로 encoding할 때 어느 의미를 추가로 고정해야 하는가. 이 질문들이 해결되기 전에는 표현력 우위 표에 X를 채우지 않는다.
