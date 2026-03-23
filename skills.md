# JoI Code Generation Pipeline

## 1. Project Overview

자연어 IoT 명령을 **JoI DSL 코드**로 변환하는 LLM 파이프라인.
- **Model**: Qwen3.5-9B (소형 로컬 LLM). llama.cpp(GGUF) 또는 vLLM(AWQ) 으로 서빙.
- **Core Problem**: 소형 모델이 디바이스 선택 + 시간 분석 + 코드 생성을 한번에 하면 환각이 심함. context 4000~5000 토큰 초과 시 성능 급락.
- **Solution**: 파이프라인을 여러 단계로 분리하여 각 LLM 호출의 인지 부하를 줄임.

---

## 2. JoI DSL (Differences from Python)

| 개념 | JoI | Python |
|------|-----|--------|
| 초기화 | `:=` (최초 1회만) | `=` |
| 대입 | `=` (매 tick마다) | `=` |
| 루프 | **금지**. 외부 `period` JSON으로 반복 | `for`/`while` |
| 지연 | `delay(N UNIT)` | `time.sleep()` |
| 이벤트 대기 | `wait until (condition)` | 없음 |
| 다중디바이스 | `all(#Tag).Action()`, `==\|`, `>=\|` | 없음 |
| 수학 | 내장 math 금지. 직접 구현 | `math.abs()` 등 |

**출력 형식**: JSON `{"cron": "...", "period": N, "script": "..."}`
- NO_SCHEDULE: cron="", period=0, script만 있음
- SCHEDULED: cron 설정, period로 반복 주기
- DURATION: cron 시작 + period 반복 + script 안에 break 조건

---

## 3. Current Pipeline (run_local.py)

```
Stage 1: Translation (한국어 → 영어)
Stage 2: Mapping (run_mapping)  ←  순차 실행
Stage 3: Routing (run_router)   ←  순차 실행
Stage 4: JoI Code Generation
Stage 5: Post-processing (WindowCovering refine, Reasoning strip)
```

### Stage 2: Mapping (서비스 선택 + 태깅)
- **connected_devices 있을 때**:
  1. `connect_mapping_intent` → Device.Service 쌍 선택
  2. `connect_mapping_precision` → `(#Tag #Device)` 셀렉터 생성 (Reasoning 기반)
  3. `connect_quantifier` → single/all/any 판별
- **connected_devices 없을 때**:
  - `all_mapping_intent` → 전체 서비스 목록에서 선택

### Stage 3: Routing (시간/조건 분석)
1. `filter` → 조건/스케줄 존재 여부 (true/false)
2. `extractor` → 시간 로직 분석 (arrow notation 형식)
3. `router` → NO_SCHEDULE / SCHEDULED / DURATION 분류

### Stage 4: Code Generation
- cmd_type + is_connected 조합으로 6개 프롬프트 중 선택
  - `{connect|all}_joi_{no_schedule|scheduled|duration}`

### Stage 5: Post-processing
- WindowCovering → #Window/#Blind/#Shade 변환 (LLM + exec)
- `<Reasoning>` 태그 strip
- NO_SCHEDULE인 경우 JSON으로 래핑

---

## 4. Dataset (local_dataset.csv)

280개 레코드, 8개 카테고리:
1. Immediate-All: 단순 조작 (전체 서비스)
2. Immediate-Connected: 단순 조작 (연결된 디바이스)
3. Snapshot Conditions: if/else 스냅샷 체크
4. Event-Driven Polling: wait until 이벤트 대기
5. Sequences and Delays: delay() 포함 순차 액션
6. Complex Logic: 복수 and/or 조건
7. Schedules & Continuous Polling: cron/period/duration
8. Global State Management: := 영구 상태 변수

카테고리 1,2는 각각 all/connected 전용. 3~8은 50/50 split.

---

## 5. Prompt Engineering 핵심 구분

- **If vs When vs Whenever**: if→스냅샷, when→wait until, whenever→triggered:=false 래치 패턴
- **All vs Any vs Single**: all→`all(#Tag).Action()`, any→`==|`/`>=|` 연산자, single→단일 디바이스
- **Delay vs Schedule vs Duration**: delay→script 내 delay(), schedule→cron, duration→cron+period+break
- **이상(>=) vs 초과(>)**: 번역 단계에서 정확히 구분해야 함

---

## 6. Key Technical Details

### Addon Devices (LevelControl, ColorControl, RotaryControl)
- 독립 디바이스가 아님. 호스트 디바이스에 붙어서 사용: `(#Light).MoveToLevel(70)`
- Light에 LevelControl이 있으면 Light의 중복 서비스(CurrentBrightness 등) 필터링

### WindowCovering Refinement
- WindowCovering은 실제로 Window, Blind, Shade 등으로 나뉨
- LLM이 Python replace 코드를 생성 → exec()로 실행하여 태그 교체

### Service Details Enrichment
- ENUM 파라미터가 누락된 경우 같은 디바이스의 다른 서비스에서 ENUM pool 보충
- SetVolume → Volume 같은 읽기 서비스 자동 주입 (inject_value_service)

---

## 7. Branches

- **main**: llama.cpp 서빙 (port 8001). `./start_llama.sh`
- **vllm**: vLLM 서빙 (port 8000). `./start_vllm.sh`
- 프롬프트는 양쪽 동기화됨 (precision, quantifier, extractor의 토큰 절약 버전 적용 완료)

---

## 8. 진행 중인 작업 & 방향

### Self-Check 제거 완료
기존 self_check_translate → verify → correction (3 LLM 호출) 방식을 제거함.
- 문제: NL↔NL 비교가 본질적으로 불안정 (동의어, 의역 차이로 false negative 발생)
- 관련 프롬프트 파일도 삭제 대상: `joi_self_check_translate`, `joi_self_check_verify`, `joi_self_check_correction`

### 새로운 Verify 방향: Code Skeleton + Schedule 추출

**핵심 아이디어**: LLM이 코드를 읽는 대신, Python이 코드에서 구조를 추출 → LLM은 추출된 요약만 보고 command와 비교.

**Step 1 (Python, LLM 0회)**: 생성된 코드에서 두 가지 추출
1. **Code Skeleton** — 실행 흐름을 선형으로 펼침:
   ```
   wait until (Temperature >= 30) → delay(3 SEC) → AirConditioner.On()
   ```
   - delay 위치, operator(>=/>), 액션 순서가 자연스럽게 드러남

2. **Schedule Summary** — cron/period/break를 읽기 쉽게 변환:
   ```
   cron="0 12 * * 0,6" → weekends at 12 PM
   period=1800000 → every 30 minutes
   break: Hour == 0 → until midnight
   ```

**Step 2 (LLM 1회)**: command + skeleton + schedule을 주고 "Match?" 판단

**검증 가능한 오류 유형**:
- delay 위치가 잘못됨 (action 뒤에 와야 하는데 앞에 옴)
- period 값 틀림 (30초 = 30000ms인데 다른 값)
- cron 표현 오류
- duration break 조건 누락/오류
- 로직 순서 틀림
- 이상/초과 operator 혼동

### 이전에 시도 후 폐기한 접근

**Example DB 기반 파이프라인** (폐기):
- 48개 디바이스, ~350개 예시를 per-device DB로 구축
- Device Select → Service Select → Tagging+Quantifier → Code Gen 구조
- Device descriptions, Scheduler 가상 디바이스 등 설계
- 결론: 현재 파이프라인 대비 이점이 불명확하여 폐기. example DB 파일들도 삭제함.

**SSA (Structured Semantic Anchoring)** (검토 후 단순화):
- command와 code 각각에서 JSON 슬롯(devices, trigger, delay, timing 등) 추출 → slot-by-slot 비교
- 문제: delay가 여러개일 수 있고, "before/after" 같은 추상적 표현이 실제 코드 흐름을 못 담음
- → Code Skeleton 방식으로 단순화 (위 "새로운 Verify 방향" 참고)

---

## 9. Files Structure

```
run_local.py          # 메인 파이프라인
test.py               # 테스트 하네스 (target/custom/all 모드)
local_dataset.csv     # 280개 평가 데이터셋
skills.md             # 이 문서
start_llama.sh        # llama.cpp 서버 시작
start_vllm.sh         # vLLM 서버 시작
files/
  translation.md      # 한→영 번역
  filter.md            # 조건 유무 판별
  extractor.md         # 시간 로직 분석
  router.md            # NO_SCHEDULE/SCHEDULED/DURATION 분류
  all_service_summary.md
  connect_service_summary.md
  service_list_ver2.0.1.json
  window_covering_refine.md
  all/
    all_mapping_intent.md
    all_joi_no_schedule.md
    all_joi_scheduled.md
    all_joi_duration.md
  connect/
    connect_mapping_intent.md
    connect_mapping_precision.md
    connect_quantifier.md
    connect_joi_no_schedule.md
    connect_joi_scheduled.md
    connect_joi_duration.md
```
