# OVLA → PerCom 2027 개정 플랜 (논의 정리, 2026-08-13)

> **이 문서의 지위**: SenSys 2027 제출본(`paper/Final/OVLA_SenSys2027.pdf`)의
> 리뷰 3건(전원 weak reject)을 받아 PerCom 2027로 재조준하는 개정 논의의
> 정리본. 논의 참여: whisoo + Claude (2026-08-13 세션).
> 리뷰 원문: `review.txt`. 구현 캐논: `simulator/README.md`(test 브랜치),
> 별도 방향 캐논: `paper_v2/ideas.md` — 관계는 §7 참조.

---

## 0. 타깃: PerCom 2027

- **일정**: 등록 2026-09-04 (AoE), 제출 2026-09-11 (AoE), early-reject 통보
  /rebuttal 초청 2026-11-20, rebuttal 2026-11-27, 최종 통보 2026-12-18.
  Goa, India, 2027-03-08~12. Double-blind.
  (출처: percom.org/dates — 오늘 기준 **제출까지 약 4주**)
- **양식**: IEEE 2단. 본문 분량 제한은 CFP 재확인 필요(통상 참고문헌 포함
  10쪽 내외). SenSys본은 ACM 14쪽(부록 포함)이므로 **압축이 필수** —
  Timeline IR 문법 부록·카테고리 표는 기술 리포트/arXiv로 빼는 것을 전제.
- PerCom 성격상 "on-device/edge에서 도는 pervasive 시스템" 프레임이 잘
  맞음. SenSys 대비 센서 시스템 디테일보다 시스템+검증 기여를 앞세운다.

---

## 1. SenSys 리뷰 → 대응 매트릭스

| # | 공격 (리뷰어) | 대응 (이 문서의 절) |
|---|---|---|
| 1 | 사용자 IR 승인 능력 미검증 — "문제를 옮겼다" (A·B·C 공통) | §2: user study 없이 claim 재구성 |
| 2 | bounded, not complete — 놓치는 버그 분석 부족 (A·C) | §3: 검증기 교체로 **구성적 해소** |
| 3 | 일반화 주장 과장 — 단일 플랫폼/DSL (A) | §4: HA 타깃 추가 |
| 4 | 왜 IR→코드를 결정론적 컴파일러로 안 하나 (B) | §2.4 |
| 5 | "verifier/verification" 용어가 형식증명 암시 (B) | §3.4: 이제 정당하게 쓸 수 있는 쪽으로 역전 |
| 6 | 도입부 "rapidly moving toward LLM codegen" 근거 부족 (B) | §4.5: HA 공식 AI 기능 인용 |
| 7 | edge 실행 동기 약함 — 클라우드로 충분 (A) | §2.5 |
| 8 | 재현성 — 벤치마크/프롬프트/시드 미공개 (B) | §6: artifact release 약속 |

핵심 판단: **#1은 tone이 아니라 claim 구조를 바꿔서 대응하고, 좁아진
claim을 #2(완전성 강화)·#3(플랫폼 일반화)이 채운다. 세 수정은 한 세트.**

---

## 2. User-confirm 문제 — user study 없이 가는 전략

**결정**: user study는 넣지 않는다. "사용자가 Timeline IR을 확인·승인한다"를
명시적 가정으로 두고, 그 승인을 쉽게 만드는 것은 어려운 open problem임을
인정하고 간다. 단, 이를 버티게 하는 4개의 구조 장치를 넣는다.

### 2.1 Validation vs. Verification 구분을 전면에

- 형식검증의 표준 구분을 명시 인용: **validation**("스펙이 의도에 맞는가")
  vs **verification**("구현이 스펙에 맞는가"). CompCert도 C 프로그램이
  프로그래머 의도와 맞는지는 검증하지 않는다 — 스펙의 올바름은 검증의
  전제이지 대상이 아니다.
- OVLA의 기여를 verification 문제의 해결로 못박고, validation(Layer A)은
  확립된 별개 문제로 위치시킨다. "문제를 옮겼다"는 공격을 "이 분야가
  원래 그렇게 나누는 문제를 정직하게 나눴다"로 받는다.

### 2.2 비교 우위 논증 (측정 없이 성립하는 주장)

- 이미 인용된 TAP-Debug [34]: 비전문가는 2-slot TAP rule의 IF/WHILE 구분
  조차 50세션 중 21건에서 오독. → **코드 감사는 불가능하다는 근거가 이미
  문헌에 있다.**
- 따라서 절대 주장("사용자가 IR을 승인할 수 있다")이 아니라 상대 주장으로:
  **"검토 과제를 '임의 코드 감사'에서 '유한·열거 가능한 slot에 대한 closed
  judgment'로 축소했다."** 사용자가 통제하는 차원(start/period/trigger·edge/
  action/duration/count)은 유한하고, rendering은 그 slot들의 결정론적 사영.

### 2.3 사용자가 틀려도 남는 보증: attributability

- 신규 명문화: 사용자가 잘못된 IR을 승인해도, 배포 코드는 **화면에 표시된
  문장 그대로** 동작한다. 오동작이 "코드 속 silent bug"에서 "사용자가 읽고
  승인한 문장에 명시된, 추적 가능한 스펙 불일치"로 바뀐다.
- 이 성질(오류의 가시성·귀속 가능성)은 사용자 오류 하에서도 유지되는
  안전 속성이며, SenSys본에는 명시 서술이 없었다. §Guarantees에 한 단락
  으로 추가.

### 2.4 Reviewer B의 "결정론적 컴파일러" 질문에 대한 답

- 답의 골격: **oracle 쪽은 실제로 결정론적이다** — 검사기가 쓰는 기준
  모델(IR 의미론/IR-FSM)은 IR에서 결정론적으로 도출된다. LLM lowering이
  존재하는 이유는 (i) 타깃 플랫폼별 idiom/카탈로그/스타일 적응(§4의
  다중 플랫폼에서 강화됨), (ii) 단일 canonical 컴파일러를 플랫폼마다
  유지하는 비용, (iii) 기존 코드 수리·재생성 루프와의 통합.
- 다중 타깃(§4)이 이 답을 실체화한다: "IR→{JoI, HA}"에서 결정론적
  컴파일러는 타깃 수만큼 필요하지만, 검증기는 타깃별 step 의미론만 있으면
  된다. 컴파일러의 정확성 부담을 검사기의 판정으로 대체하는 구도.

### 2.5 Edge 동기 재서술 (Reviewer A)

- 프라이버시를 첫 논거에서 내리고, **상호작용 지연**을 앞세운다: repair
  루프(반례 → 재생성)가 authoring 세션 안에서 돌아야 하며, 검증 게이트는
  밀리초 수준(신규 측정치로 갱신)이라 클라우드 왕복 없이 즉답한다.
  프라이버시(센서 데이터 비유출)는 두 번째 논거로 유지.

---

## 3. 검증기 교체: tick-sim+event synthesis → 전수 탐색기

**결정**: test 브랜치 `simulator/`(BFS+memoization explorer + lockstep
product)로 §6 검증기를 교체한다. 이는 리뷰 공격 #2를 경험적 방어에서
**구성적 보증**으로 바꾸는 개정의 본체다.

### 3.1 구/신 비교

| | 구 (SenSys본 §6) | 신 (`simulator/`) |
|---|---|---|
| 방식 | IR-FSM에서 경계 이벤트 합성 → 두 시뮬레이터 tick 실행 → trace 비교 | 정규화 상태공간 BFS + base×variant lockstep 곱 |
| 커버리지 | 합성 시나리오에 의존 → **Coverage 실험(97.5%)으로 달램** | 도달 가능한 (상태×입력셀) 전수 방문 — by construction |
| 검출력 근거 | **Mutation 실험(99.3%)** | fragment 내 완전 동치 (곱 그래프 닫힘 = EQUIV) |
| 시간 범위 | 1주 horizon, 월 단위 sustain 미커버, tick-step 지연 long tail (worst 8.4s) | 절대 시각을 상태 키에서 제외 → **무한 시간을 유한 그래프로 닫음**; 실측 상태 4~188, 대부분 <1s |
| 허용오차 | polling tick 양자화 tolerance | 없음 — 전이 단위 정확 비교 |
| 판정 | pass / fail(반례) | **EQUIV / DIVERGE(반례 경로) / REFUSED(fail-closed)** |

유한성 장치(explore.py): counter는 최대 비교 상수 너머 포화, timestamp는
비교 임계값 사이 zone + 캡처 시각 상대 순서, 달력은 hour region+weekday,
dwell 점프는 stutter-probe 증인 하에서만. `finiteness_check`가 유한 형태
밖 변수를 이름 단위로 거부. product.py의 셀 분할은 **양쪽 술어의 합집합**.

### 3.2 논문에서 바뀌는 것

1. **Coverage 표(구 Table 4) 폐지** → 상태공간 통계(상태/에지/탐색 시간)로
   대체. 97.5%라는 어색한 숫자 제거.
2. **Mutation 표(구 Table 3)는 유지하되 재역할**: detector 충분성 검증이
   아니라 **TCB(인터프리터+정규화)의 의미론적 충실성 검증**으로.
   before/after 스토리: 구 검증기의 잔여 생존자(cmp_direction — IR 유래
   경계만 시딩한 한계; comparator one-tick — tolerance가 흡수)가 신
   검사기에서 검출되는지 표로 제시. 합집합 셀 분할 + tolerance 제거로
   원리상 검출 가능.
3. **Claim 구조 역전 주의**: 구 보증은 T2 rejection-soundness(거절 = 실행
   가능 반례)였고 완전성은 부인. 신 설계는 acceptance가 강한 쪽(EQUIV =
   fragment 내 전 입력·무한 시간 출력 동치)이고, DIVERGE는 과근사(무별칭
   가정 등)로 spurious 가능 → **반례 경로의 구체 재생(replay) 확인 단계를
   게이트에 포함**해 T2를 복원해야 함. 이거 없으면 "멀쩡한 코드를
   거절한다" 공격이 들어온다.
4. **3-way 판정**: REFUSED(fragment 밖 코드 fail-closed)가 공식 판정이
   된다. RQ3의 배포 분포에 refusal rate 추가 측정 필수.
5. **정규화 정확성 lemma**: "같은 키의 두 상태는 모든 미래 입력에 대해
   같은 액션 시퀀스를 낸다"를 변수 클래스별(포화 카운터·zone·달력·dwell
   증인) proof sketch로 §6에 서술. 리뷰어가 찌를 핵심 지점.
6. **포지셔닝 이동**: "not a timed-automaton model-checking language"
   문장 삭제. related work에 명시적 상태 model checking / timed automata
   (Alur-Dill) / UPPAAL 정면 비교 추가. novelty 방어: (i) 검사 대상이
   모델이 아닌 임의 LLM 생성 명령형 코드, (ii) 추상화 축이 두 아티팩트의
   비교 상수에서 **자동 도출**, (iii) fragment 밖 fail-closed 거부까지
   포함한 배포 게이트 파이프라인.

### 3.3 크리티컬 패스 (구현)

- [ ] **IR × JoI product**: 현 product.py는 JoI base × JoI variant.
  OVLA 게이트는 confirmed IR을 한쪽 항으로 써야 함 → IR step 의미론을
  transition system으로 노출해 곱에 연결. **최우선** — 이게 안 되면
  "IR을 oracle로 쓴다"는 정체성이 신 검사기에서 성립 안 함.
- [ ] 10 시나리오 → 382 코퍼스 스케일업. ForEach 2건은 grounding 경유
  (ground.py), cron 드라이버(cron.py) 통합, composite(P4 공유-GV 곱)은
  스코프 아웃 여부 결정.
- [ ] EQUIV/DIVERGE/REFUSED 분포 + refusal rate 측정 (신 RQ3).
- [ ] on-device 지연/메모리 재측정 (구 worst 8.4s tail은 사라질 것으로
  예상 — 실측으로 확인).
- [ ] `smt/` 독립 교차 검산(differential/induction)을 TCB 검증 보조
  근거로 1~2문장 + 표 각주로 활용.

### 3.4 용어 결정

- 헤드라인 용어는 "conformance/equivalence checking **within a declared
  fragment**". 단 fragment·world model 한정을 명시한 곳에서는 "formal"
  주장을 정당하게 사용 가능 — Reviewer B의 지적이 역방향으로 풀린다.

---

## 4. Generality: Home Assistant 타깃 추가

**결정**: Timeline IR은 **단일 공통(플랫폼 중립) specification IR**로
유지. 플랫폼 종속성은 전부 **platform profile**로: catalog, lowering
exemplar 라이브러리, 타깃 문법/legality 게이트, step 의미론(탐색기용
인터프리터), observation model 세부, mutation operator 세트. LLVM 구도
(하나의 IR, 타깃별 legalization+lowering)와 동형.

### 4.1 실행 모델 대비

- JoI: cron+period, 매 tick 재실행되는 명령형 바디, 상태는 **영속 변수**.
- HA: 이벤트 구동 — triggers(**OR**)/conditions(**AND**)/actions(순차),
  run이 delay/wait에서 **suspend**, run 간 무상태, 영속 상태는 **helper
  엔티티**(counter/timer/input_*). 거의 쌍대: "영속 변수+무상태 tick" vs
  "영속 헬퍼+상태 품은 run".

### 4.2 Op 매핑 표 (IR 차원 ↔ JoI ↔ HA)

| IR 차원 | Timeline IR | JoI | HA |
|---|---|---|---|
| 시작 | `start_at` now/cron | cron 필드 | time / time_pattern trigger |
| 주기 | `cycle.period` | period+tick | time_pattern (`/5`) — 다수 경우 native trigger로 흡수 |
| 엣지 | `wait` edge | prev/curr·flag **idiom** | numeric_state/state/template **trigger가 primitive** (교차 시만 발화) |
| 레벨 | `if`, `wait` edge=none | if문 | condition(레벨 평가), wait_template |
| 지속 | `wait ... for:` | 카운터 idiom | trigger `for:` **primitive** |
| 지연 | `delay` | tick 카운팅 idiom | delay (suspend) |
| 반복/횟수 | `cycle.count`, `break` | 영속 카운터 idiom | repeat count/while/until/for_each, stop |
| 액션 | `call` | 서비스 호출 | service call (target/data) |
| 연산 | 제한 arith/cmp | JoI 표현식 | **Jinja 템플릿 (무제한)** + 구조화 필드(above/below/for) |

핵심 관찰:
- **trigger=edge, condition=level이 HA 문법에 박혀 있다.** JoI에서 idiom
  오류였던 edge/level 버그가 HA에서는 "**trigger에 쓸 것을 condition에
  쓰는**" 문법 위치 오류로 형태만 바뀐다. 논문 Figure 1(c)의 재발화 버그
  = HA에서 time_pattern+condition(레벨) lowering과 정확히 동형.
- 같은 IR이 HA에서 numeric_state trigger / template trigger /
  time_pattern+condition / state trigger+condition 등 **더 넓은 idiom
  공간**으로 lowering된다 → "one intent, many idioms, 일부는 미묘하게
  틀림"이라는 논문 전제가 강화됨. **HA의 primitive가 많다는 것은 IR의
  약점이 아니라 oracle 필요성의 근거.**

### 4.3 HA에만 있는 행동 차원 4개와 admission criterion 적용

기준(§4에서 채택): **"플랫폼 primitive는 어떤 사용자 지정 가능 intent의
관찰 가능한 action trace를 바꿀 때만 IR에 편입된다. 아니면 lowering
idiom으로 남고 trace-equivalence가 흡수한다."**

1. **`mode`** (single[기본]/restart/queued/parallel + max) — trace-visible
  이지만 **IR에 넣지 않는다**. IR은 단일 타임라인이라 overlap 행동이 IR
  의미론에서 이미 결정됨. 사용자 의도 구분(fresh window "열리고 5분 뒤"
  vs extend window "마지막 감지 후 5분")은 서로 다른 IR 구조(delay vs
  `wait for:` sustain)로 이미 표현된다. mode는 IR 의미론과 일치해야 하는
  lowering 선택이고, 틀리면 overlap 시나리오에서 divergence로 검출.
  → **논문에 admission criterion의 모범 사례로 서술.**
  전제: 탐색기 입력 공간에 overlapping-event 시나리오 포함(재실겹침
  클래스의 연장).
2. **parallel 액션 블록** — IR sequential 유지, exemplar로 억제, 나오면
  정적 게이트 **REFUSED** (v1). observation model 확장(unordered group)은
  future work.
3. **sun/calendar** ("해질녘에") — catalog 확장이 기본(sun.elevation을
  센서 read로). `start_at "sunset+30m"` anchor 확장은 "HA가 지원해서"가
  아니라 "사용자가 말해서"라는 NL-driven 서사로만 도입.
  → **결정(2026-08-13): 해질녘류 애매한 표현은 데이터셋에 넣지 않는다.
  따라서 anchor 확장·카탈로그 확장 모두 하지 않음 (§9).**
4. **wait timeout** (`wait_template`/`wait_for_trigger`의 timeout +
  `continue_on_timeout` **기본 true** = silent-divergence 발생기) —
  **유일하게 진지한 IR 확장 후보**. "5분 안에 안 열리면 X"는 실제 사용자
  패턴. `cycle`+`until` 우회 표현 가능성을 코퍼스로 확인 후 결정.
  확장 여부와 무관하게 검증기는 반드시 커버.
  → **결정(2026-08-13): IR에 편입 확정. 문법·검증 결과는 §9 참조.**

### 4.4 HA 고유 fault class (신규 mutation operator 후보)

trigger↔condition 혼동(edge/level) / `for:` 누락 / wrong `mode` /
`continue_on_timeout` 방치 / above·below **exclusive** 경계(`above: 25`는
>25, ≥ 아님 — comparator 클래스의 HA판) / while↔until 혼동(until은 최소
1회 실행) / helper 미시드(SEED-DEP의 HA판) / single mode 이벤트 유실.

### 4.5 Intro 동기 보강 (Reviewer B #6)

- HA 2025.8: 자동화 에디터 opt-in AI 제안 기능 공식 출시. 2025.9 블로그
  "Building the AI-powered local smart home". OpenAI/Google/Ollama
  네이티브 통합, AI Task 확장. → "rapidly moving" 첫 문장에 상용 근거
  인용 가능. (home-assistant.io/blog/2025/08/06/release-20258/,
  /blog/2025/09/11/ai-in-home-assistant/)

### 4.6 검사기 관점

- HA는 이벤트 구동이라 transition-system 탐색기와 궁합이 오히려 좋다
  (tick 양자화 tolerance 불필요). 구조화 필드(above/below/for/at)는 축
  도출이 JoI 표현식보다 쉽다. Jinja 템플릿은 제한 부분집합(상수 비교·
  단순 산술·state read)만 지원, 나머지 REFUSED — "HA 전체를 검증하는 게
  아니라 배포하는 코드만 검증한다" 스토리 유지.
- Reviewer A 응답 구도: JoI(명령형 per-tick, temporal 전부 idiom)와
  HA(선언형+스크립트, 일부 temporal primitive)는 스펙트럼 양끝. HA는
  A가 "feasible할 것"이라 한 declarative에 가깝지만 순수 TAP이 아니라서
  (mode/repeat/wait/템플릿) "쉬운 케이스 하나 추가"라는 반론도 막는다.

---

## 5. JoI 플랫폼 변경 사항 반영 (2026-08 확인)

논문 실험·구현 시점 이후 JoI 플랫폼이 갱신됨. 두 가지를 개정에 반영한다.

### 5.1 신규 문법: `for` / `loop`

- `for (v : all(#X).member) {}` — **매핑된 디바이스 값 순회**(상태 조회).
  grounding이 인벤토리 바인딩 후 k회 언롤 (`ground.py` 구현 존재,
  simulator/README 2026-07-31 유저 확인 항목).
- `loop (cond) {}` — tick 내 while. `for`와 별개 구문.
- **IR은 불변** — spec-IR 입장의 실례로 쓴다:
  - "모든 창문이 닫혀 있으면"류 quantifier 의도는 IR expr 차원(`all`,
    C21 group consensus)에 이미 존재. `for`는 그 quantifier를 실현하는
    **새 lowering idiom**일 뿐 → 플랫폼이 자라도 IR이 안 바뀌는 실측
    사례. §4의 admission criterion 서사에 직접 인용.
  - parser는 test 브랜치가 이미 `loop` 구문·`OP|` 보존 (joi_parser.py).
- **검증기 영향**:
  - `for`: grounding 언롤 후 선형 — fragment 내. 단 382 코퍼스에서
    ForEach 필요 명령의 grounding 경로 검증 필요 (v1 탐색기는 2건 명시
    거부했음).
  - `loop`: tick 내 **비유한 반복 가능** → 유한성 위협. fragment 규칙
    추가: 반복 횟수가 언롤된 디바이스 수·비교 상수로 유계임을 정적으로
    보일 수 있을 때만 수용, 아니면 `finiteness_check` REFUSED.
    STEP_CAP은 최후 방어선으로 유지.
  - 신규 mutation operator: for 셀렉터 오바인딩(엉뚱한 태그 집합),
    언롤 off-by-one, loop guard 극성 반전(무한 루프/AbortTick), loop↔for
    혼동.
  - LLM lowering이 신 문법을 쓰는 빈도 측정 → idiom 공간 확대가 flagged
    rate에 주는 영향 자체가 평가 거리 ("플랫폼 진화가 idiom 공간을
    넓히고, 게이트는 그대로 동작"이라는 P2형 서사).

### 5.2 Service list 갱신 (v2.0.7 계열)

디바이스/서비스가 사라지거나 새로 생김. 반영 사항:

- [ ] **벤치마크 재감사**: 382 명령 + 수작업 레퍼런스 IR이 참조하는
  service/attr을 신 카탈로그와 대조 — 사라진 대상 참조는 명령 교체
  또는 re-grounding. 카테고리 분포(24종) 유지 여부 확인.
- [ ] **catalog 버전 고정 명시**: feasibility gate의 카탈로그 적합성
  검사(out-of-catalog fail-closed)는 이미 있으므로, 논문에 "catalog
  version pinning" 한 줄 + 평가 setup에 버전 기재 (재현성 #8 대응).
- [ ] lowering exemplar 라이브러리 재검증 (구 서비스 참조 exemplar 폐기).
- [ ] 실기기 testbed 구성과 신 카탈로그 정합 확인.
- 서사적 활용: 카탈로그 갱신에도 게이트가 fail-closed로 버티는 것 자체가
  attributability(§2.3)·spec-IR(§4) 주장의 보조 증거.

---

## 6. 신 논문 골격(안) — IEEE 지면 기준

1. **Intro** — 동기 갱신 (HA 공식 AI 근거), claim 재구성 (§2), 기여:
   (C1) spec-IR + admission criterion, (C2) fragment 내 완전 동치의
   결정론적 3-way 게이트, (C3) 다중 플랫폼(JoI+HA) 실증, (C4) on-device.
2. **Related Work** — 기존 축 + 명시적 상태 MC/timed automata/UPPAAL 정면
   비교 추가. LACE/AwareAuto 비교 유지.
3. **Problem & Guarantees** — R1~R3 유지, validation/verification 구분,
   attributability, 2-layer 경계.
4. **Timeline IR as a cross-platform specification IR** — admission
   criterion, platform profile 구성, mode/for-loop 사례.
5. **Checker** — 정규화(유한성 lemma + proof sketch), lockstep product,
   3-way 판정, 반례 replay 구체화, fragment 경계.
6. **Evaluation** —
   - E1: 상태공간 통계 (구 Coverage 대체)
   - E2: TCB 충실성 (구 Mutation 재역할) + 구 검증기 생존자 재검출 표
   - E3: 게이트 분류 (EQUIV/DIVERGE/REFUSED + refusal rate, 생성 모델 3종)
   - E4: HA 타깃 — HA fault class 검출 + 플랫폼 추가 비용(LoC/profile)
   - E5: on-device 비용 재측정 + 실기기 배포
7. **Limitations** — 사용자 승인 가정(open problem 명시), fragment 밖
   코드, composite/조합은 스코프 아웃.
- 부록(문법·카테고리·프롬프트·시드)은 기술 리포트/arXiv + artifact
  release (재현성 #8).

## 7. `paper_v2/ideas.md`(iot-sim 캐논)와의 관계

- ideas.md(8차, 2026-08-03)는 **배포 후 생애주기 재판정**(P1~P5, 바인딩
  비이식성·시간 부패·편집 이탈)으로 무게중심을 옮긴 별도 방향. 본 문서는
  **authoring-time 게이트(OVLA)의 개정**으로, 탐색기·product·fragment
  인프라를 공유하되 문제 설정이 다르다.
- 경계: percom.md = "배포 전 게이트" (OVLA 리브랜딩), ideas.md = "배포 후
  재인증" (iot-sim). 어느 쪽을 PerCom에 낼지, 혹은 게이트 논문에 생애주기
  일부(replay.py 배포 재생)를 흡수할지는 **미결 — 착수 전 결정 필요**.
  (본 세션 논의는 전자를 전제로 진행했음.)
- → **결정(2026-08-13): percom.md 노선 확정. ideas.md(iot-sim) 노선은
  기각되어 `paper_v2/` 디렉토리를 test 브랜치에서 삭제함. 생애주기 요소
  (replay.py 배포 재생)도 이번 논문에 흡수하지 않는다.**

## 8. 우선순위 (제출 D-29 역산)

1. ~~§7 방향 확정~~ → **완료: percom.md 노선 (§9)**
2. IR×JoI product 연결 (§3.3 최우선 — 정체성 성립 조건)
3. 382 스케일업 + 카탈로그 재감사 (§5.2) — 신 E1~E3 수치의 전제
4. HA profile 최소 구현 (parser→step 의미론, 제한 템플릿 fragment,
   HA fault class 주입) — E4
5. 정규화 lemma 집필 + 반례 replay 게이트
6. 본문 압축 집필 (14쪽 ACM → IEEE 지면)

---

## 9. 착수 결정 로그 (2026-08-13 저녁, whisoo + Claude)

### 9.1 브랜치 정리 (완료)

- **작업 브랜치 = `paper`.** test 브랜치는 새 시뮬레이터 코드만 가져오고
  폐기한다.
- test → paper 이식 완료: `simulator/`(BFS 전수 탐색기, 자족 패키지) +
  `smt/`(교차검산, 각주용) — 커밋 `5091e3c`.
- `paper_v2/`(iot-sim 아이디어 문서들)는 노선 기각으로 test 브랜치에서
  삭제 — 커밋 `62538b8`(test).

### 9.2 Timeline IR 동결 선언

**이 시점부로 IR 문법은 아래 확장 1건을 끝으로 동결한다.** 이후 모든 구현
(IR 한-걸음 실행기, HA 타깃, 실험)은 이 문법 위에서만 진행.

- **넣기로 한 것 — `wait`의 제한시간(timeout)**: "문이 열리고 5분 안에 안
  닫히면 알려줘" 같은 명령용. HA에는 기본 기능(`wait_template` timeout)이라
  타깃 2개 중 1개가 1급으로 지원하고, 사용자가 실제로 말하는 패턴이므로 편입.
  ```json
  {"op": "wait", "cond": "Door.Contact == closed",
   "timeout": "5 MIN", "on_timeout": [{"op": "call", "...": "..."}]}
  ```
  의미: 조건이 제한시간 안에 참이 되면 → 다음 op로 진행(성공 길).
  시간이 먼저 다 되면 → `on_timeout` 블록 실행 후 이번 회차 종료(초과 길).
  cycle 안이면 다음 회차에 다시 무장.
  렌더링(안): "문이 닫히기를 최대 5분 기다립니다. 5분 안에 안 되면: ..."
- **검증 완료(2026-08-13)**: 이 패턴의 JoI 관용구(지켜보기 래치 `watching` +
  시작시각 저장 `opened_at` + `now - opened_at > 300` 비교)를 실제로 작성해
  ① 파서 통과, ② 단편 판정 전부 기존 클래스(ENUM/LINEAR/LATCH/TIMER,
  미해명 0 = 탐색기가 그대로 다룸), ③ tick 실행에서 늦게 닫히면 정확히
  1회 발화·빨리 닫히면 침묵 확인. **JoI로 자연스럽게 표현됨 → 편입 타당.**
- **안 넣기로 한 것 — 해질녘류(sun/calendar anchor)**: 애매한 표현은
  데이터셋에 넣지 않기로 결정. anchor 확장·카탈로그 확장 모두 하지 않음.
- 기존 심사 유지: `mode` 미편입(§4.3.1, admission criterion 모범 사례),
  병렬 액션 블록 REFUSED(§4.3.2), JoI 신규 `for`/`loop`에도 IR 불변(§5.1).

### 9.3 데이터셋 후속 작업

- 382 코퍼스에 타임아웃 패턴 0건, 해질녘류 0건 확인(2026-08-13 검색).
- 카탈로그 재감사(§5.2) 때 **타임아웃 유형 명령을 신설**해 코퍼스에 추가
  (레퍼런스 IR은 신 문법 사용). 규모는 재감사 시 결정(카테고리 분포 고려).
- **탐색기의 10개 복잡 시나리오(explorer/corpus/)는 데이터셋에 넣지
  않는다** — 로컬 모델이 생성할 수 있는 난이도를 넘어서므로 탐색기
  개발·회귀 전용으로만 사용 (2026-08-13 결정).

### 9.4 기기 바인딩 표 (2026-08-14 결정)

- **확인되는 것 = IR 렌더링 + 기기 바인딩 표** 2요소로 명문화. IR 문법은
  동결 유지 — 인스턴스 선택은 IR op가 아니라 별도 바인딩 표가 담는다.
  (배경: IR은 서비스 이름만 갖고 방/인스턴스는 lowering이 정했음 →
  승인 표면과 검증기 양쪽에 구멍. 데이터셋 1행부터 식기세척기 2대 실물.)
- 바인딩 표: IR의 각 기기 이름 → 인벤토리 논리 기기(집합 가능). 렌더링에
  "선택된 기기" 목록으로 표시, 검증기의 IR-측 grounding 입력으로 소비,
  platform profile이 JoI 태그 셀렉터 / HA entity·area로 번역.
- **op 수 규칙**: IR op 수 = 의도 슬롯 수. 같은 액션을 여러 기기에 =
  call 1개 + 집합 바인딩 (grounding이 기기별 액션으로 언롤 — JoI가
  all()로 내리든 문장 2개로 내리든 trace 동일 = EQUIV). 다른 액션/인자/
  순서 = op 각각. 관찰 모델: 같은 tick 안 액션은 순서 무관·개수 유관.
  → v1 call_drop 생존자("두 방 중 하나 삭제")가 검출되는 근거 (E2).
- 게이트에서 바인딩 출처는 확인된 표(독립 출처)여야 함 — JoI 셀렉터에서
  베끼면 재배선을 못 잡는다. **단 M3(정답 307쌍 자기 검증)에서는 JoI
  셀렉터에서 키를 뽑는 지름길 허용.**
- 후속: 382 재감사(§5.2) 때 행별 레퍼런스 바인딩 명시 + "두 방 같은
  명령"류 행을 1 op+집합 바인딩으로 정규화. wrong-binding을 E3/E4
  fault class로 추가 (HA판 = entity 오선택).

### 9.5 작업 규칙

- **쉬운 네이밍**: 구현·설명 모두 어려운 용어를 자제한다. 예: "lockstep
  product" 대신 "나란히 실행 비교", "transition system" 대신 "한-걸음
  실행기(step 함수)". 코드 이름도 짧고 평이하게.

### 9.6 W1 M3 완료 (2026-08-14)

- **정답 307쌍 판정 완결: EQUIV 281 / DIVERGE 25 / joi_block 없음 1**
  (Unsupported 0). cron 47은 앵커 공통 소거(양쪽 cron 문자열 일치 검사
  후 창 내부만 비교), 주기형 blocking 23은 멈춤 이어가기 실행기
  (explorer/pause.py)로 판정.
- DIVERGE 25 전수 분류: 레퍼런스 IR 결함 8 / 생성 JoI 결함 4(v1
  생존자) / lowering 시간 어긋남 12(재무장 한 박자 6 + 회차 한 주기
  밀림 6) / 인자 서명 접착 미지원 1. 상세와 반례는
  explorer/runs/m3_findings.md — E2 절의 실물 사례 목록으로 사용.
- 파생 수정 대상: 382 재감사 때 IR 결함 8건 수정 + 태그 표기 정규화
  (#Grp2→#Group2류) + 인자 기본값 정규화. lowering 프롬프트(files/)의
  D-3 재무장·phase 첫 회차 지연은 별도 논의(게이트가 잡는 게 정답일
  수도 — E2 서사).

### 9.7 W2 카탈로그 재감사 — 382행 v2.0.7 정합 (2026-08-14)

- **카탈로그 반입**: service_list 2.0.6/2.0.7을 test 브랜치에서 paper로
  가져옴. 2.0.5→2.0.7은 스킬 4개 추가뿐(삭제·서명 변경 0). 진짜 간극은
  코퍼스가 2.0.4 시절 카탈로그 기준이라는 것 — **2.0.5로 넘어오며 7개
  스킬이 사라짐** (Dishwasher, Door, LaundryDryer, Oven, RainSensor,
  RiceCooker, Safe). 영향 85행(+함수 오용 4행) = 전체의 22%.
- **치환 정책** (구현: 감사·변환 스크립트, 산출 89행 수정):
  - 문 상태 읽기 전용 → **ContactSensor.Contact** (closed=true 규약,
    NL 무변경). 문 액션 → **DoorLock** (NL을 잠금 언어로: close→lock),
    환기 의도(욕실·비 오는 날)는 **창문(WindowCovering)**으로, 여닫기
    반복(C13_001)은 **밸브(Valve)**로 재조준.
  - Safe → **DoorLock**(금고의 잠금장치; NL 무변경, Safe 태그 유지.
    locked→closed 어휘 매핑). 한 행에 도어락 2대가 생기는 C16_002/004는
    §9.4 "같은 서비스, 바인딩 표가 구분" 설계의 실물 사례가 됨.
  - RainSensor.Rain → **WeatherProvider.Weather == "rain"** (기존
    C05_010 관례 그대로, NL 무변경).
  - 주방가전(모드·시간형)은 생존 모드 기기로 명령 재작성 (영/한 동시):
    식기세척기 건조→제습기 drying, 오븐→에어컨/선풍기 모드,
    밥솥→로봇청소기·가습기, 건조기 회전속도→환풍기 Fan.Speed.
  - 미끼 기기(인벤토리만 등장)는 카테고리 교체(충돌 회피 규칙).
- **함수 오용 4건 수정**: C17_009(값 DoorLockState를 call로 호출 — call
  제거), C08_038·C03_029(Camera.StartStream 부재 → StartRecording, NL도
  녹화로), C03_002(IsAvailable은 함수 → 결과 담는 질의 호출 + $var 읽기).
- **검증**: v2.0.7 대조 감사 0건(카탈로그 외 참조 없음), 382행 전부
  explorer IR 컴파일 통과(cron 앵커 소거 후). 행 내 태그 요동은 C05_023
  1건(Living/LivingRoom 혼용)뿐 — 정규화. 인자 부분 지정은 C03_002
  1건뿐(기본값 규약으로 허용).
- **저절로 해소된 것**: M3의 IR 결함 8건은 캐시(4월판)에만 있고 현재
  csv에는 이미 수정돼 있었음(diff로 확인 — 캐시는 v1 시대 스냅샷으로
  보존, m3_findings의 E2 서사는 유효). C15_002 인자 서명 접착도 신
  카탈로그가 1-인자 서명이라 해소.
- **잔여(다음 단위)**: ① lowering exemplar 재검증,
  ② 논문에 catalog version pinning 문구.

### 9.8 행별 레퍼런스 바인딩 — binding_gt 열 (2026-08-14)

- **스키마**: dataset.csv에 `binding_gt` 열 추가. JSON 객체 —
  IR의 서비스 자리(걷기 순서: 타임라인 위→아래, 스텝 안은 cond 원자
  왼→오 → call → args 읽기) → 인벤토리 기기 id 목록. 같은 서비스가
  다른 기기 집합으로 또 나오면 `"#2"` 접미 (예: 거실 온도 or 침실 온도
  → TemperatureSensor / TemperatureSensor#2). 같은 집합이면 자리 합침.
- **생성 규칙** (paper/reaudit/bindgen.py, 자리 726개):
  후보 1개(98) / 위치·기기어 매칭(253 — 태그 camelCase 분해 + 동의어
  + 한국어 사전; or-조건의 같은 서비스 k자리는 NL 언급 순서로 짝짓기) /
  집합 어구(124 — "all/any/at least one + 종류" 어구 안의 태그로만
  필터: "Sector B의 홀수 금고" = 교집합) / 캐시 증거(6 — 정답 쌍의 JoI
  셀렉터가 부분집합을 특정할 때) / **무지정 단수 규약**(232 — Main 태그
  56, 없으면 인벤토리 첫 후보 176; `(#Tag)` 단일 셀렉터는 "특정 한
  기기"라 캐시로도 복원 불가 → 규약으로 고정하고 확인 표면이 보여주는
  것이 제품 서사) / 수기(6 — C16_002/004: 금고와 현관 도어락이 같은
  DoorLock 서비스라 태그로 원리상 구분 불가). 규약 배정 147행 목록은
  explorer/runs/binding_review.md — 눈검토 대상.
- **파생 수정**: 태그 위생 — C20군 8행 + C08_032는 위치가 기기 id에만
  있고 태그엔 필러(Motion/Presence)뿐이라 **미끼가 태그로 구분 불가**
  (JoI 셀렉터 번역 불가능) → id 접두어를 위치 태그로 승격, 중복 태그
  16건 제거. C05_015는 1차 치환의 잔재(읽기 ContactSensor/액션
  DoorLock 분열)를 DoorLock으로 통일. C08_029 "위쪽 조명↔아래쪽 조명"
  바인딩이 명시되면서 M3의 '자기참조 의심'은 생성 JoI 결함으로 확정.
- **검증**: 바인딩 726자리 전부 — 기기 id 실재 + IR 서비스 자리 전부
  커버 (paper/reaudit/catalog_audit.py 문제 0, IR 컴파일 382/382).
- **미결 명시**: any/all 한정 의미는 바인딩 표에 없음(바인딩 = 기기
  선택만). 검증기의 IR-측 grounding이 다중 기기 읽기를 어떻게 펼칠지는
  게이트 연결(W3) 때 결정. → **§9.10에서 해소** (한정자 표기 확장).

### 9.9 타임아웃 유형 명령 신설 — C26 6행 (2026-08-14)

- §9.2에서 동결한 `wait` 제한시간 문법을 쓰는 코퍼스 행이 0이었음
  (§9.3) → **C26 카테고리 6행 신설**, 총 388행. (C25는 2026-05의
  composite 행들이 이미 쓰고 있어 C26으로 부여.)
- 모양 커버: 원샷 열림→안 닫히면 알림(001) / 주기형 밸브(002) /
  성공길이 도킹 관찰(003) / cron 앵커 + on_timeout 액션 2개(004) /
  성공길 후속 동작이 있는 타임아웃(005 — 초과 시 남은 op 건너뜀이
  드러나는 행) / 비 시작 후 창문(006). 레퍼런스 IR은 신 문법
  (`timeout` + `on_timeout`), explorer 실행기는 이미 지원.
- binding_gt 포함 생성, 감사·컴파일 388/388 통과. 카테고리 분포에
  삽입(24종→26종; C04는 캐시 전용으로 계속 부재).

### 9.10 게이트 연결 — 바인딩 표 기반 IR×후보 JoI 나란히 비교 (2026-08-14, W3)

- **구성** (explorer/gate.py): §3.3 최우선 항목("IR을 oracle로")이 실물이 됨.
  - IR 접지: 자리 걷기 순서(§9.4)대로 조건·읽기·인자의 서비스 원자를
    기기 형태("<기기id>.Attr")로 다시 쓰고, call은 자리별 기기 그룹으로
    언롤(ir_step emit에 자리별 바인딩 형식 추가). 출처는 **binding_gt만**
    — 독립 출처 원칙(§9.4), 후보에게서 베끼면 재배선을 못 잡는다.
  - 후보 JoI 접지: ground.py로 셀렉터→기기 id 읽기·액션. 단수 셀렉터가
    여러 대와 맞으면 §9.8 무지정 단수 규약(Main 태그 1개 → 그것, 아니면
    첫 후보)으로 해석 — 바인딩 생성과 같은 규약(pick_by_rule).
  - 양쪽 다 기기 id 기준 셀·타깃이라 서비스 표기 차이는 소거됨.
    판정 3-way: EQUIV / DIVERGE(반례) / REFUSED(Unsupported fail-closed).
- **any/all 펼치기 결정 (§9.8 미결 해소)**: 여러 대를 읽는 자리는
  binding_gt가 한정자를 명시한다 — `{"any": [...]}`=하나라도(or 펼침) /
  `{"all": [...]}`=전부(and 펼침). 액션 자리는 목록 그대로(기기당 액션
  언롤, 뜻 유일). 한정자는 확인 표면의 일부(사용자가 보고 승인하는 것).
  기본은 any, all은 수기 — 대상 19행 검수 결과 any 17 / all 2
  (C17_008, C03_024). bindgen이 읽기 자리 성격을 추적해 자동 표기.
- **반례 재생 = T2 복원 (§3.2-3)**: DIVERGE의 반례 경로를 정규화(키
  병합) 없이 구체 상태로 되밟아 확인하는 product.replay_divergence 추가.
  거절 = 실행 가능한 입력 시퀀스. 고장 주입 표본 전부 "확인" — spurious
  DIVERGE 방어가 게이트 판정 안에 들어옴.
- **결과** (캐시 정답 JoI 중 현행 IR과 일치하는 178쌍; 낡은 캐시 125건
  제외): **EQUIV 164 / DIVERGE 14 / REFUSED 0, DIVERGE 전부 재생 확인**.
  14 = M3 기지 결함 9 + **게이트 단독 검출 5** (C03_021 농장→메인 사이렌
  재배선, C05_027 밸브 2대 중 1대만 읽음, C09_012 침실 밖 블라인드까지,
  C10_009 데이터센터 밖까지, C15_019 커튼까지 엶). 후보 셀렉터가 확인된
  바인딩과 다른 wrong-binding류 — M3 자기검증(셀렉터 베끼기)으론 원리상
  안 보이던 것들. E3 fault class의 자연 발생 실물.
- **게이트가 드러낸 바인딩 표 결함 4행 → 수기 정정**(OVERRIDE, 검토
  목록에서 제외): C05_016·C16_001(장소 없는 "감지되면"을 규약이 첫
  후보로 좁힘 → any 집합으로), C10_005(집합 어구 판정이 앞 구절 "house"에
  오적용 → 사이렌 3대 전부로), C05_026(에어컨/가습기 두 자리를 언급
  겹침으로 4기기 한 자리로 뭉갬 → 자리 분리). C16_009 IR의 중복 원자
  (`A or A`)도 정리. 재감사·컴파일 388/388 유지, M3 회귀 무변화.
- **재배선 고장 주입 3종**(읽기 재배선·액션 재배선·집합 탈락) 전부
  DIVERGE + 재생 확인 — E3 mutation operator의 게이트판 예행.
- **남은 것**: 382 전 행 게이트 측정은 신규 lowering 산출물이 생기는
  E2/E3 때. ForEach 후보는 ground 언롤로 이제 게이트에서 판정 가능.

### 9.11 W2 잔재 정리 — exemplar 재검증 + 센서 집합 읽기 정책 (2026-08-14)

- **lowering exemplar 재검증(§9.7 잔여 ①)**: files/ 프롬프트 8개에서
  죽은 서비스·함수 오용을 정리. 카탈로그 단계 프롬프트만 대상 —
  Door 예시→ContactSensor/DoorLock(잠금 언어), Safe.Lock→DoorLock.Lock,
  oven 예시→제습기/공기청정기, AirConditioner.SetMode(×5)→
  SetAirConditionerMode("cooling"→"cool"), Camera.Capture→CaptureImage,
  (#Valve).door_open→valve_open. 순수 언어 단계(translation,
  re_translate_kor)의 낱말 예문("식기세척기=dishwasher", "Door|문")은
  카탈로그 무관이라 유지. service_plan의 Light.On/MaxLevel·
  MultiButton.ButtonN은 **의도된 오답 예시·메타 이름이라 보존**.
  전 파일 카탈로그 대조 재스캔 0건. 신규 4스킬(ArmRobotDetail,
  ChatProvider, MessageSender, NewsProvider)은 rule sheet 부재 —
  코퍼스 미사용이라 보류.
- **센서 집합 읽기 정책(whisoo 결정)**: 명령어(NL)와 동결 IR은 그대로
  두고 binding_gt 열에만 얹는 후처리. 센서류(*Sensor/*Detector)를
  **조건에서** 읽는 자리를 규약(첫 후보 1대)으로 좁히던 것을 **후보
  전체 집합**으로 — "연기가 감지되면"의 자연스러운 뜻은 "아무 센서나".
  극성: 재실류 부재 감시(Presence/Motion == false, not Motion)는
  all(전부 미감지), 그 외 any. 값 하나를 담는 scalar 자리(알림용 읽기·
  인자)는 집합 불가라 단수 유지, 기기 상태 읽기("에어컨이 냉방 모드면")·
  버튼·WeatherProvider·액션 타깃도 단수 규약 유지.
- **적용**: 40행 변경(집합 자리 48, all 7). 자리 판정 분포에 set 48
  신설(first 178→135, main 55→50). 감사 0건. 게이트 재측정: 유효 178쌍
  EQUIV 139 / DIVERGE 39(전부 재생 확인) — 늘어난 25건은 v1 캐시 정답
  JoI가 센서 1대만 읽던 행들로, 새 기준과 어긋나는 낡은 정답(E2에서
  확정 IR+바인딩 기반으로 재생성될 대상). §9.10의 178쌍 수치는 이
  정책 이전 기준.
- binding_review.md 재편: 남은 눈검토 대상 = 규약(Main/첫 후보) 자리
  145행(기기 상태·scalar·액션 — 이상 배정만 잡으면 됨) + 한정자 자동
  표기 58행(참고용).
