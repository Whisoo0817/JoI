# OVLA v2 — SMT 효율화 & Feedback 설계 (2026-07 논의)

> `ideas.md`의 §6(검증 방법)·§9(피드백)을 심화한 상세 설계. `efficient_SMT.txt`(SMT 효율 6개 전술)를 보강.
> 관통 원칙: 모든 주장은 **시스템 속성**(faithful/injective/edit-sound/localizable/closed-slot). human efficacy claim 금지(→user study). efficacy는 out of scope.

---

## Part 1. SMT를 효율적이게

`efficient_SMT.txt`의 6개 전술(① IR-guided slicing ② event-region abstraction ③ time-landmark 압축 ④ incremental solving ⑤ counterexample replay ⑥ two-tier)은 좋음. **아래는 그 파일이 놓친 것 + 전략적 레버.**

### 1-A. 파일이 놓친 것 (진짜 연구 포인트)
1. **Slice 합성 soundness (최대 리스크).** obligation별 Q1~Q4로 쪼개면 **국소 등가여도 조합이 발산** 가능(공유 persistent var/counter/순서/GlobalVariable이 slice 경계 넘음). naive slicing = unsound.
   - acyclic·무상태 부분 → slice 독립 증명.
   - 상태 공유(cycle/counter/RMW) → **assume-guarantee**(각 slice가 경계에서 타 slice 추상행동 가정). ← hard part.
2. **Decidability 경계.** theory 특정 필요: 시간/duration/counter/센서-상수 비교 = **linear arith(LIA/LRA)·difference logic(IDL)** 결정적·빠름. **임의 LLM 산술(RMW·두 센서곱=비선형)=NRA, undecidable/느림** → supported subset을 **linear fragment로 긋고 비선형은 Tier-1 sim fallback/fail-closed.**
3. **Sustain counter 심볼릭 인코딩 (time-landmark만으론 안 풀림).** `hold++; if hold>=thr fire`, thr≈18k tick unroll=폭발.
   - 표준 idiom → 닫힌형 `hold=(t−last_false)/period`, `fire⟺hold≥thr` (unroll 불필요).
   - 비표준 → **loop acceleration / k-induction으로 counter loop 요약.** ← hard part.

### 1-B. 전략적 효율 (가장 큰 레버 — 파일에 없음)
4. **오프라인 idiom-template lemma + τ-class 캐싱.** 템플릿 lowering이면 **각 idiom 템플릿 ≡ IR construct를 오프라인 SMT로 1회 증명**→캐시. 배포 시 template-conformant면 **"멤버십+slot값 검사"(no solver).** 논문의 **structural class τ(IR) 라우팅을 캐시 키로 재사용.** ⇒ **흔한 코드 SMT~0(캐시), 새 코드만 SMT(초 단위, deploy-time OK).** on-device 실현성 핵심.

### 1-C. 추천 아키텍처
```
[오프라인] idiom-template ≡ IR-construct SMT 증명 → τ-class lemma 캐시
[deploy-time]
 Tier 0: template 멤버십? → yes: slot값 검사 + lemma 재사용 (no SMT, ~ms)
 Tier 1: 빠른 boundary sim(기존) → 명백 reject/pass 분류
 Tier 2: SMT(slicing+region+landmark+incremental) → 최종 gate
         · linear fragment만; 비선형 fail-closed
         · SAT → counterexample replay로 encoding FP 제거
```
정확도 강조하려면 Tier 2가 최종 gate. real-trace는 sim/SMT 무관하게 **semantics↔현실 fidelity**로 항상 필요.

---

## Part 2. Feedback = contribution (C4)

순서: (a) document 형태 → (b) 무슨 slot을 어떻게 feedback → (c) 효율적 corrected code → (d) 효율적 re-SMT.

### 2-A. Document = 편집 가능한 구조적 뷰
read-only prose 아님. **IR slot의 편집 가능한 projection**: 섹션(Start/Repeat/Behavior/Stop), **불릿 하나 = IR 노드 하나(slot-id 태깅)**, 각 불릿에 예시 타임라인(IR-Sim 결정론 생성)+위험 slot엔 대조 이지선다. 각 slot이 **타입 가진 편집 컨트롤**로 노출.

### 2-B. Typed feedback (핵심 설계 결정)
**모든 feedback = `(slot-id, feedback-type, [new-value])`로 typed·bounded.** IR 제어차원이 닫혀 있어 feedback 공간도 유한·타입화:

| slot 타입 | feedback |
|---|---|
| condition | comparator/threshold/polarity/conjunct |
| edge | {none, rising, falling} |
| cycle | {one-shot, repeat-P, repeat-N} |
| duration | 시간 값 |
| call | device/method/args |

feedback 종류: ① 대조 선택("A아니라B")=slot+값 결정론 ② 제약 편집(picker/드롭다운)=slot+값 결정론 ③ 국소 거부("이건 안됨/빠짐")=slot 지목,교정 재도출 ④ free-text→localize+파싱.
→ **contribution: IR 닫힌 차원 유도 typed·slot-addressable feedback interface.**

### 2-C. Feedback → 효율적 corrected code
`(slot-id,new-value)`=IR 편집: ① IR 패치(그 slot만, 나머지 freeze) ② 국소 재-lowering(provenance로 해당 code-span만): **템플릿 lowering이면 값 변경=결정론 재인스턴스화(LLM 0회!)**, 구조변경=템플릿 swap; 프리폼이면 "나머지 유지, trigger만 falling" 제약 재생성. ③ JoI′=대부분 그대로, 바뀐 span만.
→ **typed feedback + 템플릿 lowering이면 대부분 교정이 LLM 없는 결정론 값 치환.**

### 2-D. Feedback → 효율적 re-SMT (incremental)
① **Incremental SMT**: base 제약(catalog/time/불변 slot obligation) 유지, 바뀐 slot obligation만 push/pop(학습절 재사용). ② **Obligation-scoped 재검증**: 바뀐 slot+의존자만 재-solve, 나머지 UNSAT 유지. ③ **Lemma 재사용**: 표준 idiom 되면 캐시 lemma→SMT 0. ④ **Collateral backstop**: JoI vs JoI′ code-diff 계산해 실제 바뀐 span obligation도 재검증(국소 재생성이 흘린 버그 방지).
→ re-check = (바뀐 IR obligation ∪ 바뀐 code-span) scope된 incremental SMT.

### 2-E. C4 정리
기술 3조각: ① typed slot-addressable feedback interface ② **provenance 그래프(slot-id↔문서조각↔code-span↔SMT obligation)** ③ incremental correct-and-verify.
- **보장(시스템 속성, study 0): edit-soundness** — 매 feedback 후 JoI′≡IR′ 재검증→"편집한 것=도는 것".
- **novelty**: 전체 재생성+재검증이 아니라 **매 편집 후에도 formally verified 유지하는 incremental verified-repair loop.**

---

## 두 Part를 잇는 통찰 (중요)
**IR의 obligation 분해가 세 payoff의 공유 substrate**: (P1) SMT slicing 단위, (P2) provenance/localization 단위, (P2) incremental 재검증 단위. → 하나의 구조(obligation-slice + provenance)로 **"SMT 효율 + feedback localization + incremental re-verify"가 전부** 나옴. SMT 효율화가 그대로 feedback 재검증을 incremental하게 만듦.

---

## 새 세션이 팔 open threads
1. **Slice 합성 soundness** — assume-guarantee 구체 설계(경계 인터페이스 정의).
2. **Counter loop 요약** — acceleration/k-induction으로 sustain counter를 unroll 없이.
3. **Feedback slot×type 전체 표** → 구현 스펙(각 타입의 편집 UI + IR 패치 규칙 + 재-lowering 규칙).
4. **오프라인 idiom-lemma 캐싱** — τ-class별 lemma 라이브러리 설계.
5. **Decidability 경계 확정** — linear fragment 정의 + 비선형 fallback 정책.
