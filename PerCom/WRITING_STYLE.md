# PerCom 문체 기준 — SenSys 원고에서 보존할 것

작성일: 2026-09-16. 근거: `docs/ovla0606.tex`. 이 원고에는 whisoo의 원문이 `%` 주석으로 남아 있고, 그 옆에 교수님이 다듬은 문장이 있다. 교수님 피드백은 "문장이 쉽게 읽히지 않는다. 부드럽게 바꾸느라 시간이 걸린다"였다. 아래는 그 43개 전후 쌍에서 뽑은 규칙이다. 내용·흐름은 PerCom에서 바뀌지만 문장을 쓰는 방식은 이 문서를 따른다.

`WRITING_GUARDRAILS.md`는 무엇을 주장할 수 있는지를 정하고, 이 문서는 어떻게 쓰는지를 정한다.

## 1. 교수님이 고친 방향 — 한 줄 요약

원문은 짧은 단정문, 대시 삽입구, 세미콜론 사슬, 수사 의문문, 메타 서술로 되어 있었다. 고친 문장은 **접속어로 시작하는 완전한 한 문장**, 목적·조건절을 앞에, 결과절을 뒤에 두고, 비유와 자기 언급을 뺀다.

## 2. 문장 규칙 — 전후 쌍으로

### 2.1 목적·이유·조건절을 앞에 둔다

| 원문 | 고친 문장 |
| --- | --- |
| Having established that..., we turn to the verifier itself... The question is simple: does the verifier actually catch wrong code? To measure this we detach... | **To evaluate whether** the verifier effectively detects incorrect code, **we** isolate it from the deployment pipeline and stress-test it using synthetic perturbations of correct JoI code. |
| We do not choose the number of mutants: every applicable site gets one first-order mutant, so the site count is the mutant count | **To ensure** deterministic coverage, we generate exactly one first-order mutant per applicable site (e.g., 436 call sites yield 436 `call_drop` mutants). |
| ...; whether the command is sent once or twice, the final device state is the same, so no distinguishing point remains | **Because** the final device state remains identical whether the command is sent once or twice, the deduplicated trace showed no distinguishable difference. |
| All of this detection happens on the synthesized event scenarios of §6.2, so we separately measure whether... | **Since** detection relies entirely on the synthesized scenarios from §6.2, we evaluated whether these scenarios adequately reach every check point. |
| Repeating the same pipeline with two weaker generators produced up to 1.8× more flagged candidates | **To evaluate robustness,** we repeated the pipeline using two additional generators, one smaller and one from a different model family. **Although** they produced up to 1.8× more flagged candidates..., the classification accuracy holds. |
| A user can approve a mis-displayed IR, in which case the verifier faithfully checks against the wrong spec. | **If** a user inadvertently approves an incorrect IR, the verifier **will** faithfully validate the code against that faulty specification. |

규칙: 실험 문단의 첫 문장은 `To evaluate X, we Y.` 꼴. 이유는 `Because ..., ...` 또는 `Since ..., ...`. 조건은 `If ..., ... will ...`.

### 2.2 대시 삽입구와 세미콜론 사슬을 문장으로 푼다

| 원문 | 고친 문장 |
| --- | --- |
| We wrote the commands to cover the reactive idiom families that commonly cause lowering errors in JoI—triggers, ...—and did not curate them to fit OVLA's IR schema. | Commands cover representative reactive idiom families prone to lowering errors in JoI (e.g., triggers, ...). The dataset was not curated to fit OVLA's IR schema. |
| —the residual class we already disclosed, appearing where expected. | As disclosed in §6.2 this residual class is excluded from boundary seeding, making this escape expected. |
| the ungated lowering fires 30 seconds after the room is vacated—all four ungated generations carried this sustain fault—while the gate-repaired lowering fires at 5:00 | all four ungated lowerings suffered from a sustain fault, prematurely turning off the TV just 30 seconds after the room was vacated. In contrast, the gate-repaired lowering fired precisely at 5:00, exactly as predicted by the IR. |
| each twisting one dimension of the slot set—comparator flips, ...; argument values ... on action slots; durations on time slots; ... | (itemize) Part A (Synthetic Check): ... These classes spanned condition slots (...), action slots (...), time slots (...), and structure slots (...). |

규칙: em-dash 삽입구는 쓰지 않는다. 나열은 괄호 `(e.g., ...)`이거나 별도 문장이거나 itemize. 세미콜론으로 문장을 잇지 않는다. 대비는 `In contrast,`로 새 문장을 연다.

### 2.3 콜론 뒤 조각, 수사 의문문, 메타 서술을 뺀다

| 원문 | 고친 문장 |
| --- | --- |
| The key point is that silence is part of the trace. | **Significantly,** silence is part of the trace. |
| and compared with the same criterion. To state the conclusion first: | using the same trace-equivalence criteria. **This re-examination confirmed that** every deployed automation conforms... |
| Measuring detection requires a large supply of code that is correct except for one slip. The experiment therefore proceeds as follows. | (삭제. 바로 "We take 328 valid (IR, correct code) pairs..."로 시작) |
| Where RQ1 twisted the IR and asked whether..., here we twist the code and ask whether... | (삭제) |
| : the tail comes from one class whose... | **This tail originates exclusively from** a specific automation class whose... |
| What is observed is the time at which the TV-plug-off action fires: | **The plot highlights** a sharp contrast in firing times: |
| Rejection Soundness side: was rejected code really divergent? | **Rejection Soundness:** |
| caption: Rendering faithfulness: do behaviorally different IR pairs render differently? | caption: Evaluation of rendering faithfulness against synthetic and real logic faults. |

규칙: 본문·소제목·캡션에 의문문을 쓰지 않는다(Evaluation 도입부의 RQ 나열만 예외). "The key point is", "To state the conclusion first", "The question is simple", "as follows" 같은 자기 언급을 쓰지 않는다. 앞 RQ와 짝을 맞추는 재치 문장은 뺀다. 콜론 뒤에는 완전한 절을 둔다.

### 2.4 짧은 단정문·부정문을 완전한 긍정문으로

| 원문 | 고친 문장 |
| --- | --- |
| These checks are not interchangeable. | These checks **serve** independent, non-interchangeable **purposes:** |
| This is an existence proof, not statistics. | This deployment **serves as** an existence proof of end-to-end integration. |
| It does not ask the user to approve arbitrary code or write formal properties. | This representation is intentionally minimal. It **avoids requiring** the user to approve arbitrary code or write formal properties. |
| The confirmed IR is the behavioral reference. | ...the confirmed Timeline IR, **which serves as** the behavioral reference, ... |
| If repair is exhausted, OVLA rejects the automation fail-closed. | If the repair budget is exhausted, OVLA rejects the automation **under a fail-closed policy.** |
| Efficiency numbers are reported as the precondition for on-device deployment, not as a contribution in themselves. | (삭제) Note that LLM cost is confined to the authoring step, and a deployed automation makes zero LLM calls. |

규칙: "X, not Y." 조각 대신 `serves as`, `provides`, `yields` 같은 동사로 완전한 문장. 두세 단어짜리 단정문은 앞 문장의 관계절로 접는다. 스스로를 낮추는 문장("not a contribution in themselves")은 빼고 사실을 적는다.

### 2.5 숫자는 문장 끝 목적어로, 주어는 사물

| 원문 | 고친 문장 |
| --- | --- |
| 0.97ms at the median over all 382 automations (10 repetitions each), | the verifier checks one automation **with a median latency of 0.97ms** (10 repetitions per automation) |
| With the 9B generator the outcome distribution is: | Using the 9B generator, **the pipeline yielded** the following outcome distribution: |
| A caution in reading the 99.3%: ... The number therefore says that | The 99.3% recall rate **warrants a caution:** ... **This high score indicates that** |
| These numbers concern divergence from the approved IR, not whether the IR matched the user's true intent | **Note that** these metrics evaluate correctness relative to the approved IR, **distinct from** whether the IR itself aligns with the user's latent intent |

규칙: 문장을 숫자로 시작하지 않는다. 주어는 the verifier, the pipeline, this score, the plot처럼 사물이고 동사는 checks, yielded, indicates, highlights, confirmed. 단서는 `Note that ...`로 연다.

### 2.6 비유·구어 대신 결과절

| 원문 | 고친 문장 |
| --- | --- |
| —the scenarios do not just walk the spec; they reach inside the code under test. | , **proving that** the scenarios thoroughly test the implementation, not just the specification. |
| If even one slot difference rendered identically, the user could not tell a wrong IR from the right one, and the gate would then check against the wrong reference. | If different slot configurations rendered identically, users could not distinguish a faulty IR from a correct one, **compromising** the verification gate. |
| and it cannot hide behavior that the IR contains. | The rendering cannot introduce behavior absent from the IR, **nor** omit behaviors contained within it. |
| the IR is both an approval surface through its rendering and a behavioral reference | **Thus,** the IR serves a dual purpose: **as** an intuitive approval surface through its rendering, **and as** a rigorous behavioral reference |

규칙: "walk the spec", "one slip", "twist" 같은 비유·구어는 쓰지 않는다. 결과는 문장 끝 `, proving that ...` / `, compromising ...` / `, making ... expected`로 붙인다. 병렬은 `cannot X, nor Y`, `as X, and as Y`, `both X and Y`로 맞춘다.

### 2.7 과정 서사를 지운다

원문에는 "평가 도중 진짜 버그 두 개를 찾았고, falling 시나리오를 추가해서 고쳤으며, 아래 수치는 그 뒤의 것이다"라는 문단이 있었다. 교수님은 이 문단 전체를 지우고 최종 수치만 남겼다. 실험 절에서는 무엇을 했고 무엇이 나왔는지만 쓰고, 어떤 순서로 발견했는지는 쓰지 않는다. (PerCom에서 이런 발견은 아티팩트나 각주로 보낸다.)

같은 이유로 "Metrics: one per question—..." 같은 요약 반복 문단도 지워졌다. 같은 내용을 두 번 말하지 않는다.

## 3. 유지할 문단 구조

- **볼드 리드인 문단.** `\textbf{Why this is hard:}`, `\textbf{Running example:}`, `\textbf{Rejection Soundness:}`처럼 짧은 명사구 리드인 뒤에 콜론 또는 마침표. 소절을 늘리지 않고 문단을 나누는 방법이다. PerCom 9쪽에서도 이 방식이 subsection보다 싸다.
- **평가 도입부는 질문 나열.** "Our evaluation asks four questions, ordered as the pipeline reaches the user. Does ...? Does ...? ... Each answer is a premise for the next." 이 자리만 의문문을 허용한다. 그 뒤 "Setup." 문단에 하드웨어·모델·데이터셋.
- **실험 소절 순서.** 첫 문장 `To evaluate X, we Y.` → Design(필요하면 itemize) → Results(숫자는 표를 가리키고 본문엔 해석) → 남는 사례를 하나씩 설명 → 읽을 때의 주의(`warrants a caution`).
- **한계는 "where they arise".** 각 절이 자기 한계를 그 자리에서 말하고, Limitations 절은 그것을 가리키기만 한다("are stated where they arise (§6.5, §8.2, §8.3)").
- **문단 첫 문장이 주장, 나머지가 근거.** 예: "This representation is intentionally minimal." → 이유 두 문장 → "Thus, ..." 정리.

## 4. 자주 쓴 접속어와 동사 (그대로 재사용)

- 문장 머리: `To evaluate ...,` `To ensure ...,` `Because ...,` `Since ...,` `Although ...,` `If ..., ... will` `Once ...,` `Note that` `Specifically,` `In contrast,` `Consequently,` `Accordingly,` `Thus,` `Crucially,` `Significantly,` `Finally,`
- 동사: `serves as` `provides` `yields` `confirms/confirmed that` `indicates that` `highlights` `originates from` `warrants` `constitutes` `spans` `comprises` `exposes` `absorbs`
- 부사: `deterministically` `faithfully` `silently` `precisely` `exclusively` `strictly` `inadvertently` `prematurely`
- 대비: `rather than` `distinct from` `not X but Y`(완전한 절 안에서만) `as X, and as Y`

## 5. PerCom에서 새로 지킬 것 (SenSys와 다른 점)

- SenSys 문체는 형식 검증 독자를 의식해 "deterministic", "fail-closed", "rejection-soundness"를 자주 썼다. PerCom은 가드레일 §11.1대로 본문에서 그 용어를 줄이지만, **문장 구조는 그대로** 둔다. 용어를 쉽게 바꾸는 것과 문장을 짧게 끊는 것은 다른 일이다.
- 금지어(가드레일 §0·§2·§5·§10)는 이 문체 규칙보다 우선한다. SenSys 문장을 재사용할 때 `first`, `deterministic gate`, `bounded`, `on-device`, `directly executes`가 섞여 들어오지 않는지 본다.
- SenSys 문장 재사용은 문장 단위로 한다. 문단째 옮기지 않는다(내용·주장이 바뀌었다).

## 6. 쓰고 나서 볼 목록

- [ ] em-dash 삽입구 0개, 세미콜론 사슬 0개.
- [ ] 본문·소제목·캡션에 의문문 없음(Evaluation 도입부 제외).
- [ ] "The key point", "as follows", "To state the conclusion first", "The question is" 없음.
- [ ] 숫자로 시작하는 문장 없음.
- [ ] 실험 문단 첫 문장이 `To evaluate X, we Y.` 꼴.
- [ ] 두세 단어 단정문은 관계절로 접었는지.
- [ ] 발견 과정 서사 없음. 같은 내용 두 번 없음.
- [ ] 비유·구어 없음.
