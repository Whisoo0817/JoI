# OVLA v2 — 아이디어 정리 (2026-07-27 6차: 5차 + 검증 도구 재배치·3구역 모델·contingency compilation)

> 상태: 논문 프레이밍 재확정 (07-22~27 논의). 4차(NL 편집 중심 "신뢰 보존 편집")에서 **메인 시나리오를 회전**: user 자연어 명령/편집은 대상에서 제외, **환경 이식 + 런타임 장치 장애에 대한 자동 적응**이 메인. 4차의 기계(앵커 회전·frame-and-residual·계층 검증)는 전부 이월. 6차 증보(07-27 후반, "SMT 제외하고 재판정" 논의): **검증 도구 재배치**(SMT 코어=두 자리만), **3구역 모델**, **W 문제 재평가**, **GV=자유입력 락**, **contingency compilation**. 구버전은 git 이력.
> 근거 체인: SMT gate 실측(메모리 `project-smt-gate-progress-2026-07-15.md`) + codex 2회 리뷰 + 수작업 코퍼스(`joi_automation_codes.json`) 정량 분석 + 온습도 walkthrough.

---

## 0. 문제 프레이밍 (유저 락, 2026-07-27)

**전제: user intent가 없다. 자연어 명령은 대상이 아니다.**
- 시나리오 직접 저작은 진입 장벽이 큼 (SmartThings든 Joi든). 시나리오는 하나의 **목적/의도**(온도 제어, 재실 감지, 보안…)를 갖고 구성되며, 제대로 만들면 길고 복잡해짐 (수작업 코퍼스 실증: 온습도 512tok, 공기질 539tok).
- **Problem 1 (환경 이식)**: 집집마다 device/tag/location/수량이 달라 매번 재생성 어려움.
- **Problem 2 (런타임 장애)**: 센서/장치 하나가 오류 나면 시나리오 전체가 중단됨.
- 목표: **목적을 가진 시나리오를 환경과 상황에 따라 동적으로 자동 생성/변경**하는 시스템. 실시간이므로 빨라야 하고, 바뀌어도 정확히 동작함이 검증되어야 함. Task 4(신규 로직 창작)는 스코프 밖 (LOCK).
- 세부 판단 이슈: 동일 기능 장치 추가/대체, drop된 장치 없이도 시나리오가 도는지, 아예 무의미해져 중단해야 하는지의 판정.
- **GV 락 (유저, 07-27)**: 시나리오 간 통합/합성 검증은 **안 한다**. GlobalVariable은 센서처럼 "밖에서 자연히 변하는 값" = **자유 입력(tau)** 으로 취급 → 검증은 항상 **시나리오 하나 단위로 닫힘**, v1의 tau 입력 기계 그대로 재사용. 성질: 과대근사(실제 생산자 패턴보다 넓은 입력 허용)라 **놓치는 방향 오류 0**, 드물게 실제로 안 일어나는 GV 조합의 spurious 반례만 가능(안전한 쪽 편향). assume-guarantee 분해 불필요해짐.

### 한 줄 주장 (LOCK)
> **Structure is preserved; correctness is not — it lives in the binding.**
> 구조를 고정해도 정확성은 보존되지 않는다. 정확성은 로직의 상수·guard·관용구가 "바인딩된 장치의 물리적·시간적 의미론"과 맞물리는 데 있다. 검증 대상은 사라지는 게 아니라 **프로그램 등가 → 바인딩 적합성(binding conformance)** 으로 이동한다.

### Service-oriented 계보 접속 (유저 확정, 2026-07-27)
연구실 계보(하순회: SoPIoT'17 → SeMo'18 → 스케줄링'21 → 계층 edge'23)의 **service-oriented 추상**이 우리 어휘의 직계 조상: 서비스 인터페이스=role 슬롯, 서비스→장치 매핑(미들웨어)=바인딩 β, 복합 서비스/service graph=목적 템플릿, 장애 시 재배치=Problem 2. **단, 그대로 채택이 아니라 반박-완성**:
- SO의 존립 가정 = **인터페이스 수준 대체가능성**("같은 서비스 이름이면 어느 장치든 OK") — 우리 6 고장 클래스가 정확히 이 가정이 반응형-시간 시나리오에서 거짓임을 보이는 분류학. **SO 미들웨어 = unsound baseline의 체계화** (IoTGPT Service 그룹핑=그 LLM 시대판).
- 구조 델타 ①: SO=호출 시점 **late binding**(런타임 간접화, 검증과 상극) vs 우리=**verified early binding**(바인딩 시 코드 구체화→증명→가용성 이벤트에 재바인딩; contingency 표=late의 유연성+early의 검증가능성).
- 구조 델타 ②: SO=**앱 불변 가정**(제공자 없으면 호출 실패, degrade/중단 판단 없음) vs 우리=대체가 코드 로직 변경을 강제함을 인정(drop 16~41%·latch 삽입)하고 그 재작성을 검증.
- 포지션 문장: "SO는 배관(발견·매핑·스케줄링)을 해결했다; 우리는 빠진 정확성 층을 추가한다 — **role 계약=행동 명세가 붙은 서비스 타입, 바인딩 적합성 검증=sound한 서비스 대체**."
- 활용: §1을 "SO의 약속→왜 미완→binding conformance"로 열기 가능; '21 스케줄링과는 직교 합성("적합 후보 간 선택은 에너지/deadline 최적화로") 인용; **주의**=JoI 카탈로그 "Service"(skill 의미)와 용어 구분 정의 필수; super service/런타임 브로커링은 스코프 밖.

- 시스템 한 줄: **Certify once, bind anywhere** — 목적 템플릿을 오프라인에 1회 파라미터 인증하고, 모든 환경 인스턴스화/런타임 재바인딩은 기계 생성 obligation 방전으로 인증.
- Problem 1 = 최초 바인딩, Problem 2 = 재바인딩 — **같은 연산**.

### 문제 진술 재정박 — "생성이 아니라 무인증" (유저 반론 검토 확정, 2026-07-28 포크)
유저 자기반론 3종("#ifdef식 사전 대비면 충분 / 클라우드에 맞춰달라면 됨 / 오프라인이면 다 대비 가능")의 판정:
- **#ifdef식 사전 대비 = 우리 아키텍처 그 자체**(contingency 표). 반론이 성립하려면 "그 변형을 누가 만들고 누가 맞다고 보장하나"에 답해야 함 — 사무실 하나가 70행(N×M 폭발), 수작업은 K1 재발. **결정적 실측**: 우리 자신의 fail-closed 슬라이서 산출물조차 정화기 drop 시 경고 토스트 call site를 함께 잃었고(miter 반례로만 검출), 센서 절단은 분모가 바뀌어 보존 채널 행동이 실제 변함. 신중한 기계 산출물이 이 정도면 손 #ifdef는 더함. + 베이스 1회 수정에 변형 가족 전체가 낡음(stale 기계 필요).
- **클라우드 재생성 = B3 베이스라인으로 흡수.** 만들 수는 있으나 보장 못함(v1: 강한 모델이 silent-wrong 더 놓침 9.2%; 6 고장 클래스=전부 무사 실행). 논문 문장은 "클라우드로 못 한다"가 아니라 **"누가 만들든 배포 전 인증 층의 부재가 문제"**.
- **오프라인 전수 = 절반만 참 → 두 경로의 근거.** 열거 가능 고장은 표로 닫힘(우리가 함); 환경 이식은 조합 폭발로 온라인 경로 필수; 표는 구멍을 escalate로 정직 기록.
- **문제 진술 문구(락 후보)**: "적응 변형을 만드는 것은 어렵지 않다 — 사전 컴파일이든 클라우드 생성이든 변형은 나온다. 문제는 변형이 조용히 틀리고(6 고장 클래스), 스케일에서 변형마다 사람이 검토할 수 없다는 것. 기여 = 변형의 기계 생성 + 채널별 행동 인증을 하나의 파이프라인으로; contingency 표는 그 산출물." → §1 예상 반론 선제 배치로 두 반론을 각각 "우리 아키텍처의 절반"·"B3"로 흡수.

### 한 문단 문제 진술 (유저 채택 2026-07-29 — P1~P5 종합, 상세=§11)

> 시나리오는 검증되어 배포되지만, 검증은 (코드×환경×시점)의 스냅샷이다. 배포된 시나리오는 다른 집에 바인딩되고(P1), 환경 변화에 침식되고(P2), 사용자에게 수정되고(P3), 다른 시나리오들과 조합되며(P4) 산다 — 그 각각이 검증 지위를 조용히 깨뜨리고, 어느 것도 벤더가 원격으로 재판정할 수 없다. 필요한 것은 더 좋은 검증기가 아니라, 검증된 지위를 아티팩트의 생애 전체에 걸쳐 로컬에서 보존·재판정하는 기계이며(P5: 그 판정을 가능케 하는 계약·인증서의 동반 배포 포함), 그것이 이 논문이다.

락 문장: **"검증은 이벤트, 유효성은 생애주기."**

### 트리거 3종, 기계 1개 (유저 확정, 2026-07-28 — NL 편집 요청 채택)

트리거: ①환경 이식(P1) ②장치 장애(P2) ③**사용자 NL 편집 요청**(신규 채택). 셋 다 같은 연산으로 수렴 — **typed edit → footprint → 변환 → 계약 방전 → 인증**. 기계가 트리거에 무관하다는 것 자체가 일반성 논거.

**★NL 락 (v1과의 결정적 구분)**: NL은 **스펙이 아니라 델타 지시자**다. 정확성 기준은 여전히 ①검증된 베이스 코드(언급되지 않은 모든 것은 불변이어야 함) ②role 계약. 한 줄: **"NL names the delta; contracts define correctness."**

왜 K1(리뷰 killer)의 재발이 아닌가:

| | v1 | 채택한 구조 |
|---|---|---|
| 스펙 출처 | 자연어 명령 | **검증된 기존 코드 + 계약** |
| 사람 확인 표면적 | 프로그램 전체 의미(512tok) | **델타 1~3 연산** |
| 오라클 | 없음(사용자 머릿속) → 측정 불가 | **있음** — 벤치마크를 우리가 저작하므로 gt typed edit이 **구성적으로 존재** → NL→Edit IR 정확도가 측정 가능 |
| 오해 시 | 틀린 코드를 충실히 검증(silent) | 타입 공간 밖=fail-closed / 렌더된 diff에 표면화 |

리뷰어 요구는 "사람 의존을 없애라"가 아니라 **"남긴 부분을 측정하라"**였음 — 이 구조가 정확히 그 답.

**가드레일 3 (LOCK)**
1. 보장 문장은 항상 "**주어진 typed edit에 대해** frame 보존 + 계약 방전을 증명한다". NL→Edit IR 정확도는 **별도 숫자**로 보고하고 end-to-end 합산 금지.
2. **닫힌 연산 집합**(ReplaceSelector / ReplaceArgument / ModifyPredicate / InsertGuardedAction / DeleteAction / ChangeDelay / ChangePeriod) + 밖이면 **거부** — 열린 의미 번역이 아니라 **유한 분류 문제**로 유지.
3. **검토 표면적 ∝ 델타** — 결정론 diff 렌더링 + "나머지 전부 동일"의 UNSAT 증명.

**편집 요청 3유형 — NL 난이도와 검증 난이도가 반대** (§1 hook 재료):

| 유형 | 예 | NL 난이도 | 검증 난이도 | 왜 |
|---|---|---|---|---|
| 값 수정 | "25도를 26도로" | ~0 | **의외로 있음** | deadband 반전·계절 분기 경계 넘김·**장치 setpoint 유효 범위 밖** → vacuity/도메인 검사 필요 |
| 명시적 대체 | "에어컨 말고 X로" | 낮음(대상을 사용자가 지정) | **최고** | 6클래스 전부 발동 |
| 암묵 적응 | "connected devices에 맞춰" | 없음(파이프라인 트리거일 뿐) | 높음 | Problem 1 그 자체 |

→ **언어적으로 가장 쉬운 요청이 의미적으로 가장 위험하다.** Hero는 여전히 binding conformance; NL 편집은 **인터페이스이자 측정된 컴포넌트**(hero 승격 금지).

---

## 1. 왜 어려운가 — "구조 동일·무사 실행인데 틀리는" 6 고장 클래스 (fault model, 코퍼스 실증)

**"슬롯만 갈아끼우면 검증할 게 없지 않냐"는 착각을 깨는 분류학. 논문의 hard problem.**

| 클래스 | 사례 (코퍼스) | 본질 |
|---|---|---|
| (a) 효과방향/능력 불일치 | 에어컨→선풍기: heat 없음·setpoint 없음·실온 안 내림 → 겨울분기 유해("추우면 선풍기")·off 영원 미도달 | 제어 루프의 물리 전제 붕괴. IoTGPT식 property 치환이 무보장 통과 = **unsound baseline 실존** |
| (b) 시간 특성 불일치 | presence(level)→motion(pulse): grace 10s가 무력 → 착석자를 부재 판정 | 슬롯 교체가 **관용구 변환(latch/debounce 삽입)+재튜닝을 강제**. K=3 flip 실측이 이 부류의 실재 증거 |
| (c) 수량 변화의 quantifier 의도 | 연기감지기 1→2대: 화재는 any, 소등은 all, 온도는 avg — 같은 수량 변화의 정답이 **목적** 의존 (C12_007 `all(#Smoke)==|true`는 2대에서 안전상 오답) | 구조 어디에도 없는 정보 |
| (d) 값 도메인/단위/극성 | °F 센서: 타입 통과·avg≈77→`>25.5` 항상 참→24시간 냉방; open/closed vs bool; 가습기→제습기=극성 반전 | 카탈로그 대조 층 |
| (e) 시나리오 간 재배선 | 대체 선풍기를 #Office 플러그에 → 절전 제어가 밤마다 전원 차단; Section1 센서 사망→`occupancy_section1` stale→소비자 5개 오염 | 개별 구조 불변인데 **간섭 그래프**가 변함. (6차 갱신: 검증은 GV=자유입력으로 시나리오-로컬 유지; 간섭은 **정적 footprint 교차·전원 토폴로지 검사**로만 잡음 — §0 GV 락) |
| (f) 목적-공허/유해 | ModeToggle 버튼 사망: 보안모드는 멀쩡히 돌지만 출근마다 침입 경보 — 중단보다 나쁨 | "돌 수 있는가"는 잘못된 질문; **잔여 행동이 목적에 봉사하는가**가 기준 — 목적의 형식화 없이는 정의 불가 |

---

## 2. 해법의 형태: 목적 템플릿 + role 계약 + 바인딩 (LOCK)

```
템플릿 T = ( 스켈레톤 (관용구 구조: 게이트·계절분기·for집계·deadband·cooldown·seed…),
            role 슬롯: TEMP_SENSORS, THERMO_ACTUATOR, OCC_SOURCE, ALERT_SINK, …
            role별 계약: 요구 능력(setpoint형/on-off형), 효과 방향(어떤 property를 ↑/↓),
                        시간 클래스(level/pulse/event), 값 도메인·단위, essential/optional,
            행동 계약 C: "재실∧초과→발동", "부재→발동 금지", "여름 heat 금지",
                        deadband·cooldown, quantifier 의도(any/all/avg), 안전 불변식,
            파라미터 + validity domain )
바인딩 β: role → 실장치 (환경 인벤토리+토폴로지+실시간 가용성)
```
- **role 계약 = 코드에 이미 새겨진 암묵적 가정의 명시화** (`humid < min → on`이라는 guard 극성 자체가 "이 장치는 습도를 올린다"는 가정). 온습도 walkthrough로 전 항목 실증됨.
- 템플릿은 **오프라인 1회 파라미터 인증** (M2.6이 프로토타입: 4종 tick-귀납 증명·0.16ms 매칭·K-무한정 — 이미 실측). 바인딩 시엔 obligation만 방전.
- **모델의 자리**: 후보 다수일 때 적합성 판단, 관용구 변환 선택, degrade 설계, "무의미→중단" 판단 보조 — 출력은 **결정 객체** {substitute(D′)|delete(role)|degrade(방식)|escalate}, 코드는 harness가 결정론 실체화 (**모델은 코드를 복사하지 않는다** — 4차 결론 유지: 오류 표면적 512→~30tok, 94%↓).
- **바인딩 시 방전 obligation**: (a)능력·효과방향 대조(효과 주석 카탈로그 — EUPont류를 채택하되 **검증에** 사용 = IoTGPT 델타) (b)시간 클래스 일치, 불일치 시 인증된 변환 규칙(latch 삽입) 발동 (c)quantifier를 계약 의도에서 유도 (d)도메인/단위 매핑 (e)전 시나리오 footprint 교차+전원 토폴로지 간섭 검사 (f)공허/유해 = SMT vacuity 질의.

### 검증 도구 재배치 (6차 LOCK — "SMT 제외하고 재판정" 논의의 결론)

**병목은 검증 엔진 선택이 아니라 ①생성을 "모델 재출력"에서 "harness의 typed edit 기계 적용"으로 바꾸는 것, ②중단/유지 판단 근거인 목적 메타데이터(essential/optional 계약)의 획득.** 검증은 의무별 최소 충분 도구를 배치하고, SMT는 척추가 아니라 사다리 최상층 **두 자리에만** 남긴다:

| 의무 | 최적 도구 | SMT? |
|---|---|---|
| 슬롯 치환·수치·주기 반영 | AST 변환 (결정론; 코퍼스상 편집=타입화된 슬롯 5.5~9.3%) | ✗ |
| 타입/단위/효과방향/극성 | 정적 계약 검사 (타입체커 수준) | ✗ |
| drop 전파 범위 | 의존 슬라이싱 | ✗ |
| GV/시나리오 간 간섭 | 정적 그래프·footprint 교차 (GV=자유입력이라 합성 검증 소멸) | ✗ |
| vacuity/도달성 대부분 | 구간 추상해석 (threshold·enum 비교 위주라 ms) | 잔여만 |
| **"안 건드린 곳 안 깨짐" 증명** (③구역: counter/latch/cooldown 얽힌 보존-투영 등가) | — | **✓ 유일** |
| **최소 구별 반례 = 사용자 설명** ("이 상황만 다르고 나머지 동일=UNSAT") | — | **✓ 유일** |

→ 7역할 중 **R4(투영 등가)·R7(반례 설명)이 solver 코어**; R3(계약)·R2 대부분·R1의 단순 케이스는 정적 검사/구간 분석으로 강등(solver는 잔여 방전만). 시뮬레이션은 위 두 자리를 *테스트*는 해도 *증명*은 못 함 — SMT가 도구가 아니라 **주장의 등급**을 바꾸는 자리. 논문 서사: "SMT로 다 검증"이 아니라 "판단의 각 층에 최소 충분 도구, 증명이 필요한 두 지점에만 solver".

### 3구역 모델 (편집 후 코드의 안전 분해)

편집 시 코드는 3구역으로 나뉜다 (자르는 기준 = **"센서/액츄에이터 관련"이 아니라 편집의 의존 원뿔**):
- **① 편집부**: 실제 바뀐 코드 → 계약 방전 대상.
- **② 독립 비편집부**: 편집과 상태 공유 없음 → **검증 불필요.** splice로 바이트 동일 + 공유 상태 없음 = 동작 동일이 **구성적으로** 보장 (복사조차 안 했으므로 달라질 방법이 없음). 코퍼스상 편집이 5~9% 산재라 대부분의 코드가 ②.
- **③ 공유상태 비편집부**: 코드는 그대로인데 편집부와 GV/타이머/카운터를 공유 → **SMT relational 증명의 유일한 일감** (구/신 두 버전을 원뿔+공유상태로 잘라 "보존 출력 전 입력 동일" miter).
- 원뿔은 **과대근사만 허용**: 독립을 공유로 오판=증명 하나 낭비(느림), 공유를 독립으로 오판=틀린 안전 주장(사고). "느려질 수는 있어도 틀릴 수는 없다."
- v1 실측 참고: 코드가 작아 통짜 인코딩 비용은 문제가 아니었음(307쌍 전부 통짜 miter; 비쌌던 건 W). 자르는 이유 = ②를 0원으로 만들기 + 의무를 role 단위의 사람이 읽는 문장("가습기 동작 보존됨")으로 쪼개기.

### 얽힘(entanglement) 문제 — 어려움의 정체와 분업 (유저 정의 확정, 2026-07-28)

**문제 정의 (유저)**: 수정/교체/drop은 한 줄 변경이 아니라 **의존성 원뿔** — 변수 선언, composite 전체, 그 service를 위해 존재하던 if/wait/for/계절 branch까지 딸려간다. 어려운 건 그 line들이 drop되는 service **전용이 아니라 유지되는 service와 공유**될 때: drop 부분만 쏙 빼야 한다.

**현재 v0의 대응 (M-D 실증)**: 구문적 얽힘의 절반은 이미 처리 — ①feature 클로저(카메라 drop→미정의 `video`를 읽는 이메일 동반 삭제), ②소스별 부분 절단(AQ 사망 시 AQ 루프 2개만 절단, `temp_sum` 먹이는 TS/HS 루프 유지), ③진짜 얽힌 경우(공유 guard 내 산/죽은 소스 혼재, if/else 한 팔)는 **fail-closed escalate**. T1+base_office에서 escalate 0은 코퍼스가 깨끗해서이지 문제가 없어서가 아님 — 합성 환경/T2에서 escalate 발생 지점이 이 어려움의 실측이 됨.

**contribution 문장 (분업이 핵심 — "SMT가 line dependency를 체크"가 아님)**:
- line 의존성 추적 = 정적 슬라이싱(구문, ms). SMT의 일 = **슬라이싱이 원리적으로 못 잡는 의미적 얽힘을 보존-계약 증명으로 닫기**.
- 즉: **"복합 편집의 정확성은 line을 따라가서 확립되는 게 아니라 보존 계약이 여전히 성립함을 증명해서 확립된다"** — 슬라이서는 제안(propose), 계약+relational miter가 판정(dispose).
- baseline 논증 연결: B1(슬롯 치환)은 다중-line 얽힘 자체를 못 하고, B3(전체 재출력)은 보존 구역 무결성을 보장 못 하고, B5(계약 없는 patcher)는 그럴듯한 틀린 편집을 냄. 우리 = 최소 편집 + 보존 증명.

**유저 정의 밖의 추가 얽힘 5종 (전부 ③구역/miter의 존재 이유)**:
1. **구문 공유 없는 의미적 얽힘**: 변수를 하나도 공유 안 해도 같은 액추에이터/GV에 쓰면 결합 ("밤에 꺼줘" drop → 살아남은 "더우면 켜줘"의 듀티 사이클 변화; last-writer-wins, level/pulse). 슬라이싱 불가시, relational miter만 검출.
2. **삭제가 시간을 민다**: 시퀀스 내 `wait`/`delay` 한 줄 삭제 → 텍스트상 살아남은 뒤쪽 line들의 실행 시각 전부 이동. 보존 구역 바이트 동일해도 행동 상이 — "Structure is preserved; correctness is not"의 시간판, (b)클래스.
3. **수량/분모**: 센서 절단 후 `sum/3→sum/2`, N개 기준 임계값 의미 변화, 소스 전멸 시 `all()` 공허참→(f) 목적-공허.
4. **교체는 삭제보다 나쁨**: AC→히터 극성 반전은 교체 장치를 언급조차 안 하는 line(임계값 25, 계절 branch)까지 수정 대상 — 편집 footprint가 셀렉터 밖 상수/조건으로 번짐. template (d)검출이 담당.
5. **재배포 시점 상태 잔류**: 실행 중 아티팩트 교체 시 구 시나리오가 남긴 상태(켜진 장치, GV 값); "꺼주는 line"을 drop하면 아무도 안 끔 → 전환 cleanup obligation. 현재 미해결, 논문에 한계/설계로 명시 가치.

### W 문제 재평가 (6차)

- v1은 전부가 W 싸움(코드↔IR을 W틱 병렬 실행); v2는 **③구역 한 곳만** W 싸움. 나머지 의무는 전부 시간 무관(표 대조·정적 검사·슬라이싱·구간 산수) 또는 검증 불필요(②).
- ③구역도 **relational induction이 자연 무기**: v1은 서로 다른 언어(JoI↔IR)라 대응 불변식이 어려웠지만, v2는 **같은 코드끼리**라 "공유 변수 같으면 같은 코드는 같은 동작" 불변식이 거의 자명 — 증명이 "편집 지점이 공유 상태에 미치는 영향" 한 조각으로 좁아짐. M2.6 tick-귀납(0.16ms·W-무한정)이 이 방식의 실증.
- 귀납 실패 시(편집이 공유 카운터 궤적 자체를 바꾸는 경우) bounded unroll 폴백 → **M2.5 폐쇄형·M3 run-accel 그대로 재사용** (새 코퍼스의 3h 주기·30min cooldown·요일창이 정확히 이 fragment 모양). 그리고 무거운 증명은 전부 오프라인(아래)이라 몇 분 걸려도 무방.

### Contingency compilation (6차 신규 — 시스템 주장의 핵)

**role이 유한하므로 고장 모드가 오프라인에서 전수 열거된다.** 시나리오마다 (role 고장 → 대응) 표를 미리 컴파일:
- 오프라인(밤): 각 role 사망 케이스별로 슬라이싱→결정(치환/degrade/중단+사유)→패치 생성→검증(귀납/accel/unroll 폴백 포함)까지 완료해 표에 저장. 시간 걸리는 일 전부 여기서.
- 런타임: 장치 사망 → 표 룩업 → 미리 검증된 패치 적용 또는 중단+사유 통지 = **밀리초**. 생성·검증·판단을 그 순간엔 하나도 안 함.
- 정직한 한계: 표는 열거 가능한 고장만 커버. **환경 통째 이식**(조합 폭발)은 온라인 파이프라인 경로. → 시스템 = 두 경로: **런타임 고장 = 표 룩업(ms) / 환경 이식 = 온라인 생성+검증(초~분)**.

### SMT의 역할 7종 (5차 원판; 6차 재배치 적용 — 코어=R4·R7, R1~R3은 정적 우선+solver 잔여)
의미 좌표(데이터/제어 의존, 효과, 시간축 소속)는 결정론 슬라이싱이 계산. SMT는:
- **R1 절단 무결성**: 잘라낸 뒤 잔여 기능 도달 가능? (PM2.5 제거 시 `n_pm25>0` conjunct 잔존→청정기 조용히 사망 — 구문·실행 멀쩡한 기능 상실을 도달성 UNSAT으로 검출)
- **R2 도달성/공허성**: 화씨 바인딩→guard 상수화 검출; **essential 분기 도달 불가 = "이 바인딩에서 무의미→중단" 판정의 기계적 근거**
- **R3 계약 방전**: C1(부재 무동작)·C3(deadband)·C4(cooldown)… 재검증 (incremental)
- **R4 투영 등가/방향성 정련**: P₁ ≡ π_D̄(P₀) miter; 등가 아닐 땐 Q1(과잉 발동 없음=UNSAT)+Q2(핵심 기능 보존)+Q3(안전 방향 변화 허용) 분해
- **R5 변환 규칙 오프라인 증명**: "latch(pulse,g) ≈ level" 등을 M2.6 방식 파라미터 1회 증명 → 인증 변환 라이브러리
- **R6 파라미터 재합성**: validity domain을 solver가 산출 (해상도 변화 시 밴드 폭 등; MaxSMT)
- **R7 반례 = CEGIS 피드백 + 사용자 설명** (콘크리트 타임라인; 기존 추출→replay→렌더링 재사용)

### 정직한 경계 2개 (LOCK — 논문에 명시가 방어력)
- **open-loop 한계**: "선풍기가 안 꺼짐"은 자유 입력 모델에선 못 잡음(환경이 협조하는 입력 존재). 잡는 층 = 정적 효과-방향 규칙(현실적) / closed-loop 물리 가정 추가(확장, assume 명시). 
- **공허해진 계약은 "통과"가 아니라 "포기됨"으로 보고** (setMode 삭제로 C2가 공허히 참이 되는 함정).

### 검증 사다리 (4차 이월 + 재배치)
L0 구문 → L1 보존=splice 구성적(footprint 밖 바이트 동일, 증명 불필요) → L2 블록 시그니처↔계약 diff 대조(ms; IoT 블록은 목적이 명확해 **의미 기반 블록 주소**가 성립 — 일반 코드에서 실패한 anchoring이 이 도메인에선 공짜: Cursor full-rewrite 후퇴와의 대비 논거) → L3 SMT(R1~R7) → L4 합성 behavioral diff 통지. **느려질 수는 있어도 틀릴 수는 없다** 원칙 유지, 소진 시 safe-mode(정지+통지)=fail-closed.

---

### 서비스×공간 2축 바인딩 + Composite service (유저 확정, 2026-07-28)

**① 공간 축 (SoPIoT Device.Service 논의에서)**: 후보 탐색 술어 = **capability(d) ⊨ role 계약 ∧ space(d) ⊨ 공간 제약**. 안방 온도 시나리오에 거실 에어컨은 후보가 아님 — `closed_loop` 효과는 같은 공간 안에서만 성립하므로 공간 제약은 효과방향 계약의 공간적 확장.
- role 계약에 `spatial: same_space | anywhere | follows_user` 추가 (기본=same_space; 센서·액추에이터=same_space, 알림=anywhere/follows_user, GV·Clock=무관).
- **태그 taxonomy 필요**: JoI 태그는 장치타입(#AirConditioner)·공간(#Office)·인스턴스(#CO2_Indicator)·그룹(#NoneNecessary)이 한 평면 — 인벤토리 모델에서 3분류해야 공간 필터가 기계적으로 됨 (M-C 첫 작업).
- 계보: '23 계층 edge 논문(방→층→건물)이 공간 계층을 관리 단위로 제안 → 우리는 공간을 **바인딩 적합성의 제약**으로 승격 (반박-완성 서사 강화).

**② Composite service (SoPIoT 원어휘의 채택-완성)**: M-B의 미해결 문제("타입 넘는 대체 시 새 호출열은 누가 정의하나")의 답.
- composite = 추상 연산 + **계약(post-condition)** + 장치별 **실현(realization)** 목록. 예: `reach_target_temperature(mode,target)` — 계약 "temperature가 target 방향으로 움직임(closed-loop)·cooldown 준수", AC 실현 = `[switch_on; setMode; setTargetTemperature]`(온습도 스켈레톤의 3연속 호출이 그 실물).
- **대체 단위가 멤버→composite로 승격**: AC→X 대체 = "X에 인증된 실현이 있는가" 조회 → 실현 교체(typed edit 묶음) / 없으면 abort·degrade.
- **R5의 액추에이터판**: "실현 ⊨ composite 계약"을 M2.6 방식 장치별 1회 증명 = 인증 어댑터 라이브러리. **Certify once, bind anywhere가 composite 단위로 확장.**
- 계보: "SoPIoT이 composite service를 정의했고, 우리는 계약+장치별 인증 실현을 붙여 대체를 sound하게 만든다."

**가드레일 2 (LOCK)**: ①composite는 **컴파일 타임 어댑터** — 인스턴스화 시 구체 호출열이 splice되어 배포 코드엔 구체 멤버만 남음(런타임 간접화=late binding 회귀 금지) ②실현은 **계약 없이 등록 불가** — 이름 매칭 실현 등록=B1 unsound baseline과 동일; uncertified 실현으로의 대체는 fail-closed.

### 생성 = 검색된 베이스로부터의 편집 (커버리지 corollary — 기여 아님, 2026-07-28 채택)

새 단순 요청도 같은 기계로 처리: "문이 열리면 온도를 높여줘" → DB에서 τ-근접 베이스("문이 열리면 불을 켜줘") 검색 → 델타 자동 유도(LIGHT 액션 → THERMO 액션) → typed edit → 인증. **최초 바인딩·재바인딩·사용자 편집·신규 요청이 전부 같은 연산**(생성 = 베이스가 라이브러리에서 온 편집).

- **왜 넣나 (어필이 아니라 실질)**: v1 리뷰 **K2**("IR을 확정해놓고 왜 LLM lowering으로 비결정성을 다시 넣나")의 완결된 대답 = **"우리 시스템에서 LLM은 반응형 코드를 한 줄도 쓰지 않는다"** — 구조는 인증된 라이브러리에서 오고, 모델은 목적 선택과 델타만 고름. v1이 발견했던 메커니즘 오류(edge↔level, cycle↔once)가 **구조적으로 발생 불가**(메커니즘=베이스에서 상속).
- **별도 시스템이 아님**: 예시의 LIGHT(on/off·즉시·무인자) → THERMO(setpoint형·연속값·유효 범위)는 **능력 교차 대체** = 6클래스 (a). "온도를 **높여줘**"는 인자 미지정 → THERMO 계약("setpoint형은 값 필수, 범위 X~Y")이 기본 정책 또는 abstain을 유도. 계약이 없으면 모델이 아무 값이나 채우고 조용히 통과.
- **실패 모드 전이**: v1=메커니즘 오류(조용·치명·측정 불가) → 여기=**목적/구조 선택 오류**(측정 가능 — 24 category·D-1~D-9 gt 라벨 존재).
- **측정 (신규 실험 거의 없음)**: ①τ-class hit rate(gt 관용구 라벨 대비) ②생성 결과를 **v1 gate로** gt_ir과 등가 판정 ③**abstention rate**.
- ⚠️ **프레이밍 주의**: gt_ir은 **오프라인 벤치마크의 참조 정답**으로만 사용. v1이 맞은 이유는 "시스템이 **런타임에** 사용자 IR 승인을 요구"했기 때문 — 이 구분을 문장으로 못 박을 것.
- **문구 규율**: coverage / abstention / "no LLM authors reactive code"만. 금지="NL 이해"·"생성 정확도 X%"·abstract hero 승격. 라이브러리 밖 요청은 fail-closed abstain + **비율 정직 보고**(no silent caps).

---

## 3. 정량 근거 (코퍼스 분석, 2026-07-22)

- 수작업 9시나리오 2,958tok: 환경 이식 시 변경 = **task1+2 슬롯 5.5%(보수)~9.3%(공격), 전역 산재**(#Office 95곳 — naive suffix엔 기각 ~160지점, **선제 치환 후 기각 ~0** = 치환 가치의 정량화) / **장치 drop 16~41%, 전부 연속 블록**(frame-and-residual 최적형) / 신규 기능 삽입 ~7% 연속.
- **장치 수량 변화는 수정량 0** — `all()`/`for`가 흡수. 유일한 예외 재실 집계 41% = GlobalVariable 키 수동 열거 → 수량-파라미터 템플릿(N-way or-fold)으로 접힘.
- 스펙트럼: 태그 중심 13.5% ~ 순수 로직 0%(재실 집계) — "수정량 ∝ 환경 결합도" 비례 주장의 실분포.
- GlobalVariable 그래프: 생산자(섹션×7)→집계→소비자 5. 관용구 수렴: cooldown 6/9·write-on-change·deadband·debounce·seed·rising-edge = 템플릿화 실증 근거.

### 코퍼스 재정의 — 2-tier (2026-07-28 확정: v1 382 재활용)

| Tier | 출처 | 용도 | 한계 |
|---|---|---|---|
| **T1 단순·균일** | v1 382 (24 category·D-1~D-9 관용구·307 SMT 판정·284 EQUIV·**49 M2.6 인증**). **원 NL 명령은 버림** — 생성 벤치마크가 아니라 시나리오 description/라벨로만 | ①**검증된 편집 베이스**(베이스 자체가 spec이라 role 계약 없이도 편집 검증 성립 → T1 provenance 약점 소멸) ②규모·통계(**리뷰 K8의 N=9 취약점 해소**) ③템플릿 추출기 검증 테스트베드(같은 τ-class에서 같은 스켈레톤을 복원하는가) ④**Certify once의 실물 입력**(49 인증 템플릿) | (e)재배선·GV 미노출; 코드가 LLM 생성물(단 307쌍 SMT 판정 완료) |
| **T2 복잡·실사용** | 수작업 시나리오(GV·for·cooldown·계절분기) | 6클래스 전부 노출, 하드 케이스, 곡선 우측 | N 작음 → **검정 단위를 (바인딩×고장) 조합**으로 재정의해 보강 |

- **★복잡도 판별 곡선 (핵심 그림)**: x=복잡도(관용구 수·상태 변수·GV·시간 구조), y=naive 슬롯 치환(B1) 성공률 → T1에서 대체로 성공, T2에서 붕괴. 이중 효과 = ①우리 fault model이 공허하지 않음 ②**선행연구(TAP·subtask concat·IoTGPT)가 왜 이 문제를 만나지 못했는지를 데이터로 설명**(그들의 평가 대상이 곡선의 왼쪽 끝). 리뷰 K3(일반화 과장)의 반대 처방 = 범위를 데이터로 그림.
- **편집 벤치마크 저작**: 시나리오 × K개 NL 편집 요청(3유형) + **gt typed edit**(구성적 존재) → B3/B4(LLM 코드 편집기)와 **사과 대 사과** 비교 가능(NL 편집 요청이 그들의 표준 인터페이스이므로).
- **v1 렌더러 + faithfulness-surfacing 재조준**: 1504/1504·blind 0 방법론을 IR 렌더링 → **편집 diff 렌더링**("NL 오해가 사용자에게 표면화되는가")으로.

## 4. 구현 현황 (완료 실측 — base case의 기계; 상세는 메모리)

Gate 306/307(99.7%)·DIVERGE 21/21 재현·FP 0 / E-B 1,225/1,227(99.8%)·MISS 0 / M2.6 템플릿 4종·49/72·0.16ms·K-무한정 / K-민감도(M2 5 flip 전부 재현=scope 실증) / grounding alias 3=전부 아티팩트 / M2.5·M3 accel. Eval 프레이밍 락 유지(정확도 %는 없다 — 조건부 정리).

### smt/ 자산 재배선 맵 (2026-07-28 확정: 재작업 아님 — miter에 물리는 대상만 교체)

v1 SMT는 IR↔JoI 비교였지만 v2 ③구역 증명은 **구 JoI ↔ 신 JoI** — miter 양쪽이 전부 JoI라서 인코더를 두 번 쓰는 구조. 세 무더기:

**① 그대로 엔진 (~70-80%)**
- JoI 인코더(심장: tick 의미론·레지스터 점화식·cooldown/counter/latch·방출) — 한 줄도 안 버림
- InputModel(tau·K 변화점·grid): GV=자유입력 락 덕에 GlobalVariable=tau 키 추가로 흡수
- M2.5 폐쇄형·M3 run-accel: IR 비교의 성질이 아니라 JoI 쪽 인코딩 가속 → W 폴백 그대로
- M2.6 tick-귀납: "Certify once"·③구역 relational induction의 직접 프로토타입
- grounding/alias(바인딩=장치 문제라 더 중심으로), E-B 1,227 뮤턴트+반례 replay(결함 시딩+R7 렌더링), M0 분류기+fail-closed 규율

**② 역할 전환 (버림 아님)** — IR 인코더/"IR↔JoI gate" 프레임:
1. 탄생 인증 경로(DB 진입 시나리오가 LLM 생성물일 때; 수작업 9개=저작이 신뢰 뿌리라 불필요)
2. **인코더 신뢰성 증거 이월**: 같은 JoI 인코더를 v2가 쓰므로 1,227 뮤턴트 99.8%·MISS 0·FP 0·반례 전수 재현이 그대로 v2 엔진의 품질 보증서
3. 논문 C3(완료·실측)

**③ v2 신규 작업**
1. JoI↔JoI relational miter(공유 입력 심볼+보존 출력 단언) — NEXT의 obligation 분리 리팩터가 그 준비
2. relational induction("공유 변수 같으면 같은 코드=같은 동작" 불변식) — M2.6 변주
3. **새 구문 인코딩 확장 = 최대 신규 공수**: v1 인코더는 dataset 문법까지, v2 코퍼스(수작업 9개)는 `for`(장치 컬렉션)·`loop(cond)`·GlobalVariable·`<|`/`>|`·인자 있는 함수 바인드 사용. 전략 확정: for=grounding 후 정적 unroll / GV=tau 키 / `<|`·`>|`=비교 연산 추가 / 인자 함수 바인드=uninterpreted 입력 / **loop(cond)만 까다로움**(forecast 1~6h — 정적 bound 필요)
4. 계약/vacuity 질의(R2·R3 잔여): 같은 인코딩 위 새 질의 형태(도달성 UNSAT·계약 위반 SAT)

한 줄: **v1이 만든 건 "JoI→수학 번역기 + 품질 보증서"고 v1 논문은 그걸 IR 대조에 썼을 뿐 — v2는 같은 번역기로 대조 대상만 바꿔 끼움 = 재배선.**

## 5. 관련연구 포지셔닝

- **Service-oriented IoT/로봇 플랫폼 (연구실 계보: SoPIoT'17·SeMo'18·스케줄링'21·계층 edge'23 + SOA/pervasive service composition/semantic service substitution 문헌)**: 우리 role/바인딩의 정식 조상 카테고리 (§0 계보 절). 델타=인터페이스 매칭·무계약·무검증·무중단판단·앱 불변 가정 → 우리가 정확성 층을 완성. v2 축 상세 지도는 `related_works_v2.md`(IoTRepair·Chu SEAMS'24·H-RePlan·SafeTAP·SmartHomeSecure 등).
- **IoTGPT(2601.04680)**: subtask 재사용·Service 그룹핑·개인화 — 그러나 subtask=무상태 API열(TAP급)이라 concat이 자명, 검증=sim 재시도+사람. **우리 unsound baseline**: "재사용 효율은 실증됨(그들); 표현력 있는 코드에서 정확성을 잃지 않는 재사용(우리)".
- **Suffix/speculative 편집 가속**: Cursor Fast Apply·OpenAI Predicted Outputs(프로덕션 상식), EfficientEdit(ASE'25)·Blazedit·SAM-Decoding·REST·PLD. **"기법 발명" 주장 금지.** 남는 델타 = ①선제 슬롯 치환(draft의 의미론적 사전 변환 — 어디에도 없음) ②계약 기반 **정적** 스케줄링(Blazedit의 동적 acceptance와 대비) ③재검증과의 결합. 엔진은 vLLM PLD/predicted-outputs 재사용, 기여=draft **구성**. 속도 기둥이지 정확성 기둥 아님.
- 차분/회귀 검증(RVT·SymDiff·UpProver), incremental SMT(Green·Cache-a-lot·MUC-G4): 백엔드로 인용. 우리 델타=바인딩 적합성이라는 문제 자체+계약이 spec과 전이 경계를 생성.

## 6. Contributions 후보 (5차)

- **C1 — Binding conformance**: 6-클래스 fault model + 목적 템플릿/role 계약 + 바인딩 obligation 방전. "Certify once, bind anywhere." **세 트리거(환경·장애·사용자 요청)가 하나의 연산으로 수렴**(§0).
- **C2 — 가용성 기반 인증 자기수리 + contingency compilation**: device-offline → 결정 객체(모델) → harness 실체화 → 투영/방향성 정련 인증 → hot-swap; 수리 spec이 장애에서 기계 유도(NL 불개입). 공허/유해 판정(R1·R2) 포함. **role 유한성 → (시나리오×role 고장) 전수 오프라인 사전 검증 → 런타임 = 표 룩업 ms 반응** (§2).
- **C3 — SMT gate + 인증 템플릿** (완료·실측): base case와 오프라인 인증의 기계.
- **C4 — 합성 behavioral diff** (설명=검증 부산물).
- **C5 — 선제 치환 suffix decoding** (지원; AST patcher 하한 대비 정직 포지셔닝).
- *(기여 아님)* 생성 커버리지 corollary (§2): "LLM이 반응형 코드를 쓰지 않는다"는 시스템 주장 — K2 해소용.

## 7. Evaluation 스케치

**데이터**: T1(v1 382, 편집 베이스)+T2(수작업 복잡) 2-tier(§3); 합성 환경 인벤토리 N개(장치 구성 섭동); (시나리오×role) 전수 장애 주입 스윕; 6클래스별 결함 시딩; 시나리오×K개 NL 편집 요청(3유형)+gt typed edit.

**베이스라인 — 주장별로 하나씩 (★=필수)**

| 이름 | 무엇 | 어떤 주장을 검정 |
|---|---|---|
| B0 무적응 | 그대로 배포 | Problem 존재(이식 깨짐률·장애 중단률) |
| **B1 naive 슬롯 치환** ★ | 이름/타입 매칭 device·tag 교체 = **SO 미들웨어 / IoTGPT식 property 치환** | **C1 핵심**: 6클래스 무사 통과율 + **복잡도 판별 곡선**(§3) |
| **B3 LLM 전체 재출력** ★ | "새 환경용으로 바꿔 전문 출력"(Cursor식 실무) | **C3**: 긴 코드 복사 정확도 붕괴(오류 표면적 512→~30tok 주장의 정면 측정) |
| **B5 계약 없는 AST patcher** ★ | 우리 ①⑤만, 계약·검증 없음 | **C2 ablation**: 계약 층이 무엇을 잡는지 분리 |
| B2 처음부터 재생성 | 목적 설명→코드 생성(v1 방식) | 보존성(무관 슬롯 표류)+latency; v1 instability 자산 재사용 |
| B4 LLM diff/patch 편집 | edit-block·unified diff | B3보다 강한 실무 상대 |
| B6 IoTRepair식 정책 처리 | 재시도/무시/일반 폴백 | **C4**: 목적 판정 없는 고장 처리와의 차이 |
| B7 LLM-as-judge 수락 | 검사 대신 LLM이 판정 | 검증층 필요성(v1 계보) |

**지표**: silent-wrong 수락률(통과했으나 계약 위반) / **중단 판정 정확도**(should-abort recall·precision — B1~B5는 개념 자체가 없어 0) / 편집 정밀도(의도 외 변경) / abstention rate / latency **두 경로 분리**(contingency 표 룩업 ms vs 온라인 파이프라인 초~분) + 표 컴파일 오프라인 비용.

**Ablation**: −효과 카탈로그 / −vacuity / −SMT(③구역) / −슬라이싱(구문 footprint만) / −선제 치환(accept run).

**기존 자산 재사용**: 1,227 뮤턴트(off-contract 후보), gate(fresh 판정 대조 + 생성 corollary의 등가 판정기), grounding, 반례 replay, 렌더러+surfacing 방법론, v1 testbed(E2E 수리 데모).

## 8. 보류함 / 리스크

- 보류: closed-loop 물리 가정(확장), ChangePeriod incremental(=fail-closed 유지), lossy acceptance, 일반 조합, MaxSMT repair, consensus, runtime monitor. *(NL 사용자 편집은 2026-07-28 채택 — §0 트리거 3종)*
- 리스크: ①대체 의미 적합성 오판(사무실↔실외 센서) — 카탈로그+태그 필터+diff 통지로 wrong-but-safe ②투영 의미론 엄밀화(죽은 장치 상태를 타 블록이 읽는 경우 — footprint+impact로; 시나리오 간은 GV=자유입력 락으로 소멸) ③effect 주석 카탈로그의 저작 비용(role 계약 추출을 반자동화할지) ④(f) 목적 형식화의 범위 — essential 표시+vacuity로 제한적으로만 주장 ⑤GV 자유입력 과대근사의 spurious 반례 빈도(파일럿에서 실측; 잦으면 GV별 간단한 도메인 제약만 추가) ⑥contingency 표의 신선도(환경/카탈로그 변경 시 재컴파일 트리거 — 인증서 버저닝과 동일 기계).

## 9. 구현 계획 — `adapt/` 파이프라인 (2026-07-28)

기반 확인 완료: ANTLR 문법(`parser/JOILang.g4`) + 생성 파서, `validate_joi`, 카탈로그(`files/service_list_ver2.0.7.json`: type/unit/enum/함수 인자 보유 — **없는 건 효과방향·시간클래스·essential 3축뿐**). SMT는 ⑦에서 호출만.

| 단계 | 모듈 | 입력→출력 | 모델 |
|---|---|---|---|
| ① 구조 추출 | `structure.py` | JoI → AST + **블록 시그니처 테이블**(읽는 키·쓰는 GV·guard 원자·액션·시간상수) + **role 참조 테이블**(span↔device/tag) + 의존 그래프. **문자 오프셋 span 추적이 파이프라인 전체의 토대** | ✗ |
| ② 템플릿 추출 | `template.py` | AST → 스켈레톤 + role 슬롯(device/tag/threshold/period 파라미터화) + 계약 스텁 | 초안만 |
| ③ 효과 카탈로그 | `effects.py`+`effects.json` | 카탈로그 skill에 (효과방향·시간클래스·도메인/단위·능력종류) 주석 | 반자동 |
| ④ 바인딩·결정 | `bind.py` | 인벤토리+role → **후보 열거(SO 층)** → 계약 대조 → 결정 객체 {substitute/degrade/delete/abort} | ✓ (여기만) |
| ⑤ 변환 | `patch.py` | typed edit 적용(ReplaceSelector/ReplaceArgument/ModifyPredicate/ChangeDelay/DeleteSlice/InsertLatch) → **splice 출력**(미편집부 바이트 동일) | ✗ |
| ⑥ 정적 검사 | `check.py` | L0 `validate_joi` + L1 splice 불변식 + L2 계약/시그니처 diff + **vacuity(구간 분석)** | ✗ |
| ⑦ 인증·컴파일 | `certify.py`,`contingency.py` | ③구역 obligation → `smt/` 호출; (시나리오×role 고장) 전수 → **표** | ✗ |
| (NL 경로) | `editir.py` | NL 요청 → **닫힌 typed Edit IR 분류**(밖이면 거부) + grounding | ✓ |

**설계 결정 (LOCK)**: ⑤의 출력은 문자열 재생성이 아니라 **원본 바이트 + 편집 span 치환**. 그래야 L1이 증명 없이 성립하고 3구역 모델이 작동.

**마일스톤**
- **M-A ✅ 완료 (2026-07-28)**: ①`structure.py` + ⑤`patch.py` + 검증 하네스·유닛테스트. 실측은 아래.
- **M-B ✅ 완료 (2026-07-28)**: ②`template.py`+템플릿 4종 / ③`effects.py`+`effects.json`. 실측은 아래.
- **M-C ✅ 완료 (2026-07-28)**: ④ `bind.py`+`inventory.py`+`composites.json`. 실측은 아래.
- **M-D ✅ 완료 (2026-07-28)**: ⑤b `slicer.py` + ⑥ `check.py`. 실측은 아래 (AC→Fan·presence→motion은 M-B/M-C에서 abort로 이미 관통).
- **M-E ✅ 완료 (2026-07-28)**: ⑦ `contingency.py` + 침입감지 템플릿. 실측은 아래. (smt 배선=certify는 relational miter 선행 필요라 NEXT ⑤⑥ 이후로.)
- **병행**: 합성 환경 인벤토리 N개(없으면 B0~B5를 못 돌림), 편집 요청 벤치마크 저작(3유형×gt typed edit).

### M-A 실측 (2026-07-28) — `python3 -m adapt.run_structure_check`, `python3 -m adapt.test_patch`

| | T2 수작업 | T1 v1-382 (sim/cache) |
|---|---|---|
| ANTLR 파싱 | **10/10** | **306/306** (빈 스크립트 1건 제외) |
| identity splice (0 편집 = 바이트 동일) | **10/10** | **306/306** |
| retag splice + L0 재파싱 + 바이트 델타 정확 | **9/9** | **306/306** |
| **시그니처 불변**(순수 재바인딩) | **9/9** | **304/304** |
| 규모 | 130 device ref / 103 블록 | 678 device ref / 615 블록, 태그 502곳 치환 |

- **capability는 태그가 아니라 멤버에서 온다**(`switch_on`→switch/on; `sim.expr.canonical_key` 재사용 = SMT와 동일 규약). 따라서 태그=순수 바인딩 정보 → 재바인딩은 시그니처를 건드리지 않음. **`#AirConditioner`→`#Fan` 교체도 구조 diff에는 안 보인다** = 우리 명제가 코드로 표현됨(잡는 건 ④ 계약 층). 유닛테스트 `test_device_type_swap_is_invisible_to_structure`가 이걸 고정.
- 예외 2종은 실패가 아니라 **올바른 검출**: `#GlobalVariable`(role 아님·네임스페이스), 접두사 없는 멤버(`stopCharging` — capability가 태그에서 유래).
- `verify_splice`는 `apply_edits`와 독립 구현(보존 구역을 직접 바이트 비교) → 변조·조용한 삭제를 모두 거부함을 테스트로 확인(동어반복 아님).
- **문법 1줄 확장**: `primary_expression`에 `IDENTIFIER DOT IDENTIFIER`(legacy `clock.time`) 추가 후 ANTLR 재생성 → T1 파싱 295→306. `validate_joi`·SMT 회귀(M1 EQUIV/DIVERGE+재현) 정상 확인.
- 이 하네스가 그대로 **베이스라인 B5**(계약·검증 없는 결정론 AST patcher).

### M-B 실측 (2026-07-28) — `python3 -m adapt.run_template_check [--matrix]`

**아티팩트**: `adapt/effects.json`(장치 프로파일 15종) + `adapt/templates/*.json` 4종.

| 템플릿 | roles(필수) | params | 계약 | 스켈레톤 | 검사 |
|---|---|---|---|---|---|
| thermo_comfort 온습도 | 6 (4) | 12 | 8 | 2,804자·15 ref | identity·re-scope(11곳)·값편집·role 재바인딩·coverage 15/15 ✅ |
| air_quality 공기질 | 6 (2) | 8 | 7 | 2,876자·17 ref | 동일 ✅ |
| section_presence 재실(Sec1) | 4 (3) | 4 | 6 | 2,243자·21 ref | 동일 ✅ |
| occupancy_aggregate 재실집계 | 2 (2) | 8 | 4 | 978자·10 ref | 동일 ✅ |

- **효과 카탈로그 = 없는 3축만 추가**: 효과 방향·시간 클래스·control(setpoint/onoff/level). 나머지(타입·단위·enum)는 플랫폼 카탈로그가 권위이고, **전 항목을 카탈로그와 교차검증**(음성 테스트 3종으로 공허 통과 아님을 확인). `essential`은 카탈로그가 아니라 **템플릿의 role 계약**에 둔다(목적 정보이므로).
- **role 커버리지 100%**: 4개 스켈레톤의 63개 device ref가 orphan 0·중복 0으로 role에 귀속. **identity 라운드트립**(base 바인딩 → 편집 0건, 바이트 동일)이 슬롯 테이블의 완전성을 보증.
- **★고장 주입 11/11**: (a) AC→Fan=abort(setpoint 없음·양방향 불가·멤버 2개 부재) / **(b) Presence→Motion=abort**(같은 BOOL·같은 property인데 pulse→level 위반: "latch 없이는 level guard를 지탱 못함") / (d) Humidifier→Dehumidifier=**극성 반전**으로 자동 분류 / (f) 필수 role 상실=abort·선택 role 상실=degrade. 즉 **구조 diff가 못 보는 것을 계약이 전부 잡는다**는 것이 실증됨.
- **후보 매트릭스**(④ 예고편): TEMP_SENSORS는 AirQualitySensor+TemperatureSensor 둘 다 충족(다중 소스 실증), 나머지는 base 타입만 — 이는 role 계약이 **스켈레톤이 호출하는 멤버**까지 요구하기 때문. 즉 현재 매트릭스는 "무편집 drop-in 가능"의 척도이고, 타입을 넘는 대체는 ReplaceMember 편집을 동반해야 함(M-C의 일).
- **스키마 결정 2건**(코퍼스가 강제): ①**소스별 멤버** — 한 role을 여러 장치 타입이 채우므로(온도=AQ+TS) 멤버 요구는 role이 아니라 소스에 붙는다 ②**위치 태그는 role이 아니라 파라미터** — 재스코프와 재바인딩이 독립 편집이 되도록.
- ⚠️ **코퍼스에서 발견한 실제 단위 불일치**: `공기질`의 `st_tvoc := 0.6`은 토스트 문구상 mg/m³인데 카탈로그의 `TvocLevel`은 **ppb**. 자연 발생한 fault class (d) 사례(템플릿에 FLAG로 기록). 논문 예시로 쓸 수 있으나 **사용 전 유저 확인 필요**.

### M-C 실측 (2026-07-28) — `python3 -m adapt.run_bind_check` (18/18)

**아티팩트**: `inventory.py`(인벤토리 모델+태그 taxonomy: 카탈로그 id→타입 / 선언 공간→space / 나머지→instance = 보수적 기본값이라 오분류해도 후보가 줄 뿐 틀리지 않음) / `composites.json`(4종: reach_target_temperature·humidify·purify_air·indicate_state — 계약 없는 실현은 **스키마 수준에서 로드 거부**) / `bind.py`(결정 엔진: keep / substitute(drop-in) / **realize**(인증 실현 교체) / drop_feature / abort).

- **[1] base 인벤토리**: 4템플릿 전부 keep·편집 0·verdict OK.
- **[2] 장치 사망(P2)**: AC→abort / Humidifier→drop_feature(degrade) / PresenceSensor→abort / AirPurifier→advisory-only degrade — 전부 role 계약이 지시한 대로.
- **[3] 공간 축**: 거실 AC는 Office 시나리오의 후보가 **아님**(2축 술어 작동) ↔ scope를 LivingRoom으로 바꾸면 같은 AC가 후보(공간=장애물 아닌 제약); notifier(anywhere)는 공간 무관.
- **[4] 다중 소스 생존**: TemperatureSensor 사망 시 AirQualitySensor 소스가 TEMP_SENSORS를 커버(one_or_more).
- **[5] 실현 교체 역학**(합성 Chiller — 실카탈로그에 2번째 온도조절기가 없어 기계 검증용): AC 사망→realize 선택, 5편집·2,688자 보존·재파싱 OK, 배포 코드엔 구체 Chiller 호출만(컴파일 타임 어댑터 락 준수). **버그 발견·수정**: stop()/off-분기 참조가 죽은 AC에 댕글링→시퀀스 밖 참조는 공유 switch capability만 이식 허용(그 외=fail-closed)으로 해소, 회귀 테스트 고정.
- **[6] fail-closed**: 같은 실현을 uncertified로 바꾸면 realize 대신 **abort**.
- **모델의 자리 구현으로 고정**: `needs_llm_choice` 플래그 — sound 후보가 2+일 때만 모델이 고름; 후보 집합을 넓히는 건 불가능.

### M-D 실측 (2026-07-28) — `python3 -m adapt.run_slice_check` (23/23)

**아티팩트**: `slicer.py`(drop_feature → DeleteSpan 계획: seed refs→taint 전파→제어 오염 블록→전행 단위 삭제) / `check.py`(정적 검사 3종: domain·band·drop-signature).

**슬라이서 안전 규칙 4 (전부 위반 시 escalate=fail-closed, 나쁜 편집은 불가능)**:
①**essential role은 drop 불가**(abort 경로지 degrade가 아님 — 지우면 "구조 멀쩡·목적 사망" R1 상황을 만들므로 계획 전에 거부) ②오염 블록 안에 live 액추에이터 호출 금지(notifier는 동반 삭제 허용 — 사라진 동작을 알리는 토스트는 같이 가야 함) ③if/else 분리 삭제 금지(v0) ④**undefined survivor 금지**(삭제부에서만 쓰이던 변수를 생존 코드가 읽으면 거부). 삭제는 전행 단위 = 문법의 비어있는-블록 금지와 L1을 동시에 존중; 덜 지우는 쪽이 안전 방향(죽은 seed 상수는 의도적으로 남김).

- **[1] 가습기 사망**: 5삭제·2,400자 보존, 습도 read/call 전무·AC 4참조 그대로·drop-signature clean.
- **[2] 온도센서 소스 사망**: 해당 for-loop 1개만 삭제, AQ 루프 생존, temp_sum 여전히 기록(undefined survivor 없음).
- **[3] 청정기 사망**: 청정기 if 2블록 삭제, **블록 안 토스트는 collateral로 동반 삭제**, CO2 경고 토스트·인디케이터 생존.
- **[4] escalation**: CLOCK drop·TEMP_SENSORS 전체 drop → essential 규칙으로 거부.
- **[5] "25→26" 데모 (§0 hook의 실물)**: 26.0=통과 / **24.0=재파싱은 되지만 band 검사가 거부**(min 24.5≥max=양 분기 도달불가) / **99=domain 검사가 거부**(장치 setpoint 범위 밖). 문법·splice 완벽한 편집이 의미 검사에서 걸리는 실측.
- **[6] E2E**: 가습기 사망→bind(degrade)→feature drop(5삭제)→정적 검사 clean→"humidity_control abandoned" 보고. 2,804→2,400자.
- **검사기 결함 수정 1건**: drop-signature가 capability 키(`switch.on`)로 비교→가습기와 AC의 공유 capability 충돌(false positive) → **서비스 태그 한정 키**(`humidifier:switch.on`)로 수정.

### M-E 실측 (2026-07-28) — `python3 -m adapt.run_contingency_check` (16/16)

**아티팩트**: `contingency.py`(오프라인 전수 컴파일→`contingency_tables/*.json`) + 템플릿 5호 `intrusion_alert.json`(침입감지 4-role: ALERT_SINK 필수 / VOICE_NOTICE·EVIDENCE_SOURCE·EVIDENCE_SINK 선택) + effects.json에 Camera·EmailProvider 추가.

- **전수 컴파일: 5템플릿 × 14장치 = 70행, 오프라인 255ms.** 행동 분포 abort 4 / keep 56 / redeploy 10 / **escalate 0** (구멍은 숨기지 않고 escalate 행으로 기록되는 구조 — 이번 코퍼스에선 0).
- **침입감지 프로토타입**: 토스트 사망=**abort**("알릴 수 없는 침입 시나리오는 목적 사망") / 스피커 사망=음성 안내만 drop / **카메라 사망=evidence 클로저(카메라+이메일) 동반 drop인데 "[긴급] 침입 의심" 토스트는 생존** — 목적 유지 강등의 실물 / 이메일 사망=동일 아티팩트(결정론).
- **소스 수준 절단**(`plan_drop_source` 신설): AQ 사망→자기 루프 2개만 절단, TS·HS 루프가 평균을 계속 공급(2,557B) / TS 사망→루프 정확히 1개 절단(4→3).
- **런타임 경로**: 표 저장(11.5KB)→재로드→**룩업 평균 <1µs**(10k회) — "런타임 고장 대응=ms" 주장의 하한 실측(배포 비용 별도) / **stale 표 거부**(소스 해시 불일치 시 낡은 아티팩트 배포 대신 예외+재컴파일 요구=인증서 버저닝 축소판) / 미사용 장치=keep.
- **모든 redeploy 아티팩트(10개) 재파싱 통과 + 죽은 장치 타입 참조 0.**
- **슬라이서 결함 2건 발견·수정**: ①**호출-대입**(`video = capture(...)`)이 writes에 빠져 카메라 단독 삭제 시 이메일이 미정의 `video`를 읽는 걸 놓침→writes에 assigns_to 포함+호출 인자도 독자 스캔 ②read seed를 감싸는 assign 줄(`now = clock.timestamp`)을 삭제 단위로 승격 못해 co2_warning 클로저가 escalate→승격 후 rule 5가 생존 독자 검증.
- **정직한 한계**: 클로저 drop의 (f)-리스크는 텍스트 수준 — 삭제된 기능을 언급하는 생존 알림 문구까지는 안 봄; 아티팩트의 행동 등가(③구역)는 §NEXT의 relational miter로.

### M-G 실측 (2026-07-28) — 새 구문 인코딩 + redeploy 아티팩트 인증 (`smt/encode_v2.py`·`smt/run_certify.py`)

- **③새 구문 (예정 앞당김)**: 파서 확장(`//` 주석·`;` 구분자·`:` 토큰·`for (x : all(#T #S).member)`·selector의 quant/전체태그 보존=`QuantRef(DeviceRef)` 서브클래스 — v1 소비자는 동일 DeviceRef로 봄; **코퍼스 307/307 파싱 불변**) + `encode_v2.py` grounding/desugar(인벤토리 정적 unroll·수량화 비교→And/Or·GV get="globalvariable.k" 자유입력/set=메서드에 키 폴딩=`setboolean_occupancy` 채널 분리·call-assign·resolved type을 service로). `:=`(init_once)와 tick-영속 env는 **M2 엔진에 이미 존재** — 스켈레톤 5/5가 기존 unroll 엔진에 그대로 들어감. 인코더 추가 2건: `clock.timestamp`=**epoch T0(공유 심볼 상수)+t/1000** — 배포상대 시각이면 `last:=0` sentinel의 쿨다운 게이트가 창 내내 닫혀 전 증명이 공허해짐(실제 겪고 수정; T0 심볼=모든 배포 시각에 대해 증명), `clock.month/day`=창 내 상수·심볼(모든 달에 대해 증명).
- **relational v2**: `check_relational_v2(skel, artifact, period, inv, preserve)`; **w_cap=32**(v1 창 규칙이 co2>1500 같은 센서 리터럴을 tick 임계값으로 읽어 1,524 tick 요구 → 상한=창-한정 정리로 정직 기록) + **채널별 in-window 도달성 질의**(미스매치 단언 전 같은 solver) → EQUIV를 실증명/공허(VACUOUS)로 구분 보고.
- **redeploy 아티팩트 10개 인증 (1호 목표)**: intrusion 3행(cam/em/sp) **완전 인증** — 보존 채널 전부 UNSAT 증명(sp1의 camera/email 채널은 창-공허로 정직 라벨). air li1 완전 인증(재시도 w=24). air ap1=**부분 채널 검출 실물**: 정화기 feature와 함께 경고 토스트 call site가 사라진 것을 count:publish 반례로 가시화(슬라이서 텍스트 수준에선 허용된 notifier collateral을 miter가 잡음). **thermo 교차 localization**: ts1 사망→가습 채널 EQUIV 증명·온도 채널만 DIVERGE / hs1→AC·목표온도 EQUIV·가습만 DIVERGE / aq1(양쪽 평균에 기여)→전 채널 DIVERGE = "어떤 센서 상실이 어떤 계약을 건드리나"를 solver가 갈라줌(분모 변화=예상된 강등 가시화). 미결 1종: align:movetocolor/3(3-인자 색상 밴드) 2행에서 TIMEOUT — 오프라인 야간 예산/induction 후보로 기록.
- **잔여**: cron 스켈레톤(현재 5종 전부 period형이라 미노출)·relational induction(장주기 쿨다운의 무한 창 답)·`adapt/certify.py` 배선(contingency compile_row에 miter 호출 추가).

### M-I 실측 (2026-07-28) — 합성 환경 24개 + B1 복잡도 판별 곡선 (`adapt/environments.py`·`baselines.py`·`run_b1_curve.py`) — eval 1호 그림 데이터

- **합성 환경 24개**: 앵커 6개(env00=베이스 대조군 / env01=AC→Fan (a) / env02=가습기→제습기 (a·d) / env03=Presence→Motion (b) / env04=온도센서 3개 (c) / env05=토스트 없음 essential) + 시드 랜덤 18개(냉방/습도/재실 대체·센서 수·통지자 유무·공간). 결정론(seed 고정).
- **B1 구현**: 인터페이스-수준 naive 슬롯 치환(IoTGPT/SO 가정 충실 재현) — 멤버명 정확일치 2점·set*Mode 유사 1점·값-읽기는 **카탈로그 선언 타입(BOOL↔BOOL) 일치 요구**·read-only kind 보너스; 계약·슬라이싱·검증 없음. 판정=기계 검사만: 배포가능(파싱+댕글링 없음)+`check_binding` blocking(a~f)+v2 grounding 수량 함정.
- **곡선 (120 T2 셀 + T1 10)**: T1(cx1) **100%** → occupancy(cx5) 100% → section(cx11) 46% → intrusion(cx15) 46% → air(cx16) 62% → **thermo(cx18) 29%**. **핵심 수치: B1은 118/120 셀에서 "무사 배포"되는데 그중 42%(50셀)가 조용한 계약 위반** — "돌아간다≠맞다"의 정량 실물. 고장 클래스 분포 a=256·b=8·c=4·d=5. 같은 셀에서 우리 바인더=abort 32(정직 거부)·degrade 22·ok 66.
- **앵커 전부 명중**: env01/02→(a·d) 검출, env03→Motion 치환 후 (b) temporal blocking, **env04→thermo의 all()/for가 3×TS를 흡수해 B1도 sound 유지**(코퍼스 정량 "수량 편집=0" 라이브 재현 — B1이 이기는 지점도 정직 기록), env05→ALERT_SINK "actuator, role needs a notifier" blocking.
- 데이터: `adapt/b1_curve.json`(행 단위; 그림은 집필 때).

**B5(계약 없는 AST patcher) 실측 (2026-07-28, B1 스윕 합류)**: 후보 선택은 B1과 동일, 적용만 typed edit(ReplaceSelector/Member+splice 검증). **결과: soundness가 B1과 120/120 셀 완전 일치** — 무사 배포 118/120·조용한 결함 42%·고장 클래스 히스토그램(a256·b8·c4·d5)까지 동일. **"Structure is preserved; correctness is not"가 데이터 행으로 실증** — AST 규율은 배포 위생을 바꿀 뿐 정확성을 바꾸지 못하고, 정확성은 계약 층에서만 생긴다.

**B3(LLM 전체 재출력, Cursor식) 실측 (2026-07-28, 로컬 Qwen3.5-9B·temp 0·5템플릿×앵커6, `run_b3_check.py`·`b3_check.json`)**:
- 배포가능 28/30 (실패 2=env05에서 없는 ToastPublisher를 그대로 참조 — air는 원문을 통째 복사하며 무시).
- **원문 라인 생존율 89%(1,223/1,368)** — "나머지는 그대로 두라"고 명시하고 temp 0인데도 건드릴 이유 없는 코드의 11%가 다르게 재출력됨. splice는 구성상 100%.
- **항등성 대조(env00: 같은 집에 적응 = 정답은 무변경): 5/5 전부 항등 실패** — ①thermo·intrusion·section: 타입 태그를 **장치 id 태그로 치환**(`(#AirConditioner)`→`(#ai1)`) → 바인딩 규율 파괴, 인증 진입조차 불가(miter가 거부; 관대한 배포 검사는 통과 = 조용한 결함의 또 다른 얼굴) ②occupancy: `occupancy/1` 채널 DIVERGE 반례 실물(무단 행동 변화) ③air: 판정 TIMEOUT. 우리/B1은 이 셀에서 구성상 항등.
- 논문 문장: "재출력은 보존을 *보장할 수 없다*가 아니라, 가장 온순한 설정(온도 0·보존 지시 명시·동일 환경)에서조차 보존을 *실제로 하지 않는다*."

### M-J 실측 (2026-07-28) — relational tick induction: 무한-시간 인증서 (`smt/induction.py`·`run_induction.py`)

- **기계**: M2.6 tick-귀납의 relational판. 기저=tick 0(init 포함) 양쪽 실행→보존 방출 동일+공유 변수 동일; 스텝=임의 tick k≥1에서 "공유 변수 동일"을 가정(심볼 상태 주입, t=k·period 심볼)하고 **한 tick만** 실행→방출 동일+불변식 유지. 둘 다 UNSAT ⇒ **모든 tick에서 동일** — 창 없음. 과대근사(도달 불가 상태 포함)라 SAT=spurious 가능→bounded로 폴백(fail-closed); INDUCTIVE_EQUIV만 인증서.
- **결과 (redeploy 10행)**: **5행 무한-시간 승격**(intrusion 3+air li1·tp1) — 행당 **0.02~0.09초**(bounded 40~600초의 ~1000×). **movetocolor 미결 2건 해결**: 32-tick 몸통에서 300~600s TIMEOUT이던 obligation이 1-tick 스텝에선 0.06초 EQUIV. 보너스: bounded에서 창-공허(VACUOUS)였던 sp1 카메라·이메일 채널이 induction의 임의-상태 스텝에선 **비공허 증명**이 됨(도달 가능 상태 포함).
- **음성 대조(공허하지 않음의 증거)**: thermo 소스절단 3행=NOT_INDUCTIVE+invariant breaks, SAT가 정확히 bounded의 DIVERGE 채널에만 뜨고 교차-무관 채널(ts1→가습, hs1→AC·목표온도)은 EQUIV — bounded의 localization 패턴 재현. ap1=degraded publish만 SAT.
- W 재평가 서사 완성: "③구역은 같은 코드끼리라 relational induction이 자연 무기 — 스텝이 1-tick이라 W 소멸"이 실측으로 닫힘.

### M-K 실측 (2026-07-28) — E2E 지연 (`smt/run_e2e_latency.py`·`results/e2e_latency.json`)

- **런타임 경로(장치 고장)**: 표 룩업+stale 검사 = **0.12µs** → 사전 검증 아티팩트 배포. "ms" 주장은 4자릿수 보수적.
- **오프라인 경로(야간)**: contingency 컴파일 82ms/템플릿(슬라이싱+정적 포함) + 인증 = **induction 중앙값 0.06s**/행(bounded 폴백 101s 중앙·530s 최대) — 귀납 덕에 야간 인증이 사실상 공짜.
- **편집 경로(NL)**: extract 19ms + 규칙 분류 0.06ms + typed patch+splice 38ms ≈ **규칙 커버 요청은 증명서 포함 ~0.1초**; 자유 표현은 sLLM 분류 17.7s가 지배(이후 동일 결정론 경로).
- 두 경로 주장 실측 확정: 런타임=µs / 온라인=~0.1s(규칙)·~18s(자유 NL) / 인증=0.06s(귀납)~분(bounded 폴백).

### M-H 실측 (2026-07-28) — editir: NL 편집 요청 → typed edit (`adapt/editir.py`)

- **설계**: "NL names the delta" 그대로 — 분류기는 요청을 5종(param_change/device_swap/feature_drop/env_adapt/reject)으로 분류하고 **앵커만 명명**; Edit 객체는 patch.py 닫힌 연산(7종)이 합성; 정확성 판정은 기존 파이프라인(splice→계약→miter). 규칙 백엔드=결정론 코어(한/영 패턴+앵커 스캔: guard 상수·호출 인자·`:=` 설정 상수 3곳)+어휘 힌트 좁히기(여름/습도/co2...); **모호=거부**(후보 나열), LLM 백엔드는 같은 인터페이스 뒤 슬롯(7지선다+reject).
- **벤치마크 14케이스**(`edit_requests.json`+`run_edit_check.py`) **ALL PASS**: 3유형 전부 실현(25.5→26 파라미터·에어컨→선풍기 교체 4사이트·가습기/스피커 drop=슬라이서 연계) + 함정 4종 정확 거부 — ①"50을 55로"=2앵커 모호(여름 습도 힌트 주면 min_humid_summer로 유일화) ②air "800을 1000으로"=**guard 인라인+설정 상수 중복** → coordinated-change 함정을 거부가 정확히 잡음 ③"토스트 빼줘"=essential 거부 ④무관 요청/값 없는 요청=escalate.
- **E2E 실물**: "여름 최고 온도 25.5도를 26도로 바꿔줘" → ModifyPredicate → miter가 **편집이 행동으로 실재함**(온도측 채널 4개 DIVERGE)과 **무관 채널 보존**(sethumidifiermode EQUIV 증명)을 동시에 판정 = NL→편집→증명 전 경로 관통.
- 부수 수정: `template.py`의 `Binding = dict[...]`(3.9+ 전용 런타임 서브스크립트) → typing 별칭으로 3.8 호환; 전 adapt 하네스 3.8 스윕 ALL PASS.
- **LLM 백엔드 (2026-07-28 완성, 로컬 vLLM Qwen3.5-9B-AWQ @8002)**: 규칙이 거부한 자유 표현만 sLLM이 **델타 JSON**(7지선다: param/swap/drop/env/reject)으로 번역 → 같은 결정론 합성 경로 재진입(앵커·모호 거부·essential 가드 전부 그대로) — "NL names the delta" 문자 그대로. 컨텍스트=코드가 아니라 **사실 목록**(`:=` 상수·장치 태그·feature 이름). **자유 표현 6/6 ALL PASS**: "여름엔 좀 시원하게, 26도 기준으로"(old값 25.5 추론)·"음성 안내는 필요 없어"→VOICE_NOTICE·"미세먼지 PM10 기준을 100으로"→st_pm10·구어체 "한 30초 정도로"→absence_grace_sec·비요청 거부. **모델 특성 실측**: thinking OFF=grounding 실패(PM10·음성 매핑 못함) / thinking ON=전부 성공하나 사고 누출이 형식 예시 JSON을 인용 → 추출기를 "플레이스홀더(`<...>`) 제외+마지막 파싱성공 객체"로 강화해 해결. `adapt/llm.py`(stdlib urllib·enable_thinking 제어).

### M-F 실측 (2026-07-28) — miter obligation 분리 + relational miter v0 (`smt/obligations.py`·`smt/relational.py`)

- **obligation 분리 (①완료)**: 4개 인코더(M1 경로/M2 unroll/accel run/M3 cron)의 monolithic `Or(*mismatch)`를 **출력 시그니처(method/arity=계약 방출 단위)별 obligation**으로 분해, assumption 스위치 설치(`Implies(b_k, viol_k)`+`Or(*switches)`). 기존 `check()`=verdict-동일 monolithic, `check(b_k)`=계약별 질의. 전 `check_pair*`에 `split=` 모드+DIVERGE 시 위반 라벨 보고. **회귀: M1 187쌍(EQUIV 182/DIVERGE 5 전부 replay 재현)·M3 47쌍(43/3/1) flip 0**; accel 14쌍 EQUIV→TIMEOUT은 의미 flip이 아니라 60s 예산 경계(기준선도 57~3697s; 1h 예산 재검서 **14/14 전부 EQUIV 재확인**, 시간 분포도 기준선과 동일). **split 차분(306쌍·개별 obligation 551건): mono↔split 상반된 확정 판정 0건**; split 비용 mono 대비 ~11×(1,114s→12,087s) → 분업 확정: 게이트=mono, 오프라인 계약별 인증서=split. localization 실물: C05_003 divergence가 shape:count 하나로 좁혀지고 시그니처 obligation 2개는 개별 UNSAT 증명.
- **relational miter v0 (②T1 단계 완료)**: `check_relational(joi_old, joi_new, preserve)` — 양쪽 JoI 인코더+공유 입력, **preserve(보존 채널 집합)로 π-사영 후 비교** = R4 `P₁≡π(P₀)` 실물. 엔진: one-shot=경로 미터/periodic=tick unroll(동일 period 요구)/cron=③ 대기. **하네스(`run_relational`) 전 코퍼스 PASS**: 자기동치 196/196 EQUIV(M1 188+M2 표본 8) · 씨딩 인자 편집 104/104 검출+**104/104 정확 localize**(위반 라벨=변조 채널만) · drop 130/130 검출 + **preserve 사영 증명 130/130**(생존 채널 개별 UNSAT; 공허성 가드 포함 — 라벨 규약 미스로 사영이 안 물리면 FAIL).
- **인코더 근본 수정 1건**: 대입 간접 enum 비교(`v = (#Pump).mode; v == "normal"`)에서 타입 관찰이 끊겨 guard가 정적 거짓→모든 비교 공허(C03_007 검출). `collect_keys_and_types`에 var→key env 추가로 근본 수정; **v1 게이트 flip 0**(양쪽이 같은 모델 약점 공유했었음 — 입력 모델만 강화됨).

## 10. 다음 할 일 (2026-07-28 갱신 — adapt/ M-A~M-E + smt/ M-F·M-G 완료 후)

**완료 (§9 실측 참조)**: ~~템플릿 수작업 추출~~(5종) ~~효과 카탈로그~~(17 프로파일) ~~장애 주입 파일럿~~ ~~contingency 표~~(70행) ~~obligation 분리~~(M-F) ~~relational miter T1 단계~~(M-F) ~~새 구문 인코딩 v0~~(M-G: 파서+grounding+desugar, 스켈레톤 5/5) ~~redeploy 아티팩트 10개 인증~~(M-G: intrusion 3+air 1 완전 인증·부분채널/교차 localization 가시화).

1.~~obligation 분리~~ 2.~~relational miter+인증+certify.py~~ 3.~~새 구문 v0~~ 4.~~editir v0~~ 5.~~합성 환경 24+B1 곡선~~(M-I) — 완료.
~~relational induction~~(M-J) ~~editir LLM 백엔드~~ ~~B3~~ ~~B5 합류~~(B1과 120/120 soundness 일치) ~~E2E 지연~~(M-K) — 완료.
~~T1 편집 벤치 v0~~ — 완료(`adapt/make_t1_bench.py`→`t1_edit_bench.json`: **191케이스/158베이스**, param 143·swap 48, 전건 왕복 검증[editir가 gt 복원+splice 게이트 통과]; 미수록=적합 앵커 부재만, 복원 실패 0. 확장 여지: enum 파라미터·swap 쌍 추가·LLM 패러프레이즈 티어).
남은 큐:
1. M2 기본 K(유저) / st_tvoc 단위(유저).
2. 이후=집필(곡선 그림·문제 진술 반영·N=9 검정 단위·M-A~M-K 실측 종합) — **골격은 §11(2026-07-29 브레인스토밍: 세 질문 분해·C1~C4 7차 문안·티어 경계·TAP 방어)**.
3. Q3 purpose liveness 구현(§11 설계, 반나절, **유저 보류 중** — "구현은 아직, 논문 흐름 먼저"): certify verdict에 invalid→halt 추가+음성대조 3종. C3에 넣으려면 집필 중 선행 필요.
4. **editir.py** (NL→typed edit 7지선다 분류+거부; 유저 체감 데모 열쇠) + 편집 요청 벤치마크 저작(3유형×gt).
5. **합성 환경 인벤토리 N개** + **B1 복잡도 판별 곡선**(T1 382 vs T2 수작업) — eval 1호 그림.
6. E2E 병목 측정 (C5 위상 결정; 두 경로 latency 분리).
7. M2 기본 K 결정 (유저).
8. st_tvoc 단위 불일치(mg/m³ vs ppb) 판정 (유저).

## 11. 논문 골격 (2026-07-29 유저 논의 — 집필용 확정 재료; 탐색 로그는 §12로 분리)

### 세 질문 분해 = §1 등뼈 (제안)

바뀐 환경에서 시나리오에 묻는 독립된 세 질문. 각 층의 검사만으로는 위 층의 실패가 안 보임 → 층을 하나씩 빼면 조용한 실패가 정량으로 드러나는 ablation이 문제 진술에 내장된다 (각 행이 아래 행의 반례).

| 질문 | 판정 층 | 실패 모드 | 실측 |
|---|---|---|---|
| Q1 거기서 실행될 수 있는가 | 2축 바인딩(capability×space)+role 계약, 6클래스 | 배포되는데 계약 위반 (공간 오배선 포함) | B1 118/120 배포, 그중 42% 조용한 위반 |
| Q2 여전히 하던 일을 하는가 | relational miter+tick induction, 채널 단위 | 의도 밖 행동 변화, 얽힘 잔여 | B3 항등 0/5·11% 무단 재출력; cross-localization 반례 |
| Q3 여전히 존재할 이유가 있는가 | purpose liveness(필수 채널 non-vacuity) — **미구현** | 구조·행동 통과인데 필수 채널 영구 fire 불가 → 중단이 정답 | 음성대조 제작 예정 |

- 목적 한 문장: "환경이 바뀔 때(장치 장애·교체·이주·NL 수정) 배포된 시나리오가 **계속 실행될 자격이 있는지**를 로컬에서 자동 판정하고 인증서와 함께 산출한다."
- 공간 축(M-C 기구현·실측[3]): 1차로 Q1 제약, 서사적으로는 Q2·Q3의 원인 축 — 공간 무시 대체(거실 AC)는 배포·코드 무결인데 closed_loop 불성립→목적 사망. '23 edge 계보 문구 유지: "공간을 관리 단위가 아니라 바인딩 적합성의 제약으로 승격".
- §1 오프닝 후보: 한 집의 단일 스토리로 세 층 관통 — 이사(Q1 공간 재바인딩)→제습기 장애 대체(Q2 보존)→재실 센서 사망·무대체(Q3 중단).

### Q3 purpose liveness — 설계 (구현 보류: 유저 "구현은 아직", 반나절 규모)

- **현 구멍(코드 확인)**: `certify.py:71-74` — VACUOUS는 라벨만 붙고 defect도 아님 → 필수 채널 전부 공허해도 verdict=certified(proofs=0). 얽힘(drop 잔여로 공유 guard 항상 false 등)으로 필수 채널이 fire 불가능해진 artifact가 인증됨.
- verdict 격자 4분: certified / degraded-visible / **invalid→halt** / defect (+undecided). 규칙: 필수 role 채널이 base에선 도달 가능·artifact에서 VACUOUS → invalid, contingency row를 abort로 강등. optional 공허=라벨 유지(오탐 중단 금지). base부터 공허=템플릿 저작 문제로 분리 표시.
- 구현 5단계: ①relational 도달가능성 base/artifact 양측 분리 ②essential role→canonical 채널 라벨 매핑 소함수 ③certify verdict 추가 ④contingency 스탬핑 시 invalid→abort 강등 ⑤음성대조 3종(얽힘 drop이 이웃 필수 채널 살해 — 구조검사·기존 certify 모두 통과, 새 층만 잡음 / optional 공허→certified 유지 / base 공허→저작 문제).
- 구조적 절반은 기구현: `contingency.py:134` abort(필수 role 상실+무대체, 한국어 통지) / editir essential drop 거부 / check_binding blocking. 빈 것은 의미적 절반뿐.
- 용어: field-standard **purpose liveness / non-vacuity**만 사용. "service validity"는 동기 문단의 일상어로만.
- 논문 문장: "시나리오는 장치 목록 검사가 실패해서가 아니라, **그 존재 이유가 더 이상 발생할 수 없음이 증명되어** 중단된다."
- 이웃 선제 인용: vacuity detection(Beer et al. — 기법은 기존, 승격이 우리 것), KAOS obstacle analysis(모델 수준), Shelton&Koopman graceful degradation(사람이 utility 저작), SOC substitution(시그니처 수준·무증명). 신규성 = 공허성을 시나리오 존속 판정 기준으로 승격 + 중단 결정 구동 + 대체 탐색(bind) 실패 후에만 중단.

### Contribution 4개 (7차 문안 — §6 5차 후보의 재구성)

- **C1 문제 정식화**: 병목=생성이 아니라 판정. "실행 가능 ≠ 올바름 ≠ 유의미" 3층 분해 + 각 층의 조용한 실패 정량(42% / 항등 0/5 / vacuity 케이스).
- **C2 계약 층**: 목적 템플릿 role 계약 + capability×space 2축 바인딩. 저작=템플릿 저자 1회·최종 사용자 0회(K1 방어를 contribution 문장에 내장). 결정 5종(keep/substitute/realize/drop_feature/**abort**) — abort가 1급 출력이라는 것 자체가 주장.
- **C3 다름의 판정**: 채널 단위 4분(certified/degraded-visible/defect/invalid→halt). 보존=miter+induction, 열화=선언·가시화, 존재 이유=liveness. 얽힘(공유 line 잔여)의 의미 판정 포함. 증명 기계=기존 기법(EC/SEC·differential verification·vacuity detection) 명시, 신규성=판정 대상과 분류 격자.
- **C4 전 로컬 두-경로 시스템**: 오프라인 contingency 컴파일+인증(행당 0.06s) / 런타임 µs 룩업 / NL 편집=델타 명명 후 같은 결정론 경로 합류. E2E 실측.
- LLM 노동 분할 문장(C4 핵심): "LLM은 두 자리에만 있다: 자연어를 닫힌 델타 어휘로 번역하는 입구, 재저작 후보를 제안하는 상단. 두 자리 모두 출력이 결정론 게이트를 통과해야만 효력을 가지며, **시스템의 어떤 판정도 LLM의 올바름을 전제하지 않는다.**"

### LLM의 자리와 티어 경계 (유저 질의 확정)

| 티어 | 수정 규모 | 처리 | LLM |
|---|---|---|---|
| 0 | 코드 무변경(셀렉터 수준) | 재바인딩 β만 | 없음 |
| 1 | 상수·기기·기능 단위 | typed edit(7 ops)+재인증 | 델타 명명만(규칙 우선, sLLM 후순위) |
| 2 | 구조 변경(새 guard/블록/시간 구조/역할) | 목적 템플릿 재저작 | 후보 **생성기** 가능(미구현) |
| ⊥ | 어느 층도 판정 불가 | reject+이유+후보 | 없음(fail-closed) |

- 경계의 동치 정의 2개: (구문) 기존 AST 노드의 수정·삭제로 표현 vs 앵커 없는 새 노드 합성 필요 / (계약) role·채널 집합 불변·감소 vs **증가**. 경계는 미학이 아니라 운영적: 규칙→sLLM 델타 환원 시도 실패 = 티어 2 승격(editir reject가 신호).
- 티어 2 예시(10~30줄+role 1~2개 신규): 조건 분기 신설("미세먼지 나쁠 땐 환기 대신 청정기") / 채널 추가("침입 시 조명도") / 시퀀스 신설("환기 10분 후 청정기") / 목적 변경("피크 시간 절전") / 시나리오 병합(클래스 e). 반례(티어 1로 환원, 실측): "방마다"(for/all 흡수, env04·코퍼스 수량편집=0), "여름엔 시원하게"(L-티어 param 환원).
- 깊은 이유: **새 채널은 비교 대상이 없다** — miter는 old가 있어야 성립. 새 기능의 잣대는 계약뿐 → 티어 2가 "재저작"인 이유(코드+계약 둘 다 신규 저작 = 템플릿 수준으로 승격). LLM 개입 범위가 취향이 아니라 **증명 가능성의 경계에서 도출**됨 — "왜 LLM을 더/덜 안 썼나" 질문 무력화.
- 티어 2 스코프 권고: 생성은 선행연구(v1 포함)로 스코프 아웃, 우리는 "무엇이 오든 판정하는 층". 티어 2는 에스컬레이션 사다리 한 칸으로만 명시.

### 증명 가능성 경계 — claim ladder (티어 2 확장)

- **증명 가능(전부 소진)**: (i) 기존 채널 보존 — old 있는 채널엔 miter 그대로. 생성의 최대 위험=조용한 부수 파괴(B3 11% 무단 재출력, 얽힘 경유 포함)가 전부 사정거리 안. (ii) 새 채널의 계약 준수(Q1)·liveness(Q3)·안전 불변식(효과 방향, "난방·냉방 동시 금지" 류 — 단일 프로그램 성질).
- **원리적 불가**: 새 채널의 의도 일치(oracle problem) — spec 없이 어떤 방법으로도 불가. "해결"이 아니라 **표면 최소화** 3겹: ①환원 우선(티어 1에선 old 코드=암묵 spec, 잔여 0) ②명시 spec은 새 role 1개 분량(프로그램 전체 아님) ③잔여는 채널 1개 분량 렌더된 diff로 표면화. K1과의 차이 = 떠넘김이 아니라 기계가 증명 가능한 것을 소진한 뒤의 원리적 잔여.
- 부수 효과: **"왜 전부 재생성하지 않는가"의 최종 답** — 재생성=증명 불가 표면을 프로그램 전체로 확대(모든 채널이 새 것=비교 대상 소멸), 편집=델타로 축소. B1/B3 수치가 각주.

### 티어 2 확장의 3층 처리 (유저 정리의 수정본 — "안 놓기"와 "잡기"의 분리)

- 섞임 벡터 5종(실재): **period 전역성**(모든 시간 guard가 t=k·period 위 — 주기 변경은 채널-로컬이 아님) / **ordered 의미론 순서 민감성**(중간 삽입이 방출 집합 불변이어도 align: 의무 파괴) / **상태 공유**(`:=`·tick-지속 env·GV) / **for 수량 구조**(삽입 효과가 인스턴스 수만큼 증폭) / **변수·인자 포획**.
- **핵심 분리**: 안 섞이게 *놓는* 것=합성 규율(생성 쪽 의무), 섞였는지 *잡는* 것=판정(**원인 불문** — miter는 벡터 열거에 의존하지 않음; cross-localization 실측이 증거: 경로를 미리 모르고도 잡음). 규율은 통과 확률을 만들고 **신뢰는 게이트가 만든다** — 규율 준수도 검사 없이 안 믿음(refactoring 엔진 버그 문헌과 동일 철학, splice 게이트).
- 합성 규율 4칙: ①append-only(중간 삽입 금지 — π-사영은 sig별이라 말미 추가 새 채널 방출은 기존 채널 사영에 불가시) ②fresh 변수·기존 변수 write 금지(read는 계약에 선언) ③기존 채널 sig 방출 금지 ④**동일 period일 때만 같은 스크립트** — 다른 주기 필요 확장(1s 루프에 10분 리포트 등)은 **별도 시나리오+간섭 검사**(클래스 e, footprint 교차)로 공존 판정. "추가=같은 파일 삽입" 가정 폐기.
- 정리 문장: "합성 규율이 새 코드를 섞임 없을 자리에 놓고, 판정이 규율과 무관하게 기존 채널 보존을 원인 불문으로 증명하며, 표면화가 증명 불가능한 잔여만 렌더된 diff로 보인다." 이 불신 관계가 있어 LLM을 생성석에 앉혀도 시스템이 무너지지 않음(C4 접속).
- 정직 각주: cron 엔진·교차-period 간섭은 설계/부분 구현(footprint 정적 검사만, cron 스켈레톤 미노출).

### 비판적 이웃 점검 (novelty 방어선 — 2026-07-29 논의 결론)

- **인정하고 선제 인용**: 하드웨어 EC/SEC(miter·π-사영=don't care·tick induction=product machine k-induction — 기법 신규성 주장 즉사) / RVT·SymDiff·differential assertion checking(부분 동치=relative correctness로 기존) / refactoring 엔진(닫힌 편집 카탈로그+게이트 구조 동형; 엔진 버그 문헌은 우리 게이트 철학의 근거) / Coccinelle·SmPL("수정 부위 탐색·치환"의 산업 선례, 무증명) / SPL·variability-aware 검증("Certify once" 정면 비교 상대 — 한정구 필수: "부울 feature가 아닌 **열린 인벤토리**[인스턴스 수·수량자·GV] 위의 재바인딩") / ENTRUST·QoSMOS(장애→재구성→배포 전 보증의 정신적 선행, 모델 수준·무코드).
- **남는 신규성 3개**: ①의도된 다름의 4분 판정(2값 EQUIV/DIVERGE를 계약으로 열화·결함·무효로 분화, 열화·중단이 인증서의 1급 결과) ②NL→델타→typed edit→인증서 전 로컬 파이프라인(제안/판정 분리의 구조적 강제) ③얽힘의 의미 판정(구문 계보 commit untangling·feature unweaving이 못 하는 잔여 판정).
- **"간단 치환" 반론 2종+반박**: (A) "slicing+impact analysis로 충분" → 공유 line 잔여는 slice 삭제가 아니라 의미 잔여 판정, cross-localization 실측 반례. (B) "DSL 작아 자명" → 판정의 자명함≠판정의 유의미함; vacuity 함정 3종 실측(clock epoch·1524-tick 창·대입 간접 enum)이 "naive 인코딩은 조용히 통과"의 증거 — 어려움은 solver가 아니라 obligation 설계.
- 전략 한 줄: "어떻게 증명하나=기존 기술, 무엇을 증명 대상으로 삼고 다름을 어떻게 분류하나=우리 것" — §2에서 저 계보 전부를 부품 공급자로 배치.
- 인용 전 원문확인 필요(락): differential assertion checking, Shelton&Koopman, commit untangling, Beer et al. vacuity.

### TAP 저평가 방어 (유저 질의 2026-07-29)

리뷰어 심상 모델: "시나리오=TAP 규칙(IF trigger THEN action), 적응=배치(재매핑)" → 난이도 저평가. 방어 4겹:
1. **용어 락 재사용(v1)**: "reactive-temporal code vs TAP rules"를 첫 페이지에서 선언 + v1 Table 1 4칼럼(상태·시간·수량·다채널 축) 재활용.
2. **구성적 반박**: "배치만 잘하면"은 문자 그대로 **B1**(+AST 규율=B5)이고 이미 구현·측정됨 — 118/120 배포·42% 조용한 위반·B5 soundness 120/120 동일. 리뷰어의 제안을 베이스라인으로 실체화해 논변이 아니라 측정으로 답함.
3. **양보 구조(곡선의 힘)**: TAP급 복잡도(cx1·T1)에서는 배치만으로 100% — 먼저 인정하고 "우리 문제는 TAP에서 시작하지 않는다"고 명시. 난이도는 TAP이 표현 못 하는 구조(지속 상태·cooldown·hysteresis·수량자·순서)와 함께 자람: 100%→29%. (b) temporal·cooldown vacuity·얽힘 사례 전부 non-TAP 구조 발.
4. **§1 오프닝 예시를 TAP 오독 불가능하게**: cooldown+hysteresis+수량자 포함(thermo 계열). TAP 계보(SafeTAP 등)는 related_works_v2.md + v1 인벤토리 락 "TAP=intent EMPTY 증명" 재사용.

### 변화의 비대칭 — 빼기=닫힌 세계 / 더하기=열린 세계 (2026-07-29 유저 논의: 문제 정의 재료)

- 유저 관찰: 복잡 시나리오(보안모드 등)도 **장애·drop 방향은 사전 준비**(대체 기기·코드 segment 미리 저작)로 풀 수 있다 → 맞고, 그것이 곧 contingency 표(우리는 "깔끔하게 미리"를 행별 인증서까지 격상). #ifdef 반론과 동일 계보, 이미 흡수.
- **핵심 비대칭**: 빼기는 **닫힌 세계** — 고장날 수 있는 것=설치된 것, (시나리오×role×장치) 유한 → 전수 오프라인 컴파일+인증 가능. 더하기는 **열린 세계** — 도착할 수 있는 것(새 타입·새 의미론·새 단위)은 열거 불가 → 사전 컴파일 원리적 불가, **도착 시점 판정**만 가능. 이 비대칭이 두-경로 아키텍처(오프라인 표+µs 룩업 / 온라인 바인딩+초 단위 인증)를 취향이 아니라 **세계의 열림성에서 도출**함 — 문제 정의·필요성 문단에 쓸 것.
- 열린 세계에서 미지의 장치를 판정 가능하게 하는 것 = **role 계약** (장치 목록이 아니라 role에 대해 저작 → 본 적 없는 장치도 capability×space 프로파일로 판정). "Certify once bind anywhere"의 정확한 의미가 이것.
- **추가의 4 케이스 분류**:
  ① 동일 타입 인스턴스 추가 → 수량자 grounding이 흡수(for/all) 또는 fail-closed(단수 읽기 trap (c)); 표 신선도 재컴파일 트리거(리스크 ⑥).
  ② 더 나은 후보 도착(대체 운전 중이던 role의 원 타입 복귀 등) → 개선 재바인딩+재인증; **drop됐던 feature의 복원** = drop의 역연산, bind 재실행으로 자연 도출(둘 다 인증 경유) — 대칭 서사.
  ③ **조금 다른 기능의 서비스** → 최난 케이스(아래 별도 항).
  ④ 완전 새 기능 → 티어 2(비교 대상 없음 → 계약 신규 저작, §11 티어 경계).
  (+횡단: 새 장치가 기존 시나리오와 간섭 — 클래스 e, footprint 교차.)
- **③ "비슷함은 위험을 숨긴다" (near-miss가 본론)**: 터무니없는 대체는 아무 검사나 잡음; 그럴듯한 대체가 조용히 틀림 — B1 구현 중 실측 서사(Presence→AirConditioner는 자명 오답 → 정교화하자 Presence→**MotionSensor**가 나왔고 이것이 temporal (b)를 노출), fault class (b)(d)가 전부 near-miss 전용, st_tvoc mg/m³ vs ppb 실사례(유저 판정 대기). 효과가 다른데 role은 채울 수 있는 경우 = composite **realize**(인증 실현 교체, composites.json 4종)가 담당. v1 related-works 락 "near-collision=LACE+AwareAuto만" 재사용.
- 필요성 문장 후보: "사전 준비는 빼기의 세계에서만 완결된다. 더하기의 세계에는 도착 시점 판정 기계가 필요하며, 그 판정은 생성이 아니라 인증이어야 한다(B1 42%)."

### "검증된 채 배포" 전제 하의 문제 공간 P1~P5 (2026-07-29 — §1 세 번째 축)

- 락 문장 후보: **"검증은 이벤트, 유효성은 생애주기"** — 벤더 검증=(코드×환경×시점) 스냅샷; 시나리오는 다른 집·변하는 환경·수정·조합 속에서 수년을 삶.
- **P1 바인딩 비이식성**: 인증은 바인딩을 건너 이동 안 함 — "검증된 시나리오 설치"의 실제 의미="검증 유효 조건을 방금 깨뜨림". 실측=B1 42%. 답=role 계약+2축 바인딩+재인증("Certify once bind anywhere"=이 문제의 해법명).
- **P2 시간 부패**: 장애·교체·추가가 검증 스냅샷을 **조용히** 무효화(시나리오는 계속 돎). 답=contingency 두-경로(닫힌 방향 사전 전수/열린 방향 도착 시점).
- **P3 편집 이탈**: 첫 수정에서 인증 이탈; 벤더 재검증 불가(환경 무지+프라이버시+지연) → 로컬 재인증 기계 없으면 생태계가 첫 수정에서 끝남. 답=editir+patch+miter/induction(0.1s+0.06s).
- **P4 조합 무인증**: 개별 인증≠내 집 N개 조합의 인증(GV·장치·전원 간섭, 클래스 e — 조합은 본질적으로 로컬만 앎). 답=footprint 교차+(열린 논점)GV 생산자-소비자 계약.
- **P5 주장의 검사가능성**: "verified" 뱃지가 아니라 로컬 재확인 가능한 인증서(무엇에 대해=계약/어떤 성질/어떤 전제)가 코드와 동반 이동해야 — proof-carrying scenario; 입고 인증서 사슬이 구현. 계약 없이 온 "검증된" 코드=판정 불가능한 코드(P1~P4의 전제 조건).
- **스코프 아웃 명시**: 원저작의 기능적 올바름(저자 의도 부합)=벤더/커뮤니티 검증으로 주어짐 — 우리 책임=지위의 **보존**만("행동 보존≠절대 정확성" claim ladder가 이 전제의 자연 귀결).
- §1 3축 완성: Q1~Q3=무엇을 판정 / 닫힌·열린 세계=언제 판정 / P1~P5=**왜 로컬이어야·왜 벤더 검증으로 불충분**.

### HA 관점 적응 문제 4종 — 최난=상태 provenance (2026-07-29 유저 구체화)

- 유저 제시 4종(Home Assistant 실감): ①state 도메인/타입 불일치(on/off vs locked/unlocked enum) ②service 방식 차이(Hue 밝기·색온도 vs Switch on/off) ③재실=GV(헬퍼) vs PresenceSensor 직독 ④헬퍼·타이머 구조 의존(가상 변수·타이머로 상태 기억).
- **서열**: ①=카탈로그 value domain+enum 정렬 1회 저작(class d, 기계 있음) < ②=requires.control 충돌→realize/degrade/abort(Light→Switch 워크스루 그대로) < ④로컬 절반=tick 상태+관용구 어휘(해결) < **③+④공유 절반=최난**.
- **③이 최난인 이유 4겹**: (a)판정 스코프 초과 — GV 의미는 생산자 시나리오가 정의, 로컬 판정 불가(GV=자유입력 락의 경계; 보안모드 ③과 동일 구멍) (b)의미 차=시간적 — 헬퍼=파생(hold/hysteresis) vs 센서=순간값 → class (b) near-miss (c)staleness 결합 — 센서→GV 대체=타 아티팩트 생존에 결속(class e stale; Q3 비로컬화) (d)**헬퍼 의미=무문서·분산** — 카탈로그 ground truth 없음, 갱신 로직이 타 automation에 산재 → 의도 메타데이터 oracle 경계.
- 완화 경로: **GV 생산자-소비자 계약**(인벤토리 수준 등록 — 장치뿐 아니라 시나리오 간 데이터 채널에도 계약 판정; 기존 열린 설계점의 동기 강화) + **상태 실현(state realization)** — 헬퍼 파생 로직=관용구 조합(hold/debounce)이므로 생산 블록을 로컬 합성·인증해 물질화(composite realize의 상태판). 잔여=무문서 헬퍼의 의도 복원 불가 → "행동은 증명, 의미 주석은 정합성+표면화" 경계 선언.
- 집필 가치: HA 4종=우리 P4·class (b)(e)의 실세계 대응물 — 문제 진술 외적 타당성 근거.

## 12. 아이디어 브레인스토밍 로그 (2026-07-29 — 탐색적·채택 미정; 노이즈 방지를 위해 골격과 분리)

**성격**: 아래는 논의만 됐고 채택·구현 결정이 나지 않은 탐색 기록. 집필 골격은 §0·§11만 참조할 것. 각 항목의 결론(기각/optional 카드/측정 전환)은 항목 내 명시.

### 입고 구조화 — 인증된 템플릿 lift (2026-07-29 유저 제안: "오프라인에 유리한 구조를 미리")

- 유저 제안: 임의의 지저분한 입력 시나리오(벤더/DB, 주석 있어도 role이 블록 경계와 어긋남 — 실물=`paper_v2/joi_automation_codes.json` idx2 "보안모드 자동제어": 안내가 2블록에 분산·rearm이 occupancy GV에 얽힘·attendance 부수 채널)를 그때그때 처리하지 말고, **입고 시 클라우드 AI로라도 우리 템플릿으로 구조화**(로직·목적·의도·결과 유지 전제) → 이후 수정·교체·추가·검증이 전부 쉬워짐.
- **핵심 관찰**: "유지 전제"=행동 보존=우리 Q2 기계가 증명하는 것. 구도=untrusted lifter(클라우드 LLM) + 로컬 miter 검증(preserve=전 채널, induction) = **translation validation의 입고 적용**. editir의 제안/판정 분리를 ingestion에 재적용 — 조용히 틀린 구조화는 반례와 함께 기각, 신뢰는 인증서에서.
- 보안 제약과 양립: 클라우드 금지 근거=사용자 사적 데이터. 벤더/DB 시나리오=공개 아티팩트→입고 클라우드 lift 허용; 사용자 자작=로컬 sLLM lift(실패율↑, 실패=비구조 등급 잔류=전체 교체만 가능한 축소 서비스). 출처별 등급.
- **프레이밍: schema-on-write** (vs schema-on-read) — 매 편집마다 해석 대신 입고 1회 구조 부여; 시나리오=1회 입고·수년 다회 적응이라 상각 승리. 두-경로→**세 시간축**: 입고(1회·분·클라우드가능) / 야간(0.06s/행·로컬) / 런타임(0.12µs·로컬).
- 이득 3: ①**얽힘 선해소**(분산 안내→ANNOUNCER role, 버튼 해제→optional feature, 부수 채널→별도 feature — drop이 수술 아닌 표 행; 얽힘 비용을 입고 1회로 상각) ②**검증 가능성 by construction**(canonical 스켈레톤=인코더가 다루는 관용구만→UNSUPPORTED·vacuity 함정 구조적 감소) ③**변경 범위 확장**(합성 규율 4칙이 관례가 아니라 템플릿 모양 자체=3구역 by construction→티어 2 확장 지점 구조화).
- **Novelty 이웃=verified lifting**(QBS·STNG·Dexter·Casper — 선제 인용 필수). 델타 3: ①lift 대상=성능 DSL이 아니라 **적응 인터페이스**(role·공간·essential·param·feature 계약) ②**인증서 사슬**(입고 인증서[원본≡canonical]가 모든 후속 적응 인증서의 밑변→최종 배포물이 벤더 원본까지 의미 소급) ③reactive-temporal+tick induction 도메인.
- **K1 재방어 강화**: "템플릿 누가 저작하나" → "기계가 기존 시나리오에서 lift + 동치는 증명 + 저자는 의도 플래그만 검토". 저작 비용 반론 구조적 약화.
- **정직한 경계(티어 2와 대칭)**: miter가 인증하는 건 lift의 행동뿐; essential 플래그·purpose·param 의미 등 **의도 메타데이터는 인증 불가**(oracle 경계). 완화=정합성 obligation(essential 채널은 base에서 live·role members=코드 사용 일치 — M-B 왕복 검사 꼴)+1회 검토 표면화. claim ladder: "행동은 증명, 의도 주석은 정합성 검사+표면화".
- **평가 보너스=N=9 정면 답**: 수작업 5종→joi_automation_codes 10종·코퍼스 382종 lift로 "lift 성공률+동치 인증률" 측정, 템플릿 수십~수백 확장→검정 단위(환경×템플릿×채널) 실물 규모. 대조군 공짜: 인증 없는 LLM 구조화(B3의 입고판)의 silent-wrong 표.
- 리스크: lift 실패율(정직 측정) / canonical 문법 표현력 한계 / 의도 오주석의 하류 파급(오판 abort — 정합성 검사로 부분 완화).

### cron 인코딩 설계 (2026-07-29 — 미구현이지만 같은 기계 꼴, 이월 근거 명문화)

- **환원**: cron=새 엔진 아님 — tick 인덱스 k→**발화 인덱스 j**, 자유 달력 심볼→**cron 술어의 산술 제약**. τ_j = T0 + j·gap (매일: gap=86400 상수, T0=D0·86400+7·3600·D0∈ℤ); 입력=발화별 자유, 상태 체인·방출·obligation 동형.
- **창 의미 변화**: w_cap=32가 period 1s에선 32초, cron에선 발화 32회=32일 — 같은 전개 비용에 지평 수천 배 (3일 cooldown류가 bounded에서 자연 생존).
- **공짜 판정 2**: ①달력 guard 정적 사멸 (cron이 hour 고정→본문의 다른 시각 guard=영구 거짓; cron 시각 편집 후 본문 guard 방치 = NL 편집 경로의 조용한 dead code→vacuity 라벨) ②**불규칙 cron×cooldown 반례 클래스**: "평일 9시"→gap_j∈{86400,259200} 유한 선택(여전히 선형 산술) — 2일 cooldown이 주말 경계에서만 행동 분기, solver가 금→월 반례 산출. period 세계에 없는 cron 고유 고장.
- **miter**: 같은 spec=발화별 페어링(동형). 다른 spec=발화 시각 **합집합 공통 타임라인**에 lift, 각자 자기 발화만 활성 (실시간 hyperperiod 분석 꼴; period×cron 혼합도 동일).
- **induction**: base=발화 0, step=임의 j(상태 심볼 시드, gap=선택 심볼) — tick induction 기계 그대로 이월, "주말 경계 포함 모든 발화" 인증서.
- 집필: 인코딩 절 1단락+주말-cooldown 반례 예시로 미구현 상태에서도 설계 완결성 제시. 실측 각주: 보안모드 시나리오 인코더 갭 1건=weekday enum 조건("weekday cond in one-shot" UNSUPPORTED — clock.month/day와 동일 방식[enum 공유 상수]으로 닫히는 소규모 확장; 채널 4종 추출·수량자 trap은 정상 작동 확인).

### "SMT를 IoT용으로 변형?" 논의 결론 (2026-07-29 유저 브레인스토밍)

- 유저 제안: trigger=변수·timestamp의 복잡한 묶음인 IoT 특성에 맞춰 SMT 자체를 periodic/temporal로 변형 → 돌파구?
- **결론: solver 변형 비추** — ①병목 아님(실측: obligation 전부 LIA+불리언+enum 결정 단편, 느림의 원인=전개 방식이었고 induction으로 0.06s) ②선행 두꺼움(timed automata/UPPAAL·MTL/STL 인코딩·TAP 한정 SafeTAP/Soteria/IoTSan — "IoT용 SMT 이론" 주장 시 전면 비교, 우리 무기 안 쓰임) ③학회 미스매치(solver 결정절차=CAV/TACAS).
- **진짜 광맥 3**: ①**CHC+Spacer(IC3/PDR)로 invariant 자동 합성** — 최대 변환점: 보안모드류 spurious step(GV 자유입력) 문제에서 손 invariant(I₁ sync 단조·I₂ 미러 동기)를 Spacer 합성으로 대체; tick 전이→CHC 기계적; relational CHC/product program 계보 인용; induction이 "실패=bounded 폴백"→"실패=자동 강화 재시도"로 승격. 파일럿 1건=하루 안쪽(보류). ②**difference logic 규율**: cooldown·debounce·cron gap=τ차 제약 단편 유지 명시→"왜 빠른가"가 원리가 됨. ③**tick/발화 프로그램 소이론의 정식화**(프레젠테이션 기여): trigger=guard 식, action=guarded 방출, 시나리오=tick 반복; 관용구(엣지·cooldown·hysteresis·init-once·변경시-set)별 인증 obligation 스키마 — TAP 검증 계보가 못 다루는 상태·시간이 이 단편에서 판정됨.
- 돌파구의 정직 평가: field-level이 되려면 "tick 프로그램 동치의 결정 단편 특성화+전용 절차 N×" 꼴(PL 이론) — 가능하나 수요 없음(이미 초 미만). **돌파구는 solver 쪽이 아니라 문제 쪽**(무엇을 obligation으로 만드나)이라는 게 프로젝트 일관 결론.
- 프레이밍 락 후보: "우리는 solver를 확장하지 않는다. IoT 시간 관용구가 결정 가능 단편(LIA+DL+enum)으로 컴파일되도록 언어와 obligation을 설계했다 — 초 미만·로컬 검증은 solver의 기적이 아니라 이 설계 결정이다." ("왜 새 이론 안 만들었나"를 약점→설계 원칙으로 반전)

### CFG/DFG/PDG/slicing 적용 논의 (2026-07-29 — 얽힘 지수 + lift 골격)

- 표준 CFG=자명(tick 본문=guarded DAG) — 필요한 변형: tick 본문=루프 몸체, 상태 변수=**loop-carried dependence**(`was_pushed=pushed` 류) + GV 간선(시나리오 간).
- **DFG line-역할 분류(기계적)**: source(장치/GV/Clock 읽기)/gate(guard로만)/state(tick 경계 넘음)/sink(액추에이터·알림·GV set)/config(`:=` 상수=editir 앵커). +**관용구 인식**(PDG 서브그래프 패턴): 엣지 검출·cooldown·hysteresis·init-시드·변경시에만-set — 보안모드의 사람 주석 수준 "구조적 의도"가 자동 복원.
- **backward slice(sink별)=trigger 묶음의 기계적 분해**: 슬라이스 서로소=독립 TAP 묶음(B1 충분 영역) / 겹침=얽힘의 실체. 보안모드: speak 슬라이스=버튼만, security_mode 슬라이스=md 경유 버튼까지 포함, attendance⊂전이 — drop #3 최난이 그래프에서 사전 가시화.
- **신규 재료 ①: 얽힘 지수** — sink 쌍별 슬라이스 Jaccard 겹침 평균(시나리오당 스칼라). **B1 곡선 x축의 예측 변수 가설**: 서로소→100%, 겹침↑→29% 상관이 코퍼스 382+템플릿에서 나오면 "복잡도→어려움"이 "얽힘=어려움의 원인"이라는 측정 인과로 승격. 순수 정적·코퍼스 전수 몇 초. (실험 후보, 저비용)
- **신규 재료 ②: PDG-유도 인증 lift** — 입고 구조화의 LLM 몫 축소: sink 채널 묶음+backward slice=role 후보, 겹침=공유 상태 분리, 관용구=블록 라벨까지 결정론; LLM은 **이름·essential 추정만**, miter 최종 인증. lift 실패율 직접 하락.
- **한계=분업 근거**: 정적 그래프는 "의존한다"까지, "어떻게"는 불가(과대근사) — 잔여 판정·공허성·동치는 의미 질문=SMT 몫. 락 문장: "그래프=발견 / 계약=선언 / SMT=판정" (slicer M-D→miter 현 파이프라인이 이 분업의 구현).
- 의도 2층 분리: **구조적 의도**(어느 채널의 trigger 묶음·어떤 관용구 부품)=기계적 / **목적적 의도**(essential·임계값의 이유)=oracle 경계, 어떤 그래프로도 불가→role 계약의 존재 이유.
- novelty 정직: 기법 자체(Weiser·Horwitz-Reps) 주장 금물; 남는 것=tick/GV-aware 변형(소소)·얽힘 지수×B1 상관(실증 후보)·PDG-유도 lift(입고 결합).

### 소형 모델 논의 (2026-07-29 — v1 이벤트 추출 회귀는 기각, editir 증류는 강화 카드)

- 유저 제안: v1의 timeline IR 경계값 이벤트 추출(week 단위 폭발)을 9B보다 훨씬 작은 훈련 모델로 → 설득력?
- **기각 3근거**: ①문제 소멸 — v2 miter는 이벤트를 추출하지 않음(심볼 입력=전 이벤트 양화, week=induction 0.06s) ②위치 오염 — 검사 경로에 학습 모델=under-extraction이 silent-miss, "어떤 판정도 LLM 올바름을 전제하지 않는다" 락과 정면 모순(크기 아닌 위치 문제) ③week 시뮬 필요 시 이벤트 스케줄=**solver 반례 witness**(반례 replay 자산)로 충분.
- **채택 방향(optional 강화 카드)**: editir sLLM 폴백(자유표현→델타 JSON 5종)을 9B→sub-1B 증류 — 제안 경로라 안전(오류=게이트 거부), 닫힌 어휘라 증류 적합, 데이터 보유(T1 벤치 191 왕복검증+edit_requests+패러프레이즈 티어), 스토리="허브 기기(라즈베리파이급)에서 완전 로컬 NL 편집"으로 C4 로컬 주장이 하드웨어 사양까지 하강. 집필 필수 아님.

### 전수 템플릿 DB 논의 (2026-07-29 유저 제안 — "모든 로직 미리 + 1B replacement")

- 유저 제안: 모든 코드 로직(템플릿)을 경우의 수 전수로 미리 구축, 편집=1B급의 argument/tag/service replacement만; retrieval·용량은 양자화/RAG로; joi_automation_codes 템플릿화 가능? 오프라인이니 클라우드·시간 무제한 허용?
- **용량=비문제(계산)**: 시나리오 ~2KB×382<1MB; 1만 템플릿=50MB+임베딩 수십MB — 라즈베리파이급. 양자화/RAG 최적화=오버엔지니어링. 진짜 문제=retrieval 품질.
- **"전수"의 올바른 형태=곱이 아니라 축**: 시나리오=skeleton×slots×features로 인수분해. skeleton은 유한·소수(idiom-multiplicity·category_v2 24종·보안모드=전부 알려진 관용구 분해), slot 공간은 열거 불요(바인딩 β가 파라메트릭). contingency 표 교훈 재적용: **DB=인증된 skeleton family, 구체화=주문형** → 비용이 skeleton 수에 선형. **제품 전개 금지**(feature 부분집합×기기 조합 사전 구체화=지수 폭발).
- **가능성 질문→측정 전환**: =입고 lift와 동일 질문. 10종+382를 lift 파이프라인에 넣어 lift 성공률+동치 인증률=skeleton family 커버리지 주장. 오프라인 클라우드·시간 무제한 허용하되 인증 경제학 분리: skeleton 인증(계약 정합·liveness)=구축 시 1회 / 바인딩 인증=홈별 주문형(초 단위) — "Certify once bind anywhere"가 DB 운영 원리로. long tail=비구조 등급 폴백, 비율 자체가 보고 수치.
- **1B 과제 붕괴**: 템플릿 밖 금지 전제 시 LLM 일=①retrieval ②slot 추출 ③델타 명명(5지선다) — 전부 닫힌 과제, editir 증류 카드와 합류. **retrieval 오류=시나리오 수준 near-miss(새 silent-wrong 공급원)** → 제안/판정 분리 불변: 구체화 결과가 계약+인증+표면화 통과해야 배포.
- **novelty 정직**: 이웃=SPL(전수 사전구축+구성)·IFTTT 레시피 DB(무계약 퇴화판)·program sketching(skeleton=sketch, slot=hole, 바인딩=검증된 hole-filling — 인용 프레임). "시나리오 DB" 자체=기여 아님; 우리 것=**인증서 붙은 skeleton 공급망**(입고→DB→retrieval→바인딩→런타임) — 새 축이 아니라 C2·C4+입고 lift의 완성형으로 판매. 세 시간축이 "인증된 자산의 공급망" 단일 서사로 묶임.

### 구조화 단위 하강 — 시나리오가 아니라 블록 관용구 (2026-07-29 유저 우려 해소)

- 유저 우려: 시나리오 전체 구조의 사전 열거=불가능(시간 판정·threshold·센서 연산/flag 등 블록 의도가 다양) → **동의하되 단위 하강으로 해소**: 유저가 나열한 블록들 자체가 유한 어휘의 증거.
- **언어 설계와 동형**: 닫는 것=블록 관용구 어휘(시간대 판정·엣지·cooldown·hysteresis·config·파생 flag·변경시-set·init-시드·알림·GV 미러 — 코퍼스 24 카테고리·D-1~9가 기존 증거) / 여는 것=조합. 보안모드 실증: 전부 알려진 관용구로 남김없이 분해, 새로운 건 조합뿐.
- **조합의 거시 형태 가설**: sense→derive→decide→act **계층 DAG**(보안모드 적합 확인). 템플릿 "구조"=관용구 어휘(미시)+계층 DAG(거시), 조합 그래프는 시나리오 고유·사전 지정 불요.
- **측정 전환**: ①관용구 line 커버리지 %(코퍼스 전수, PDG 인식으로 몇 초) — 95%+=어휘 닫힘 실증, 미커버=novel glue 플래그 ②새 시나리오당 새 관용구 발견률 하강 곡선=어휘 유한성 증거 ③계층 DAG 적합률. lift 난이도 하강: skeleton 매칭→블록 라벨링+조합 그래프(PDG-유도 lift 합류).
- **인증 합류**: 어휘 각 항목=자기 obligation 스키마(엣지=count 정합·cooldown=시간 산술·변경시-set=direction) → 시나리오 계약이 조합에서 유도 — 어휘를 닫는 대가로 인증이 조합적으로 저렴.
- **안전망 락**: 구조화 실패≠안전성 붕괴 — miter는 원인 불문(구조 무지에도 행동 보존 판정). 구조화=판정 전제가 아니라 **서비스 수준**(구조화됨=세밀 편집·drop·복원 / 비구조=전체 교체만). "가능한가"=사활 아닌 커버리지 수치, 정직 보고.

### "MLP를 시뮬레이터로" 논의 (2026-07-29 — 훈련 기각, exact 텐서 컴파일은 3용도 optional)

- 유저 아이디어: MLP처럼 입력→내부 graph→출력이니 시나리오를 신경망 시뮬레이터로? (+선행 fork: GPU로 SMT/시뮬 폭발 해결=기각 — z3 코어는 C++·CDCL은 GPU 부적합·induction 0.06s가 이미 답·배치 시뮬은 v2가 의도적으로 떠난 길)
- **훈련된 대리 모델=기각**: 근사가 판정 경로에 들어오면 근사 오차=silent-wrong(우리가 때리는 그것) + 시나리오별 훈련 비용.
- **통찰은 사실**: tick 본문=feedforward DAG(sense=입력층→derive=은닉→act=출력), "가중치"=시나리오 상수(이미 주어짐)→**학습 불요, exact 텐서 컴파일**: 시간축=scan(순차), 배치축=GPU(trace 100만·환경 수백 병렬) = tensorized simulation(Brax/gymnax/Isaac Gym 계보, 근사 아님).
- **쓸모 3자리(전부 증명 옆, 판정 아님)**: ①**검증기의 검증** — 랜덤 trace 대량 실행↔miter 판정 대조로 인코더 FP/FN을 코퍼스 규모 측정(v1 confusion matrix 의무 자동화; clock epoch류 인코딩 버그 안전망) ②**측도** — solver는 ∃/∀만, Monte Carlo로 "조용한 결함 주당 X회 발동" 체감 수치(42% 주장에 빈도 부여) ③**TIMEOUT 반증 사냥** — guard soft 완화→미분 가능→경사 탐색으로 divergence 입력 사냥(S-TaLiRo/Breach 계보); 찾으면 exact 재검 후 DIVERGE 확정, 못 찾으면 무주장. "증명=solver, 반증=GPU" 포트폴리오.
- 평결: 검증 대체=No(부재 증명은 trace로 불가) / optional 도구 각주=Yes. novelty 기둥 아님(양쪽 다 기존 계보), 인증서 체계와의 포트폴리오 결합만 우리 것.
- 한 줄: "시나리오는 훈련이 끝난 네트워크다 — 학습은 불요, 텐서로 컴파일해 배치축만 GPU에 태우면 exact 대량 실행이 공짜."

### LLM의 코드 이해 논의 (2026-07-29 — lift 실용 부품 2건)

- 유저 질문: 복잡 시나리오(복잡하지만 의도는 명확)를 LLM이 이해하게 하는 법 + "이해했다"는 확신의 근거.
- **이해의 3층 해부**(Claude 자기보고→기계 대응): ①관용구 사전 조회(블록 단위 패턴 매칭)=블록 어휘 ②변수 def-use 심적 추적=PDG ③까다로운 순서만 tick 심적 시뮬=SMT의 수동·불완전판. "복잡하지만 의도 명확"의 정체=구문 복잡·의미 단순(부품이 표준품).
- **처방**: 날코드+"이해해봐" 금지 → 결정론이 중간 구조(line 역할표·sink 슬라이스·관용구 라벨)를 선계산해 제공(editir의 fact 목록 원리); 자유 서술 대신 닫힌 어휘 분류로 답하게.
- **신규 ①: 알림 문자열=의도 신호** — toast/speak 문자열("보안 모드가 해제되었습니다")은 원작자가 전이 의도를 자연어로 기록한 것; 주석보다 신뢰(사용자에게 보이는 텍스트) → lift의 의도 라벨 1차 후보.
- **신규 ②: 이해의 검증 가능화** — LLM 이해를 산문이 아니라 **검사 가능한 주장 목록**으로 출력("버튼 없이 speak 발화 없음" 등) → 각 주장=gating/direction obligation으로 변환 → solver가 확정/반례. "이해했는가"(검사 불가)→"주장 중 몇 개가 증명되는가"(측정 가능). 반박된 주장=오해의 좌표. lift 품질 게이트로 사용 가능.
- 확신 사다리 락: 느낌<정독<심적 시뮬<실행<증명 — 읽기는 3단까지, 확신은 5단만(자기 실증: 인코더 저자들도 clock epoch 함정, 잡은 건 정독 아닌 하네스).

### ★유력: Exact-change 인증서 — "편집에 붙는 증명, 비용∝얽힘" (2026-07-29 유저 wow point 요청)

- 리프레임: spec=검증된 베이스 시나리오(P5 인증서 동반)+선언된 델타(NL→editir). 명제="**정확히 요청된 변화만** — no more, no less".
- **3부 구성**: ①**No more(보존)** — **프레임 룰**: 편집 footprint(PDG 슬라이스)∩채널 backward slice=∅ ⇒ 보존이 solver 0회로 성립(tick 의미론 메타 정리 1회 증명=슬라이싱 정당성의 재포장; separation logic frame rule의 이식). solver는 얽힌 채널만. ②**No less(유효성)** — 행동이 실제로 달라지는 witness 존재 증명(경계 trace); **죽은 편집 검출**(cron 시각 편집 후 본문 guard 방치=조용한 무효 — 편집의 vacuity, 도달가능성 기계 재사용). 아무도 안 하는 조각. ③**비용∝얽힘** — obligation 분리(M-F)가 인프라: 델타 footprint 교차 obligation만 재검, 나머지 인증서 **그대로 승계**(induction invariant도 상태 변수 미접촉 시 생존). 얽힘 지수=검증 비용 예측자.
- 한 문장: "인증서가 코드가 아니라 편집에 붙고, 재검증 비용이 프로그램 크기가 아니라 편집의 얽힘도에 비례한다."
- **즉시 실증 가능**: T1 벤치 191케이스로 전체 재인증 vs 델타-범위 재검 — 재검 obligation 비율·시간, 예상 10~100× = 논문 그림.
- **K1 구조 해소**: 아무도 spec을 승인 안 함 — spec=검증된 베이스, 변경 명세=사용자 NL 요청 자체. human dependence가 "승인"→"요청"으로 하강.
- 선제 인용: change contracts(Yi·Qi·Roychoudhury — 사람 저작 명세 vs 우리=7 ops 스키마 자동 유도), DiSE(증분 심볼릭 — 우리=인증서 승계+유효성+tick 도메인), Verification Modulo Versions(Logozzo — 의미 사실 재사용), 슬라이싱 정당성(Weiser/Reps — 프레임 룰=재포장 명시). 신규성=3부 인증서+스키마 조합+NL 통합+실측 배수. 경계: GV/공유 상태=프레임 밖(겹치면 solver) — 기존 분업 서사와 일치.
- 구현 리스크 낮음: 전부 기존 기계 재배열(obligation 분리·PDG·도달가능성·T1 벤치).

### 시나리오 그래프화(HHTPG)·세그먼트·재사용 논의 (2026-07-31 유저 제안 — 요약)

- 유저 제안: 코드를 상태/조건/행동/연산 블록으로 세그먼트 → 계층·이종·시간 그래프(멀티레이어, 에지=의존), IR·부분검증·검색·재사용. `:=`=threshold/flag, `=`=상태/버퍼라는 변수 직관 포함.
- 판정: 새 발명이 아니라 **기존 파이프라인이 암묵 계산하는 것의 명명**(extract=L0, obligation 분리 551건 상반 0=채널 cone 분해의 실측 근거, feature closure=L2, 얽힘지수=cone 교집합). "검증된 노드+합법 연결=문제없음"은 부정 — 문제를 에지 위로 옮겨 유한·검사가능하게 할 뿐(락 "correctness lives in the binding" 그대로). **에지 의무 어휘(단위/극성/edge-vs-level/provenance/신선도/초기화)=6 고장클래스가 사는 곳** → 주장 가능한 정리: "배선은 열거된 클래스를 도입할 수 없다". 하드웨어 IP 재사용 유비: top-level 검증을 없애지 않고 줄였다.
- 변수 3분류(구문 아닌 사용 패턴): 재대입 없음=**param**(재바인딩 표면), 가드 하 재대입=**register**(tick induction 상태 벡터), 매 tick 무조건 재계산=**wire**(노드 아닌 에지로 소거).
- 실물 분해(보안모드 자동제어=노드 6): S1 시간창(derive)/S2 버튼 엣지+latch set+act/S3 부재 latch reset(**S2+S3=SR 래치, reset-dominant가 문장 순서에만 존재**)/S4 정책 접착 3줄(재사용 불가가 정상=의도가 사는 곳)/S5 시드/S6 write-on-change. 의존 4종: wire/register+**순서**(S2→S3 부재 우선, S5→S6 첫 tick 이중알림 방지 — 데이터 에지만으로는 부족, ordering/dominance가 1급 속성)/control/시나리오 간 GV(재실감지→자동제어→침입감지 3-체인).
- 재사용성 3층: 상=device-free 신호변환(write-on-change가 idx2·idx5 재등장, 침입감지 전체=관용구 ~6개 조립+파라미터), 중=로직+act 분리 시 승격(act는 이벤트에 매달린 잎), 하=정책 접착. 경계="정답 있음/없음" 경계와 일치.
- 채우기=**program sketching hole-filling**: 블록 내부는 장치 무언급(typed port) → ①입력 포트: 그래프가 그 지점의 가용 신호를 typed 메뉴로 제공 → LLM 일이 자유 생성→제약된 선택으로 붕괴(1B 실현성, 오선택=의무 방출 실패로 fail-closed) ②장치 슬롯=role 계약 2축 바인딩 그대로(P1이 블록 입도로) ③파라미터+부수조건(lo<hi 등). 완료 조건=의무 집합 공집합. **per-node 계약 저작 금지(K1이 노드 수준 재발) — 계약은 role/GV/관용구 라이브러리 3곳만**. 인증된 코퍼스에서 같은 관용구 채움 사례 retrieval=정답 코드가 spec+prior 이중 역할.
- CDC(clock-domain crossing): period↔cron 에지에 staleness 의무=합성규율 "동일 period만"의 원리적 일반화(EDA 어휘).
- novelty 지뢰: Lustre/SCADE(tick 의미론 원류, 인용 필수)/Simulink/**Node-RED**(IoT 노드 그래프 이미 대중화 — 차별=의미론·계약·인증서 부재)/PDG·slicing 고전. **그래프를 기여라 하면 죽고 그래프 위의 판정을 기여라 하면 산다** — 내부 형식+Fig 2 자리. 텍스트가 소스로 남으면 text↔graph 번역 검증이 새 의무(새 구문 v0로 가면 해소).
- 측정 훅(각 반나절): 코퍼스 관용구 커버리지 %/보안모드 cone 교집합(얽힘 실측)/period×cron 혼재(CDC 인스턴스) 수.

### HA blueprint 대응 + 커뮤니티 실증 조사 (2026-07-31 웹 조사 3건 — §1 동기 인용 후보)

- blueprint=골격+input 슬롯(selector 필터=원시 role 계약), 인스턴스화=바인딩 — **재사용은 이미 대중화, 보증만 부재** → 존재 증명 불필요 구도.
- P1 실증: device_id 지옥("If I could change the device_id… tedious affair, since I have 70+ devices", forum 408896; 해법이 부족지식 "so easy, when ur in the know"), binary_sensor 상태어휘(on/off vs Detected/Wet, forum 541329), 단위 °F/°C 라벨 불일치(core #73459), LLM 변형("the AI starts hallucinating devices that don't exist in my setup", forum 979260, 2026).
- P2 실증: 환풍기 한 달 24/7 무감지(발견=소리 우연, forum 360339), 누수 8시간 무알림(dev.to genebean), 없는 엔티티 참조=2020년까지 완전 무음·지금도 로그 한 줄, 깨짐 배지 없음(WTH 805777). **발견 경로가 항상 물리적 우연="검증은 이벤트, 유효성은 생애주기"의 야생 증거**. Watchman 671★ HACS 기본("Missing 181 entities from 1178… over a few years")=수요 실증이자 **전부 구문 수준**(B5 구조≠정확성과 동일 간극).
- P3 실증(최대 수확): "take control"=편도(공식 문서 "되돌릴 수 없다") → **커스터마이즈와 업데이트 수신이 상호배타**(forum 419247, WTH 469776); 업데이트 엔진 요청 4년+ 반복(forum 366939, 3페이지); **frenck(HA 코어 개발자, WTH 803306, 2024-12): "We don't know if the update will break stuff. There is no guarantee the new Blueprint is compatible with existing automations" — 보존 보증의 부재가 기능 부재의 공식 사유 = exact-change 인증서가 정확히 이 빈칸의 이름**.
- P4 실증: helper/Jinja 매크로 숨은 의존성(WTH 470587·802664·467456)=state provenance 생태계판.
- P5 실증: 배포 전 테스트 불가("Can an automation be tested before it gets deployed?", forum 535090; trace는 발화 후에만, forum 832460), 유통=포럼·버전/호환성/의존성 메타데이터 전무(WTH 805982 "very 'developer UX'"), blueprint 1개가 전체 자동화 삭제(forum 267861, 2021).
- 활용: §1 동기 문단 직접 인용 + TAP 저평가 방어("배치만 잘하면"에 대한 구성적 반박) + 관련연구 practitioner evidence.

### 평가 스타일 — "% 없는 eval" 5형 (2026-07-31 유저: mutation/coverage % 찜찜함 해소)

- 찜찜함의 원인 3: 분모 불명·잔여 미설명(K4)·결과 미연결. 해법=%를 주인공에서 제거.
- **E1 정리 표**: 범위 선언 후 obligation **전수**(증명/의도된 반례/범위 밖 **건별 호명** — 97.5%가 아니라 "이 3건은 밖이며 이렇게 표면화"). **E2 전문가 대조**: expert 이벤트⊆도출 카탈로그(분모 명확한 포함률)+기계가 더 찾은 이벤트가 시딩 fault 적발(사건으로 보여주는 순간). **E3 6클래스 fault injection**: per-class 전수 표+음성대조(정상 변형 전부 통과, FP 0). **E4 mutation-until-dry 수렴 곡선**: 생존 0 도달 또는 잔여 전 건 범위 귀속(v1 99.3%에서 멈춘 것과의 차이=마를 때까지+전 건 설명). **E5 베이스라인 head-to-head**: soak(며칠 돌리기)/LLM 리뷰/구조 검사 대비 검출률+**검출까지 시간**("soak은 11일 또는 영원히 못 밟는 fault를 obligation은 4초 증명").
- %가 나오는 유일한 곳="코퍼스의 몇 %가 선언 범위 안"=한계 서술. 검정 단위=(시나리오×fault×obligation) 조합 전수 → N=9(K8) 동시 해소.

### 임계 이벤트 도출 — "테스트는 저작되지 않고 도출된다" (2026-07-31)

- 관찰: 사람이 고르는 "중요한 이벤트"(20도 상향 돌파, 10분 유지 딱 못 채움)는 마법이 아니라 **코드에서 읽은 것** → 기계가 같은 곳에서 도출.
- 3원천: ①**술어 경계**(상향/하향/near-miss + MC/DC: 각 조건이 단독으로 결과를 뒤집는 입력) ②**시간 연산자별 임계 시퀀스 스키마**: duration=D-1/정확히 D/중단-재개(리셋 vs 누적 의미론 갈림), 반복 카운트=2회+상승/3회/샘플간 aliasing(의미 선택=표면화 대상), cooldown=창 경계 직전·직후 — **관용구가 자기 검사 스키마를 지고 다님**(사람의 직관=관용구 수준 지식의 1회 저작) ③**base 발화 영역=oracle**: must-fire/must-not의 정의를 사람이 아니라 인증된 base가 제공(K1 회피; miter가 이미 양방향 증명).
- 점검 3층: (1) 지원 구문=solver 증명(열거 없음, 존재 질의; D는 심볼=parametric 또는 induction) (2) witness 트레이스→simulator 재생(UNSUPPORTED 폴백+**인코더 translation validation**: SMT 의미론과 simulator 의미론의 이중 실행 일치+사용자 증거 "이 시퀀스에서 원본은 울리고 수정본은 침묵") (3) mutation-until-dry(생존 뮤턴트=빠진 경계의 고발자, 스키마 추가 후 재순환).
- 인접: GATeL/Lurette(동기언어 제약 기반 테스트 생성=최근접)·MC/DC·경계값 분석·DSE — 차이=①oracle을 base가 제공 ②시간 경계 지식을 관용구 스키마로 1회 저작 ③완전성을 mutation 루프로 측정.

### 못 잡는 것 전수 목록 (2026-07-31 — K4 대응 "what we miss" 절 재료)

- 구분 핵심: **표면화되며 못 잡는 것**(호명되고 멈춤) vs **certified 도장 받고 조용히 새는 것**(위험).
- A. 조용히 새는 9: ①base 자체 오류 — **omission: 코드에 없는 조건은 경계도 없어 시험 문제가 출제되지 않음**(구조적 사각) ②요청 자체 오류(8시라고 잘못 말한 소원의 정확한 이행) ③파라미터 부적정(20도가 이 집에 안 맞음) ④물리 피드백 act→환경→sense·actuator 간섭(코드 그래프 밖 에지) ⑤카탈로그-실장치 괴리(모델이 틀리면 증명도 틀림) ⑥시나리오 간 조합 타이밍/레이스(P4 — 각자 동치여도 조합 미증명) ⑦공통모드 toolchain 버그(UNSAT 방향은 witness 재생 불가; 인코더·시뮬레이터가 같은 오해 공유 시 이중 실행도 침묵) ⑧이중 사각(관용구 스키마 어휘에도 mutation 연산자에도 없는 fault 유형) ⑨문자열 의미(동작 보존인데 문구가 상황과 어긋남).
- B. 호명되고 멈추는 4: tick 사이 연속시간(모델 선언)/UNSUPPORTED(건별)/TIMEOUT(에스컬레이션)/표면화 후 사람 판단(fail-closed는 배포만 막음 — K1 잔재).
- 논문 처리: 3라벨 — 스코프 선언(①②③=정답 없음 입장의 논리적 귀결), 완화 존재(⑤ 신뢰기반 명시·⑥ GV 계약·⑦ 독립 이중 실행), 정직한 한계(④⑧⑨). 숨긴 99.3%는 공격당하고 호명한 목록은 방어선(v1 교훈).

### ★유력: 이산화 전수 시뮬레이터 — "샘플링이 아니라 열거" (2026-07-31 유저 제안 → 공동 설계, 상세)

**출발(유저 제안)**: 상태공간을 최대한 quantize(float→threshold 위/같음/아래, elapsed time→넘었냐만, 시간축=period 중심, cron·Clock.hour=단순 분기) + GPU 병렬 탐색으로 시뮬레이터 커버리지를 극대화.

**정체(기존 이론과의 대응)**: predicate abstraction(Graf-Saïdi, SLAM 계열) + timed automata의 region/zone abstraction(Alur-Dill, UPPAAL) + explicit-state model checking(SPIN). 기법 자체는 전부 기존 — novelty는 배치(base-상대 동치 spec, SMT와 상호 검증, 조합 인증 대상). **GPU는 기각**: 추상화가 성공하면 상태공간이 붕괴(보안모드 추산: 달력 칸 ~6 × 입력 칸 ~24 × 레지스터 2^4 × zone 소수 → 도달 그래프 수천~수만 에지 = CPU 밀리초~초). "GPU가 필요해지는 순간=추상화가 실패했다는 신호". GPU를 헤드라인에 걸면 "UPPAAL 쓰지 그랬냐" 리뷰 직행.

**설계 (합의된 형태)**:
1. **칸의 기준=코드 자신의 술어**(임의 3분할 아님). `temp>=20`이 있으면 20이 경계. 같은 칸의 두 값은 그 tick의 모든 분기를 동일 통과 → 칸당 대표값 1개=칸 전체를 돈 것. 시뮬레이터가 샘플링을 멈추고 **열거**를 시작하는 지점.
2. **탐색=BFS with 메모이제이션**: 상태=(레지스터 값 × 타이머 zone × 달력 칸), 매 스텝 모든 feasible 입력 칸 조합 주입, 방문 상태 재방문 시 가지 닫음. **무한 시간이 공짜**: 재방문=그래프 폐쇄(lasso) — BMC 창 문제의 탐색판 해법, SMT 쪽 tick induction과 동급 보증.
3. **동치 검사=곱 구성**: base×변형을 같은 입력 칸 시퀀스로 lockstep 실행, 출력 채널 비교. 술어 집합은 양쪽 프로그램의 합집합.
4. **시간 처리 — boolean 추상화 불필요(유저 "뒤에 잰 게 크다" 질문의 해소)**: 타임스탬프 값은 전부 어느 tick의 `now` 읽기이고 **점프 길이를 탐색기 자신이 고르므로**, `now - reg > c`의 진리값은 추측(자유 boolean)이 아니라 **계산**된다. 모든 타이머 술어가 동시에·모순 없이·결정론적으로 평가 → 타이머發 가짜 반례("120 안 넘고 600 넘음", "만료 후 재미만료")는 대부분이 아니라 **전부 소멸**. 유일한 주의: 점프 분기점에 각 타이머의 다음 임계 통과 **직전·직후**를 포함(zone successor). JoI 관용구 `reg = now` + `now - reg > c`가 timed automata의 클록 리셋+가드와 **정확히 동형**이라는 것이 이 설계가 서는 이유.
5. **술어 상관 — feasibility 사전 필터(유저 "LLM이 걸러내면" 질문의 해소)**: 시나리오당 술어 ~10개 → **오프라인 1회, 2^n 조합 각각을 구간 산술/미니 solver로 feasibility 체크** → "가능한 칸 목록"만 주입(a>3000 ∧ b<500 ∧ ¬(a-b>2000) 같은 수학적 불가능 조합은 원천 제거). 밀리초·결정론·시나리오당 1회. **LLM 금지 원칙(신규 일반 규칙)**: 오류가 비대칭 — 불가능을 남기면 가짜 반례(안전), **가능을 지우면 실제 행동 누락=EQUIV가 조용히 unsound**(C4 "어떤 판정도 LLM 올바름을 전제하지 않는다" 위반). → "**LLM은 후보를 늘리는 자리에만; 지우는 자리는 항상 결정론**".
6. **tick 축소 규칙(유저 "100ms 다 돌 이유 없다"의 합법화)**: **고정점+다음 사건 점프** — 입력을 고정했을 때 상태가 더 안 변하면(f(s,i)=f(f(s,i),i) 도달) 다음 사건까지 점프. 사건 3종=①타이머 임계 통과 시각(미리 계산 가능) ②달력 경계(hour/weekday 칸 전환) ③입력 칸 변경점(탐색이 비결정적으로 고르는 분기). **예외 2(여기서 깨짐)**: (a) 엣지·카운터 관용구 무장 중("3회 연속 하락" 등)은 건너뛴 구간의 토글이 카운트를 바꾸므로 1 tick 보행(관용구가 자기 활성 구간을 선언) (b) 조건 유지 중 매 tick 방출하는 코드는 점프 구간 방출을 **다중도 k**로 기록(count 의무 보존 — 안 하면 count 판정이 조용히 틀림). 두 예외를 넣으면 근사가 아니라 **정확한 압축**.
7. **boolean 추상화의 비대칭 soundness(단편 밖 잔여를 다룰 때의 원리)**: 술어를 자유 boolean로 두는 과추상은 실제보다 많은 행동을 탐색 → **EQUIV 판정은 공짜로 유효**(불가능 경로 포함 전부 같았으면 실제도 같음) / **DIVERGE는 가짜 가능**(FP=0 원칙 위반 → 반례별 실현 가능성 검사 필요=작은 산술 풀이, solver가 유일하게 사는 자리) / **존재 주장(must-fire·vacuity·Q3)은 불성립**(추상 도달≠실제 도달). "같음을 증명할 땐 공짜, 다름을 주장할 땐 영수증 확인".

**완전성 주장의 형태 — 단편(fragment) 정의**: 비교가 ①센서값-대-상수 ②타임스탬프차-대-상수(4번으로 정확) ③현재 tick 센서들 위 선형 술어 조합(5번 사전 필터로 정확)에 속하면, 이산화 전수 탐색은 **정확히 완전**(bisimilar): 놓치는 행동 없음, EQUIV/DIVERGE/liveness 전부 진짜, 반례 검사 불필요. **단편 밖(호명)**: ①비선형·동적 임계(임계값 자체가 센서 계산) ②래치된 센서값과의 후행 비교(`baseline=temp` 후 `temp-baseline>5` — 선형이면 baseline을 파라미터 칸으로 편입 가능하나 상태 증가) → 건별로 solver 잔여 또는 표면화.

**SMT의 강등된 역할(대체 아닌 재배치)**: 주 엔진=이산화 탐색기(전 구문 커버=UNSUPPORTED 소멸·무한 시간·liveness/vacuity=Q3 공짜·**시나리오 2~3개 곱 전수 탐색=P4 조합 인증**=현 SMT miter가 못 하는 것), SMT=①단편 밖 산술 잔여 ②파라메트릭 주장(∀D) ③**교차 검산**(독립된 두 의미론의 일치=toolchain 공통모드 방어; 기존 307페어·induction 0.06s 실측 자산 유지). 반례는 상호 재생(추상 반례→구체 재생, SMT witness→시뮬레이터 재생).

**얻는 것 종합**: 인코더 신뢰 문제 해소(시뮬레이터=실제 의미론 실행이라 코드→SMT 번역 신뢰 불필요) / UNSUPPORTED 갭 소멸 / Q3·vacuity 자연 산출 / P4 곱 탐색 최초 진입 / v1 서사 회복(시뮬레이터가 얻어맞은 bounded·coverage 비판이 정확히 abstraction 논증으로 고쳐져 귀환) / eval은 조건부 정리 프레이밍 그대로("단편 안 완전, 밖 호명").

**새 신뢰 기반(정직 선언)**: 칸 폐쇄 여부 구문 판정기 + feasibility 전처리기 + 점프 규칙(고정점 검사·임계 시각 계산) 구현이 TCB로 추가됨. §12 "MLP를 시뮬레이터로" 아이디어와의 관계: 그 기각 사유(coverage)를 abstraction으로 제거한 **옳은 버전**.

**측정거리(구현 전 반나절급)**: ①코퍼스 단편 커버리지 %(변수-대-상수 비교 비율 — 조건부 정리의 조건 실측) ②시나리오별 추상 상태수·도달 그래프 크기 실측(CPU 충분성 입증) ③보안모드 3-체인 곱의 크기(P4 실험 가능성 판단).

### ★구현 완료: 이산화 전수 시뮬레이터 실측 종합 (2026-07-31~08-01, `joi/simulator/`)

위 설계를 이틀에 걸쳐 전부 구현·실측했다. 상세는 `simulator/README.md`(이슈
로그 20건 전수)와 `simulator/runs/e1.md`(기계 생성 전수 표). 집필에 바로 쓸
숫자와 교훈만 여기 요약한다.

**측정거리 3건의 답(게이트 통과)**: ①단편 커버리지 = 술어 127건 중 즉시 85.8%
+ GROUND 18건(ForEach 평균·최대 — 그라운딩 후 선형) = **미해명 0** ②추상
상태수 = 시나리오당 1~320(보안모드 최대), 탐색 밀리초~23초 = CPU 충분성 입증
③3-체인 곱 = 보류(P4 TODO), 대신 쌍 단위 충돌 깔때기 설계 확정.

**파이프라인 실측 (코퍼스 10/10)**: 전 시나리오 그래프 닫힘(=무한 시간 판정
완료)·자기동치 EQUIV·의무 판정에서 진짜 발견 1건만(재실감지 occupancy 시드
전제 — 6 고장클래스 '시드 없는 write-on-change'의 야생 실물). cron 2건은
60s tick+달력 가드로 편입, forecast(h)는 루프 범위 추론으로 축 생성. 임의
신규 시나리오("10분마다 온도 재서 25도 이상이면 조명 전부 켜기")를 즉석
판정: 상태 1·에지 2·닫힘, "모두→하나만" 편집 변형에 li1 누락 반례, 임계
25→20 변형에 정확히 20.0도 반례.

**고장 주입 7클래스 전부 검출 (표 2)**: 경계 `>`→`>=`(정확히 120s 경계 tick)
· 시간 상수 30분→3분 · 엣지→레벨 · 재알림 600→60 · **재배선(카메라 교체 —
불투명 토큰 ⟨capturevideo@cam1⟩ vs @cam2 출처 비교 = P2 배선 인증)** · 점유
겹침(cooldown 600→5 → "10s 점유 중 6s 재발화", 그래프 위 Dijkstra) ·
**quantifier ∃→특정 1대 = k=1 EQUIV / k=2 DIVERGE("동치는 바인딩의 성질"
실행 실증; k=2 반례 = ps2만 재실+연기인데 변형이 대피 방송 누락)**.

**집필용 교훈 4 (§설계 재료)**:
1. **점프 합법성은 ∃-양화**: "도달했을 때의 입력"이 아니라 "조용히 유지
   가능한 입력의 존재"로 판정해야 함(stutter 증인). 아니면 반복 발화 입력이
   점프를 막고 memoization이 보행을 끊어 분 단위 임계 너머가 영구 미탐색.
2. **달력 셀은 진리값이 아니라 위상**: hour 술어 진리벡터로 키를 만들면
   0시와 11시가 병합되어 주간 사다리가 절단됨. timed automata region이
   위상을 담는 이유의 달력판 — 경계 구간(segment) 인덱스가 정답.
3. **실패는 안전 방향으로 떨어지게**: 미탐색(under-exploration) 오류 6건은
   전부 vacuity 의무가, 과탐색은 자기동치 EQUIV가 적발 — 검사 층이 엔진을
   검증하는 구조가 자체 개발에서 먼저 작동. dedup의 "불확실=유지" 설계는
   버그(＃19)가 성능 손실로만 떨어지고 판정은 무손상임을 실증.
4. **지우는 자리는 결정론 락의 배당**: 콤보 서명 dedup(조건식 순수 부분트리
   진리+값흐름 키)으로 강수 468,750→768 에지(610×), 판정·반례 불변.

**출력 형식(인증서의 실체)**: 도달 그래프(상태·에지·닫힘) + 동치 verdict
(EQUIV/DIVERGE+구체 반례: 입력 세계·깊이·액션 차이) + 의무 발견 목록
(VACUOUS/SEED-DEP/OVERLAP/COUNTER-CARRY[질문형]) + 그라운딩 리포트
(바인딩 표+부유 셀렉터=이식 검사 출력) + E1 markdown 표.


---

## ★ FSM 프레이밍 확정 + 4 트리거 분해 (2026-08-03 세션)

### 위치 (선행 대비)
BFS+메모=**명시적 상태 탐색**(SPIN/TLC/JPF와 동일 계열, 인용 대상). 델타 셋:
①입력이 모델이 아니라 **배포물 자체**(번역 간극 0) ②**성질을 안 받음**
(의무는 코드에서 도출=K1 회피) ③**상태 공간을 소비하지 않고 산출물로 보관**
(모델검사기는 성질 확인 후 버림). 산출물은 결정론 **Mealy 기계**:
상태=(추상 기억, 달력 칸) / 입력=(센서 칸 조합, dwell) / 출력=액션 다중집합.
결정론이라 동치가 lockstep 곱으로 싸다(이중 시뮬레이션 불필요).

### 엣지를 왜 뽑는가 — 3단 논증 (각 단이 다른 반론을 막음)
1. **사양 부재 → 이전 행동이 유일한 기준.** 무인 수리에서 "고쳤다"의 의미는
   "죽기 전 하던 일을 다시 한다"뿐. 그 기준을 **물건으로** 만들어야 비교가
   되는데 코드 텍스트는 의미가 아니다(문법 같아도 의미 다름·역도 성립).
   → 엣지=사양 없는 세계에서 "이전 행동"을 사양으로 물질화한 것.
2. **기준은 완전해야 한다 → 로그·샘플 시뮬레이션 불가.** 부분 기준으로
   수리하면 미관측 행동을 조용히 부순다(여름 로그로 고치면 겨울 분기 붕괴;
   실측: 여름 30일 로그는 정상 코드와 가습 영구불가 코드를 구분 못 함).
   게다가 필요한 판정이 전부 **부정 진술**("더는 못 한다"/"결코 도달 못 한다").
3. **사건 순간엔 늦다 → 평시 선계산.** 판정의 본질이 비교라 상대(고장 전
   FSM)가 미리 있어야 한다. 고장 후엔 원래 능력을 복원 불가. 운영 중 감시는
   탐색이 아니라 그래프 조회(0.12µs).

### 4 트리거 (하나의 메커니즘, 네 계기) — 3분류에서 개정
- **A 이식**: 환경이 다름 → 목표=원본 FSM, 보존율·부유 셀렉터
- **B 장애**: 기기 사망 → 목표=고장 전 FSM, 잃은 엣지=손실 목록
- **C 배포 불일치(객관·자동 수리 가능)**: 센서/액추에이터가 코드 가정과
  어긋남. **판정 근거가 의도가 아니라 사실**이라 자동화가 정당화된다:
  ①미충족 의존성(GV 생산자가 이 집에 없음=패키지 의존성 문제)
  ②기기 건강(무변화 flatline·선언 도메인 밖·동종 센서 불일치)
  ③단위/스케일 불일치(카탈로그 도메인 vs 코드 상수; st_tvoc 실사례)
  ④액추에이터 무응답(명령 후 상태 시계열이 **아예** 안 움직임 — 물리 모델이
    아니라 이진 반응성만 요구=저위험)
  ⑤죽은 바인딩
- **D 부적합(주관·제안만)**: 임계가 이 집 분포와 안 맞음, 집계 선택
  (평균/최대/중앙값), 주기·상수 조정. 오라클 없음 → 재설계지 수리가 아님.
  **C와 D를 섞으면 "수리와 재설계를 혼동"으로 정확히 찔린다.**

### 자동 수리의 수락 게이트 (신뢰가 아니라 인증서로 자율성을 제한)
목표=이전 FSM → 후보 생성(결정론 규칙 또는 로컬 LLM) → **가격표=엣지 차분**
→ 게이트: **잃은 엣지 0 ∧ 새 엣지는 호명된 것뿐**(Exact-change) → 되돌리기
가능 + 인증서 로그. C 중에서도 이 게이트를 통과하는 것만 자동 적용.

### 이 세션의 구현 추가
- `project.py`: 엣지 몫. 인터프리터가 `IfStmt` 분기를 기록(`StepResult.guards`)
  → (결정 경로, 액션 집합)으로 엣지 분할. **코드 자신의 조건이 열=내포적**이라
  결합 가드(`temp_avg > max_temp`)가 한 열로 들어옴(값 나열 실패 문제 해소).
  실측 온습도 278,516→21행(13,262×)·보안 7,680→40·절전 2,560→162(16×).
  **폭증원 2개**: 입력 곱(사영이 제거) + 그라운딩 언롤(제거 못 함, 2^그룹).
  후자용으로 **액션 역상+필수조건**: 절전 157행→그룹당 한 문장, 2단 절전
  계층이 역상 비교만으로 드러남. GV 쓰기 역상 매칭 버그(문자열→fired_key) 수정.
- `replay.py`: 배포 로그 재생 → ENGAGED/WINDOW/UNMET/NONCONFORM/VACUOUS.
  관측값은 **원시값이 아니라 칸으로** 기록해야 함(7월 vs 대표값 4.0 오판 실측)
  → `Axes.cell_preds`+`cell_of()`. **엣지 필요성 실증**: 같은 여름 로그에서
  원본=WINDOW vs is_winter 상실 변형=VACUOUS(로그만으로는 구분 불가).
- **이슈 ＃21(유일한 과탐색 결함)**: 점프의 stutter 판정이 정규화 키만 비교 →
  `reg = now`로 매 tick 갱신되는 레지스터가 delta 0으로 고정돼 정지로 보임 →
  점프가 옛 값으로 gap tick을 재생해 **없는 발화를 발명**. `_regs_frozen`으로
  구체 정지 요구 + 억제 시 notes 호명. 적발 수단=**구체 실행 대조**(vacuity는
  과탐색에 침묵). 회귀 없음(E1 3회 동일). 교훈: 추상화가 상대값을 쓰면 "정지"가
  두 개(추상/구체)로 갈리고 시간 점프는 구체 정지를 요구한다.

### 용어 락
"실시간" 금지 → **무인(unattended) 온라인 적응**(예산=다음 이벤트 전, µs 아님).
"한 번 뽑으면 끝" 금지 → FSM은 바인딩 상대적이라 재바인딩마다 재탐색(초 단위).
