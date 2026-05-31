# OVLA — Paper Skeleton (workflow-reframed, 2026-05-30)

> New structure (replaces `paper.md` flow — do NOT reuse it). Abstract = `Final/abstraction.md`.
> System = **OVLA** target DSL = JoI (existing).
>
> **HERO (reframed)** = a **verified deployment workflow for non-experts**: a non-expert's NL request becomes a *verified* automation with **no expert and no cloud** in the loop, via a **two-stage safety net** built on **Timeline IR**:
>   - **Stage 1 (intent↔IR)**: ★포인트 = **검증 oracle(IR)을 코드 생성 *전에*, end-user(비전문가)가 직접 확인·확정한다.** user가 IR의 직관적 평문 rendering을 확인 → 비전문가가 *검증 기준을 스스로 세움.* (error-propagation 차단은 *부수 효과 중 하나*일 뿐 핵심 아님; 사람이 잘 잡지만 100% 아님 → user study가 입증.)
>   - **Stage 2 (IR↔code)**: deterministic LLM-free verifier MUST catch any code-vs-spec divergence (no FN on set) → pass=deploy / fail=repair or reject (fail-closed).
> **Timeline IR = 중심** (확인 대상 + 검증 기준 + 생성 틀). 주요 기여 = IR.
>
> **Guards:** never "verified/model-checked/sound/formally-verified/bounded-completeness"; keep "rejection soundness","event-triggered"; IR = "finite-state view / enumerable obligations — NOT a model-checking target", never "timed automata"; upstream (intent/service/device) = substrate not hero; no em dash (AI-tell); EN+KOR sync at prose time.
> **★ verifier 가치 = safety(silent-wrong 0), NOT accuracy lift(+3.4%는 헤드라인 금지). minus-IR의 큰 generation gain = "Role 0" 부수효과로 정직히, hero(verified-deploy) 흐리지 말 것.**
>
> **`* …` = 그 파트의 lock (위반 금지). 새 결정은 해당 파트에 `*`로 추가.**

---

## Section order

- **§0 Title + Abstract** — see `abstraction.md`.
- **§1 Introduction** — beats below (non-expert + no-cloud + verified-deploy).
- **§2 Background & Problem** — reactive automation; verification-oracle 부재; multi-stage error propagation; define "correct" = Rung-1.
- **§3 System Overview** — full pipeline figure + **two-stage safety net** (Stage-1 user-confirm / Stage-2 verifier) + IR **triple-role** (confirm-target / verification-oracle / generation-scaffold).
  * upstream (intent/service/device mapping) = substrate, NOT contribution (명시 문장).
  * 2층 분리 명확히: Stage-1 = 사람이 직관적으로(잘 잡지만 100% 아님), Stage-2 = 기계가 결정론적으로(반드시).
- **§4 Timeline IR** — non-expert-confirmable (NL rendering, **deterministic/no-LLM**) + machine-checkable; finite-state view → enumerable obligations.
  * "finite-state view / enumerable obligations — NOT a model-checking target"; never "timed automata".
  * NL→IR은 LLM, **IR→plain-language rendering은 결정론(LLM 없음)** → 사용자가 보는 게 IR을 정확히 반영(환각 없음).
- **§5 Verifier (CORE)** — IR→FSM→construct-derived boundary events→trace-equivalence; LLM-free, on-device. **상세 흐름 = 아래 "§5 detail" 블록** (정당화 → ★기여 event synthesis → omission 검출 → claim ladder → adequacy 실험 → 한계).
  * verdict 결정론·LLM-free. T1 determinism + T2 **rejection soundness** (flag ⇒ REAL divergence). **"pass ⇒ correct" 금지.**
  * IR-FSM은 **test-generation projection**이지 model-checking 대상 아님. completeness 류 단어 금지 → **bounded-fragment** 설계 근거로(아래 guard).
- **§5b Structural exemplar routing (SUB, IR's 3rd payoff, [PLANNED]/unbuilt)** — IR 구조로 exemplar 동적 retrieval; verifier-accepted exemplars accumulate → improve retrieval (NOT "self-learning"); generator prompt-construction only, verdict LLM-free.
  * routing은 **IR STRUCTURAL SIGNATURE 기반** (IR-linked가 핵심, generic text-RAG 아님). hero는 이것에 의존 X.
- **§6 Why existing verification doesn't transfer** — `why_not_fsm.md` 요약; vs MBT / monitor synthesis / formal verification (+ honest concession).
- **§7 Implementation** — ≤9B 4-bit on-device, no fine-tuning; multi-stage decomposition; edge co-design (edge가 검증을 LLM-free/on-device로 강제).
- **§8 Evaluation** — RQ below.
- **§9 Related Work** — our real survey (AutoTap/TAPFixer, GPIoT/TaskSense/SimuHome/Sasha, openHAB).
- **§10 Limitations** — coverage ceiling (n%2 counters); Rung-1 not all-input; **Stage-1은 사람 의존(완벽 아님)**; generalization.
- **§11 Conclusion.**

---

## §1 beats (workflow flow)
1. 비전문가가 NL로 개인 IoT 자동화를 요청 → LLM이 reactive 규칙 코드 생성 → 배포 전 "의도대로인가" 확인 필요.
2. reactive 자동화라 "의도대로"가 특히 어렵다(fire-once vs every-time, 지속, 반복, 순서) → 배포 전 행동 확인이 *필수*. (※ multi-stage error propagation은 *부수적으로 한 번만* 언급, §1 메인 beat 아님.)
3. 기존 길은 다 막힘: (a) **expert가 명시 spec 작성**(AutoTap류) = end-user 못 함, (b) **코드 다 만들고 검증** = reactive엔 비교할 oracle 없음 + user가 코드 못 읽음, (c) **LLM judge로 검증** = 못 믿음(9B P=0.71; 복잡·multi-GT에서 클라우드도 실패 — RQ2). → "prerequisite absence" (NOT "impossible").
4. → OVLA의 **2층 안전장치**: (1) **검증 oracle(IR)을 코드 생성 *전에* non-expert가 직접 확인·확정**(NL rendering) = 비전문가가 검증 기준을 세움 (부수효과: error propagation을 읽을 수 있는 지점에서 차단), (2) **결정론 LLM-free verifier가 IR↔code를 무조건 검증**, fail→repair/reject.
5. → **비전문가의 NL 명령이 expert도 cloud도 없이 verified 배포된다. silent-wrong = 0.**
- Contributions: **C1 Timeline IR (hero)** = non-expert-confirmable spec + machine-checkable oracle / **C2 two-stage verified-deploy workflow** (user-confirm + 결정론 verifier, fail-closed) / **C3 on-device ≤9B no-cloud LLM-free-verifier** / **C4 evaluation** (+ SUB exemplar routing, [PLANNED]).

## §5 detail — Verifier (flow + ★technique + adequacy)

> 흐름: **reactive·temporal·behavioral IoT 특성**을 가져와서 → 왜 무거운 형식기법(MC/SMT) 없이 가벼운 온디바이스 검증으로 충분한지 정당화 → 그 정당화를 실현하는 ★핵심기술(IR-FSM→event synthesis) → commission+omission(이상행동) 검출 → 무엇을 주장/실험으로 입증하는지 → 정직한 한계. (codex 2-round vetted.)

### §5.0 왜 behavioral·왜 lightweight (정당화; §5.1을 forward-ref)
* 출발: 생성 JoI엔 **정적 oracle 없음** + **non-canonical**(같은 행동 여러 표현) → 동등성은 구문 아닌 **behavioral(trace)** 로 봐야.
* **IoT 시간적 특성 = 형식 뼈대**: reactive 자동화 행동은 **(시간 랜드마크 × 센서값 구간 × edge × bounded 내부상태)** 의 유한 추상 위에서 **piecewise-constant**(조각마다 일정). 행동 불연속 후보 = guard 임계값 / 조건 edge / 시간 랜드마크(delay·duration·period·cron) / 상태 전이.
* **유한한 근거**: IR은 재귀·무한루프 없이 **bounded 타이머·카운터·유한 제어**만 허용 + **고정 7일 지평**. → (시간×센서×내부상태) 조합이 유한 → cell당 대표 입력 하나로 그 cell 전체를 검사.
* → full equivalence/model checking/SMT **안 함.** **bounded trace-equivalence**(고정 지평 + tolerance)를 결정론·solver-free·on-device로. **"IoT의 시간적 구조 자체가 가벼운 온디바이스 검증을 충분케 한다."** 단 MC/SMT의 *대체 아님* = **배포시점 필터.**
* ★ **GUARD**(codex): "decided / suffices / **exactly** the boundaries / no unbounded computation / realistically rare / makes verification sufficient" 같은 **completeness 단어 금지** → **bounded-fragment 설계 근거**로 표현. **내부상태 축 빼먹지 말 것**(hysteresis·토글·counter·sustain은 센서값만으론 설명 안 됨). [[reference-verifier-rigor-theory-2026-05-30]]

### §5.1 ★기여: Construct-Derived Boundary Event Synthesis (IR-FSM → events) — 묻지 말 것
* IR → FSM **결정론 도출**(`ir_fsm.derive_fsm`, LLM 없음): call/wait/delay/read/if/cycle/break **obligation** + after-edge(순서) + branch guard + cycle 재arm.
* 경계를 **IR 결정점**(guard 임계값·edge·타이머·cron·상태전이)에서 수집 → 각 경계 주위에 **대표 이벤트 1개**(지속 boundary 값) 합성. *(IR-driven only; "IR∪JoI 합집합 합성"은 미구현 + 불필요 — 2026-05-31 실험으로 확인, 아래.)*
* **crossing 크기 무관**(31°C나 100°C나 같은 구간) → 중요한 건 *타이밍*. 
* ★**poll→react 검출 확인 (2026-05-31)**: C17_10(15분 폴링)에서 정확 JoI=PASS, react 버그(빠른 폴링)=L2-FLAG. event_synth가 *지속(persistent) 경계값*만 심어도, react는 지속 입력에서 발화 빈도/타이밍이 달라 잡힘. **transient-spike에서만 보이고 모든 지속 입력엔 IR과 동일한 버그**는 자기모순적(연속 감시면 지속 입력서도 빈도 차이)이라 LLM이 안 만듦 → **union 불필요.** (transient-only는 §5.5 limitation 각주로.)
* IR 기반(surface syntax 아님): read→source 센서 추적, abs/min/max+clamp, value domain 양끝(≥2점=affine 검출), RMW skip, **re-arm 2nd edge(=1-switch 맛)**.
* §5.0 정당화 단락은 이 서브섹션을 **forward-ref만** 하고, 알고리즘은 여기서 contribution box로 세운다(묻히지 않게).

### §5.2 Trace-equivalence + 이상행동(omission) 검출
* 두 시뮬레이터(IR sim, JoI sim) 실행 → action trace를 ±tolerance(max 500ms, 10%) 윈도우 그룹·dedup·순서보존 비교.
* **commission + omission 동시 검증**: trace의 **침묵(silence)** 도 trace의 일부 → IR trace의 빈 구간 = "여기선 아무것도 안 함"의 **oracle.**
* 이상행동 예("15분마다 체크"인데 react로 오역): **2026-05-31 실험으로 검출 확인** — react 버그는 IR의 *지속 boundary 시나리오*에서 발화 빈도/타이밍이 달라 IR(드물게/침묵) vs JoI(과다 발화) **trace 불일치 → flag.** (transient-only 코너는 자기모순적이라 불필요 — §5.1.)
* **complete-behavior IR이라 가능**; partial property/LTL은 침묵을 못 박아 이상행동을 못 잡음. (Q1의 "complete behavior vs constraint" 차이의 실전 효과.)

### §5.3 Claim ladder
* verdict 결정론·LLM-free. **T1 determinism + T2 rejection soundness**(flag ⇒ REAL divergence). **"pass ⇒ correct" 금지.**
* "real divergence" RELATIVE 정의: 두 sim 의미론 + (t,service,method,args) obs model + tolerance + **bounded fragment F** → bounded conformance(Rung-1), **proof 아님.** **TCB = 두 시뮬레이터 + tolerance + 등가관계**(LLM 제외 = 신뢰 축소). soundness는 "Coq 증명"이 아니라 "시뮬레이터 충실성으로 환원 + mutation 증거"로 표현.

### §5.4 Adequacy 증거 (실험; 상세 §8 RQ2)
* **exhaustive construct-derived mutation**(헤드라인): operator family(**12개 active**: arg_numeric/enum_flip/call_drop/call_add/tick_scale/guard_polarity/comparator/assign_init/cmp_direction/arith_op/break_drop/**wait_drop** + 2 제외 quantifier·tag_swap=trace 관측모델 밖)를 **IR construct × 결함차원**에서 도출 → 적용가능 **모든 위치에 1차 mutant 전부** 생성 → **99.3% 검출 (1551/1562 genuine; 331 seed)**. ★**cap==uncapped 동일** = truncation 없음 = *1차 전수*. **equiv-filter = 모든 시나리오 기준**(happy 하나 아님 = 더 엄격; equiv 111). "버그 몇 개 심음"이 아니라 **"단일점 IR-결함 전수열거"**. **wait_drop = 54/54=100%**(gate-closed 시나리오로 복귀). **survivor=11 전부 특성화**: 8 = `comparator >=→>` sub-tolerance 타이밍(0.1s<0.5s tol, 설계상) + 1 = `call_drop` fan-out 중복 + **2 = C14_4 arithmetic-RMW**(currentBrightness가 read-modify-write라 boundary-seed 제외 → 미exercise = 연속산술 한계, §5.5/SMT future). 고차결함=coupling effect, mutation=real-fault proxy=Just'14. (2026-05-31 v3; 이전 99.05%/1475/14, 99.3%/1330/9는 stale.)
* **coverage**: **IR-FSM transition + guard-boundary** = Ammann-Offutt edge/0-switch(state coverage subsumes) + BVA; re-arm=1-switch; **+ gate-closed(wait cond-false)**. spec **97.4%(342/351)** + impl JoI-branch **95.6%(566/592)**. 미실행 9 = 합성불가 분기 guard(C13 var-comparison + C14_3 arithmetic; 별도 보고, coverage 주장 X).
* **residual 정량**(의심 해소): Good-Turing Ĉ=0.909 + Chao1 미관측≈0.5 — **단 n=11라 통계 약함 → 주장 핵심은 *특성화*(survivor 11개 전부 알려진 3종: sub-tolerance/fanout-redundant/arith-RMW)**, Good-Turing은 각주.
* **vs LLM judge**(RQ2): verifier sound vs judge over-reject/miss + 복잡도별·multi-GT·GPT-4o arm("클라우드도 못 잡음").

### §5.5 Limitations (정직)
* **연속 산술**(action arg가 센서의 연속함수, 예 setBrightness(temp*2)): 대표 ≥2점이 affine 발산은 잡지만 임의 고차는 미증명 → **SMT future**(전수증명=이벤트 불필요화; 시간 여유 시, 100ms→tolerance 이산화로 부담↓).
* **bounded 7일 지평**(여러 period·cron 주기 포함, 너머 미검증); partition=참 등가분할 **가정**(IR boundary로 합성 + mutation 99.3%로 검증).
* **transient-only 코너**(모든 지속 입력엔 IR과 동일, transient glitch에서만 다른 버그) = 이론상 IR-only가 놓칠 수 있으나 자기모순적이라 LLM이 안 만듦(2026-05-31 확인) → 각주 처리.

---

## §8 Evaluation — RQ + 각 특징
> 핵심: "정확도 경쟁"이 아니라 **workflow의 각 고리(사람 확인 가능 / 기계 반드시 검증 / no-cloud)가 성립함**을 component별 입증. headline = silent-wrong 16%→0% (capability matrix).
> **BASELINE 재배치 (codegen 경쟁 → 검증 대안)**: 메인 비교 = **LLM judge(9B/GPT-4o)** = verification 대안(RQ2); workflow 차별 = **capability matrix**(AutoTap expert-spec / code-then-verify / cloud-judge, RQ5); **minus-IR + SOTA codegen self-correction = 보조(Role 0)**, 메인 아님(IR op 보여주면 generation 효과 직관 수긍).
> **정확도 3종 = 다 측정하되 보조**: (a) NL→IR = 자동 IR-vs-gt_ir 정확도 + user study confirmability(RQ1), (b) IR→JoI = Stage-B acc + verifier detection(RQ2, verifier 작동 무대), (c) E2E = 전체. headline은 정확도 아니라 safety.

- **RQ1 — Stage-1 (사람이 IR로 의도오류를 잡고 고치나) = USER STUDY, P0 메인** [#65]
  * **per-fault-class confirmation + correction** (단순 readability 아님): 비전문가 N명에게 명령 + 시스템 IR rendering 제시, 일부에 fault 주입(wrong trigger / condition polarity / delay·duration / target device·tag / any-all quantifier / schedule / missing-cancel / stale-state).
  * 측정: **fault-detection recall + correct-accept specificity(over-reject 방지) + correction 성공률 + per-construct 분해 + time/confidence**.
  * 비교군: IR rendering **vs 생성 코드 vs raw trace** (within-subject, 균형배치). faulty+correct 둘 다.
  * powered + preregistered. 참가자 = 타깃 사용자 닮은 non-expert (CS 학생만 X).
  * 주장: "비전문가가 코드/trace보다 IR로 의도오류를 잘 잡고 고친다" → Stage-1 작동. **(가장 fragile = 가장 중요한 de-risk: 이게 무너지면 'LLM이 만든 spec에 대한 검증'으로 전락.)**

- **RQ2 — Stage-2 (기계가 틀린 코드를 무조건 잡나) = DETECTION** [부분 done]
  * 맞는 JoI + 버그 주입 JoI(mutation)를 주고 verifier가 가려내나: **mutation 99.3%(1551/1562 genuine; 12 op incl wait_drop; cap==uncapped=전수; equiv-filter=all-scenario, 111 제외), coverage spec 97.4%(342/351) + impl JoI-branch 95.6%(566/592)**. survivor 11 = 8 sub-tolerance comparator + 1 fan-out 중복 + 2 C14 arith-RMW(전부 특성화). uncovered 9 = 합성불가 분기 guard(C13 var-comparison·C14_3 arithmetic). tolerance sweep = non-circular. (※ natural-error 검출은 별개: 데이터셋 실제 faulty 출력에 R=1.0 no-FN — mutation survivor와 혼동 금지.)
  * **vs LLM judge** (9B P=0.71 done): "LLM은 못 가린다".
  * **★ "클라우드도 못 잡는다" 실험 (의심 해소)**: ① **복잡도별**(코드 길이/중첩/디바이스 수/시간조건) — ours(평평) vs **GPT-4o**(클라우드 최강) vs 9B → 복잡할수록 LLM 급락, 우리 평평. ② **multi-GT**(같은 의도의 여러 valid 코드) — LLM judge는 valid 변형을 over-reject, 우리는 trace-equiv라 idiom-invariant 통과. (GPT arm = openai.txt 재추가 + 비용.)
  * **trace-bound adequacy**: "왜 bound 충분? 무엇이 escape?" (bound-sensitivity + 무엇을 못 잡는지 명시).
  * verifier는 **파이프라인 독립** (IR+JoI 쌍만, gt_ir 사용) — 전체 파이프라인 먼저 안 돌려도 됨.

- **RQ3 — 시스템 안전 = HEADLINE (capability matrix)**
  * **silent-wrong-deployed 16% → 0%** (검증 OFF 16%가 조용히 배포 → ON에서 다 검출), repair 32% / reject 나머지 (fail-closed). qualify: benchmark·trace-bound·confirmed-IR 가정 하에서(보편 정확성 아님).
  * **표**: `[System | Correct deployed | Silent-wrong | Repaired | Rejected | Needs-expert | Needs-cloud]` — 우리만 silent-wrong 0 + no-expert + no-cloud.
  * **failure taxonomy**: 무엇이 reject되나(fail-closed가 "어려운 거 다 reject"로 안 보이게). **repair-loop cost/stability**: 반복 횟수/oscillation/error-class별 성공.

- **RQ4 — feasibility (no-cloud/on-device)**
  * ≤9B 4-bit local, stage별 latency, **LLM-free verifier overhead 무시 가능**(vs cloud judge). on real edge hub(Jetson/mini-PC + HA + Matter/Zigbee, subset 실배포 rest sim) [RQ8 deploy 통합].

- **RQ5 — workflow 차별 (capability matrix + 정량)**
  * vs expert-spec(AutoTap: expert 필요) / code-then-verify(reactive oracle 없음 + user 코드 못 읽음) / SOTA codegen self-correction(oracle 없는 LLM self-critique = 틀린 거 못 잡음). 능력 행렬 + 가능한 곳만 정량 (weak baseline 경쟁 금지).

- **보조 (뒤, 정직히) — accuracy + IR ablation**
  * end-to-end accuracy (Stage-B ON/OFF) + **minus-IR ablation** = IR이 generation도 크게 돕는다 (**Role 0** 부수효과). hero(verified-deploy) 흐리지 말 것. self-correction은 비교군 동등 통제.

---

## Open decisions (fill as we go)
1. 이름 OVLA vs OVLA 최종확정. 2. user study N/IRB/fault set (#65, P0). 3. GPT-4o judge arm(키 재추가) + 복잡도/multi-GT 설계. 4. baseline = capability matrix 구성 + minus-IR self-correction 통제. 5. deploy hardware + device list. 6. trace-bound adequacy 실험.
