# Related Work 통합 목록과 원문 확인 범위

2026-09-09. OVLA 원고의 Related Work에서 실제 사용한 **20개 citation key 전부**를 A표에 보존했다. 원고 다른 절·최근 논의·기존 문헌 catalog의 추가 자료는 B/C표에 연결한다. 기존 논문 전체를 PerCom 본문에 넣자는 뜻은 아니다. 관련성이 낮은 문헌과 원문 미확인 후보를 지우지 않고 구분했다.

원본: [`ovla0606.tex`](../../../docs/ovla0606.tex), [`refs.bib`](../../../docs/refs.bib), [옛 catalog](../../../etc/related_works/related_works.md), [9월 초 corpus](../collection/), [최근 도메인 논의](../../../docs/VETS_DOMAIN_PROBLEM_AND_HA_POSITIONING.md).

접근 수준: **본문**은 전문을 확보하여 비교에 필요한 방법 절을 읽음, **부분**은 공식 초록/특정 절 또는 출판사 검색 캐시, **기존**은 예전 기록 유지이며 이번에 상세 재검토하지 않음. ‘부분/기존’을 근거로 기능 미지원 판정을 하지 않는다. 아래 venue/year는 읽은 판본과 기존 서지를 구별하며, 투고용 BibTeX는 출판판에 맞춰 정리해야 한다.

## A. OVLA Related Work 실제 인용 20개

| 기존 key | 논문·판본 | 현재 분류 / 확인 수준 | 근거 카드 |
| --- | --- | --- | --- |
| `autotap` | AutoTap, ICSE 2019 | 사용자 시간 속성·합성·repair / 본문 | [formal](formal_prior.md) |
| `tapinspector` | TAPInspector, TIFS 2022 | concurrent/timed property checking / 본문 | [safety](safety_prior.md) |
| `tapfixer` | TAPFixer, USENIX Security 2024 | timed correctness property·repair / 본문 | [safety](safety_prior.md) |
| `iruler` | Charting the Attack Surface…, CCS 2019 | inter-rule vulnerability / 본문 | [safety](safety_prior.md) |
| `soteria` | Soteria, USENIX ATC 2018 | source→IR→functional/safety/security checking / 본문 | [safety](safety_prior.md) |
| `hawatcher` | HAWatcher, USENIX Security 2021 | learned normal behavior/runtime anomaly / 부분 | [safety](safety_prior.md) |
| `gpiot` | GPIoT, SenSys 2025 | IoT algorithm code generation/testing / 본문 | [generation](generation_prior.md) |
| `spider` | Spider, EMNLP 2018 | text-to-SQL benchmark / 부분 | [generation](generation_prior.md) |
| `codet` | CodeT, ICLR 2023 | generated tests / 부분 | [generation](generation_prior.md) |
| `selfdebug` | Teaching LLMs to Self-Debug, ICLR 2024 | execution/explanation feedback / 부분 | [generation](generation_prior.md) |
| `autoiot_maude` | AutoIoT, Cheng et al., arXiv 2411.10665 (2024) | LLM rule generation + Maude conflict checking / 본문 | [generation](generation_prior.md) |
| `dsia` | DS-IA, arXiv 2603.16207 (2026) | room/device/capability grounding / 본문 | [generation](generation_prior.md) |
| `tasksense` | TaskSense, SenSys 2025 | sensor-language DAG/grammar check / 본문 | [generation](generation_prior.md) |
| `agentspec` | AgentSpec, ICSE 2026; preprint 2025 | DSL semantics/runtime enforcement / 본문 | [safety](safety_prior.md) |
| `chatiot` | ChatIoT, IMWUT 2024 | TAP IR/clarification/LLM Evaluator / 본문 | [generation](generation_prior.md) |
| `giudici2025` | Generating HA Automations, arXiv 2505.02802 | NL→HA/validity+manual evaluation / 본문 | [generation](generation_prior.md) |
| `iotgpt` | IoTGPT, arXiv 2601.04680 (2026) | simulation correction/feedback/memory / 본문 | [generation](generation_prior.md) |
| `awareauto` | AwareAuto, arXiv 2408.12687 (2024) | temporal rule authoring/confirmation / 본문 | [authoring](authoring_prior.md) |
| `lace` | LACE, arXiv 2505.23835 (2025) | NLI+SMT conflict+OPA / 본문 | [generation](generation_prior.md) |
| `simuhome` | SimuHome, arXiv 2509.24282v3 | temporal/environment benchmark / 본문 | [generation](generation_prior.md) |

## B. 원고 다른 절·기존 corpus·최근 논의·이번 추가 자료

| 자료 | 유입 경로 | 역할 / 근거 |
| --- | --- | --- |
| [Sasha, IMWUT 2024](https://arxiv.org/abs/2305.09802) | OVLA Intro | underspecified goal→action/routine; primary abstract 재확인, [generation](generation_prior.md) |
| [SAGE, arXiv 2023/v2 2024](https://arxiv.org/abs/2311.00772) | OVLA Intro | persistent monitoring 포함 runtime agent; 부분, [generation](generation_prior.md) |
| AutoIOT, Shen et al., MobiCom 2025 | OVLA 다른 절·기존 corpus | **Maude AutoIoT와 별개**; 본문, [generation](generation_prior.md) |
| TAP-Debug, IMWUT 2022/UbiComp 2023 발표 | OVLA motivation·기존 corpus | feedback-driven symbolic/SAT repair; 본문, [authoring](authoring_prior.md) |
| Trace2TAP, IMWUT 2020 | 기존 catalog | trace→multiple TAP, sustain, clustering/selection; 본문, [authoring](authoring_prior.md) |
| SENSATION, INTERACT 2021 | 기존 catalog | event/state guided authoring; 본문, [authoring](authoring_prior.md) |
| IoTSan, **CoNEXT 2018** | OVLA 다른 절·기존 corpus | app/model/property checking; 본문, [safety](safety_prior.md). 옛 catalog의 MobiSys 표기 정정 |
| [IoTGuard, NDSS 2019](https://www.ndss-symposium.org/ndss-paper/iotguard-dynamic-enforcement-of-security-and-safety-policy-in-commodity-iot/) | OVLA 다른 절 | runtime policy enforcement; 공식 abstract 수준 |
| CASPER, BIT 2026 + AutomationXP26 동반 문서 | 최근 도메인 논의 | structured NL→generation→conflict/chain/goal checks; journal 부분/workshop 본문, [authoring](authoring_prior.md) |
| Murphy et al., arXiv 2410.19736 (2024) | 최근 도메인 논의 | NL→TSL→reactive synthesis; 본문, [formal](formal_prior.md) |
| Temporal Stream Logic: Synthesis Beyond the Bools, CAV 2019 | 이번 formal 비교 보강 | data/control stream semantics의 선행; [formal](formal_prior.md). TSL modulo Theories (FoSSaCS 2022)는 추가 부분 확인 자료 |
| Translation Validation, TACAS 1998 | refs.bib·최근 논의 | 정식 학회 논문, 후속 전문 확보; [정밀 분석](translation_validation_deep.md) |
| Modular Translation Validation of a Full-sized Synchronous Compiler | 최근 도메인 논의 | 저자 공개 상세 manuscript; **JAR 2015로 확정 인용하지 않음**, [formal](formal_prior.md) |
| [Alive2, PLDI 2021](https://github.com/AliveToolkit/alive2) | refs.bib 배경 | LLVM bounded translation validation; 공식 project README만 재확인 |
| ARTEMIS, ICSE 2026 | 이번 추가 | NL→TL, proxy·balanced traces·의미 중복 제거; [정밀 분석](artemis_deep.md) |
| Req2LTL / OnionL, ASE 2025 | 이번 추가 | implicit temporal relation을 IR로 명시·LTL 변환; [formal](formal_prior.md) |
| NLForge, arXiv 2605.11315 (2026) | 이번 추가 | NL spec→C/C++ code checking; formal soundness 주장과 구별, [formal](formal_prior.md) |
| VIGIL, arXiv 2606.26524 (2026) | 이번 추가 | temporal policy·cross-call value binding·finite trace SMT; [safety](safety_prior.md) |

## C. 기존 기초·주변 문헌의 유지/보류

| 자료 | 정리 방향 |
| --- | --- |
| Practical Trigger-Action Programming (Ur et al., CHI 2014) | 사용자 authoring 배경; [기존 카드](../collection/reactive-temporal-iot/practical-tap/card.md). 이번 상세 재독 없음 |
| A Theory of Timed Automata (1994) | 시간 의미·도달성의 기초; [기존 카드](../collection/executable-semantics/timed-automata/card.md). timed IR 자체의 novelty 근거로 쓰지 않음 |
| The Synchronous Languages 12 Years Later (2003) | 결정적 reactive semantics의 기초; [기존 카드](../collection/executable-semantics/synchronous-languages/card.md) |
| SPIN (1997), Symbolic Model Checking without BDDs (1999), Model Checking textbook (1999) | 상태 탐색·bounded/unbounded 구분의 기초. [기존 reachability corpus](../collection/reachability-boundedness/INDEX.md). 기존 카드의 ‘VETS는 bounded’ 설명은 현 계약으로 대체 |
| How Users Interpret Bugs in TAP (CHI 2019), IoT-Spaces/Corno (2021) | 기존 catalog의 사용자/표현력 배경 후보. 이번 원문 재확인 안 함; 핵심 차별성의 근거로 사용하지 않음 |
| LLMind 2.0, Sigfrid | 기존 catalog의 이름/요약만 유지. 정확한 버전·서지·method 재확인 필요 |
| IoTMediator / Detecting and Handling IoT Interaction Threats (2023), SAFECHAIN (2019), DeLorean (2022), Fernandes et al. (2016), IoTRepair (2020) | multi-channel/security/runtime fault 확장 후보. 이번 핵심 표에서는 상세 비교하지 않음 |
| Model-based testing / runtime verification (기존 Utting/Bauer 항목) | 방식의 기초. 현 VETS를 이전 OVLA의 MBT+RV 구현으로 고정 분류하지 않음 |
| SoundOff, Sovereign, FSAIoT, Unvoiced | 기존 catalog에서 플랫폼을 사용한 주변 논문. 핵심 related work 제외 후보. FSAIoT 서지 오류 경고는 미해결로 유지 |
| HA/openHAB/AWS IoT Events/ESPHome 등 플랫폼 | 논문과 별도 범주. 기능 변경 가능성 때문에 옛 platform 표를 최신 기능표로 재사용하지 않음. 이번에는 연구 논문 비교에 집중 |
| Qwen/Gemma/GPT, vLLM/AWQ, HumanEval, LLM-as-a-judge | 원고의 모델·실험 인프라/평가 인용. 모두 related-work 경쟁 논문으로 세지 않음 |
| PerCom exemplar 7편 | venue writing pattern 자료. 현재 문제의 closest-work 목록과 구분 |
| Translating NL to Strategic Temporal Specifications, arXiv 2606.30441 | 이번 primary abstract 검색에서 발견한 MAS ATL/ATL* 후보. method 미확인, [초록](https://arxiv.org/abs/2606.30441). broad NL→temporal novelty를 주장할 때 추가 검토 |

## 조사 방법과 범위

1. `ovla0606.tex` Related Work의 citation key를 추출해 A표 20개와 대조했다.
2. `docs/refs.bib`, 옛 catalog, 기존 여섯 literature strands, 최근 domain/flow/extension 논의를 seed로 사용했다.
3. 검색어는 `Combining LLM Code Generation …`, `natural language smart home temporal specification verification LLM 2025 2026`, AwareAuto/CASPER/TaskSense/CodeT 등 exact title과 NL temporal specification을 사용했다. 추가 직접 경쟁 후보는 primary methods를 따라 확인했다.
4. API 검색 결과만으로 차이를 판단하지 않고 arXiv·저자 공개본·출판사 본문과 기존 PDF의 방법 절을 확인했다. OpenCite 일부 provider 실패는 문헌 부재의 증거로 해석하지 않았다.
5. ‘IR에서 표현 가능’, ‘실제 시스템이 지원’, ‘평가에 사용’, ‘정리로 보장’을 분리했다. 각자의 abstraction, 시간 단위, 값 관계, user confirmation, 검사 대상을 카드에 기록했다.

이 목록은 **현재 논문 motivation을 반증하려는 targeted narrative review**다. DB 전체의 체계적 검색이나 동등 태스크의 도구 실행 비교는 아니다. 부재/최초를 확정하는 목록으로 사용하지 않는다.
