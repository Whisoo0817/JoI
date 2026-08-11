# sLM 절 분할 연구 노트 — Streaming Typed Segmentation

> 2026-08-11 논의 정리. 대상 모델: `cyankiwi/Qwen3.5-2B-AWQ-4bit` (연구 목표는 1–2B sLLM).
> 데이터: 루트의 `dataset.csv` (382개 유니크 명령어, `ir_gt` timeline JSON + JOILang gold).

## 1. 문제 정의

절이 여러 개인 복잡한 명령어를 2B 모델이 이해할 때 **정보를 누락하거나 변형**한다.
이를 줄이기 위해 명령어를 절 단위로 분할하고, 절 안에서만 분석시키는 접근을 탐색해왔다
(이전 실험: 9B attention probe로 경계 검출 93.1% top-1, 지배 head는 L3_h8).

## 2. 아이디어: 단어 단위 순차(streaming) 처리

IoT automation 명령어는 대체로 **시간 순서대로 나열**된다 — 복합 조건절(-하고/-하면) 뒤에
trigger 시 수행할 action들이 나온다. 이 temporal/sequential 특성을 이용해, 명령어를 한 번에
prefill하지 않고 **단어(어절) 단위로 앞에서부터 처리**하며 절이 완성되는 시점마다 확정(commit)한다.

예: "밤 12시 이후에 사람이 감지되면 조명을 모두 끄고 스위치도 다 꺼줘."
- "밤" → 절 미완성, 계속
- "이후에" → 유력한 절 후보
- "사람이" → 새 절 시작 = "밤 12시 이후에"를 절로 확정 (사실상 wait-1 lookahead)

### 2.1 전제 검증 (dataset.csv 382개)

- 순서를 뒤집는 구문("-기 전에") **0건**, 후행 조건절(문미 -면) **0건** → "표면 순서 = 처리 순서" 성립
- 382개 중 **264개(69%)** 가 문장 중간 단어에 절-경계 접속어미(-면/-고/-서/-거나/-는데/후에/때/자마자) 보유, 경계 표지 총 523개. 나머지는 대부분 단일 절
- **한국어 head-final 특성**: 접속어미가 절의 마지막 단어에 붙으므로, 왼쪽부터 읽으면 절이 끝나는
  바로 그 시점에 경계 신호가 나타난다 (영어는 if/when이 절 시작에 옴 → 이 방법은 한국어에 특히 유리,
  HA/영어 일반화 시에는 약점이 될 수 있음)

### 2.2 핵심 인사이트: "N번 추론"의 절반은 공짜

causal LM은 **한 번의 prefill로 이미 모든 prefix 상태를 계산**한다. causal mask 때문에 위치 t의
hidden state는 "t까지만 읽은 상태"다. 따라서:

- **경계/타입 판정**: 각 단어 위치의 hidden state에 작은 분류 head를 얹으면, 단어별 순차 추론과
  수학적으로 동일한 판정을 prefill 1회로 얻는다. 토큰 생성 없음.
- **진짜 순차 생성이 필요한 부분**: 절이 확정될 때마다 그 절의 frame을 즉시 생성하고 이어 읽는
  **읽기-쓰기 인터리브** 방식. `[명령 1..k] → [절1 frame] → [명령 k+1..m] → [절2 frame] → …`
  시퀀스가 append-only라 KV 캐시 100% 재사용(vLLM prefix caching). "파싱한 절을 문맥에 적어두고
  다음을 읽는" 구조 자체가 누락/변형 문제를 직접 공격한다.

### 2.3 지연 추정 (2B AWQ, RTX 5090, vLLM)

- head 방식: prefill 1회 + 선형 head → 수십 ms
- 단어별 판정을 API 생성으로 할 경우: 스텝당 HTTP 오버헤드 ~10–20ms 지배, 12단어 ≈ 0.3–0.5초
- 인터리브 frame 생성: 총 생성 토큰 수는 일괄 파싱과 유사 → 전체 지연 비슷
- 주의: "캐시 재사용으로 빠르다" 자체는 기존 기술(prefix caching, simultaneous MT의 wait-k)이라
  contribution이 되기 어렵다. contribution 축은 **monotonic clause-commit이 sLLM의 정보 누락을
  줄인다는 정확도 주장** + (음성 입력 시) 스트리밍 ASR과의 계산 중첩.

### 2.4 리스크

1. 2B zero-shot은 절 분리에 실패함(smoke test 확인) → 판정에 SFT 또는 head 학습 필요.
   AWQ 체크포인트는 직접 파인튜닝 불가 → bf16 원본에 LoRA 후 재양자화 경로
2. "-고" 역할 중의성: 조건 연쇄("감지되고 … -면") vs 액션 연쇄("켜고 … 꺼줘")는 뒤 문맥이 결정
   → 경계는 즉시 commit, **타입은 해소 시점까지 유예** 가능
3. 조기 확정의 비가역성 → 확신 낮으면 판정을 미루는 adaptive wait-k로 완화
4. 복합 조건 내부 경계(중첩)는 여전히 어려운 케이스

## 3. Segment 단위: "절"이 아니라 IR 프리미티브

절의 단위가 애매하다는 문제("오후 1시부터 3시까지 10분마다"는 구문/moment 어느 축으로도 못 나눔)는
**segment를 timeline IR의 head 프리미티브 인스턴스로 정의**하면 사라진다. 인벤토리는 새로 정의할
필요 없이 `ir_gt`에서 도출되며, 382개 전체에 대해 닫혀 있다:

| 구분 | 프리미티브 | 출현 횟수 (382 명령) |
|---|---|---|
| head (8) | `call` | 505 |
| | `start_at` | 382 |
| | `if` | 166 |
| | `wait` | 124 |
| | `cycle` | 109 |
| | `delay` | 52 |
| | `read` | 44 |
| | `break` | 1 |
| modifier slot (~6) | `edge` (rising 34 / none 90), `for`(sustain, 27), `until`, `period`, `cron`, `count` | |

- 실제 등장하는 **op 조합 패턴은 20가지뿐** → 구조 조립은 규칙으로 가능한 수준
- HA와 1:1 대응: `wait+edge=rising` ≈ trigger, `if` ≈ condition, `call` ≈ action, `for` ≈ HA의 `for:`,
  `cycle` ≈ time_pattern → 일반성 주장 + MTL(metric temporal logic)로 형식화 가능

### 3.1 2층 구조가 애매함을 해소하는 예

"오후 1시부터 3시까지 5분마다 밸브를 …" 의 실제 IR:
- "1시부터" → `start_at.cron = 0 13 * * *`
- "3시까지" → `cycle.until = clock.time >= 1500`
- "5분마다" → `cycle.period = 5 MIN`

세 조각이 서로 다른 op의 **슬롯**을 채운다. 시간 복합구는 통째로 하나의 SCHEDULE segment이고,
내부 분해는 segment 안의 슬롯 추출 문제다. ("까지"의 의미가 "마다" 유무에 따라 달라지므로
독립 segment로 나누면 오히려 해석 불가.)

프레이밍: "명령어는 timeline 위의 프로그램, parsing은 표면 span을 timeline op으로 컴파일하는 것."

## 4. 판정기 구현: BIO 태깅 head (토큰 생성 없음)

"유한 슬롯 중 고르기 + 어디까지 묶을지"는 여러 토큰짜리 출력이 필요 없다. **sequence labeling**으로
분해된다: 단어마다 `B-X`(타입 X segment 시작) / `I-X`(계속) 라벨을 붙이면, 경계는 "다음 단어 라벨이
B냐 I냐"로 표현된다. head 8종이면 라벨 ~17개 = 위치당 17지선다 분류 1회.

```
밤        B-SCHED     사람이    B-WAIT      조명을  B-CALL     스위치도  B-CALL
12시      I-SCHED     감지되면  I-WAIT      모두    I-CALL     다        I-CALL
이후에    I-SCHED                           끄고    I-CALL     꺼줘      I-CALL
```

- 라벨 일관성(I-X가 O 뒤에 못 옴 등)은 CRF/Viterbi로 강제 (마이크로초 단위)
- **head가 못 하는 것**: 슬롯 값 정규화("오후 1시"→cron, "10분"→`10 MIN`)와 중첩 구조 조립
  → 타입 확정 후 결정론적 규칙(현 파이프라인의 lowering/naming과 같은 성격) + 잔여만 segment별 생성
- 학습 강도 2단계: (a) 백본 동결 + 선형 head만 (AWQ 위에 바로 얹음, 수 분 학습, 타입 정보의
  선형분리성은 미검증), (b) bf16 원본에 token-classification LoRA (여전히 분류 objective, 재양자화 필요)
- 라벨은 ir_gt와 명령어 정렬(숫자·기기명·어미 단서)로 상당 부분 자동 생성 가능

## 5. "5분 이상 유지" → sustain 판정 방법론

같은 단어 "유지"가 데이터에서 두 가지로 갈린다:
- "전력이 5W 미만으로 10분 이상 **유지되면** 꺼줘" → `wait(cond, edge=none, for="10 MIN")` (조건측)
- "잠길 때마다 조명을 최대밝기로 10초 **유지하다가** 꺼줘" → `call → delay(10 SEC) → call` (액션측)

단어 사전만으로는 실패. 타입은 부착 구조가 결정하고 한국어에선 어미에 드러난다(-되면 vs -하다가). 3겹 방법론:

1. **닫힌 선택**: head 타입과 duration의 슬롯 귀속을 enum에서 고르게 하고 vLLM structured output으로 강제
2. **minimal-pair SFT**: 같은 "5분"에 프레임만 바꾼 자동 생성 쌍 —
   "5분 **후에**"→delay, "5분**마다**"→period, "5분 이상 **유지되면**"→`for`, "5분 **동안** 켜줘"→delay-괄호,
   함정 "습도가 5 **이상이면**"(값 비교). edge 판정(감지**되면**=rising vs 상태**면**=none)도 같은 틀
3. **결정론적 검증기**: "모든 숫자는 정확히 한 슬롯에 복사", "분/초/시간 단위어는 duration형 슬롯에만",
   "'마다' 있으면 period 존재", "`for`는 cond 필수" — 위반 시 재생성/AMBIGUOUS. 이 검증기가 그대로
   GRPO의 verifiable reward가 된다

## 6. Wait-k probe 실험 (2B): 오른쪽 문맥은 노이즈인가 신호인가

**가설 대립**: "causal(왼쪽만)이 temporal 명령어에서 노이즈를 줄인다" vs "이 길이(~20단어)에선 오른쪽 문맥이 신호다"

### 설계

- `cyankiwi/Qwen3.5-2B-AWQ-4bit`, CPU, hidden state 추출 (`experiments/waitk_extract.py`)
- 각 명령을 `cmd ### cmd`로 두 번 입력 (echo trick): 1번째 복사본의 단어 state = causal(왼쪽만),
  2번째 복사본 = 전체 문맥을 본 state
- 피처 = 단어 마지막 subword 토큰의 hidden state (layer 2/6/12/18/23), 로지스틱 probe,
  명령 단위 GroupKFold 5-fold (`experiments/waitk_probe.py`)
- 조건: `pos`(위치만) / `C0`(causal만) / `C1·C2·C4`(다음 1·2·4단어 state 연결) / `CF`(causal+전체) / `Fonly`(전체만)

### 결과

**과제 A — 절 경계 판정** (gap 3,037개, 접속어미 유래 라벨, majority 0.828):

| 조건 | acc / F1 (최고층) |
|---|---|
| C0 | **0.996 / 0.987** |
| C1~C4 | 0.991~0.996 (이득 없음) |
| CF / Fonly | 0.996 (동일) |

경계 신호는 완전히 국소적 — causal만으로 충분. (라벨이 어미 규칙 유래라 sanity check 성격.)

**과제 B — "-고" 절의 조건/액션 판정** (n=194, 라벨 = 뒤에 -면 존재 여부, majority 0.562):

| 조건 | acc (층별 최고) | 오류율 |
|---|---|---|
| pos | 0.758 | — |
| C0 (causal만) | 0.923 | 7.7% |
| C1 | 0.954 | 4.6% |
| C2 | 0.954 | 4.6% |
| **C4** | **0.974** | **2.6%** |
| CF (causal+전체) | 0.954 | 4.6% |
| Fonly (전체만) | 0.964 | 3.6% |

### 해석

1. **"미래 = 노이즈" 기각**: lookahead 한 단어씩 추가마다 전 층 단조 개선, k=4에서 오류 1/3로
2. **약한 버전은 성립**: 전체 문맥(CF/Fonly)은 -면 마커를 볼 수 있음에도 유계 창(C4)보다 낮다
   → 필요한 건 근처 몇 단어, 전역 문맥은 무이득 + 표현 희석
3. causal만으로도 92% → 2B가 동사 의미("감지되고"류)로 뒤에 -면이 올지 예견 → 조기 commit 기반 튼튼
4. **최적점 = causal + 소규모 lookahead 창 (wait-k, k≈2–4)** — 스트리밍 설계와 일치.
   논문 서사: "경계 판정은 국소적, 타입 판정은 k≤4 창에서 포화, 전역 문맥 무이득 → incremental 처리는
   정확도 손실 없이 가능"

### 한계

- 과제 B의 n=194 → 1%p ≈ 표본 2개. echo trick의 전체-문맥 state는 진짜 양방향 인코더와 다른 계산
- **생성 단계의 누락/변형 감소 주장은 미검증** — 절 단위 인터리브 생성 vs 일괄 생성을 2B 서버로
  직접 비교하는 것이 다음 실험

## 7. 파일

- `start_qwen35_2b_5090.sh` — 2B vLLM 서버 (port 8002, GPU 1 기본). sm_120(5090) 우회는 9B 스크립트와
  동일(CUDA_HOME→pip nvcc). **주의**: 2B는 `</think>`를 안 뱉어서 `--reasoning-parser qwen3` 상태로는
  출력이 전부 reasoning 필드로 들어간다. 요청에 `"chat_template_kwargs": {"enable_thinking": false}`를
  넣으면 content로 정상 반환
- `experiments/waitk_extract.py` — hidden state 추출. AWQ 체크포인트 로딩 시 config 패치 필요:
  `quantization_config.ignore`에 `re:.*in_proj_a$`, `re:.*in_proj_b$` 추가 (linear_attn 미양자화 가중치)
- `experiments/waitk_probe.py` — wait-k 조건별 로지스틱 probe 비교
