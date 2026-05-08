# whisoo 노트 — 2026-05-06

논문 방향과 검증 방식을 정리한 노트. 교수님 미팅 전후로 뭐가 바뀌었는지, 지금 어디로 가는지.

---

## 1. 논문의 큰 그림 (변동 없음)

**목표**: 한국어 IoT 명령어를 작은 LLM (≤9B) 으로 JoI 코드로 바꾸기. 엣지 디바이스에서 돌아야 함 (privacy, latency, offline).

**핵심 문제**: 9B 모델이 한 번에 NL → JoI 잘 못 함. idiom 선택, 문법, selector, 시간 산술을 동시에 다 못 풀음.

**해결 (HERO)**: **Decomposition**. NL → JoI를 한 번에 안 하고 세 단계로 쪼갬:
1. NL → Timeline IR (LLM이 의도만 추출)
2. Timeline IR → 사용자에게 한국어로 보여주고 OK 받음 (이게 spec 역할)
3. IR → JoI (결정론적 lowering)

이 쪼개기가 검증 가능성을 만들어줌. 사용자가 OK한 IR이 spec이니까 이제 "JoI가 IR을 따르나?"만 보면 됨.

---

## 2. JoI가 IR을 따르는지 어떻게 검증?

가장 중요한 부분이고, 여기서 SBP-DT, DMWS, 3-layer 등 여러 안이 나왔어. 정리:

### 후보들이 거쳐 온 길

**옛날 안 (catalog + LoRA)** → 폐기
- "이런 lowering 버그들의 catalog를 만들고, LoRA로 어떤 시나리오 던질지 학습"
- 문제: catalog가 휴리스틱이라 정의되지 않은 패턴은 못 잡음. ML4test 비판도 받음.

**중간 안 (SBP-DT + DMWS hybrid)** → sharpen됨
- **SBP-DT** (Semantic Boundary Partitioning + Distinguishing Traces): IR 보고 "의미적으로 갈라지는 모서리 (cond boundary, edge 전이, cycle 경계)"를 다 enumerate해서 시나리오로 만듦.
- **DMWS** (Differential IR Mutation + Witness Synthesis): 각 시나리오에 대해 "이 시나리오는 IR의 어떤 field를 검증하는 건지" 자동 라벨 붙임. JoI가 어디 잘못했는지 진단 정밀화.

**현재 확정 안 (transition-obligation coverage on IR-FSM, 2026-05-06 교수님 미팅 후)**
- IR의 9개 op (`wait`, `if`, `cron`, `delay`, `cycle` 등)마다 **반드시 지켜져야 할 transition 의무**가 정해져있음. 이걸 모아서 IR FSM을 자동으로 만듦.
- IR FSM의 모든 transition 지점을 cover하는 시나리오 합성 = **transition-obligation completeness**.
- DMWS는 cut 안 함. evaluation에서 marginal 가치 측정해서 keep/cut 결정.

### 3-layer 검증 구조

```
시나리오 들어옴
   │
   ├─ L1 정적 검사 (수 ms): 코드 보고 명백한 버그 (flag init 빠뜨림 등)
   │
   ├─ L2 IR-FSM transition check (수십 ms, HERO): 
   │    JoI를 시뮬레이터로 한 번 실행 → trace 출력 → 
   │    IR-FSM의 transition 의무에 어긋나는지 체크
   │
   └─ L3 Differential simulation (≤1초, fallback):
        L2가 표현 부담스러운 복잡 케이스 (중첩 cycle 등)에 한해
        IR 시뮬레이터까지 돌려서 trace 풀비교
```

대부분 L1/L2에서 끝나고, L3는 진짜 어려운 케이스만.

---

## 3. 교수님 미팅 (2026-05-06) 이후 바뀐 것

**바꾼 것**

1. **L2가 hero로 격상**: 단순 trace 비교 (L3)는 completeness 주장이 약하다고 지적. IR FSM의 transition 지점을 빠짐없이 cover하면 약하지만 결정론적인 completeness 주장 가능 → 이걸 paper의 핵심 contribution으로.

2. **L3 역할 재정의**: "복잡한 명령어"가 기준이 아니라 "L2 transition-locality 가정이 깨지는 합성 케이스"가 기준. 정직한 fallback으로 위치.

3. **JoI side는 여전히 시뮬레이터**: JoI에서 FSM 추출은 안 하기로. 이유:
   - JoI는 일반 프로그래밍 언어 (변수, 반복문, 시간, 센서값 다 섞임) → FSM으로 만들면 조합 폭발
   - JoI는 같은 의도를 여러 방식으로 코딩 가능 (`triggered`/`prev-curr`/`phase`) → FSM 추출하려면 패턴 매칭 catalog 박혀버림 (절대 안 함)
   - JoI에 형식적 의미 정의 없음 → 시뮬레이터를 의미 정의로 사용

4. **MBT 변형으로 인정**: 우리 방법이 새 paradigm 아니고 model-based testing의 새 setting (NL-derived DSL lowering verification) 적용임을 명시. 그래야 reviewer "이거 MBT 아닌가" 공격 회피.

**유지된 것**

- 논문 메인 주제는 여전히 decomposition.
- 검증 verdict path에 LLM 없음 (trust boundary).
- DMWS 살림. evaluation에서 가치 측정 후 keep/cut.

---

## 4. 용어 정리 (헷갈렸던 것들)

- **IR FSM**: Timeline IR의 9개 op에서 자동 도출된 finite state machine. 각 op마다 어떤 transition 의무가 있는지 인코딩.
- **Transition 지점**: IR FSM에서 event로 인해 state가 바뀌는 지점. 즉 wait, if, cron, period, delay, rising edge 같은 것들.
- **Transition-obligation completeness**: 모든 transition 지점을 cover하는 시나리오로 검증하면, IR이 명시한 reactive 의무는 모두 검증됐다는 의미. 모든 lowering bug 잡는다는 뜻 아님 (그건 너무 강한 주장).
- **DMWS**: Differential IR Mutation + Witness Synthesis. IR의 한 field만 살짝 바꿔서 (예: `wait edge:rising` → `none`), 원본과 변형의 trace가 갈리는 시나리오를 찾음. 이걸로 "이 시나리오는 어떤 field 검증용인지" 라벨링.
- **Catalog**: 옛날 안의 hero. 지금은 evaluation용 calibration benchmark로 demote (paper contribution X).
- **MBT (Model-Based Testing)**: spec/모델에서 자동으로 테스트 도출 + 시스템 실행 trace 비교. 우리 방법이 이 카테고리에 속함.
- **L1/L2/L3**: 검증 3-layer. 각각 정적 / FSM transition / 시뮬레이션 비교.

---

## 5. 앞으로 할 일

### 즉시

**Memory + paper_summary 동기화 (완료, 2026-05-06)**
- `paper/paper_summary.md` §3.2 / §5 / §6 전면 rewrite
- `memory/project_paper_framework.md` C4 재구성
- `memory/MEMORY.md` 인덱스 갱신

### 다음 (Phase A3 — precision-stage IR annotation)

**왜**: IR이 selector/quantifier/tag 정보를 안 들고 있어서, lowering이 selector 잘못 짜도 trace에 안 잡힘. 검증 framework가 selector 버그도 잡으려면 precision stage 결과를 IR에 박아야 함.

**해야 할 일** (순서대로):
1. **selector_resolver**: `all(#Bedroom #Light)` 같은 selector를 connected_devices와 매칭해서 정렬된 device ID 리스트로 변환. 결정론적, LLM 없음.
2. **IR schema 확장**: call op에 `target_set` 필드 추가.
3. **TraceRecord 확장**: `(t, service, method, args, affected_set)` 으로.
4. **Comparator 업데이트**: affected_set 비교 포함.
5. **Multi-device world model**: 시뮬레이터가 device-instance 단위로 state 추적.
6. **Simulator emission 업데이트**: target_set 읽어서 affected_set으로 trace에 emit.
7. **Pipeline 재정렬**: precision stage 다시 활성화, IR에 annotation 주입.
8. **회귀 테스트**: C01-C07 결과 유지/향상 확인.

추정: ~1.5-2주.

### 그 다음

**교수님 요청 실험**: IR의 transition 지점 수 N 측정. C01~C18 데이터셋 IR들에 대해 "n!이 아니라 polynomial로 자란다"는 주장을 empirical하게 보여줘야 함. paper §6.6의 affordability argument 근거.

### 더 나중에 (Phase B/C/D/F)

- Phase B: 검증 mechanism 코드 구조 확정 + real-backend validation layer
- Phase C: SBP-DT (=transition-obligation coverage 시나리오 합성) + DMWS 구현
- Phase D: counterexample-guided self-correction
- Phase F: evaluation (mutation testing E2, ablation, open-domain holdout 200, human study, GPT-4 baseline)

---

## 6. 결정 안 된 것 / 검증 필요한 것

1. **DMWS의 marginal 가치**: evaluation에서 측정 후 keep/cut.
2. **N 분포 실험**: transition 지점 수가 진짜 affordable한지.
3. **L3 routing 룰 정확화**: "어떤 IR이면 L3 보낸다"의 정적 분류기 (예: nested cycle ≥3, multi-device cross-tag cond 등).
4. **Real-backend validation layer**: 실제 JoI runtime에서 일부 시나리오 돌려서 simulator drift 측정.
5. **Phase A3 시작 여부**: 위 plan 확정 후 (a) selector_resolver부터 코딩.

---

## 7. 한 문장으로

**"NL → IR (사용자 OK) → JoI 결정론적 lowering" 구조 위에서, 사용자가 OK한 IR로부터 자동 도출한 FSM의 모든 transition 지점을 cover하는 시나리오로 JoI를 검증한다. 검증 verdict path에 LLM 없음. MBT를 NL-derived 스마트홈 DSL lowering 검증에 처음 적용한 것이 contribution.**
