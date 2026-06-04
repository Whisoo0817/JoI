# OVLA — Paper Flow Plan (SenSys 2027, 12-page, 집필 backbone)

> 권위 flow = `outline2.md`(+§0 SPINE), detail = `outline.md`. 이 문서 = 두 SenSys exemplar(TaskSense·GPIoT SenSys'25)의 writing convention을 우리 flow에 매핑한 **집필 계획**. codex 리뷰 대상.
> System = **OVLA**, DSL = **JoI**. 한글 본문 + 핵심 용어 영어(Rendering, Timeline IR, trace-equivalence 등). paper.md/paper_kor.md(루트) = 유저 from-scratch, 건드리지 않음 → 새 본문은 `Final/paper_kor.md`.

---

## SenSys convention 요약 (두 exemplar에서 추출 — 우리도 따른다)

1. **Abstract (~180 단어)**: 문제 → 기존 방식 실패 이유 → 시스템 한 줄 정의 → 핵심 메커니즘 → headline 숫자. (둘 다 이 패턴.)
2. **Teaser Figure 1 (page 1)**: "기존 vs ours" 대비 그림. (GPIoT=cloud-leak vs 3 local SLM / TaskSense=시나리오.) → 우리도 page-1 teaser.
3. **Intro = 깔때기**: 광맥락 → gap → (RQ 한 줄 가능) → naive 접근 + 왜 실패 → 우리 해법 + 장점 → challenges → contributions(3-4 bullets, "first/처음" 표현). 
4. **Motivation = 경험적 (SenSys 시그니처 move)**: SOTA baseline을 직접 돌려 실패를 보이고 **named failure type + 분포 figure**로 정리. (TaskSense=HuggingGPT 3-error / GPIoT=MapCoder 28%·domain-mismatch 53.4%.) → **우리 instability 실험이 정확히 이 자리.**
5. **System Overview = full-width figure\* + phase walkthrough** (한두 문단).
6. **Design = 메커니즘별 subsection** (수식·figure 적극).
7. **Eval 순서**: metrics+baselines → **end-to-end 시연 1개**(deployment walk, 시나리오 하나를 자세히) → overall 정량 → microbenchmark → ablation → overhead/cost.
8. **각 subsection은 takeaway 문장으로 끝.** "Figure X는 ~를 보여준다" 톤.
9. **Discussion = 짧은 future-work 문단 3개** (선택), **Conclusion 짧게**.
10. user study: GPIoT=20명 5-Likert no-stats(최소치). **우리는 no-IRB라 사람 study 없음 → RQ1을 renderer faithfulness 측정으로 대체.**

---

## Page budget (12p = body ~10 + refs ~2)

| § | 제목 | 페이지 | 핵심 |
|---|------|-------|------|
| Abs | Abstract | 0.15 | SPINE 재작성(VIOLA→OVLA, 숫자 갱신) |
| §1 | Introduction | 1.25 | target-artifact 오프닝 + claim chain + contributions + teaser Fig1 |
| §2 | Related Work & Positioning | 1.25 | 3-step 검증 funnel + near-collision + positioning 표 |
| §3 | Background, Problem & Motivation | 1.25 | reactive-temporal 정의 + 인용탄 + **instability 실험(Fig3)** + bridge to IR |
| §4 | System Overview | 0.75 | LLM-boundary 원리 + **arch figure\*(Fig2)** + 2-phase + stage layering |
| §5 | Timeline IR | 0.75 | 두 속성 + finite-state view + typed tree + 문법 G (Fig4) |
| §6 | Verifier (CORE) | 2.0 | 왜 behavioral/lightweight → event synthesis → trace-equiv+omission → claim ladder → feasibility → adequacy(forward) → 한계 (Fig5) |
| §7 | Implementation | 0.5 | ≤9B 4-bit no-FT, no-cloud 공동설계, exemplar routing(효과주장X) |
| §8 | Evaluation | 2.75 | RQ1 faithfulness / RQ2 detection / RQ3 safety(headline) / RQ4 feasibility+deploy / positioning 표 / 보조 |
| §9 | Limitations | 0.4 | intent 미해결 + coverage ceiling + 정직 |
| §10 | Conclusion | 0.2 | |

**Figures(가정 존재)**: F1 teaser / F2 system arch(full-width) / F3 instability 분포 / F4 Timeline IR+rendering 예시 / F5 verifier 메커니즘(boundary event→IR-sim‖JoI-sim→trace-equiv) / F6 worked examples(맞는 IR rendering vs 틀린 IR rendering) / F7 detection+coverage / F8 latency 분포+signature plot+deployment timeline trace.
**Tables**: T1 positioning 조합행렬(§2) / T2 mutation·coverage(§6/§8) / T3 RQ3 safety 행렬 / T4 capability(§8, T1과 행 공유).

---

## §0  Abstract (재작성)
- 패턴: ① reactive IoT 자동화를 LLM이 NL→코드로 생성, 배포 전 검증 필요 ② 기존 검증=사람 코드검사/오프라인 expert/클라우드 LLM 재검사 → edge(프라이버시·지연)서 부적합 + LLM judge 불안정 ③ **OVLA = LLM을 생성(IR 제안 + JoI lowering)에 한정, 배포 게이트는 결정론·LLM-free**: 평문 Rendering을 사용자가 승인 + 생성코드를 그 IR에 대해 bounded equivalence로 검사 ④ 메커니즘: Timeline IR → FSM → boundary event → trace-equivalence, counterexample로 자동 repair ⑤ 숫자: 382 automations, ≤9B 4-bit 로컬, **silent-wrong 9.2%→0**(11 repair·24 reject), 주입 결함 **99.3% 검출**, boundary case **97.4% 커버**, 검증 루프에 LLM 0.
- 금지어 점검(verified/model-checked/sound-acceptance/bounded-completeness). VIOLA→OVLA. 옛 숫자(1,475/99.0%) 폐기.

---

## §1  Introduction  (1.25p)

**오프닝 = target-artifact 구분 (problem-first).**
- 선행연구도 user intent를 자동화로 표현·검증했으나 그 artifact = **flat trigger-action / 정적 policy**(유한·무상태·비시간) → 고전 형식검증이 그 클래스서 tractable.
- 우리 대상 = **reactive-temporal IoT 코드**(persistent state, "N분 지속"=sustain, cycle, timer, 다단계). 대중 플랫폼 근거: IFTTT 단일 trigger→action / SmartThings "stays for X"+delay까지·loop/persistent var는 Rules-API JSON / **Home Assistant GUI = 스키마 폼 수동 입력→YAML 직렬화, loop·persistent·중첩 reactive는 YAML/Jinja2 절벽**(비전문가 벽).
- 이 복잡도가 (a) 검증이 어려운 이유 + (b) 코드가 에러나기 쉬운 이유. ★codex 교정: "고전 FV가 reactive에 전이 안 됨"이라 말하지 말 것 → "이 세팅에 FV를 쓰려면 authored property + heavyweight solver(=non-on-device)가 필요하고 '의도대로'라는 property가 선재하지 않으며, 선행 IoT automation 연구는 flat TAP 대상."

**Claim chain (safety-first):**
① 생성된 reactive 자동화가 *시스템이 생성·표시한 바로 그 IR*과 silently 어긋난 채 배포됨 → ② 뻔한 대안인 LLM judge는 불안정 게이트(행동-동일 프로그램이 temp=0서도 verdict flip; **숫자는 §3, 여기선 질적+forward-ref**) → ③ OVLA는 IR을 결정론 Rendering해 승인받고 IR↔code를 결정론 검사 → ④ 덤으로 on-device·no-cloud로 충분히 작다.

**Honest-boundary 문장(일찍):** "OVLA는 배포된 코드가 *표시된 IR*과 일치하는지 검사하지, IR이 사용자의 진짜 의도를 담았는지는 검사하지 않는다 — 승인 이후에도 남는, 실행 자동화가 표시된 행동과 silently 어긋나는 한 가지 실패 모드를 제거한다."

**THESIS + POSITIONING 문장**(outline2 §0 verbatim 평문화).

**Contributions:**
- **C1 — Timeline IR**: 동시에 (a) 승인용 결정론 평문 Rendering surface + (b) reactive-temporal 코드용 기계검증 behavioral reference. (★C1 재정의: AwareAuto가 confirmable temporal IR 선점 → 우리 주장 = *그 IR을 결정론 LLM-free로 검증·렌더하고 on-device로 돌리는 조합*.)
- **C2 — 결정론 배포 게이트**: IR→FSM→boundary-event→bounded trace-equivalence, LLM-free, fail-closed(pass=deploy / fail=repair·reject), rejection-sound.
- **C3 — on-device 실현**: ≤9B 4-bit, no FT, 게이트에 LLM 호출 0 → ms·no-cloud.
- **C4 — evaluation**: renderer faithfulness(RQ1) + verifier detection(RQ2) + system safety(RQ3, headline) + on-device feasibility+deployment(RQ4).
- (구조분석 = IR 다목적 부산물: feasibility `IR∈L(G)` 결정론 reject[본문 메커니즘] + exemplar routing[§7 impl, 효과주장X]. 별도 contribution 아님.)

**§1 끝 = FATAL 선제**(outline2 §0 verbatim 평문화).
**Teaser Fig1**: (위) NL→LLM→JoI→deploy = silent bug가 그대로 배포 / (아래) OVLA = NL→LLM→Timeline IR→[결정론 Rendering 승인 + 결정론 IR↔code 검사]→deploy/repair/reject.

---

## §2  Related Work & Positioning  (1.25p, CONSOLIDATED early)

> 여는 1줄 bridge(§1 회수): 출력 = **non-canonical reactive-temporal** 프로그램(같은 행동·다른 표현) → 구문·주어진-oracle 검사 안 통함 → behavioral 검증 필요.
> **★RW 정보 = related-works-analyst agent 산출물 사용**(드롭인 positioning 문장·near-collision diff·표 행). 

**3-step 검증 funnel** (discriminator = "생성 이후 CHECK"):
- **§2.1 — 검증을 *하냐?*** 대부분 안 함(validity/satisfaction/none): EcoMate·IoTGPT·ChatIoT·Sasha·SAGE. **closest generator = AwareAuto**(confirmable temporal IR 생성하나 생성코드를 그 IR에 행동 검증 안 함; intent=수작업 annotation; rendering=LLM 산문) → C1 재정의 셋업.
- **§2.2 — *무엇을* 검증?(reference)** 의도된 행동 아님: (a) 고정 property = AutoTap(expert LTL)·TAPFixer·TAPInspector·AutoIoT(Maude conflict)·HAWatcher·DS-IA(feasibility)·iRuler·Soteria; (b) *주어진* oracle = non-IoT analogy(짧게) text-to-SQL/CodeT/GPIoT → "실행 검사는 oracle이 도메인서 주어질 때만; reactive엔 없어 OVLA가 confirmed-IR서 유도." ("전이 안 됨" manifesto 금지 → "property·oracle·semantic target이 다르다".)
- **§2.3 — intent를 *무엇으로*?(mechanism)** 학습/확률 judge: **closest verifier = LACE**(생성물 back-translate→intent-equivalence = 우리 문제 verbatim; BUT static policy·확률 NLI·user無·자기 NLI가 certify한 100%). + ChatIoT Evaluator·IoTGPT/SAGE self-correction·SimuHome. 같은 축이나 모델→불안정·edge불가 → **§3 forward-ref**.
- **ENDPOINT = OVLA**: 행동을 / approved-IR로 / 결정론으로.

**NEAR-COLLISION (careful) = LACE + AwareAuto만.** 나머지 = 한 줄 positioning(DS-IA·AutoIoT·AutoIOT·EcoMate·IoTGPT·ChatIoT·GPIoT·Sasha/SAGE).
**Positioning Table T1 (조합행렬)**: `System | Spec source | Target | Reference checked | Det. verifier` — OVLA만 [approved | reactive-temporal | behavior | ✓]. 범례 + "flat TAP도 reactive냐" 선제차단(stateless·instantaneous=pointwise vs reactive-temporal=trace 필요).
**NOVELTY DISCIPLINE**: "생성+검증 결합"=장르 표준 → novelty = user-approved 결정론 behavioral 검증(reactive-temporal·on-device)+IR 다목적. arXiv=preprint 표기·정량 baseline X.

---

## §3  Background, Problem & Motivation  (1.25p)

**Background/Problem**: reactive-temporal 자동화 정의(persistent state·sustain·cycle·timer·다단계) + 왜 정적 oracle이 없는가 + "correct"=Rung-1(transition-boundary conformance) 정의.

**외부 인용탄(related-works Phase1, agent가 정확 숫자 제공):**
① **SimuHome(ICLR'26)**: 18 *모델*이 workflow-scheduling 실패 + self-correction recovery ≤18.5%/0%, oracle-fed ≤67%, "agents cannot detect their own mistakes" → *pre-deploy 검증 필요*. (eval=HYBRID simulator-assert+LLM-judge — 인용위생.)
② **TAP-Debug(IMWUT'22)**: 비전문가가 raw rule IF(event)↔WHILE(state) 오독, Control 21/21 실패 → *읽을 수 있는 Rendering 필요*.
③ **GPIoT(SenSys'25)**: algorithmic code엔 executable oracle(pass@k) 있어 검증 쉬움 vs reactive엔 없음 → oracle을 confirmed-IR서 유도.

**Motivation 실험 (ours-free, NO IR, NO verifier; §1이 forward-ref한 숫자 = 여기):** SenSys 시그니처 move.
- **instability(헤드라인, label-free)**: 행동-동일(trace-exact) 프로그램을 idiom만 바꿔도 accept/reject verdict flip — temp=0서도 **9B 33% / GPT-5.1 14%**(재번역 round-trip 29%/18%), ours(결정론 trace-check)=0. 정답 라벨 없이 flip 자체가 불안정 증거. → "verdict가 행동 아닌 표면 form을 따라감 = 게이트 부적격." **Fig3** = flip-rate 분포(모델별).
- ★무능 주장 금지: clean injected bug엔 steelman GPT-5.1 유능(FN 5.8%) → motivation은 miss-rate 아니라 **instability**에 의존.
- ★cost는 motivation 아님 → §1 beat ④ + RQ4.

**BRIDGE to IR (codex; 비약 방지):** ⓪ 대상=reactive-temporal라 정적 oracle 없음 → ① 동치성=timeline 위 semantic property → ② NL·code·trace는 behaviorally-equivalent 변형 多 → ③ LLM judge는 그 변형에 불안정(=instability) → ④ 고로 reference는 canonical·executable = **Timeline IR.** (이 motivation judge[NL+code] ≠ RQ2[IR↔JoI judge].)

---

## §4  System Overview  (0.75p)

**조직 원리(평문, coined word 금지):** LLM은 *생성*(IR 제안 + JoI lowering)에 쓰고; feasibility 게이트·Rendering(승인용)·verifier(L1/L2)는 결정론·LLM 호출 없음. **lowering이 LLM이라 바로 그래서 결정론 verifier가 필요.**
**Fig2 (full-width arch figure\*)**: Phase1 Generation(on-device LLM) = NL → semantic parsing(intent/service/device) → Timeline IR extract → **feasibility `IR∈L(G)`** → 결정론 Rendering → **user 승인** → JoI lowering. Phase2 Verification(결정론, LLM-free) = L1 static → IR→FSM+event synth → IR-sim ‖ JoI-sim → trace-equivalence → (mismatch) counterexample → repair(JoI 재생성, IR 고정) / pass→deploy / unrepairable→reject(fail-closed).
**STAGE LAYERING (L1≠feasibility 혼동 방지):** feasibility=IR typed-tree 구조 게이트(IR extract 직후) / L1=생성 JoI 정적 well-formedness(lowering 후) / L2=behavioral trace-equivalence(코어). 셋 다른 시점·artifact → hero=L2.
**IR roles**: 승인 대상 / 검증 reference / generation scaffold / structural signature. upstream(intent/service/device mapping)=substrate, NOT contribution(명시).
- device mapping은 IR extract와 병렬(각주 1줄), figure는 sequential. structural routing은 figure에 안 넣음.

---

## §5  Timeline IR  (0.75p)

- **두 속성 동시**: (a) 결정론(LLM-free) 평문 Rendering으로 승인 제시 + (b) 기계검증 behavioral reference. NL→IR은 LLM, **IR→Rendering은 결정론**(환각 없음 = 표시된 게 IR을 정확 반영).
- **finite-state view → enumerable obligations** ("NOT a model-checking target"; never "timed automata").
- **typed tree + 의존성 문법 G**: start_at 정확히 1개(+top-level cron 1개) / `cycle.body`에 `cycle` 금지(nesting 불가) / `then`·`else`는 `if` 자식만 / `break`는 `cycle` 안만 / `cycle`은 period·until 필수 / edge∈{none,rising}. 멤버십 `IR∈L(G)` = 결정론·decidable(§6 feasibility 근거).
- **Fig4**: 구체 IR 예시(start_at/wait(cond,for:T)/cycle{…}/call(svc,args)) + 그 결정론 Rendering(평문) 나란히.
- op 목록(start_at, wait[cond·edge·for], delay, read, call, if[then/else], cycle[period·count·until·body], break) 간단 표/문단.

---

## §6  Verifier (CORE)  (2.0p)

> 흐름: 왜 behavioral·왜 lightweight → ★event synthesis → omission 검출 → claim ladder → feasibility → adequacy(실험은 §8) → 한계.

- **§6.0 왜 behavioral·왜 lightweight**: 생성 JoI엔 정적 oracle 없음 + non-canonical → 동등성=behavioral(trace). reactive 행동 = (시간 랜드마크 × 센서값 구간 × edge × bounded 내부상태)의 유한 추상 위 piecewise-constant + 고정 7일 지평 → cell당 대표 입력 하나 → **bounded trace-equivalence**(결정론·solver-free·on-device). MC/SMT 대체 아님 = 배포시점 필터. ★GUARD: "decided/suffices/exactly/completeness" 단어 금지 → bounded-fragment 설계 근거. 내부상태 축(hysteresis·sustain) 빼먹지 말 것.
- **§6.1 ★기여 = Construct-Derived Boundary Event Synthesis**: IR→FSM 결정론 도출(LLM 없음) → IR 결정점(guard 임계·edge·타이머·cron·상태전이)에서 대표 이벤트 1개 합성. crossing 크기 무관(타이밍이 핵심). poll→react 검출 확인. union 불필요(transient-only=자기모순). **Fig5**.
- **§6.2 Trace-equivalence + omission**: IR-sim·JoI-sim → action trace ±tolerance(max 500ms,10%) 그룹·dedup·순서보존 비교. **commission+omission 동시**(trace의 침묵=oracle). complete-behavior IR이라 가능; partial property/LTL은 못 함.
- **§6.3 Claim ladder**: verdict 결정론·LLM-free. **T1 determinism + T2 rejection-sound**(flag⇒REAL divergence). "pass⇒correct" 금지. TCB=두 시뮬레이터+tolerance+등가관계(LLM 제외). soundness="시뮬레이터 충실성 환원 + mutation 증거"(proof 아님).
- **§6.4 feasibility = `IR∈L(G)`**: 위치=IR extract 직후(lowering·L1·L2 이전), L1과 별개. correctness=by-construction(문법 멤버십) → 실험 없이 메커니즘 서술. caveat: 보장은 extractor *literal-transcription* 가정 위에서만(silent-flatten은 G통과→confirmation 잔여).
- **§6.5 Adequacy(실험; §8 RQ2 forward)**: exhaustive construct-derived mutation(12 op active) → **99.3% 검출(1551/1562 genuine)**; coverage spec **97.4%(342/351)** + impl JoI-branch **95.6%(566/592)**; survivor 11 전부 특성화(8 sub-tolerance comparator + 1 fan-out + 2 C14 arith-RMW). residual Good-Turing=각주(n=11 약함→핵심은 특성화).
- **§6.6 Limitations(정직)**: 연속 산술(SMT future) · bounded 7일 지평 · transient-only 코너(자기모순→각주) · threshold 없는 변수-변수 산술=boundary 앵커 부재(coverage-limit, soundness 아님) · same-service read의 device-key 붕괴(precision scope 밖).

---

## §7  Implementation  (0.5p)

- ≤9B 4-bit on-device, no fine-tuning; multi-stage decomposition(intent/service/device/IR-extract/lowering). (vs GPIoT=FT 13B+LoRA, TaskSense=cloud — 우리=no-FT ≤9B + 결정론 verifier.)
- **no-cloud 공동설계(평문)**: no-cloud 세팅이 cloud LLM-judge를 배제 → 게이트는 LLM 없는 결정론 검사여야 함(같은 결정이 §3 instability상 옳기도). ("edge co-design" coinage 금지.)
- **structural exemplar routing = impl detail, 효과 주장 금지**: IR 구조클래스 τ(IR) 공유 exemplar retrieval → lowering prompt 구성. generator-only, verdict LLM-free. ablation 안 함 → "어떻게 도는지"까지만, contribution bullet 아님.

---

## §8  Evaluation  (2.75p)

> 핵심: "정확도 경쟁" 아니라 **workflow 각 고리 성립**을 component별 입증. headline = **silent-wrong 9.2%→0**(RQ3). 메인 baseline = LLM judge(verification 대안).
> **Setup**: 하드웨어(Mac Mini M4 16GB MLX 4-bit = headline edge / RTX 5090 AWQ = reference) · 데이터셋(382 automations, 24 categories) · backend별 safety invariant(feasibility=M4 / yield=backend별 / silent-wrong 0=invariant).

**RQ1 — Stage-1 (IR Rendering이 충실한 승인 surface인가). 사람 study DEFERRED(no-IRB) → renderer faithfulness 측정.**
- 사람 0명 증거 3종: (1) **faithfulness 정량**: 주장(precise) = "renderer가 checker·lowerer가 소비하는 IR 필드를 노출 → IR-to-code 관계의 fault가 표시 행동에 보인다; 우리 테스트셋의 모든 행동 차이가 서로 다른 Rendering을 냈다." 결과: Part B 합성 8클래스(comparator/polarity/arg/device/timing/oneshot↔waituntil/single↔cycle/and-drop) **1504/1504 surface, blind 0**; Part A 실제 logic-fault **56/56**(C16_5 1-outlier=selector-free IR 계약 위반=renderer 한계 아님). (2) **worked-example Fig6**(명령→IR Rendering + 틀린 IR Rendering 나란히). (3) prior-work TAP-Debug 21/21 인용.
- 금지: "비전문가가 fault를 더 잘 잡는다"(detection rate=study). future-study foreground 금지(중립 1줄까지). non-expert=motivation/workflow 속성만.

**RQ2 — Stage-2 (기계가 틀린 코드를 무조건 잡나) = DETECTION.**
- mutation 99.3%(§6.5) + coverage. **숫자 3개 분리**(Alive2/Test-Suite-Acc/Csmith 차용): (i) neighbor-mutant kill rate (ii) human-adjudicated 샘플 대비 FP/FN (iii) residual Good-Turing. soundness = rejection-sound·bounded-incomplete·auditable.
- **INDEPENDENT-ORACLE(circularity 방어)**: 독립 human-adjudicated 실LLM-bug corpus(여러 모델 NL→JoI → 사람 기대행동 판정, gt_ir·verifier 무관) → {caught/IR-error/unsupported-rejected/ambiguous/escaped}. mutation=메인 stress, corpus=독립 validation.
- vs LLM judge(9B P=0.71; ChatIoT Evaluator를 named cloud judge로): 복잡도별(ours 평평 vs 강한 클라우드 judge 급락) + multi-GT(over-reject vs idiom-invariant). **Fig7**. (★GPT-4o arm 제외 결정 — GPT-5.1로 충분, 메모리.)
- COVERAGE-LIMIT(정직): threshold 없는 변수-변수 산술 value-specific 버그 일부 놓침 = coverage 한계, soundness 아님.

**RQ3 — 시스템 안전 = HEADLINE.**
- **2층 분리(circularity 방어)**: (a) **IR-code mismatch(verifier 공로)**: silent-wrong-deployed **9.2%→0** — scoped 문장: "게이트 없으면 382 중 35개(9.2%)가 표시 IR과 silently 어긋난 채 배포; OVLA의 bounded IR↔code 검사가 0으로(11 repair, 24 fail-closed reject, 정확한 후보 2개 over-reject 비용). 이는 표시 IR로부터의 divergence이지 IR이 사용자 의도와 맞았는지가 아님(confirmed-IR 가정)." deployed-correct 90.84%→93.19%. denominator=382. (b) **end-to-end intent-wrong(정직 decomposition)**: NL→IR wrong(자동 gen vs gt_ir) / user가 IR오류 못잡음(THIS ROUND 미종결=§9) / IR→JoI caught·missed(RQ2) / unsupported-rejected / ambiguous.
- **표 T3**: `System | Correct deployed | Silent-wrong(IR-code) | Repaired | Rejected | Needs-expert | Needs-cloud` — 우리만 IR-code silent-wrong 0 + no-expert + no-cloud. + failure taxonomy + repair-loop cost/stability.

**RQ4 — feasibility(no-cloud/on-device) + deployment.**
- **DISTRIBUTION**: latency p50/p95/worst(평균 금지) + peak mem + power + model load + repair 횟수 + **복잡도별 worst-case verifier runtime**(triggers/timers/state-vars/quantifiers/devices/boundary-events 기준, LOC 아님).
- **signature plot Fig8a**: LLM-free verifier(ms·$0) vs local-9B-judge(초·VRAM) vs cloud-judge(초+$+network).
- **deployment(SenSys convention=시나리오 1개 자세히)**: Mysmax 실배포 Pi 허브 ~10기기, N≈12-15 수동등록 = demonstration(통계 아님). hero 시나리오 = 회의실 sustain(presence-false 10분 지속→소등; 버그=1분). 증거 = testbed 사진 + functional 표 + **timeline trace(센서/actuator vs IR예측) Fig8b** + **verifier-value before/after**(OFF 오작동 vs ON repair). 물리 realizable subset 52/382(temp ~73), verifier-value 9개(7 reject + 2 repair).
- efficiency = enabler NOT headline.

**Positioning/capability table T4 (§2 T1과 행 공유)**: 열 = [입력 end-user NL / 결정론 검증 / 검증대상=intent-conformance / no-cloud / on-device]. 칼럼은 §1 문제정의서 유도 명시(cherry-pick 방어). empirical RQ 아님.

**보조(뒤, 정직)**: E2E accuracy(Stage-B ON/OFF) + minus-IR ablation = IR이 generation도 도움(**Role 0** 부수효과). hero 흐리지 말 것.

---

## §9  Limitations  (0.4p)
- **NL→IR intent correctness 미해결**(user가 틀린 IR 승인 가능) = §1 FATAL과 동일 선, 정직히. ethics="Not applicable: no human participants".
- 사람 confirmation 행동 미연구(중립 1줄, future-study foreground 금지).
- coverage ceiling(n%2 counters) · Rung-1 not all-input · bounded 7일 지평 · 연속산술(SMT future) · threshold 없는 변수-변수 산술(coverage-limit) · same-service read device-key 붕괴(precision scope 밖) · generalization.

---

## §10  Conclusion  (0.2p)

---

## REVISIONS (post-codex, 적용됨 — 충돌 시 이 블록 우선)

> codex 독립 리뷰를 내 판단으로 취사선택. 본문(paper_kor.md)은 아래를 반영해 집필.

**R1. Eval 재배치 + 재번호 (headline-first).** 본문 RQ 번호 = 설득순:
- **RQ1 = 시스템 안전 (HEADLINE)**: silent IR-code divergence 9.2%→0. (옛 lock의 "RQ3"=safety가 본문 RQ1)
- **RQ2 = verifier detection**: 독립 corpus 먼저 → mutation은 stress. (옛 "RQ2")
- **RQ3 = rendering faithfulness**: 승인 surface의 prerequisite. (옛 "RQ1"=faithfulness가 본문 RQ3)
- **RQ4 = on-device feasibility + deployment**. (그대로)
- Eval은 Setup → RQ1 headline → RQ2 → RQ3 → RQ4 순. (no-user-study 부분을 맨 앞에 두지 않는다.)

**R2. §1 강화.** (a) 1페이지에 **구체 silent-divergence 예시**: "presence-false 10분 지속 시 소등" 의도가 lowering에서 1분(또는 timer-reset)으로 새는 버그 = 표시 IR과 어긋난 채 배포. (b) **2층 scope 문장 1페이지**: Layer A(NL→IR intent 포착 = 제안·rendering하나 user로 *검증 안 함*) / Layer B(승인된 IR 이후 IR→code silent divergence를 bounded regime서 차단). (c) **no-cloud/edge = problem setting**(privacy·latency)로 §1에 명시(C3 늦은 add-on 아님). (d) bridge(우리 게이트가 *실제로* 잡음)를 contributions 전에 forward-ref(RQ2).

**R3. §3 motivation 재프레이밍.** instability를 **binary 배포결정**에 묶는다: "동일 행동 프로그램이 서로 다른 deploy/reject를 받으면 게이트로 부적격." 핵심 주장 = **확률적 judge는 behavior-preserving rewrite 하에 배포정책이 불안정(원리적); OVLA는 0 by construction.** "GPT-5.1 14%"를 fixable처럼 과시 X. **majority-vote arm 있으면 추가**(없으면 "더 큰 모델/voting/프롬프트로 고치면?" 반론을 이 프레이밍으로 방어). [NEW EXP FLAG]

**R4. RQ2 circularity 방어.** (a) **독립 human-adjudicated 실LLM-bug corpus를 먼저 제시**(여러 모델 NL→JoI → 사람이 기대행동 판정, **gt_ir·verifier 안 보고** = leakage 차단 protocol 명시), mutation은 그 다음 stress coverage. (b) **3 claim 시각적 분리**: ①실제 lowering 버그 잡음 ②인접 construct 결함 검출(mutation) ③382 파이프라인서 silent mismatch 0. (c) **escaped 실제 케이스 예시**(버킷만 X). (d) **repair는 safety 증거 아님 → fail-closed가 safety 주장.**

**R5. RQ3 faithfulness 프레이밍.** "user study 대체물/substitute" 표현 금지 → **"승인 surface의 narrower prerequisite"**(rendering이 행동관련 IR 차이를 다 노출하는가)로만. **"surface 안 되는 것" taxonomy 추가**(device-name 모호성·도메인용어 오해·빠진 intent·rendering 前 reject되는 unsupported construct) = 정직 + 공격 선제.

**R6. Eval 누락 보강** (Setup/표에 명시): baseline 정밀정의(프롬프트·입력 artifact[IR/code/rendering/trace]·temp·retry·voting 여부) / **3-way safety ablation**(generation-only · LLM-judge-gate · OVLA-gate) / repair-loop accounting(시도·성공·지연·repair가 correct→wrong 만든 케이스) / **false-reject(over-reject 2건) main table에** / 복잡도별 scalability curve(boundary-event·timer·state-var·device·horizon) [NEW EXP FLAG] / **unsupported-intent rate**(현실 자동화 중 검증 前 reject 비율) [NEW EXP FLAG] / dataset provenance(382/24-cat, OVLA 문법에 맞춰 curate된 게 아님 명시).

**R7. 분량/figure/table 정리.** §2 RW = 1.25→**1.0p (early 유지 — near-collision lock; codex의 "뒤로" 거부)**. figure ~6개(F4 IR예시→F5/F2에 흡수, F6 worked-example=callout). table = **positioning 1개(§2, 옛 T1+T4 통합)** + mutation/coverage(§6/§8) + **RQ1 safety 행렬**. 본문 overflow 시 §5 Timeline IR을 §6 앞 0.5p로 더 압축(§5+§6를 "Design"으로 묶는 것도 허용).

**R8. 가장 큰 acceptance risk(codex)** = "code matches IR은 증명하나 automation matches user-intent는 아님 + user study 없음." → **R2(b) 2층 scope를 1페이지에 + R1 headline-first + R5 prerequisite 프레이밍**으로 정직하게 정면돌파(숨기지 않음).

---

## GUARDS (집필 내내 점검)
- 금지어: verified / model-checked / formally-verified / sound-acceptance / bounded-completeness. 유지: rejection-sound, event-triggered, fail-closed.
- **coined/내부 scaffolding 용어 금지(논문 표준어만)**: trust loop·hinge·deployment-axis·edge co-design·SPINE·"faithfulness-surfacing"(이름으로) → 전부 평문. ("confirmable"→"plain-language rendering shown for approval".)
- IR = "finite-state view / enumerable obligations", never "timed automata".
- em dash 금지. 일본어 금지(한/영만). EN+KOR sync는 prose-time.
- no-IRB: 사람 user study OUT, ethics="Not applicable". non-expert empirical 능력 주장 금지. future user-study foreground 금지.
- verifier 가치 = safety(silent-wrong→0), NOT accuracy lift. minus-IR gain = Role 0 부수효과.
- openai.txt 커밋 금지. paper.md/paper_kor.md(루트) 편집 금지 → 새 본문=Final/paper_kor.md.
