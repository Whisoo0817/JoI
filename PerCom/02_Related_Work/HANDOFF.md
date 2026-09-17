# Related Work handoff

상태: **네 비교 축에 따른 재작성 완료 (2026-09-17); 문장별 검토 및 최종 인용 선정 전**.

- 네 문헌 묶음을 유지하고 각 문단은 “무엇을 검증하는가”를 중심으로 압축한다.
- `skill_result/02_literature/related_work_review_2026-09-09/`의 primary-source 카드에서 BibTeX key와 정확한 기능을 대조한다.
- nl2spec, TAPInspector, Don’t Judge Code by Its Cover는 반드시 원문 기반으로 인용한다.
- “기존은 시간을 다루지 않는다”, “코드를 분석하지 않는다”, “negative property만 검사한다”는 문장을 넣지 않는다.
- `first`, `only`, `no prior work`는 최종 citation-forward/backward search 없이는 사용하지 않는다.
- PerCom page budget에 따라 사례를 압축하되 모델 기반 평가와 명세–구현 의미 보존 검증의 구분은 유지한다.
- HA는 실험 대상이 아니라 필요할 때 선언형 언어도 충분히 expressive할 수 있음을 정확히 설명하는 Related Work 사례다.
- openHAB을 실제로 구현·평가하지 않으면 broader relevance/Future Work 이상으로 쓰지 않는다.

## 절 배치 (2026-09-17)

- §2에 배치하여 Introduction 다음, Problem and Motivation 앞에서 선행연구와의 위치를 설명한다.
- Introduction S4·S5의 문제 설명을 반복하기보다 각 연구의 검증 대상·기준과 VETS의 차이를 구체화한다.

## 현재 초안과 원문 대응 (2026-09-17)

- `SenSys_version.md`의 기존 요약을 제출 원고 §2의 실제 8문단으로 교체했다. 과거 주장까지 원문 그대로 보존하므로 현재 주장 근거로 사용하지 않는다.
- `PerCom_version.md`는 짧은 도입(P0) + 속성·충돌 검증(P1) + 생성 코드·정책 평가(P2) + 의도 명세화·확인(P3) + 구현 행동 보존(P4)의 5문단이다.
- R1의 reference 확보·authoring 배경은 삭제하고 분류 문장만 남긴다. 네 묶음은 비교 목적에 따른 배치이며 시스템의 상호 배타적인 기능 분류가 아니다.
- [문단 비교표](RELATED_WORK_FLOW_COMPARISON.md)에 SenSys R1–R8의 유지·이동·삭제와 신규 문헌의 역할을 기록했다. 굵게 표시는 대응 SenSys 문장에서 바뀐 단어·구절만 뜻한다. 완전히 새 문장은 전체를 굵게 표시했다.
- 원문 설명은 AutoTap/TAPInspector/TAPFixer, ChatIoT, AutoIoT, AwareAuto, LACE, HAWatcher 중심으로 재사용했다. GPIoT는 모델 크기·on-device 설명을 빼고 실행 시험의 역할만 남겼다. R4의 primitive/idiom 설명은 P4에 재사용했다.
- nl2spec·ARTEMIS의 명세화/해석 확인과 Moon et al.의 code judge 편향을 현재 위치 설명에 사용했다. P1에 IoTSan의 앱 코드→Promela→Spin 분석을 추가했다. P4는 AutoTap·TAPInspector·IoTSan의 속성 기반 합성·분석과 VETS의 명세–구현 행동 보존을 대비한다. Murphy et al.의 reactive synthesis와 translation validation은 이번 문단 흐름에서 제외했다. IoTSan도 imperative 앱을 분석하므로 imperative 지원 자체를 차별점으로 주장하지 않는다.
- CodeT/Self-Debug, DS-IA, TaskSense, Giudici et al., IoTGPT, AgentSpec, SimuHome의 개별 소개는 압축 과정에서 제외했다. 기능이 없다는 판정이 아니다. CASPER·Req2LTL·VIGIL·synchronous compiler validation도 문헌 카드에 남아 있으며, 최종 인용 선정 시 직접 관련성과 지면을 함께 검토한다.
- LACE의 요청–정책 의미 일치 판정은 NLI이며 별도 SMT 충돌 검사도 있다. 시스템 전체를 LLM judge만 사용하는 방식으로 분류하지 않는다. Moon et al.의 code judge 결과를 LACE·ChatIoT의 직접 평가로 확대하지 않는다.
- 명세의 올바른 사용자 확인은 전제다. 기존 확인 UI보다 우수하다는 주장이나 deterministic rendering의 차별화는 하지 않는다.
- 기존 모델검사도 시간·활성·사용자 속성 및 관계적 행동 검증을 다룰 수 있다. P1은 소개한 연구의 검증 질문과 현재 VETS의 reference를 비교한다. `static reference` 대 동적 행동으로 구분하지 않으며, TAP·formal verification·model checking을 같은 수준의 서로 다른 부류로 나누지 않는다.
- DSL이 최종 산출물이라는 사실만으로 차별화하지 않는다. P4는 별도 생성된 imperative JoI 구현이 확정 명세의 timed action trace를 보존하는지 검사하는 역할을 설명한다. primitive를 플랫폼에서 구현하는 경우와 LLM이 idiom으로 구현하는 현재 JoI 설정의 차이를 조건부로 기술한다.
- compiler는 미평가 대안으로 인정하며, 생성 결과 검사 자체의 최초성을 주장하지 않는다.
- P2는 모델 기반 요청 충족 판정만으로 실행 행동 보존이 확립되지는 않는다는 점을 설명한 뒤 Moon et al.과 §3의 LLM 판정 일관성 조사로 연결한다. 두 실험으로 앞서 소개한 시스템들의 오류를 입증했다고 주장하지 않는다. 마지막 문장은 §3의 조사 대상만 소개하며 Motivation의 수치·모델별 결과는 반복하지 않는다.

## 인용 근거와 서지 통합

기존 인용 키는 `docs/refs.bib`를 재사용했다. 새 키 4개는 [references.bib](references.bib)에 추가했다. 최종 LaTeX 조립 때 두 파일을 함께 불러오거나 새 항목을 통합해야 한다. 이 작업에서 기존 SenSys bibliography는 변경하지 않았다.

| 키 | 원문 확인 및 초안에 사용한 범위 |
| --- | --- |
| `lace` (기존 키) | [원문](https://arxiv.org/html/2505.23835v1) §IV-A Step-II, §IV-B 및 [문헌 카드](../../skill_result/02_literature/related_work_review_2026-09-09/generation_prior.md): deterministic templates와 fine-tuned NLI를 통한 요청–정책 의미 일치 판정, 별도 SMT 충돌 검사. |
| `nl2spec` | [arXiv 원문·초록](https://arxiv.org/abs/2303.04864): 자연어 조각과 temporal subformula의 매핑을 사용자가 수정. 이번 BibTeX는 확인한 preprint 서지이며 최종본 통합 시 CAV 출판 서지로 정규화할 수 있다. |
| `artemis` | [저자 공개 ICSE 2026 원문](https://cs.stanford.edu/people/trippel/pubs/mendoza_ICSE26.pdf): 후보 명세를 구별하는 traces를 통한 semantic validation. 사용자 이해도·선택 정확도 향상을 VETS에 전이하지 않음. |
| `murphy2024reactive` | [원문](https://arxiv.org/html/2410.19736v1): LLM code generation과 reactive synthesis의 결합. 합성 controller의 보장을 임의 LLM wrapper나 전체 플랫폼 코드로 확대하지 않음. |
| `moon2026cover` | [ACL Anthology 공식 원문·BibTeX](https://aclanthology.org/2026.findings-eacl.70/): 의미를 보존하는 표면 변화에 따른 code score 편향. §3의 temporal 구현 재작성 및 동일 코드 재판정 조사와 구별. |

기존 시스템 설명은 [원문 대조 카드](../../skill_result/02_literature/related_work_review_2026-09-09/README.md)의 해당 논문별 방법·범위에 맞췄다. 현재 초안은 도구 간 우열이나 분야 전체의 부재를 확정하는 문헌 조사 결과가 아니다.
