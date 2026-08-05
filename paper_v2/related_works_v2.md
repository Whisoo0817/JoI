# OVLA v2 Related Work 지도 (2026-07-27 1차 서치)

> v1의 관련연구(`paper/related_works/`: AutoTap·ChatIoT·LACE·TAP-Debug·AutoIOT·GPIoT·TaskSense·SimuHome·IoTGPT)는 **NL→코드 생성** 축. v2는 축이 다르다: **환경 이식 + 장치 장애 적응 + 바인딩 적합성**. 이 문서는 v2 축의 지형.
> ⚠️ 전부 검색/초록 수준. **인용 전 원문 확인 필수** (v1 규칙 유지). `[R]`=원문 읽기 우선순위.

---

## A. 최근접 (must-cite, 차별화 문장 필수)

| 논문 | 무엇 | 우리와 겹침 | 델타 (우리 주장) |
|---|---|---|---|
| **IoTRepair** (Norris, Celik, Venkatesh, Zhao, McDaniel, Sivasubramaniam, Tan — IoTDI 2020; arXiv 2002.07641) `[R]`★ | 상용 IoT 장치 고장(device failure·network disruption) 처리 시스템: fault identification 모듈 + fault-handling 함수 라이브러리 + 자율 fault handler(사용자/개발자 설정 입력). "incorrect states 평균 50.01% 감소" | **Problem 2 그 자체.** 장치 고장을 시스템 층에서 다룸 | ①보장 없음(50% 감소=통계적 개선, 우리는 수리 후 코드에 대한 기계 검증) ②고장 처리=일반 정책(재시도/대체/무시)이지 **시나리오 목적에 대한 판정 아님** — "중단해야 하는가"를 묻지 않음 ③표현력: 우리 대상은 상태·타이머·GV 있는 반응형-시간 코드 ④사전 컴파일 없음 |
| **Requirement-driven Graceful Degradation & Recovery** (Chu, Koe, Garlan, Kang — SEAMS 2024; arXiv 2401.09678) `[R]`★ | 요구사항을 STL로, **weakening/strengthening**을 명세 완화·강화 연산으로 형식화. minimal/optimal/current 3단, 환경 예측 + MILP로 최소 완화·최대 회복. UUV 파이프 검사 사례, baseline=TOMASys | **essential/optional + degrade 결정의 형식화**라는 아이디어의 최근접 형식주의 사촌 | ①대상=제어 요구사항(연속 신호/STL), 우리=**배포되는 이산 자동화 코드**(코드를 실제로 다시 만들어야 함) ②그들은 요구를 완화, 우리는 **코드를 재바인딩하고 그 결과가 계약을 지키는지 증명** ③"목적-공허/유해" 판정 없음 ④런타임 MILP vs 우리 오프라인 전수 컴파일 |
| **H-RePlan + HeraBench** (Yao et al., arXiv 2606.20487, 2026-06) `[R]` | cross-device 에이전트에서 **device-local 전략 복구 vs orchestrator 전역 replan** 계층 분리; 고장 주입 벤치(strategy·device level) | 장애→복구의 **계층 분리 + fault-injection 평가**가 우리 설계/eval과 동형 | ①도메인=computer-use(API/CLI/GUI), 반응형 IoT 코드 아님 ②검증 0(완료율·토큰 비용 지표) ③런타임 LLM replan vs 우리 사전검증 표 룩업. **→ eval 방법론(고장 주입) 정당화 인용으로 유용** |
| **SafeTAP** (CMU 기술보고서; Zhang·Lu·Ur 계열) + **Towards Usable Security Analysis Tools for TAP** (McCall et al., SOUPS 2023) `[R]` | TAP용 **incremental symbolic model checking**: 규칙 추가/삭제로 유발된 분석만 재수행, 신규 위반만 보고 | "바뀐 것만 재검증" | ①단위=TAP 규칙 집합의 보안/충돌 property, 우리=**프로그램 내부 편집의 행동 보존**(counter/latch/cooldown) ②우리 ②구역은 재검증조차 안 함(구성적) |
| **IoTGPT** (Yu·Choi·Lee·Kim·Ko·Ko·Oh, arXiv 2601.04680) — 기존 분석됨 | subtask DAG 재사용·Service 그룹핑·선호 개인화, 캐시 히트 시 LLM 생략 | 시나리오 재사용·Service 추상 | 이미 락: subtask=무상태 API열이라 concat 자명, 검증=sim 재시도+사람 = **unsound baseline** |

## B. Problem 1 (환경 이식) 계보

- **Automation of Smart Homes with Multiple Rule Sources** (arXiv 2401.02451 / SCITEPRESS 2024) `[R]` — 규칙을 장치 구현과 독립된 **고수준**으로 쓰고 Concrete State Manager가 장치↔방 매핑으로 구체화 → "유사한 집에 이식 가능". **Problem 1의 가장 직접적 선행 주장**. 델타: 이식 가능성을 *설계 원칙*으로 말할 뿐, 이식 결과의 정확성 판정·장치 부재 시 판단 없음.
- **EUPont** (Corno·De Russis·Monge Roffarello 계열) + 확장 연구 — IoT end-user programming의 **기술 독립 추상 표현**, 추상 trigger-action 규칙. `role 슬롯/능력 추상`의 직계 조상. 델타: 추상화는 하지만 **검증에 쓰지 않음**(우리 델타 문장 이미 확보).
- **SAREF** (ETSI) / **W3C WoT Thing Description 1.1·2.0** / **Matter cluster 정보모델** — 능력·property·action 어휘의 산업 표준. role 계약(능력·도메인·단위)의 **접지 근거**로 인용. 델타: 능력은 기술하지만 **효과 방향·시간 클래스·essential 여부는 없음** → 우리 효과 주석 카탈로그의 필요성 논거.
- **Smart home transfer learning / READY / 신규 입주 개인화** (Appl. Artif. Intell. 서베이 2019; READY) — 새 집 적응을 **데이터/학습 전이**로 접근. 델타: 학습된 행동이지 검증된 코드가 아님; 우리는 목적 시나리오의 구조 보존.
- **HomeGenii / RAG-TAP** (IMWUT, 10.1145/3789673) `[R]` — 규칙 코퍼스에서 cluster-then-search로 의미 정렬 규칙 검색 + 압축. 우리 "시나리오 DB 검색" 부분의 최근접(단 TAP 규칙 수준, 검증 없음).

## C. Problem 2 (장치 장애·degradation) 계보

- **IoTRepair** — §A.
- **Chu et al. SEAMS'24** — §A.
- **Formal analysis of feature degradation in fault-tolerant automotive systems** (Sci. Comput. Program. 2018) + **Predictable timing of gracefully degrading automotive systems** (DAES 2023) `[R]` — 자원 부족 시 feature 비활성/강등을 형식 분석. **essential/optional의 자동차판 선행**. 델타: feature 수준 자원 스케줄링, 코드 재생성 없음.
- **TOMASys / metacontrol** (Chu et al.의 baseline) `[R]` — 로봇 기능 계층·role 기반 재구성 모델. "role"이라는 단위의 선행 용례 — 용어 충돌 점검 필요.
- **Automated Robot Recovery from Assumption Violations of High-Level Specifications** (arXiv 2407.00562) `[R]` — 명세 가정 위반 후 **새 skill 제안·offline repair**. 우리 "role 계약 위반 → 변환/대체" 구조와 유사. 델타: 도메인·표현력, 그리고 우리는 계약 방전으로 판정.
- **Unified Framework for Real-Time Failure Handling (VLM + behavior trees)** (arXiv 2503.15202) — LLM/VLM 기반 실시간 실패 처리. 무보장 대비점.
- 산업/실무 증거: Home Assistant의 `unavailable` 엔티티가 자동화를 통째로 깨뜨리는 이슈들(GitHub #78050, #105329; HA 커뮤니티) — **Problem 2의 현장 근거로 인용 가치 높음**(motivation 문장에 실사례).
- **SmartThings device health (UNHEALTHY 상태)** 공식 문서 — 장치 offline이 플랫폼 1급 개념임의 근거.

## D. 검증 기법 계보 (우리 도구 배치의 배경)

- **TAP 검증/충돌**: AutoTap(v1 보유), TAPInspector, IoTGuard, IoTCheck, Salus류, 충돌 탐지 서베이(arXiv 2310.04447) — v1에서 이미 "intent EMPTY" 논거로 정리됨. v2에선 "이들은 규칙 집합의 안전/충돌을 보되 **바인딩 적합성은 안 봄**"으로 재사용.
- **Regression/relational verification**: RVT(Godlin & Strichman), **SymDiff**(Boogie 기반 semantic diff), **Differential Symbolic Execution**(Person et al.), **Impact summaries**(CAV/NFM 계열), **ARDiff**(FSE'20), **PASDA** — v2 ③구역 relational miter의 직계 배경. 델타: 우리는 **편집이 계약과 footprint를 생성**하고 ②구역은 구성적으로 면제.
- **Template/proof reuse**: 검증된 설계 템플릿 재사용(Springer'97), formal template language + metaproof(2006), template-based verification & synthesis(MSR), parameterized verification(CMP abstraction), proof reuse(KeY 계열) — **"Certify once, bind anywhere"의 형식 배경**. 델타: 우리 파라미터는 **물리 장치 바인딩**이고 인증 단위가 목적 템플릿.
- **Vacuity/도달성**: vacuity detection 고전(Beer et al.) — R2 "essential 분기 사망 = 중단 판정"의 기법 뿌리. `[R]` 원문 확인 후 인용.
- **Program slicing**(Weiser 등) — 의존 원뿔의 표준 도구.
- **SchedCheck: Schedule-Robustness for Event-Driven Block Programs** (arXiv 2607.00623) `[R]` — 이벤트 구동 블록 프로그램의 스케줄 견고성. JoI tick/스케줄 가정과 비교 가치.

## E. LLM×IoT 생성·수리 (경쟁·대비)

- **SmartHomeSecure** (Wang, Gao, Ly, Shojaei — arXiv 2607.06748, 2026-07-07) — Home Assistant **YAML 설정 오류 탐지·수리**: 경량 프로그램 분석 + 제약 프롬프트 LLM, 결정론 auto-fix + 최소 수리. 100파일×5범주(구문/들여쓰기/매핑/시퀀스/인용) 주입, 탐지 100%·수리 87~93%. **대비점이 아주 깨끗함**: 오류 범주가 전부 **구문·형식 수준**이고 형식 검증 없음, 장치 장애·이식 미포함 → "LLM 수리는 구문 층에서 작동함이 실증됐다; 우리는 **의미·바인딩 층**에서 기계 검증과 함께"라는 문장에 그대로 쓰임.
- **IoTGPT** — §A. **AutoIoT/AutoIOT·GPIoT·TaskSense·ChatIoT·LACE** — v1 자산 재사용(생성 축).
- 벤치마크(모티베이션·평가 근거): **SmartBench**(arXiv 2603.06636, 2026-02: 이상 장치 상태 탐지 — SOTA도 66.1%/57.8%, **"LLM만으로 장애 상황 판단 불가"의 인용 근거**), **HomeBench**(ACL'25), **SMH-Bench**(2606.01912), **SimuHome**(v1 보유).

## F. 보완적/직교 (경쟁 아님, 위치 설명용)

- **Virtual/soft sensor로 결측 대체**(IEEE'20 등) — 센서가 죽으면 값을 *추정*해 잇는 접근. 우리와 상보: 그들은 신호를 복원, 우리는 **신호가 없을 때 시나리오가 성립하는지 판정**. 논문에서 "대체 신호가 있으면 우리 바인딩의 후보가 될 뿐, 적합성 판정은 여전히 필요"로 한 문단.
- **고장 탐지**: FailureSense(MASS), HAWatcher(USENIX Sec'21, 의미 상관 기반 이상 탐지), Verified Telemetry(MS) — 우리는 **탐지를 입력으로 가정**(고장 판정은 스코프 밖) 문장에 인용.
- **Home SafeHome**(arXiv 2007.12359) — 가시성·원자성으로 신뢰성. 실행 시맨틱스 층이라 직교.
- **Trace2TAP**(IMWUT'20), **TAGen** — 트레이스에서 규칙 합성. role 계약을 **관측에서 추정**하는 후속 아이디어의 선행(§8 리스크 ③의 반자동화 근거로 인용 가능).

---

## 빈 칸 = 우리 주장 (서치로 확인된 공백)

1. **장치 대체/삭제 후 "구조는 보존됐지만 목적이 깨졌다"를 판정하는 연구가 없다.** IoTRepair는 정책으로 처리, Chu et al.은 요구를 완화, SmartHomeSecure는 구문만, H-RePlan은 완료율만.
2. **role 계약(효과 방향·시간 클래스·essential)을 검증 의무로 쓰는 연구가 없다.** EUPont/SAREF/WoT/Matter는 능력을 *기술*만 하고, 방향·시간 특성·필수성은 어휘에 없음.
3. **(시나리오×role 고장) 전수 오프라인 사전 검증 → 런타임 표 룩업**이라는 배치가 없다. 자적응 문헌은 런타임 계획(latency-aware 논의는 있으나 사전 컴파일된 *검증된* 패치 표는 못 찾음) — `[R]` 이 공백은 SEAMS/TAAS 쪽 추가 서치로 한 번 더 확인 필요.
4. 6 고장 클래스 같은 **바인딩 fault model**이 없다(TAP 문헌의 fault model은 규칙 간 충돌·보안).

## 다음 서치 (2차)
- "adaptation plan precomputation verified" / "reconfiguration synthesis offline table" (공백 3 재확인)
- "effect direction / actuation semantics ontology"(효과 방향 어휘가 정말 없는지)
- IMWUT/UbiComp 2024~2026 "automation portability", SEAMS 2024~2026 "degradation"
- CHI/UIST의 자동화 유지보수(maintenance) 연구 — 사용자가 고장난 자동화를 어떻게 고치는지(motivation)
