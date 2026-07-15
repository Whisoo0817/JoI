# OVLA v2 — 아이디어 정리 (2026-07-15 전면 개편: retrieve–edit–verify 구조)

> 상태: 아이디어 정리 단계 (논문 작성 아님). 2026-07-15 세션에서 전면 개편 — 구버전(behavior contract 중심)은 git 이력 참조.
> 배경: v1(SenSys 제출본) 3약점 — ① IR rendering user study 부재 ② mutation/coverage 순환 평가 ③ 실동작 보증 부족 — 의 해소.
> 보조 문서: `smt_and_feedback.md`(SMT 효율 전술·typed feedback 상세 — §5·§7에서 참조, 대부분 유효), `efficient_SMT.txt`(SMT 효율 6전술 원본).

---

## 0. 한 줄 전환 (v1 → v2)

- v1: 매 명령마다 **전부 새로 생성 → sim boundary trace-equivalence로 검증**.
- v2: **인증된 스키마 라이브러리에서 구조가 가장 가까운 것을 검색 → slot-level로 수정 → 수정분만 incremental SMT로 재인증 → 배포.** 디코딩은 선제 치환 draft 기반 speculative editing으로 가속.

### 통일 원리: "생성 = 수리(repair)의 특수 케이스"
| 상황 | base | Δ의 출처 |
|---|---|---|
| 최초 생성 | 검색된 certified 스키마 | IR ⊖ 스키마IR |
| self-correction | 반례 난 자기 코드 | 반례가 지목한 obligation |
| 사용자 feedback | 배포된 자기 코드 | feedback 라우팅 (§7) |

셋 다 같은 연산: **인증된 base를 Δ만큼 고치고 증명을 상속.** from-scratch 생성 개념이 시스템에서 소멸 — 비용은 항상 "가장 가까운 인증물로부터의 거리"에 비례.

### 관통 원칙 2개
1. **불안정한 LLM 채널을 통과하는 정보량 ∝ 의도 변화량.** 전체 재생성 = 이미 맞았던 부분까지 재추첨(re-roll; v1 instability 데이터가 근거). delta 경로 = 바뀌는 부분만 채널 통과 + 나머지 보존은 증명으로.
2. **모델 컴퓨트는 행동이 미결정인 지점에만.** 문법이 골격을, draft가 복사를, 모델은 진짜 선택 지점만.

---

## 1. 세션 확정 결정 (락)

1. **Spine A: SMT translation validation이 deployment gate.** sim은 gate에서 강등 → ① SAT 반례 replay(인코딩 FP 제거) ② 인코더와 differential testing(**v1 순환 평가의 해소**: 두 독립 semantics 구현의 상호 검증) ③ 렌더링·예시 타임라인 생성.
2. **컴파일러 없음. 단, "불가능" 주장 금지.** 닫힌 IR이라 3~6주면 만들 수 있음(리뷰어도 앎). 방어 3종: (a) **gate는 임의 코드**(사람 수정·벤더 툴·기존 rule)를 심판해야 하고, 컴파일러는 자기 출력만 보장 (b) 플랫폼당 비용: semantics 인코더 ≪ certified compiler — "기술(describe) ≪ 생성(generate)" (c) 컴파일러가 있어도 translation validation은 필요(Alive2의 존재 이유). **latency로 SMT를 방어하지 말 것** — §10 설계공간 표로 방어.
3. **사용자 IR 확정(oracle) 단계 제거 = user study 완전 회피.** intent-conformance는 scope 밖으로 정직 서술. 완화 장치: 결정론 렌더링 disclosure(승인 요구 없음) + behavioral consensus 후보(§12). 주장은 "silent **mechanism** 오류의 제거"; slot 오류는 visible이라는 v1 원리(primitive-vs-idiom) 재사용.
4. **소형(<8B) 모델·클라우드 라우팅 스토리 보류** (아이디어는 §12 보존).
5. **Composition 정리 아이디어 철회.** 스키마를 통짜로 인증하므로 조합 건전성 문제가 발생하지 않음. (obligation slicing soundness는 full SMT 최적화 문제로만 잔존; 프로그램이 작아 통짜 인코딩이 먼저.)

---

## 2. 아키텍처 (v2 메인 루프)

### 인증된 스키마 엔트리
```
스키마 = ( IR 스켈레톤 (slot = 심볼릭),
          코드 스켈레톤,
          파라미터 SMT 증명 (∀slot ∈ validity domain) + validity domain,
          τ-signature (구조 클래스; v1 routing 재사용),
          provenance (slot ↔ code-span ↔ obligation),
          obligation별 unsat core (증명이 의존한 제약 "영수증") )
```

### 온라인 파이프라인
```
Command
 → (LLM) IR 추출
 → τ(IR)로 스키마 검색 (구조 유사도 라우팅)
 → Δ = IR ⊖ 스키마IR  (slot-level diff, 결정론)
 ├─ [경로1] Δ = 값 slot뿐 (threshold/period/device/args):
 │     코드 결정론 치환 (LLM 0회) + validity domain 확인만 (solver 0회)   [~ms]
 ├─ [경로2] Δ = 구조 포함 (edge↔level, branch/call 추가 등):
 │     선제 치환 draft로 speculative editing (§6)
 │     + 수정분만 incremental SMT (§5), 디코딩과 overlap                  [ms~수백ms 체감]
 └─ [경로3] 매칭 없음 / Δ 과대:
       freeform 생성 + full SMT (fail-closed)                            [수초, 최초 1회 정가]
       → 통과 시 slot 일반화하여 새 스키마 등록 (라이브러리 성장)
 → 배포. 반례/feedback 시 repair loop = 경로2와 동일 연산 (base = 자기 코드)
```

### 라이브러리 특성
- **Self-bootstrapped**: 경로3(생성+full SMT 인증)이 라이브러리를 만들므로 **컴파일러 불필요** (R1 우회).
- **Cold start**: 24 τ-class 코퍼스(382셋 기반)로 시드해서 출하.
- **Home-specialized 성장**: 집이 쓸수록 그 집의 명령 분포에 맞게 라이브러리가 커져 경로3 비율이 하락 — "오래 살수록 싸지는 시스템" (cold-start 곡선으로 실증, §9).
- gate는 retrieval 성공에 **무의존**: 검색이 실패해도 안전·정확성 불변, 잃는 건 효율뿐.

---

## 3. 왜 Timeline IR인가 (재정의: certified repair space)

SMT가 JoI ≡ IR을 증명하는 순간 IR은 "LLM의 스케치"에서 **"배포 코드의 인증된 모델"**로 승격. IR 위의 모든 행위(diff·편집·검색)가 증명에 의해 곧 코드에 대한 행위가 됨. 코드가 아닌 IR에서 수정해야 하는 이유(전부 시스템 속성, study 불필요):

1. **닫힌 유한 slot 공간** → feedback/수정이 "자연어로 빌기"가 아니라 풀 수 있는 유한 문제. Δ 정의 가능, 검색 가능(τ), repair 탐색 가능.
2. **Edit locality** → 의도 변경이 코드에선 비국소적(flag·reset 로직), IR에선 slot 플립. 측정 가능(코드 AST 변경량 vs slot 변경량).
3. **인증된 링키지** → 증명 없으면 IR 편집은 허구 편집. 증명이 있어야 "편집한 것 = 도는 것".

한 줄: **코드는 실행을 위한 형태, IR은 통제를 위한 형태. IR은 spec이자 생성의 scaffold이자 증명의 구조(obligation 분해·provenance·재검증 단위)다.** 렌더링/문서는 부산물이고 IR의 본업은 수정의 착륙 지점.

---

## 4. SMT gate (보장 기둥)

### 인코딩 원칙 (smt_and_feedback.md Part 1 유효)
- **tick unrolling 금지** → landmark 시간 압축(전이 지점만 심볼릭 시각; difference/linear arithmetic). 문제 크기가 IR 복잡도에 비례.
- 센서 도메인 **region abstraction** (조건식이 구분하는 구간 + off-by-one).
- **Linear fragment**로 경계: 비교·덧셈·상수배 = 결정적·빠름. 임의 산술(RMW·비선형) = fragment 밖 → **fail-closed** (v1은 residual로 배포했으나 v2는 명시적 거부 = 안전 개선으로 서술).
- Sustain counter는 **closed-form** (`hold=(t−last_false)/period`)으로, 펼치지 않음.
- tolerance 인코딩 `|t_IR − t_JoI| ≤ tol` (sub-tick 차이를 differ로 안 잡음).

### 보장 형태 (정직 서술)
"bounded horizon H·지원 fragment·인코딩 충실 가정 하에, IR과 다르게 행동하는 입력 trace가 **존재하지 않음**(UNSAT)." — v1의 "합성 boundary 시나리오에서 같았다"를 "탐색 공간 전체에 반례 없음"으로 승격. **claim은 detection upgrade가 아니라 guarantee upgrade** (§10 R2).

### TCB와 그 방어
- 신뢰 대상: 인코딩 충실성 + Z3. 방어: ① SAT 반례 → sim replay로 실재 확인(reject는 executable counterexample에 묶임, v1 철학 유지) ② **sim ↔ SMT 인코더 differential testing** (랜덤 trace에서 두 독립 구현 대조 — v1 mutation/coverage의 순환을 해소하는 방법론) ③ real-trace conformance (semantics ↔ 현실; validation RQ로 유지, 헤드라인 아님).

### 예상 latency (실측 전 ballpark; toy 실험이 최우선 §13)
obligation당 질의 = 데스크톱 1~20ms / ARM 5~50ms. 자동화당 obligation 10~40개 → **full 검증 = 엣지 0.1~2초** (counter 펼치면 수십 초로 폭발 → closed-form 필수). 수정 시엔 §5로 ms 단위.

---

## 5. 효율적 재검증 — "수정분만 다시" 4단 장치

**장치① Obligation 분해.** 등가를 IR construct별 질의로 분할(Q: edge 1회 발화? 유지 중 재발화 없음? call 인자 일치? ...). "일부만 다시"의 단위. 분할 단위는 IR 트리가 줌.

**장치② Unsat-core support tracking (핵심 신기술 포인트).** UNSAT 시 solver에서 "증명에 실제 쓰인 최소 제약 집합"(unsat core)을 뽑아 obligation별 저장. 수정 → 바뀐 span/slot의 제약 집합 D와 core 교차 검사 → **교차 없으면 그 증명은 수정과 무관함이 '확실'** (휴리스틱 아님) → 스킵. 교차한 것만 재-solve. edit-soundness 논증의 기계적 실체 = "proof-support tracking".

**장치③ Assumption-switch warm solver.** 제약 그룹마다 boolean 스위치(indicator)를 달아 solve-with-assumptions로 켜고 끔. 수정 = 옛 span 스위치 off + 새 제약 assert + 해당 질의만 재실행. solver를 안 끄므로 학습된 lemma 보존(push/pop보다 보존 우수) — 표준 incremental SMT 기법.

**장치④ 파라미터 증명 (왕).** 스키마 증명이 slot 심볼릭이므로 **값 수정은 solve 0회** (validity domain 확인 O(1)). 실사용 feedback 다수가 값 타입 → 가장 흔한 수정의 재검증 비용이 문자 그대로 0. validity domain 추출(등가가 성립하는 slot 범위) 자체가 작은 기술 조각.

**+ verify-as-you-decode**: speculative editing에서 복사로 통과된 span은 core 무결로 스킵, 새로 생성된 span이 닫히는 순간 해당 obligation 질의를 디코딩과 병렬 발사 → 재검증 latency가 생성 뒤에 숨음. **+ idle-time precompute**: 허브 유휴 시간에 파라미터 증명·validity domain·τ-lemma 사전 계산.

**Soundness 주의 (아킬레스건):** D를 정확히 잡아야 함. LLM이 편집 중 변수 재사용/스코프 변경하면 텍스트상 안 바뀐 span의 의미가 바뀔 수 있음. 처방: 수정 후 코드 전체 def-use 정적 분석을 매번 재계산(결정론, ~ms) + 편집 span과 변수 공유하는 obligation은 보수적으로 재검증 포함 + 분석 애매하면 full 재검증 폴백. **느려질 수는 있어도 틀릴 수는 없는 구조 유지.**

### 수정 유형별 비용표
| 수정 | 재생성 | 재검증 | 예상 비용 |
|---|---|---|---|
| 값 (threshold/period/args) | LLM 0 (치환) | 0 (장치④) | ~ms |
| 구조 국소 | speculative editing | core-교차 obligation 2~5개, warm | 수십~수백ms (디코딩과 overlap) |
| 구조 광역 | 부분~전체 | 다수 obligation | 초 미만~수초 |
| 분석 불가 | freeform | full 폴백 | 수초 |

---

## 6. Speculative editing (디코딩 효율 기둥)

### 기본 구도
- **Prompt 조건화 + draft는 별개 역할이며 상호 전제**: 스키마를 prompt에 넣어 모델을 "편집 모드"로 만들어야(출력 분포가 스키마 변형 쪽으로) draft acceptance가 성립. draft는 그 출력을 forward 병렬 채점으로 앞당기는 가속.
- lossless speculation은 출력 분포 보존 → "품질 희생?" 공격 원천 차단. 단 latency만 풀지 보존(preservation)은 못 품 → lossy로 확장(아래).

### Naive("유사 스키마 코드 통째로 tree") 예측 문제 P1~P5
- **P1 slot-값 불일치 연쇄**(치명): 옛 값 토큰(디바이스명·threshold)이 코드 전역에 반복 등장 → 기각 연쇄 → acceptance 붕괴.
- **P2 boilerplate 가짜 매칭**: `") {"` 같은 짧은 suffix가 여러 위치 매칭 → 오제안 연쇄.
- **P3 삽입 후 정렬 붕괴**: 구조 편집 뒤 위치 재앵커링 과정에서 P2와 결합.
- **P4 소형 모델 허위 기각**: acceptance 기준은 "draft가 맞냐"가 아니라 "모델 분포와 일치하냐" — 엔트로피 높은 모델은 올바른 draft도 기각.
- **P5 Δ 근처 낭비**: 고정 k로 계속 들이밀면 편집 지점에서 검증 forward 낭비.

### 처방 3종 세트 (설계 확정)
1. **Instantiate-then-draft (선제 치환).** draft = 스키마 원본이 아니라 **새 IR의 값-Δ를 결정론 치환한 코드**("예상 최종 코드"). 치환 후 재토크나이즈(토큰 스플라이스 금지). → P1 소멸; draft는 구조-Δ 지점에서만 기각 = LLM의 진짜 일과 정확히 일치.
2. **Δ-aware draft 스케줄링.** provenance(스키마에 저장)로 편집될 code-span을 디코딩 전에 앎 → frozen 구간 k=32~64, Δ span 안 draft off. + 최소 매칭 길이 임계·빈도 가중(P2·P3 완화).
3. **Verifier-backed lossy acceptance.** 채택 기준 완화 → 원본(인증된 스키마) 쪽으로 편향 = 재추첨 드리프트 억제. 일반 codegen에선 위험하지만 **SMT gate가 뒤에 있어 이 시스템에서만 안전** — "verifier가 있으면 생성기를 대담하게 만들 수 있다"는 co-design 논지. (P4 대응 겸용.)

### Tree 구성 (층)
```
층1: top-k(2~3) 검색 스키마의 치환본 → draft 채택 패턴이 곧 스키마 선택
     ("speculative routing"; 기각 잦은 스키마는 bandit식 강등)
층2: 이 집의 과거 인증 코드 코퍼스 (SuffixDecoding식 n-gram 폴백)
층3: (repair 루프) 직전 iteration 자기 코드 — self-correction의 이상적 draft
+ grammar-constrained scaffold: JoI 골격 토큰은 유효 토큰 1개 → forward 생략(free token)
  → 디코딩 비용 ∝ 의미적 선택 지점 수 (관통 원칙 2와 일치)
+ (repair에서) 목표 구조의 τ-템플릿 인스턴스를 draft로 = template-as-draft
  ("컴파일러가 제안, LLM이 승인, SMT가 심판" — R1 방어와 접점)
```

### 선행연구 델타 (정직)
prompt lookup decoding / SuffixDecoding / Cursor speculative edits가 계보. novelty는 speculation 자체가 아니라: **선제 치환(typed Δ를 알기에 가능) + provenance 기반 위치 인지 스케줄링 + 증명 backstop의 lossy 채택** 삼종 결합.

---

## 7. Feedback (C4) — repair 루프의 사용자 인터페이스

- **Typed feedback**: `(slot-id, type, [new-value])`로 유한·타입화 (smt_and_feedback.md Part 2 표 유효).
- **Router (V/S/E/R)**: V 값 변경→경로1(LLM 0·solver 0) / S 구조 변경→경로2, context는 기존 IR만 / **E scope 확장("B조명도")→delta grounding**: catalog 전체 재주입이 아니라 해당 항목만 retrieval — **기존 IR이 곧 upstream context의 인증된 압축**이므로 원명령·전체 catalog 불필요 / R 의도 전면 변경→정직하게 경로3 폴백. 오분류해도 verifier가 backstop이라 safety 무관, 효율만 갈림.
- **Behavioral diff 확인**: 수정 전후 IR vs IR′의 minimal distinguishing timeline을 SMT로 합성해 제시("이 상황에서만 달라지고 나머지는 동일" — '나머지 동일'이 UNSAT 증명이라 sim으론 불가한 주장). 문서 전체 재독 불필요.
- **보존성 주장(재생성 대비 핵심 우위)**: from-scratch 재생성은 무관 slot을 X% 확률로 변경(v1 instability 재활용해 측정) vs delta 경로는 0% + 증명. 재생성은 이 보존 보장이 원리적으로 불가.
- **(강력 후보) MaxSMT trace-example repair**: 사용자 불평 = (시나리오 trace, 기대 행동) → slot을 심볼릭 승격, "이 시나리오에서 기대 행동 + 기존 확인 시나리오 보존"을 제약으로 **최소 slot 변경 Δ를 solver가 탐색**. 사용자는 아무것도 편집 안 함. 닫힌 slot 공간이라 성립(코드 공간에선 불가) — "왜 IR인가"의 최강 답. 평가: (gt, 오염) 쌍 + gt trace 주입 → 복원율. 분량 보고 포함 여부 결정.

---

## 8. Contributions 후보 (초안)

- **C1 — Retrieve–edit–verify 아키텍처**: 생성·자가수정·사용자수정을 "인증물의 slot-level 수정 + 증명 상속"이라는 단일 연산으로 통일. 라이브러리는 self-bootstrapped(컴파일러 불필요)·home-specialized 성장. *"코드 재사용이 아니라 **증명 재사용**."*
- **C2 — 반응형-시간 LLM 코드의 bounded-complete SMT 등가 검증**: landmark 압축·region abstraction·counter closed-form·linear fragment fail-closed. 임의 코드 심판 + fragment 내 완전성 정리. (보장 기둥)
- **C3 — Incremental 재인증**: 파라미터 증명(값 수정 solve 0) + unsat-core support tracking + warm solver + verify-as-you-decode. edit-soundness를 기계적으로 담보.
- **C4 — Provenance-guided speculative editing**: 선제 치환 draft + Δ-aware 스케줄링 + verifier-backed lossy acceptance. 수정 디코딩 비용 ∝ 의미적 선택 지점.
- (+ evaluation: 순환 없는 방법론 — sim↔SMT differential, 반례 replay, real-trace)

---

## 9. Evaluation 계획 (전부 human-free)

### RQ (초안)
- **RQ1 gate 보장**: fragment coverage(382×3 생성물 중 linear fragment/fail-closed 비율), 반례 replay 재현율, sim↔SMT differential 일치율, v1 mutation 재활용(인코더 검증으로 강등 — 순환 아님을 명시).
- **RQ2 retrieve-edit 효율**: leave-one-out 매칭률·Δ 분포·경로(1/2/3) 분포, LLM 호출/토큰 절감, freeform 대비 품질 A/B(앵커링 crossover 곡선 포함).
- **RQ3 incremental 재검증**: zero-solve 비율(경로1 비중), core-교차 재검증 vs full 시간, edit-soundness 실증(closure 재검증 vs full의 verdict 일치 100%).
- **RQ4 speculative editing**: acceptance 분해 ablation(naive → +선제치환 → +Δ스케줄링 → +lossy), wall-clock speedup, lossy의 보존 편향 정량화(무관 slot 변경률), lossy가 흘린 오류의 gate 포착 확인.
- **RQ5 시스템**: cold-start 곡선(라이브러리 성장→경로3 비율 하락), on-device 비용(최초 full vs 수정), real-trace conformance(validation).
- **Baseline**: LLM judge(v1 재사용), random/fuzz differential testing(리뷰어 필문: "랜덤 1000 trace 대비?" — 예상 답: 검출은 비슷할 수 있으나 완전성 정리 없음), from-scratch 재생성.

### 우선 실험 (risk retirement 순 — §13와 동일)
1. **Toy Z3 timing**: C08(rising)/C20(sustain)/C15(cron)/C22(counted) 손 인코딩 → obligation당/full solve 시간 실측. **전 설계의 비용 모델 확정. 1~2일.**
2. **Leave-one-out 검색**: 382에서 τ-매칭률 + Δ 크기 분포 → 경로 분포 실증. ~1일 (τ-signature 코드 재사용).
3. **Fragment coverage**: 기존 382×3 생성 로그 분류(linear/비선형/문법밖) → fail-closed율. 나쁘면 설계 재고 필요하므로 조기 확인.
4. (보류 후보 검토용) consensus 예비: k-샘플 행동 다수결이 NL→IR 오류 59건을 얼마나 줄이나 — 기존 데이터로 가능.

---

## 10. 리뷰어 리스크 & 방어

- **R1 "컴파일러 쓰면 되잖아"**: §1-2 방어 3종. Tier0/템플릿 서술이 컴파일에 수렴해 보이지 않게 주의. template-as-draft가 정직한 중간 답("템플릿은 prior, 저자는 LLM, 심판은 SMT").
- **R2 "SMT가 sim보다 뭘 더 잡았나?"**: v1 survivor 11개 분석상 잔여 2건 = RMW = 비선형 = SMT도 fragment 밖. **detection delta ≈ 0을 인정하고 guarantee upgrade(순환 제거 + 완전성 정리 + unknown→명시적 fail-closed)로 claim.** 단 SMT는 v1 worst-case 8.4s(tick 밟기) tail을 없앨 수 있음 — "median 잃고 tail 얻는다".
- **R3 "retrieve-and-edit은 알려진 기법"** (Hashimoto '18 등): novelty = 검색 대상이 (코드+**파라미터 증명**) 쌍 + 증명 상속 + speculation 결합. v1 τ-routing의 자연 심화라는 연속성도 유리.
- **R4 "새 유형 시나리오 나오면?"**: 3중 방어 — ① 경로3 폴백 존재, gate는 retrieval에 무의존(안전 불변) ② 문법 G가 구조 공간을 유계로 묶음(신종은 "알려진 construct의 새 조합") ③ leave-one-out + cold-start 곡선 실측. **커버리지 완전성을 주장하지 말고 비용 모델("novel은 safe하게 정가, common은 fast")만 주장.**
- **R5 앵커링(잘못된 base)**: gate가 추출 IR과 대조하므로 안전 불변, 손해는 효율뿐. A/B로 crossover 실측해 router 임계 근거화.
- **R6 인코딩 TCB**: 반례 replay + sim differential + real-trace 3중.
- **R7 oracle 부재("LLM 오역을 완벽 배포?")**: scope 정직 서술("우리가 제거하는 것은 silent mechanism divergence") + slot 오류=visible 원리 + 렌더링 disclosure + (검토) consensus.
- **R8 일반화**: retargetable 구조 강조 — IR 인코딩·obligation·landmark·incremental은 플랫폼 독립, per-platform은 semantics 인코더뿐.

### 설계공간 positioning 표 (논문 수록 추천)
| 방식 | latency | 보장 | 임의 코드 |
|---|---|---|---|
| 컴파일러 lowering | ~1ms | by construction (컴파일러 신뢰 시) | ✗ |
| 컴파일+구문 대조 | ~1ms | 불성립 (등가 변형 기각) | △ |
| 템플릿 멤버십 | ~ms | 템플릿 범위 내 | ✗ |
| sim trace-equiv (v1) | ~1ms (worst 8.4s) | 경험적 (샘플) | ✓ |
| **SMT (v2)** | 초 (수정은 ms) | **fragment 내 완전성 정리** | ✓ |

"임의 코드 + 완전성 정리" 조합은 SMT 행뿐 — 이걸로 방어하고 latency로 방어하지 않는다.

---

## 11. 선행연구 포지셔닝

- **LACE**(back-translation+NLI): 가장 가까움. 차별 = 결정론 + 증명 + slot 구조.
- **AwareAuto**: confirmable reactive-temporal 표현, lowered 코드 미검증.
- **AutoIoT/TaskSense/AgentSpec/AutoTap 계열**: 결정론이나 고정 기준(conflict/well-formedness/safety rule) — intent-conformance 아님.
- **Alive2/translation validation**: SMT 등가 계보. 우리 = reactive-temporal + on-device + repair 루프 통합.
- **Retrieve-and-edit**(Hashimoto '18), exemplar codegen: 코드 재사용 계보. 우리 = 증명 재사용.
- **Prompt lookup / SuffixDecoding / Cursor speculative edits**: draft 계보. 우리 = 선제 치환 + provenance 스케줄링 + lossy w/ 증명 backstop.
- **Incremental SMT**(assumption-based solving, unsat core): 표준 기법. 우리 = provenance와 결합한 proof-support tracking으로 edit-soundness 담보.
- ⚠️ 2차 자료 인용 전 원문 확인 (기존 가드 유지).

---

## 12. 보류 / 후속 아이디어 (버리지 않음)

- **Behavioral consensus** (oracle 대체): NL→IR k-샘플을 SMT 등가로 클러스터링, 행동 다수결로 IR 확정; "다수 없음 = 해석 갈림 → fail-closed/차이 제시". draft-shared ensemble(후보1을 draft로 후보2~k 디코딩 — lossless라 독립성 보존, 비용 ∝ 모호함)과 세트. **R7 방어가 약하면 승격 검토.**
- **Runtime conformance monitor**: IR-Sim streaming 모드로 허브 상주, 실 로그 vs 예측 상시 대조; divergence = 반례 → repair 루프 직행. horizon 밖·sim-현실 gap을 상설 커버. (v1 약점③의 시스템化 — 분량 되면 승격 가치 높음.)
- **Retrospective grounding**: 집의 실제 센서 히스토리를 IR-Sim으로 counterfactual replay — "지난주에 있었다면 화 15:02 발화". 문서 예시의 현실 grounding + trace-feedback 자연 발생원. 데모 최강.
- **Physics-constrained counterexample**: 반례 탐색에 센서 dynamics 제약(판정은 무제약 유지, 보고용 반례만 제약) 또는 2단 보장 격자.
- **Semantically-minimal repair**: repair 후보 중 behavioral diff 최소인 것 선택.
- **소형(<8B) 모델 + 클라우드 라우팅**: "스키마가 구조를, verifier가 정확성을 지므로 모델은 편집만" — 스케일 다운 논리. "생성은 어디서든, 검증은 로컬"(verification-anchored trust)로 클라우드 offload 안전화. **보류.**
- **OVLA-Space** (compositional/공유상태): 후속작 유지.
- User study: 제거 유지. efficacy는 future work 한 줄.

---

## 13. 다음 할 일 (우선순위)

1. **Toy Z3 timing 실험** (§9 우선실험 1) — 비용 모델 확정. 이후 모든 설계 판단의 기준.
2. **Leave-one-out 매칭률 + Δ 분포** (§9 우선실험 2) — 경로 분포 실증.
3. **Fragment coverage 분류** (§9 우선실험 3) — fail-closed율 조기 확인.
4. JoI subset formal semantics 정의 + 인코더 프로토타입 (JoI-Sim AST 재사용, 인터프리터→선언적 제약 "번역" 작업).
5. 스키마 엔트리 포맷 + 라이브러리 시드 파이프라인 (382 → τ-class 스키마 일반화).
6. MaxSMT repair / consensus / monitor 중 승격 대상 결정 (분량·실측 결과 보고).

## 14. Venue

- **FSE 2027 (10/2, ~11주)**: translation validation + incremental verification + SE 파이프라인 — 최적합. 타이트: SMT 코어+평가는 가능, slicing 등 hard part는 범위 축소(통짜 인코딩 우선).
- 밀리면: MobiSys 2027 (12/5; monitor·retrospective 승격 시 적합), IMWUT 11/1, PerCom 9/11(촉박).
