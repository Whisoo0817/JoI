# OVLA — Paper Skeleton v2 (spine-driven, 2026-06-02)

> 이 문서 = SPINE 수렴(내 분석 → codex r1 → v2 → codex r2 = "main thesis genuinely fixed") 반영한 **새 권위 skeleton**.
> `outline.md` = 옛 lock-record(섹션별 ★LOCK rationale 상세 보관). **충돌 시 이 문서(+§0 SPINE) 우선.**
> System = **OVLA**, target DSL = **JoI**(기존). Abstract = `abstraction.md`. **paper.md / paper_kor.md 편집 금지**(유저가 from scratch).
> prose 작성 시 §0 SPINE의 verbatim 문장과 WORDING SCRUB를 점검표로 사용.

---

## §0  SPINE (framing 권위 — 모든 §1/§4/§7 prose가 정렬)

**해소하는 긴장:** (P) *문제*는 검증/safety(LLM 생성 reactive 자동화가 silently 오작동; LLM judge=불안정 게이트) ↔ (S) *시스템*은 on-device 효율(≤9B 4-bit·결정론 render·LLM-free 검사). 둘을 *하나의 설계원리*로 묶어 dissolve.

**핵심원리(한 줄):** LLM은 *생성*(NL→IR 제안 + IR→JoI lowering)에 쓰고, **trust loop = rendering(승인용) + verifier 게이트(L1/feasibility/L2)는 결정론·LLM-free**로 둔다. 사용자는 그 결정론 rendering을 승인/거부한다. 이 *한* 선택이 (P)신뢰[게이트에 확률적 judge 없음 → 안정·rejection-sound]와 (S)on-device[결정론 render + solver-free bounded sim = ms·no-cloud]를 *동시에* 귀결로 낳는다. → **on-device는 bolt-on이 아니라 공동원인.** safety = headline; efficiency = 같은 결정론의 배포-축 귀결(별도 결과로 띄우지 말 것, $599 박스로 열지 말 것).

**verbatim 문장 (prose에 그대로 사용):**
- **THESIS:** "OVLA confines the LLM to generation — it proposes a specification and lowers it to executable code — and makes the deployment gate deterministic and LLM-free: a plain-language rendering the user approves, and a bounded equivalence check of the generated code against that specification." (★ "generation은 spec 제안만"으로 줄여 쓰지 말 것 — lowering도 LLM 생성. 결정론은 *게이트*만.)
- **LLM-BOUNDARY (precise, GIGO 차단):** "The LLM proposes a candidate IR and lowers it to JoI code. Rendering the IR in plain language for the user's approval and the deployment gate that checks the lowered code against the approved IR are deterministic and call no LLM." ★ **lowering은 LLM 단계**(그래서 verifier가 필요) — 결정론은 feasibility 게이트 + rendering + L1/L2 verifier만. 사람 승인도 결정론 아님.
- **HONEST-BOUNDARY (§1에 일찍):** "OVLA checks whether the deployed code matches the displayed IR, not whether the IR captures the user's true intent; it eliminates a specific failure mode where the executable automation silently fails to implement the behavior shown in the IR."
- **SAFETY↔EFFICIENCY TIE (no slogan):** "The same design choice that removes unstable LLM judges from the deployment gate also makes the check small enough to run on the hub: deterministic rendering plus bounded simulation, no model call per check."
- **POSITIONING / money sentence (codex Q5):** "OVLA's contribution is the coupling of a user-facing reactive-temporal specification that is also executable as a behavioral reference with a bounded, on-device equivalence gate that blocks generated DSL programs that diverge from that reference."
- **FATAL 선제 (§1 끝):** "OVLA does not solve natural-language intent correctness: a user can still approve the wrong displayed behavior. Its contribution is to remove a separate deployment failure mode that remains after approval, where the generated executable silently diverges from the behavior the system displayed and asked the user to approve. This distinction matters because reactive-temporal lowering introduces state, timer, and boundary-condition errors even when the displayed IR is acceptable."

**CLAIM CHAIN (§1 순서, safety-first):** (target-artifact 오프닝 후) ① 생성 reactive 자동화가 *시스템이 생성·표시한 바로 그 IR*과 silently 어긋남 → ② 뻔한 대안 LLM judge는 불안정 게이트(행동-동일 프로그램이 temp=0서도 flip; **숫자는 §3, §1엔 질적+forward-ref**) → ③ OVLA는 IR을 결정론 render해 승인받고 IR↔code를 결정론 검사 → ④ 덤으로 on-device·no-cloud로 충분히 작다.

**SPEC-SHIFTING 반박 ("그냥 spec을 앞으로 옮긴 거 아니냐"; §1+§5):** (i) user는 *형식 spec을 작성하지 않음* — LLM 제안, user는 평문 rendering *승인*(★인지효능 주장 금지; "작성 안 함" 구조적 사실만) (ii) 기여 = 동시에 *승인용 평문 surface* + *기계검증 reference*인 표현 (iii) 루프를 닫음 = spec은 코드 검사 못하면 inert → 우리 결정론 on-device checker (iv) scoping이 비판을 rigor로: 사람 옳게 승인 주장 안 함; renderer가 checker·lowerer 소비 field 노출 + checker는 rejection-sound; 제거 클래스 = IR-code silent divergence.

**WORDING SCRUB (prose 금지 → 대체):**
- ❌"LLM-free trust loop" → LLM-BOUNDARY 문장
- ❌"confirmable" → "plain-language rendering shown for approval" / "user-facing"
- ❌intent 관계에 "oracle" → "(IR-derived) behavioral reference"; "oracle"은 IR-code *test-oracle* 의미로만 + 항상 "rejection-sound, not pass⇒correct"
- ❌"faithfully surfaces every fault" → "the renderer exposes the IR fields the checker and lowerer consume, so faults in the IR-to-code relation are visible in the displayed behavior; every behavioral difference in our test set produced a distinct rendering"
- ❌"classical formal verification doesn't transfer" → "applying formal verification here needs an authored property + a heavyweight solver (= the expert+compute burden OVLA removes), and no 'behaves-as-intended' property pre-exists; prior IoT *automation* work targets flat trigger-action"
- ❌§1 instability naked number → 질적 + §3 forward-ref
- ❌"verified 배포" / "verified/model-checked/sound-acceptance/formally-verified/bounded-completeness" → "gated / checked before deployment"
- ❌내부 scaffolding("trust loop/hinge/deployment-axis/edge co-design") → prose에선 평문 풀어쓰기

---

## Guards (불변)
- 금지어: **verified / model-checked / formally-verified / sound-acceptance / bounded-completeness**. 유지: "rejection-sound", "event-triggered".
- IR = "finite-state view / enumerable obligations — NOT a model-checking target", never "timed automata".
- coined word 금지(분야 표준어). em dash 금지(AI-tell). EN+KOR prose-time sync.
- **no-IRB this round:** 사람 user study OUT, ethics = "Not applicable: no human participants". 사람 efficacy 주장 금지(워크플로우·시스템속성만 foreground). future user study **foreground 금지**("we will run N" 금지); limitations 중립 1줄까지만.
- **non-expert** = motivation/대상 + workflow 속성(expert-authored spec 불필요·no cloud)으로만; empirical 능력 주장 금지.
- **verifier 가치 = safety(silent-wrong→0)**, NOT accuracy lift(+3.4% 헤드라인 금지). minus-IR generation gain = "Role 0" 부수효과로 정직히.
- openai.txt 커밋 금지.

---

## Section order
- **§0** Title + Abstract (`abstraction.md`)
- **§1** Introduction (target-artifact 오프닝 → CLAIM CHAIN → honest-boundary → THESIS/POSITIONING → contributions + FATAL)
- **§2** Related Work & Positioning (CONSOLIDATED early; 3-step 검증 funnel)
- **§3** Background, Problem & Motivation (instability 실험 + bridge to IR)
- **§4** System Overview (organizing banner = SPINE; 2-phase figure)
- **§5** Timeline IR
- **§6** Verifier (CORE)
- **§7** Implementation (on-device + no-cloud co-design; structural routing = 여기 impl detail)
- **§8** Evaluation (RQ1-4 + positioning table)
- **§9** Limitations
- **§10** Conclusion

---

## §1  Introduction

**오프닝 = target-artifact 구분(problem-first):** reactive-temporal IoT 자동화(persistent state·timer·"N분 지속"·cycle·다단계) vs flat trigger-action 규칙. (대중 플랫폼 근거: IFTTT 단일 trigger→action·persistent state 無; SmartThings Routines = AND/OR + "stays for X" + delay까지, loop·persistent var·중첩조건은 개발자 Rules-API JSON로만; Home Assistant = reactive-temporal 지원하나 **GUI 에디터는 codegen 아니라 스키마 폼**(수동 선택/입력 → YAML 직렬화), loop·persistent 변수·중첩 reactive는 YAML/Jinja2 절벽 = 비전문가 벽.)
- ★ 이 복잡도가 (a) 검증이 어려운 이유 + (b) 코드가 에러나기 쉬운 이유. **codex 교정**: "classical FV가 reactive 코드엔 전이 안 된다"는 *말하지 말 것*(FSM/semantics 있으면 전이됨). 대신 — FV를 이 세팅에 쓰려면 authored property + heavyweight solver(=non-on-device)가 필요하고, "의도대로"라는 property가 *선재하지 않는다*; 선행 IoT *automation* 연구는 flat trigger-action 대상. (정직: 선행을 "쉽다"로 깎지 말 것.)

**CLAIM CHAIN (§0):** ① 생성 reactive 자동화가 *시스템이 생성·표시한 IR*과 silently 어긋남 → ② LLM judge = 불안정 게이트(질적 진술 + §3 forward-ref) → ③ 결정론 render+승인 + IR↔code 결정론 검사 → ④ 덤으로 on-device·no-cloud.

**HONEST-BOUNDARY 문장(§0 verbatim)을 여기 일찍 박는다** + **THESIS** + **POSITIONING / money sentence**.

**Contributions (spine-bound):**
- **C1 — Timeline IR (hero artifact):** 동시에 (a) 승인용 평문 surface로 결정론 rendering + (b) reactive-temporal 코드용 기계검증 behavioral reference. (confirm된 NL 문장=(a)만, formal property=(b)만 → 둘을 겸하는 표현이 기여. ★ C1 재정의 lock §2 참조: AwareAuto가 confirmable temporal IR 선점 → 우리 주장 = *그 IR을 결정론 LLM-free로 검증·렌더하는 조합*.)
- **C2 — 결정론 배포 게이트:** IR→FSM→boundary-event→bounded trace-equivalence, LLM-free, fail-closed(pass=deploy / fail=repair·reject). T2 rejection-sound.
- **C3 — on-device 실현:** ≤9B 4-bit, no FT; 게이트에 LLM 없음 → ms·no-cloud(no-cloud 제약이 LLM-judge를 배제 = §3 instability상 옳은 선택이기도).
- **C4 — evaluation:** faithfulness-surfacing(RQ1) + verifier detection(RQ2) + system safety headline(RQ3) + on-device feasibility(RQ4).
- (구조분석 = IR 다목적 부산물: feasibility `IR∈L(G)` 결정론 reject[본문 메커니즘] + exemplar routing[§7 impl detail, 효과 주장 X]. 별도 contribution으로 띄우지 말 것.)

**§1 끝 = FATAL 선제 문장(§0 verbatim).**

---

## §2  Related Work & Positioning  (CONSOLIDATED, early)

> RW를 §2로 올려 끝냄(뒤에서 안 돌아옴). 본 블록 = 조직 권위. 상세 카드 = `paper/related_works/flow_userstudy_analysis.md`.
> 여는 1줄 bridge(§1 회수): 출력 = **non-canonical reactive-temporal** 프로그램(같은 행동·다른 표현) → 구문·주어진-oracle 검사 안 통함 → behavioral 검증 필요.

**구조 = 3-step 검증 funnel (codex ×2 vetted).** discriminator ≠ "intent 다루냐"(다 NL intent 입력) → **생성 이후 CHECK**으로 가른다.
- **§2.1 — (행동) 검증을 *하냐?* 대부분 안 함**(validity/satisfaction/none): EcoMate(valid=플랫폼 JSON 수락)·IoTGPT(API 에러만)·ChatIoT·Sasha·SAGE. **anchor "closest generator" = AwareAuto**(confirmable temporal IR 생성하나 생성코드를 그 IR에 *행동 검증 안 함*; intent=수작업 annotation; rendering=LLM 산문) → C1 재정의 셋업.
- **§2.2 — *무엇을* 검증?(reference)** 의도된 행동이 아님: **(a) 고정 property** AutoTap(expert LTL)·TAPFixer·TAPInspector·AutoIoT(Maude conflict)·HAWatcher·DS-IA(feasibility)·iRuler·Soteria; **(b) *주어진* oracle = non-IoT 건설적 analogy(짧게)** text-to-SQL/CodeT/GPIoT → "실행 검사는 oracle이 도메인서 *주어질 때만*; reactive엔 없어 OVLA가 confirmed-IR서 *유도*". **"전이 안 됨" manifesto 금지** → "property·oracle·semantic target이 다르다".
- **§2.3 — intent를 *무엇으로* 검증?(mechanism)** 학습/확률 judge: **anchor "closest verifier" = LACE**(생성물 back-translate→intent-equivalence = 우리 문제 verbatim; BUT static policy·확률 NLI·user無·자기 NLI가 certify한 100%). + ChatIoT Evaluator·IoTGPT/SAGE self-correction·SimuHome(recovery ≤18.5%). 같은 축이나 모델→불안정·edge불가 → **§3 forward-ref**(증명X). 우리 = 결정론 + user-approved + reactive-temporal.
- **ENDPOINT = OVLA**: 행동을 / approved-IR로 / 결정론으로.

**NEAR-COLLISION(careful) = LACE + AwareAuto만.** 나머지 = 한 줄 positioning: DS-IA(point-in-time feasibility/fail-closed)·AutoIoT'24(Maude conflict≠intent)·AutoIOT MobiCom'25(algorithmic codegen=GPIoT그룹)·EcoMate·IoTGPT·ChatIoT(LLM-judge baseline)·GPIoT·Sasha/SAGE.

**C1 재정의 LOCK (AwareAuto가 강제):** "confirmable temporal IR 있다"를 novelty로 X. OVLA IR 주장 = 조합 [*approved*-IR을 *behavioral reference*로 + *결정론 LLM-free* 검증 + *결정론* rendering + on-device]. retire: first NL→temporal IR / temporal-from-NL / show-rule-to-nonexpert / IR-as-template.

**why existing verification is a poor fit here (옛 "doesn't transfer" 재명명):** FV는 semantics 있으면 전이됨 → 진짜 장벽 = authored property 필요 + heavyweight solver(non-on-device) + "behaves-as-intended" property 선재 X. OVLA = confirmed-IR서 reference 유도 + bounded sim.

**POSITIONING TABLE = WIP draft(미확정).** feature/✓-only 금지 → **조합 행렬**(칼럼마다 변이, OVLA 유일성=행 조합): `System | Spec source | Target | Reference checked | Det. verifier`.
- AutoTap: expert | flat TAP | safety | ✓
- EcoMate/IoTGPT: NL | flat TAP·actions | none | –
- GPIoT: NL | program | external-oracle | ✓
- AwareAuto: NL | **reactive-temporal** | none | –
- LACE: NL | policy(static) | **intent** | ✗
- **OVLA: approved | reactive-temporal | behavior | ✓**
- 범례: Spec source{expert / free NL / **user-approved**} · Target{flat TAP·policy·program·actions·**reactive-temporal**} · Reference{none·safety·external-oracle·inferred-intent·**approved-temporal-behavior**} · Det.=결정론 LLM-free(–=verifier 無).
- ★ "TAP도 reactive다" 선제차단(범례 1줄): flat TAP=stateless·instantaneous(state/duration/timer/sequencing 無, pointwise 점검); reactive-temporal=그것들 추가(superset, trace 필요). 축 = temporal/stateful 표현력(Brackenbury/Ur event-vs-state + Corno sustained).
- 제외 칼럼: self-correction(non-discriminating)·silent-wrong(결과/RQ3)·on-device/no-cloud(→RQ4). text-to-SQL/CodeT = 프로스 analogy(row 아님).

**NOVELTY DISCIPLINE:** "생성+검증 결합" = genre 표준 → novelty 아님. novelty = user-approved 결정론 behavioral 검증(reactive-temporal·on-device) + IR 다목적. arXiv(LACE·AwareAuto·DS-IA·AutoIoT·AutoIOT·EcoMate·IoTGPT) = preprint 표기, 정량 baseline X.

---

## §3  Background, Problem & Motivation

**외부 인용탄(related-works Phase 1):** ① SimuHome(ICLR'26) — 18 model이 workflow-scheduling 실패 + self-correction recovery ≤18.5%/0%, oracle-fed ≤67%, "agents cannot detect their own mistakes" → *pre-deploy 검증 필요*. ② TAP-Debug(IMWUT'22) — 비전문가가 raw rule IF↔WHILE 오독, Control 21/21 실패 → *rendering 존재 이유*. ③ GPIoT(SenSys'25) — algorithmic code엔 executable oracle 있어 검증 쉬움 vs reactive엔 없음 → oracle을 confirmed-IR서 유도. ④ 분야 다 capability-gap 훅 → 우리는 **safety-gap(silent misbehavior) 훅 + measurement-motivation**으로 역전.

**Motivation 실험(ours-free, NO IR, NO verifier; §1이 forward-ref한 숫자가 여기):** LLM-as-judge가 안정적 게이트가 아님을 보임. **instability(헤드라인, label-free):** 행동-동일(trace-exact) 프로그램을 idiom만 바꿔도 accept/reject flip — temp=0서도 **9B 33% / GPT-5.1 14%**(재번역 round-trip 29%/18%), ours(결정론 trace-check)=0. 정답 라벨 없이 flip 자체가 불안정 증거. → "verdict가 행동 아닌 표면 form을 따라감 = 게이트 부적격."
- ★ **무능 주장 금지:** clean injected bug엔 steelman GPT-5.1이 유능(FN 5.8%) — 남은 FN=don't-care arg 라벨노이즈 + 의도모호성 탓. motivation은 miss-rate 아니라 **instability**에 의존.
- ★ cost는 motivation 아님 → §1 beat ③/④ + RQ4. instability가 "bigger/cloud model이 답"을 죽임 → no-cloud는 *추가 이유 + RQ4 feasibility*로 분리.

**BRIDGE to IR (codex; instability→IR 비약 방지):** ⓪ 대상=reactive-temporal 코드라 정적 oracle 없음 → ① reactive 동치성=timeline 위 semantic property → ② NL·code·trace는 behaviorally-equivalent 변형 多 → ③ LLM judge는 그 변형에 불안정(=instability) → ④ 고로 reference는 canonical·executable = **Timeline IR.**
- ⚠️ 이 motivation judge(NL+code) ≠ RQ2(IR↔JoI judge). 순환성: motivation은 ours 부재라 안전.

---

## §4  System Overview

> **★ ORGANIZING BANNER (SPINE):** figure로 pipeline을 보이되, 핵심 불변 = **LLM은 *생성*(IR 제안 + JoI lowering)에 쓰고; feasibility 게이트·rendering(승인용)·verifier(L1/L2)는 결정론·LLM 호출 없음**(LLM-BOUNDARY 문장 평문판). lowering이 LLM이라 *바로 그래서* 결정론 verifier가 필요. 이 banner 아래 2 phase를 walk → 독자에게 on-device coherence를 여기서 확립.

**Pipeline figure (제작됨 = `figs/system_architecture.pptx`):**
- **Phase 1 — Generation (on-device LLM):** NL → intent analysis → service mapping(+arg/enum resolve) → device mapping → **Timeline IR** extract → **feasibility gate `IR∈L(G)`** → **user 승인**(결정론 평문 rendering) → JoI generation(lowering).
- **Phase 2 — Verification (결정론, LLM-free):** L1 static check(JoI well-formedness) → IR→FSM + event synthesis → IR sim ‖ JoI sim → trace-equivalence → (mismatch) counterexample → **repair = JoI 재생성**(IR은 승인된 reference라 고정) / 통과 → deploy / unrepairable → **reject(fail-closed)**.
- ★ figure에 **structural routing 넣지 않음**(측정 안 함·효과 주장 X). feasibility gate만 표시.
- device mapping은 실제 IR extract와 병렬이나 figure는 sequential(각주 1줄로 "병렬" 명시).

**STAGE LAYERING (L1 ≠ feasibility 혼동 방지):**
- **feasibility = `IR∈L(G)`** — *IR* typed-tree 구조 게이트(nested loop/이중 cron/then-else 결정론 reject). 위치 = **IR extract 직후, lowering·L1·L2 모두 이전.**
- **L1 = 생성 *JoI 코드*의 정적 well-formedness**(syntax·enum·type) — lowering 후, L2 이전.
- **L2 = behavioral trace-equivalence**(IR↔code) — 코어/hero.
- 셋은 서로 다른 시점·artifact → 묶지 말 것. hero = L2; feasibility·L1 = 받쳐주는 게이트.

**IR roles:** 승인 대상(평문 surface) / 검증 reference / generation scaffold / structural signature(feasibility+routing). upstream(intent/service/device mapping) = substrate, NOT contribution(명시).

---

## §5  Timeline IR

- **두 속성 동시:** (a) 결정론(LLM-free) 평문 rendering으로 user에게 승인 제시 + (b) 기계검증 behavioral reference. NL→IR은 LLM, **IR→rendering은 결정론**(환각 없음 = 표시된 게 IR을 정확히 반영).
- **finite-state view → enumerable obligations** ("NOT a model-checking target"; never "timed automata").
- **IR = typed tree + 의존성 문법 G:** start_at 정확히 1개(+top-level cron 1개) / `cycle.body`에 `cycle` 금지(nesting 불가) / `then`·`else`는 `if` 자식만 / `break`는 `cycle` 안만 / `cycle`은 period·until 필수 / edge∈{none,rising} 등. 멤버십 `IR∈L(G)` = **결정론·decidable**(§6 feasibility 근거).

---

## §6  Verifier (CORE)

> 흐름: reactive·temporal·behavioral 특성 → 왜 MC/SMT 없이 가벼운 온디바이스 검증으로 충분한지 정당화 → ★핵심기술(IR-FSM→event synthesis) → commission+omission 검출 → claim ladder → adequacy 실험 → 정직한 한계. (codex 2-round vetted; 상세 = outline.md "§6 detail".)

**§6.0 왜 behavioral·왜 lightweight:** 생성 JoI엔 정적 oracle 없음 + non-canonical → 동등성은 구문 아닌 behavioral(trace). reactive 행동 = (시간 랜드마크 × 센서값 구간 × edge × bounded 내부상태)의 유한 추상 위 piecewise-constant + 고정 7일 지평 → cell당 대표 입력 하나로 검사 → **bounded trace-equivalence**(결정론·solver-free·on-device). MC/SMT의 *대체 아님* = 배포시점 필터. ★ GUARD: "decided/suffices/exactly/completeness" 단어 금지 → bounded-fragment 설계 근거. 내부상태 축 빼먹지 말 것(hysteresis·sustain).

**§6.1 ★기여 = Construct-Derived Boundary Event Synthesis:** IR→FSM 결정론 도출(`ir_fsm.derive_fsm`, LLM 없음) → IR 결정점(guard 임계값·edge·타이머·cron·상태전이)에서 대표 이벤트 1개 합성. crossing 크기 무관(타이밍이 핵심). poll→react 검출 확인(2026-05-31). union 불필요(transient-only는 자기모순).

**§6.2 Trace-equivalence + omission 검출:** IR sim·JoI sim → action trace ±tolerance(max 500ms,10%) 그룹·dedup·순서보존 비교. **commission+omission 동시**(trace의 침묵=oracle). complete-behavior IR이라 가능; partial property/LTL은 못 함.

**§6.3 Claim ladder:** verdict 결정론·LLM-free. **T1 determinism + T2 rejection-sound**(flag ⇒ REAL divergence). **"pass⇒correct" 금지.** TCB = 두 시뮬레이터 + tolerance + 등가관계(LLM 제외). soundness = "시뮬레이터 충실성 환원 + mutation 증거"(proof 아님).

**§6.4 feasibility = `IR∈L(G)` 결정론 구조 reject:** **위치 = IR extract 직후 IR 게이트(lowering·L1·L2 이전), L1과 별개**(STAGE LAYERING §4). correctness = **by-construction(문법 멤버십)** → *실험 없이* 메커니즘으로 서술(이번 라운드 수치 X). caveat: 보장은 extractor *literal-transcription* 가정 위에서만 — silent-flatten 시 valid IR→G 통과→의미만 틀림→승인 잔여. (`validate_ir`이 G 일부 강제 → nested-cycle·single-cron 규칙 추가=G 완성, 구현 TODO.)

**§6.5 Adequacy 증거(실험; §8 RQ2):** exhaustive construct-derived mutation(12 op active) → 1차 전수 → **99.3% 검출(1551/1562 genuine; cap==uncapped=전수; equiv-filter=all-scenario)**. coverage spec **97.4%(342/351)** + impl JoI-branch **95.6%(566/592)**. survivor 11 전부 특성화(8 sub-tolerance comparator + 1 fan-out 중복 + 2 C14 arith-RMW). residual Good-Turing=각주(n=11 약함→핵심은 특성화).

**§6.6 Limitations(정직):** 연속 산술(SMT future) · bounded 7일 지평 · transient-only 코너(자기모순→각주).

---

## §7  Implementation

- ≤9B 4-bit on-device, no fine-tuning; multi-stage decomposition.
- **no-cloud co-design(평문):** no-cloud 세팅이 cloud LLM-judge를 배제 → 게이트는 LLM 없는 결정론 검사여야 함 — 그게 §3 instability상 *옳은 선택*이기도(같은 결정이 신뢰+배포가능 둘 다). ("edge co-design" coinage prose 금지.)
- **structural exemplar routing = 여기 impl detail, 효과 주장 금지(이번 라운드 측정 X):** IR 구조클래스 τ(IR) 공유 exemplar retrieval → lowering prompt 구성; generator-only, verdict LLM-free. ablation 안 하므로 "generation 개선" 정량 주장 금지 = "어떻게 도는지"까지만. contribution bullet 아님.

---

## §8  Evaluation  (RQ1-4 + positioning table)

> 핵심: "정확도 경쟁" 아니라 **workflow 각 고리가 성립**함을 component별 입증. headline = **silent-wrong 9.2%→0%**(RQ3). baseline 메인 = LLM judge(verification 대안); workflow 차별 = capability matrix; minus-IR+SOTA codegen self-correction = 보조(Role 0).

**RQ1 — Stage-1 (IR rendering이 충실한 승인 surface인가) — THIS ROUND: renderer faithfulness 측정(human study DEFERRED).**
- 사람 user study OUT(no-IRB; ethics="no human participants"). 사람 0명 증거 3종:
  - (1) **faithfulness-surfacing 정량(DONE = `faithfulness_surfacing.json`):** 주장(precise, §0 SCRUB) = "the renderer exposes the IR fields the checker and lowerer consume, so faults in the IR-to-code relation are visible in the displayed behavior; every behavioral difference in our test set produced a distinct rendering." 결과: Part B 합성 8클래스(comparator/polarity/arg/device/timing/oneshot↔waituntil/single↔cycle/and-drop) **1504/1504 surface, blind 0**; Part A 실제 logic-fault **56/56**. (C16_5 단일 blind = selector-free IR 계약 위반 1행 = renderer 한계 아님; device binding은 병렬 precision 채널.)
  - (2) worked-example figures(명령→IR rendering + 틀린 IR rendering 나란히 = 설계 시연).
  - (3) prior-work: TAP-Debug raw-rule 21/21 실패 인용.
- 금지 주장 = "비전문가가 fault를 더 잘 *잡는다*"(detection rate=study 영역). controlled-study protocol = 내부 preregistration 보존(논문 광고 X). 상세 protocol = outline.md RQ1.

**RQ2 — Stage-2 (기계가 틀린 코드를 무조건 잡나) = DETECTION [부분 done].**
- mutation 99.3%(§6.5) + coverage. **숫자 3개 분리**(Alive2/Test-Suite-Acc/Csmith 차용): (i) neighbor-mutant kill rate (ii) human-adjudicated 샘플 대비 FP/FN (iii) residual Good-Turing. soundness 진술 = rejection-sound·bounded-incomplete·auditable("pass⇒correct" 금지).
- ★ **INDEPENDENT-ORACLE LOCK(circularity 방어):** 독립 human-adjudicated 실LLM-bug corpus(여러 모델 NL→JoI 100~300 → 사람이 기대행동 판정, gt_ir·verifier 무관) → {caught / IR-error / unsupported rejected / ambiguous / escaped}. mutation=메인 stress, corpus=독립 validation.
- vs LLM judge(9B P=0.71): "LLM 못 가린다". "클라우드도 못 잡는다": 복잡도별(ours 평평 vs GPT-4o 급락) + multi-GT(over-reject vs idiom-invariant). ⚠️ 이 multi-GT = judge가 IR 받는 RQ2 세팅(≠ §3 NO-IR multi-GT).
- ★ **COVERAGE-LIMIT LOCK(정직, §6.5/§9 공유):** boundary-event 합성은 비교 연산(threshold)을 앵커로 동작 → **threshold 없는 변수-변수 산술**(예: `notify($t1 - $t2)`, 비교 부재)은 노릴 경계가 없어 generic lo/hi seed만 가능 = 부호·구조 버그는 잡지만 **특정 값 관계에서만 터지는 value-specific 버그(clamp/min/max/crossover)는 놓칠 수 있음**. 또한 같은 서비스의 두 read는 selector-free IR에서 한 device-key로 붕괴 = entity 구분 없이 시간차 샘플로만 exercise(precision/tag는 본 논문 scope 밖, #71). 둘 다 **soundness(거짓 PASS) 아님 = coverage 한계**: 양쪽 sim이 동일 값을 공유하므로 거짓 통과를 만들지 않음.

**RQ3 — 시스템 안전 = HEADLINE.**
- ★ **headline 2층 분리(circularity 방어):**
  - **(a) IR-code mismatch(verifier 공로):** **silent-wrong-deployed 9.2% → 0%.** scoped 문장(codex Q4 원칙, 숫자 교정): *"Without the deployment gate, 35 of 382 generated automations (9.2%) deploy while silently diverging from the IR shown for approval; OVLA's bounded IR-to-code equivalence gate reduces this to 0 (11 repaired, 24 rejected fail-closed, at the cost of 2 correct candidates over-rejected). This concerns divergence from the displayed IR under the confirmed-IR assumption, not whether the IR matched the user's intent."* (denominator=382, confirmed-IR=gt_ir config; deployed-correct 90.84%→93.19%.)
  - **(b) end-to-end intent-wrong(정직 decomposition):** stage별 — NL→IR wrong(자동 gen-IR vs gt_ir) / user가 IR오류 못잡음(**THIS ROUND 미종결 = §9 limitation**) / IR→JoI caught·missed(RQ2) / unsupported rejected / ambiguous.
- 표: `[System | Correct deployed | Silent-wrong(IR-code) | Repaired | Rejected | Needs-expert | Needs-cloud]` — 우리만 IR-code silent-wrong 0 + no-expert + no-cloud. failure taxonomy + repair-loop cost/stability.

**RQ4 — feasibility (no-cloud/on-device).**
- 하드웨어: **Mac Mini M4 16GB(MLX 4-bit) = headline edge** / RTX 5090(AWQ) = reference(정확도 확립). safety=백엔드 독립(feasibility=M4 / yield=백엔드별 / silent-wrong0=invariant).
- ★ **DISTRIBUTION LOCK:** latency p50/p95/worst(평균 금지) + peak mem + power + model load + repair 횟수 + **복잡도별 worst-case verifier runtime**(triggers/timers/state-vars/quantifiers/devices/boundary-events 기준, LOC 아님).
- ★ **시그니처 플롯(SPINE 실증):** LLM-free verifier(ms·$0) vs local-9B-judge(초·VRAM) vs cloud-GPT-judge(초+$+network).
- **deployment(Mysmax 실배포 Pi 허브, ~10기기):** N≈12-15 수동등록 = demonstration(통계 아님). 증거 = testbed 사진 + functional 표 + ★timeline trace(센서/actuator vs IR예측) + ★verifier-value before/after(OFF 오작동 vs ON). 물리 realizable subset 52/382(temp 포함 ~73), verifier-value 풀 9개(7 reject + 2 repair). 상세 = [[project-rq4-deployment-efficiency-2026-06-01]].
- efficiency = enabler NOT headline; safety 헤드라인 유지.

**Positioning / capability table (§2와 행 공유; empirical RQ 아님 = differentiation table):** 행=시스템, 열=[입력 end-user NL / 결정론 검증 / 검증대상=intent-conformance / no-cloud / on-device]. 칼럼은 §1 문제정의서 유도 명시(cherry-pick 방어).

**보조(뒤, 정직):** E2E accuracy(Stage-B ON/OFF) + minus-IR ablation = IR이 generation도 도움(**Role 0** 부수효과). hero 흐리지 말 것.

---

## §9  Limitations
- **NL→IR intent correctness 미해결**(user가 틀린 IR 승인 가능) = FATAL 선제(§1)와 동일 선 — 정직히. ethics="Not applicable: no human participants".
- 사람 confirmation 행동 미연구(중립 1줄까지만; future-study foreground 금지).
- coverage ceiling(n%2 counters) · Rung-1 not all-input · bounded 7일 지평 · 연속산술(SMT future) · **threshold 없는 변수-변수 산술=boundary 앵커 부재→value-specific 버그 일부 놓침(coverage-limit, soundness 아님; §6.5)** · **same-service read의 device-key 붕괴=entity 구분 없음(precision scope 밖, #71)** · generalization.

---

## §10  Conclusion.

---

## Open decisions
1. positioning table 형태 미확정(조합행렬 draft). 2. §2 prose 미작성(funnel 구조는 lock). 3. feasibility 구현(validate_ir에 nested-cycle·single-cron) + routing 구현(측정 X). 4. RQ2 independent corpus. 5. GPT-4o judge arm(키 재추가) 복잡도/multi-GT. 6. RQ4 계측 코드 + 물리 ~12-15 subset 확정 + MLX setup(유저 추후). 7. abstract를 SPINE/SCRUB로 정렬(TODO).
