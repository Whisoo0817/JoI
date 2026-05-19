# JoI-LLM 프로젝트 인수인계 (2026-05-19 기준)

> 이 문서는 본 프로젝트에 처음 합류하는 에이전트/개발자가 코드, 데이터, 논문 방향을
> **단독으로 이해**할 수 있도록 작성된 self-contained 핸드오프 노트다. 누락된 맥락은
> 같은 폴더의 `paper_summary.md`(논문 plan canonical), `sensys.md`(venue 전략), `whisoo.md`
> (의사결정 일지), `simulators/README.md`(IR/JoI 시뮬레이터) 와 `~/joi/AGENTS.md`,
> `~/joi/PROJECT_STRUCTURE.md` 에서 보강한다.

---

## 0. 한눈에

| 항목 | 값 |
|---|---|
| 프로젝트 루트 | `/home/gnltnwjstk/joi/` |
| 논문 / 노트 | `/home/gnltnwjstk/joi/paper/` |
| Test runner | `python3 test.py target` (모드: `target` / `pre` / `custom`) |
| 핵심 파이프라인 | `paper/run_local_ir.py :: generate_joi_code_ir` |
| LLM | vLLM 서버 (`192.168.0.250:8002`), Qwen3.5-9B-AWQ-4bit |
| Service catalog | `files/service_list_ver2.0.4.json` (skills=50) |
| Dataset | `dataset_migration/local_dataset2.csv` (307 rows, `category_v2` C01–C18) |
| 현재 상태 | **NL → IR + Precision + JoI lowering 모두 활성**. Lowering bucket consolidated 5→2 (noncycle/cycle) with `files/joi_cycle.md` switchboard. cycle.period required in IR. Deterministic post-process layer (wrapper.period override, any→all+\| canonicalization, extra-paren strip). Commit `172c6bd` on `paper` branch. |
| 논문 hero | "NL→JoI 분해 + user-confirmed IR-as-spec + IR-FSM transition-obligation coverage" |
| 타겟 venue | SenSys 2027 R1 (Abstract 2026-05-29 / Full 2026-06-05) |

---

## 1. JoI Language

### 1.1 목적

JoI는 IoT 허브 위에서 돌아가는 **reactive 자동화 DSL**이다. Python-like 문법으로
디바이스 서비스를 호출하며, **컴파일러 없음 / 리턴값 없음 / 실행 결과는 물리적
사이드이펙트뿐**이라는 점이 일반 코드와 다르다. 허브는 스크립트를 주기적으로
재실행(`period` ms마다 tick) 하거나 cron으로 트리거하면서, 디바이스 상태를
폴링/관찰한다.

사용자 시나리오 스펙트럼:

| 난이도 | 예 | 구조 |
|---|---|---|
| Trivial | "Turn on the lights in Sector A at 5 PM" | one-shot cron |
| Simple | "Close the window if it rains" | one-shot condition |
| Bounded | "Check the temperature every 5 min from 1–3 PM" | time window + periodic |
| Persistent | "Turn on the light every time the door opens" | rising-edge repeat |
| Trigger→Periodic | "Sound the siren every 5 min after motion detected" | event then periodic |

**중요한 사실**: Bounded / Persistent / Trigger→Periodic 같은 reactive 의미는 JoI에
1급 primitive로 없다. 이 의미들은 평범한 변수(`triggered`, `phase`, `start_time`)와
제어 흐름으로 **idiom**처럼 작성된다. 이게 §3 문제의 출발점이다.

### 1.2 Wrapper JSON

JoI 자동화는 보통 메타데이터 래퍼와 함께 등록된다.

```json
{
  "name":   "scenario_id (downstream가 자동 부여)",
  "cron":   "0 7 * * *",
  "period": 300000,
  "script": "if (any(#Light).Switch == true) { (#Light).Off() }"
}
```

| 필드 | 의미 |
|---|---|
| `name` | 시나리오 식별자. lowering 단계에서는 emit하지 않고 downstream이 부여 |
| `cron` | 표준 5-field cron `min hour dom mon dow`. 빈 문자열 `""`이면 이벤트/매뉴얼 트리거 |
| `period` | 폴링 주기(ms). `0` = 폴링 없음(한 번 실행 후 종료 또는 wait-driven), `N > 0` = N ms마다 재실행, `-1` = 명시적 NO_SCHEDULE (레거시) |
| `script` | JoI 소스. `\n` 줄바꿈, `{ }` 안 4-space indent |

### 1.3 디바이스 셀렉터 (Tag-based)

디바이스는 ID로 직접 부르지 않고 **태그**로 부른다. 허브가 런타임에 해석한다.

| 셀렉터 | 의미 | 예 |
|---|---|---|
| `(#Tag1 #Tag2)` | 모든 태그를 가진 단일 디바이스 | `(#Bedroom #Light).Off()` |
| `all(#Tag)` | 매칭되는 모든 디바이스에 fan-out | `all(#Light).Off()` |
| `any(#Tag)` | 존재 quantifier (cond 안에서) | `if (any(#Sensor).Contact == true)` |

`==|`, `>=|` 등은 `any`와 짝지어 쓰는 **quantifier 비교 연산자**이다 (드물게 등장).

### 1.4 문법 cheat-sheet

**제어 흐름**
- `if (cond) { ... } else { ... }`, `wait until(cond)`, `break`
- `delay(N UNIT)` — UNIT ∈ {`HOUR`, `MIN`, `SEC`, `MSEC`} — lowering은 가장 큰 정확 단위를 고른다 (3 600 000 → `1 HOUR`)
- **루프 없음**: `for`/`while`/`var`/`let`/`const` 사용 금지. 반복은 허브가 `period` 폴링으로 만들어준다

**논리/비교**
- 논리 연산자: `and`, `or`, `not` (NOT `&&` `||` `!`)
- 비교: `==`, `!=`, `>`, `<`, `>=`, `<=`

**변수 — `:=` vs `=` (가장 헷갈리는 부분, joi_common.md §3.2)**

| 연산자 | 의미 | 용도 |
|---|---|---|
| `:=` | **initialize-once-then-persist.** 우변은 첫 tick에 한 번만 평가, 슬롯 값이 모든 tick에 걸쳐 유지 | persistent state flag: `triggered := false`, `phase := 0`, `state := "A"` |
| `=` | **per-tick.** 매 tick 재평가 | 센서 fresh read (`current = (#Light).CurrentBrightness`), 변화량 계산 (`new_vol = (#Speaker).Volume + 5`), `:=` 슬롯 업데이트 (`triggered = true`) |

**트랩**:
- `triggered = false` (script 맨 위, `:=` 없이) → 매 tick 초기화 → 영원히 동작 안 함
- cycle body 안에서 `new_val := X + 10` → `+10`이 한 번 계산되어 freeze → 잘못된 값

**호출은 positional only**
- ✅ `(#Light).MoveToBrightness(100, 0)` — `[Service Details]` 선언 순서대로 콤마
- ❌ `(#Light).MoveToBrightness(Brightness=100, Rate=0)` (Python-style)
- ❌ `(#Light).MoveToBrightness(Brightness:100, Rate:0)` (TS-style)
- IR의 `args:{"Brightness":100,"Rate":0}`는 lowering 시 이름이 떨어져 positional이 된다

**Clock built-in (IR/JoI 공통 표현식, 서비스 호출 X)**
- `clock.time` — 4-digit `hhmm` int (자정 `0000`, 18:00 `1800`, 23:59 `2359`). 정수 리터럴과 비교
- `clock.date` — 8-digit `YYYYMMdd` string (`"20261225"`)
- `clock.dayOfWeek` — `"MON".."SUN"` string
- `Clock.*` value 서비스도 카탈로그에 존재하지만 lowering은 항상 `clock.*` built-in을 선호

**문자열 concat**: `"text" + value` (자동 캐스트)

**금지된 것**: `Math.*`, `abs()`, `min()`, `max()`, `.ToString()`.
`abs` 우회: `diff = a - b; if (diff < 0) { diff = b - a }`.

### 1.5 Service catalog (`files/service_list_ver2.0.4.json`, skills=50)

JSON 구조: `{"skills": [{id, descriptor, values, functions, enums}, ...]}`.
`loader.py`가 dict로 평탄화한다 (`SERVICE_DATA[skill_id] = {descriptor, values, functions, enums_map}`).

각 skill은 두 종류의 멤버를 가진다:
- **`values`** (`type="value"`) — 센서 read. 인자 없음. 예: `TempSensor.Temperature`, `Switch.Switch`
- **`functions`** (`type="action"`) — 호출 가능 메서드. 인자/반환 타입 있음. 예: `Switch.On`, `Light.MoveToBrightness`

서비스 토큰은 항상 `Category.ServiceName` 형식 (e.g. `Switch.On`, `Light.MoveToBrightness`).
**디바이스 ID는 절대 쓰지 않는다** — selector 스테이지가 별도로 결정한다.

**50 skill 카테고리 (역할별):**

| 그룹 | Skills |
|---|---|
| Sub-skill capability (sub-skill 태그) | `Switch` (On/Off/Toggle), `LevelControl` (MoveToLevel + CurrentLevel), `ColorControl` (SetColor), `RotaryControl` |
| 센서 (value-only) | `ContactSensor`, `MotionSensor`, `PresenceSensor`, `PresenceVitalSensor`, `PressureSensor`, `SoundSensor`, `LightSensor`, `LeakSensor`, `SmokeDetector`, `RainSensor`, `TemperatureSensor`, `HumiditySensor`, `CarbonDioxideSensor`, `AirQualitySensor` (CO2/dust/TVOC 등 7개), `Plug` (Current/Power/Voltage), `Charger` |
| 모드 가전 | `AirConditioner`, `AirPurifier`, `Humidifier`, `Dehumidifier`, `Dishwasher`, `LaundryDryer` (+SpinSpeed), `Oven` (+`AddMoreTime`, `SetCookingParameters`), `RiceCooker`, `RobotVacuumCleaner` (Cleaning/RunMode), `Pump`, `Siren` |
| 개폐/잠금 | `Door`, `DoorLock`, `WindowCovering` (UpOrOpen/DownOrClose/SetLevel/Stop), `Valve`, `Safe` |
| 조명 | `Light` (10 values: ColorMode/Hue/Sat/XY/Brightness/Mireds…, 14 functions: MoveTo*/Step*/Enhanced*) |
| 미디어 | `Speaker` (Play/Pause/Stop/Speak/SetVolume/VolumeUp/Down/FastForward/Rewind), `Television` (Channel±/Set) |
| 캡처 | `Camera` (CaptureImage/Video, Start/StopStream), `AudioRecorder`, `FaceRecognizer` |
| 버튼 | `Button` (single), `MultiButton` (`Button1..Button4` 각각 ENUM) — C08/C14에서 집중 사용 |
| 클라우드 / 정보 | `CloudServiceProvider` (ChatWithAI/GenerateImage/ExplainImage/TTS/STT/SaveToFile/Upload…), `WeatherProvider`, `MenuProvider`, `EmailProvider` |
| 시간 / 기타 | `Clock` (12 values + `Delay` function — 단, lowering은 `clock.*` built-in 우선), `ArmRobot` |

**예시 — `Switch` skill 한 개의 catalog 모양:**

```json
{
  "id": "Switch",
  "descriptor": "Allows for the control of a Switch device",
  "values": [
    { "id": "Switch", "type": "BOOL", "descriptor": "current on/off state" }
  ],
  "functions": [
    { "id": "On",     "arguments": [], "return_type": {"type": "VOID"} },
    { "id": "Off",    "arguments": [], "return_type": {"type": "VOID"} },
    { "id": "Toggle", "arguments": [], "return_type": {"type": "VOID"} }
  ],
  "enums": []
}
```

**중요한 카탈로그 규칙**:
- `<DeviceClass>.On` 같은 메서드는 **존재하지 않는다**. 전원 토글은 항상 `Switch.On` / `Switch.Off`이고, 디바이스가 `Switch`를 sub-category로 가지고 있어야 한다 (`service_plan.md` Rule 9).
- `Switch` / `LevelControl` / `ColorControl` / `RotaryControl` 네 개는 단독 디바이스가 아니라 다른 디바이스(Light, Speaker, Plug 등)에 함께 붙는 sub-skill이다. `extract_service_details`가 parent fallback으로 찾아준다 (`run_local.py:57-82`).
- Color name → xy는 `joi_common.md` 안의 10색 표(red/green/blue/yellow/cyan/magenta/orange/purple/pink/white)로 결정론적 매핑. unknown color는 white로 fallback.

### 1.6 Dataset (`dataset_migration/local_dataset2.csv`, 307 rows)

**컬럼**: `index, index_old, category, category_v2, command_kor, command_eng, gt_old, gt_new, connected_devices, notes`
- `category_v2` (C01..C18) — 파이프라인이 사용하는 라벨. 18개 sub-cat 중 C06은 비어있음.
- `category` — legacy 1-9 분류 (참고용).
- `gt_old` / `gt_new` — `{"name","cron","period","script"}` JSON 문자열. 메서드 이름은 레거시 lowercase prefix (`light_switch_on`).
- `connected_devices` — `{device_id: {category:[...], tags:[...]}}` 형태의 stringified dict. `_parse_dict_input`이 파싱.

**18 sub-category 분류표:**

| ID | n | 패턴 | IR idiom | cron / period 패턴 | 예 |
|---|---|---|---|---|---|
| C01 | 28 | 단일 디바이스 trivial call | D-1 | `""` / `0` | "Switch the dishwasher to dry mode." |
| C02 | 33 | selector (`all()` / tag-intersect) 포함 | D-1 | `""` / `0` | "Set all dehumidifiers in the lab to AI drying mode." |
| C03 | 30 | 단일 조건 `if` | D-1 + `if` | `""` / `0` | "If the oven is in grill mode, add 4 more minutes." |
| C04 | 3 | `if-else` | D-1 + `if/else` | `""` / `0` | "If dryer spin speed > 3, decrease; else increase." |
| C05 | 30 | AND-compound `if` | D-1 + `if(AND)` | `""` / `0` | "If bedroom temp ≥26 and window open, close window and turn on AC." |
| C06 | **0** | OR / elif chain | — | — | (현재 CSV에 없음) |
| C07 | 32 | level-wait `when X, do Y` | D-2 | `""` / `0` | "When sound exceeds 50, stop speaker." |
| C08 | 41 | rising-edge `whenever` (센서 + MultiButton) | D-3 | `""` / `100` | "When button 1 pressed, turn on all bedroom lights." |
| C09 | 18 | sequential `delay` (트리거 없음) | D-1 + delay | `""` / `0` | "Switch TV to ch7, after 1 hour to ch11." |
| C10 | 9 | 트리거 + delayed action | D-2 + delay | `""` / `0` | "When presence detected, take a picture after 1 minute." |
| C11 | 1 | snapshot + delay + diff | D-8 | `""` / `0` | "Check wine cellar temp now and 10 min later." |
| C12 | 15 | phase lifecycle (`when X, every N thereafter`) | D-4 | `""` / `N` | "When door opens, say 'Welcome' every minute thereafter." |
| C13 | 7 | alternation / 토글 | D-5 | `""` / `N` | "Every 30 min, toggle AC sleep↔auto." |
| C14 | 4 | progressive update + break | D-6 | `""` / `100` | "Each button press, +10 brightness, max 100." |
| C15 | 21 | cron-only action | D-7 | `"0 18 * * *"` / `0` | "At 6 PM, set odd-tagged wall blinds to 50%." |
| C16 | 13 | cron + branch | D-7 + `if` | `"0 15 * * 0,6"` / `0` | "On weekends at 3 PM, if leak, set siren emergency." |
| C17 | 12 | period polling + branch (cron 없음) | period + `if` | `""` / `N` | "Every 10 min, if temp ≥30, set AC cool." |
| C18 | 10 | bounded window (cycle.until) | D-9 | cron + period | "Every 5 min from 1–3 PM, toggle valve." |

**Family rollup** (eval graph용): F1 Action {C01,C02} 61 · F2 Conditional {C03–C06} 63 ·
F3 Trigger {C07,C08} 73 · F4 Delay {C09–C11} 28 · F5 Cycle {C12–C14} 26 ·
F6 Schedule {C15,C16} 34 · F7 Polling/Bounded {C17,C18} 22.

(Memory 파일 `project_joi_dataset_categories.md`는 308 rows / C03=31로 적혀 있지만 현재
CSV는 307 / C03=30. C06이 비어 있는 건 일치. dataset 작업 시 항상 현재 CSV를 source of truth로.)

---

## 2. Pipeline: NL → IR (현재 활성), IR → JoI (disabled)

### 2.1 왜 SLLM은 NL→JoI 직접 못 푸나

배포 제약(C3): 프라이버시·sub-second latency·offline → on-premise 9B 클래스 LLM 강제.
이 환경에서 NL→JoI 한 방 생성은 LLM이 동시에 4개 문제를 풀어야 한다:

1. **idiom 선택** — `triggered`/`phase`/`alternation` 어느 패턴?
2. **JoI syntax** — `:=` vs `=`, `wait until`, `cron`/`period` 상호작용
3. **device selector** — `(#Loc #Skill)`, `all(...)`, `any(...)`
4. **timing 산술** — `delay(N UNIT)` 변환, cron 표현

joint accuracy가 per-aspect accuracy보다 훨씬 낮게 무너진다. 9B 직접 생성으로는
reactive 카테고리 (C07 이후)에서 사용 불가 수준 (~35%). GPT-4 수준도 ~65% 정도라
스케일만으로는 해결 안 됨 (`paper_summary.md` §1.1).

### 2.2 분해 구조 (Hero)

```
NL (영어)
  │  Stage 1: NL → Timeline IR  (9B LLM, schema-validated)
  ▼
Timeline IR ─► 한국어 readable rendering ─► 사용자 confirm/edit ─► IR'
  │
  │  Stage 2: IR → JoI  (deterministic lowering, rule-based)
  ▼
JoI 코드
```

**핵심 발상**: 사용자가 OK한 IR이 **spec 역할**을 한다. 이전에는 "NL → JoI 전체"가
verification 대상이라 spec이 없어서 자동 검증 불가능했는데, 분해 후에는 검증 대상이
"IR → JoI"로 축소되고 IR이 spec이 되어 simulation-trace 비교로 검증 가능해진다.

### 2.3 `test.py target` → `generate_joi_code_ir` 흐름

진입점 (`test.py:75-99`):
1. `dataset_migration/local_dataset2.csv` 로드
2. `test_targets = {"C09": [13], ...}` 딕셔너리에 따라 row 필터
3. 각 row에 대해:
   ```python
   result = generate_joi_code(kor, row['connected_devices'], {})
   ```
   - `generate_joi_code`는 `paper/run_local_ir.py:1005`에서 `generate_joi_code_ir`로 alias
4. `print_result`로 selectors / IR readable / code / 스테이지별 로그 출력
5. stdout은 `_Tee`로 `/tmp/joi_target_<timestamp>.log`에 미러링

### 2.4 Stage-by-stage 표

LLM 호출은 모두 `run_local.run_llm_inference` 통과 (vLLM streaming, `temperature=0.1`,
`max_tokens=512`, `enable_thinking=False`). IR extractor만 별도 — `temperature=0.0`,
`max_tokens=2048`, non-streaming (`timeline_ir.extract_ir`).

```
                                  test.py target
                                       │
                                       ▼
                          generate_joi_code_ir(kor, devices, {})
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            │  Stage 0  command_merge        (modification 있을 때만)
            │  Stage 1  translation          (KOR → ENG; Hangul 없으면 skip)
            │  Stage 1.5 pre_analysis        ENG → Logic/Devices hints
            │  Stage 2  service_plan         ENG + hints + connected + device_rules
            │                                 → ordered ["Cat.Method", ...]
            │                                 (KV-cache anchor)
            │
            ▼
   ──── Stage 3 parallel (ThreadPoolExecutor max_workers=2) ────
   Branch A (resolve + IR — sequential)            Branch B (precision)
   ─────────────────────────────────────           ─────────────────────
   3A-1 enum_cond_check (yes/no)                   3B-1 mapping_device_match
   3A-2 enum_resolve (if yes)                            (LLM, alias d1,d2,…)
   3A-3 arg_resolve                                3B-2 deterministic Python
   3A-4 timeline_ir_extract                              selector builder
                                                         (tag 교집합 + quantifier wrap)
                              │
                              ▼
              _inject_implicit_vars(ir)   (Python backstop)
              ir_to_readable(ir)          (결정론적 KR 렌더링)
                              │
                              ▼
            Stage 4 joi_from_ir lowering   ✅ ACTIVE
            (run_local_ir.py L918+, bucket routed via classify_ir)
                              │
                              ▼
              return {code:"", ir, ir_readable, precision, log}
```

| # | Stage | PROMPTS key | Input | Output | 파싱 위치 |
|---|---|---|---|---|---|
| 0 | command_merge | `command_merge` | `Original: …\nModification: …` | `<Reasoning>…</Reasoning>\n<merged>` | `run_local_ir.py:184` |
| 1 | translation | `translation` | raw KOR | ENG (no fences) | `run_local_ir.py:194` |
| 1.5 | pre_analysis | `pre_analysis` | `[Command]` + `[Connected Devices]` + `[Device Summary]` | caveman free-form `<Reasoning>` 블록 (≤150 tokens, no slots) | `<Reasoning>` 태그 strip 후 `command_hints` 저장 |
| 2 | service_plan | `service_plan` | `[Command]` + `[Command Hints]` + `[Connected Devices]`(full ids) + `[Device Rules]`(per-cat) | `<Reasoning>` + JSON `["Cat.Method", ...]` 순서 보존 | `run_local_ir.py:286-310` → `selected_services` |
| 2.5 (A-1) | enum_cond_check | `enum_cond_check` | follow-up — Stage 2 turn (`user=plan_input, assistant=plan_output`) 재사용 후 yes/no 질문 | `yes` / `no` | `run_local_ir.py:424` |
| 2.6 (A-2, conditional) | enum_resolve | `enum_resolve` | follow-up + `[ENUM-Value Services]` + per-device `# @enum_resolve` 힌트 | JSON `{Cat.Method: {op,value} \| null}` | → `resolved_enum_conds` |
| 2.7 (A-3) | arg_resolve | `arg_resolve` | follow-up + `[Command]` + `[Selected Services]`(function-only) + `[Service Details]`(args+return) + per-device `# @arg_resolve` 힌트 | JSON `{Cat.Method: {arg:val…} \| [list]}` | → `resolved_args` |
| 2.8 (A-4) | timeline_ir_extract | `timeline_ir_extractor.md` | `[Command]\n<ENG>\n\n[Services]\n<intent block>\n\n[Command Hints]\n…\n\n[Resolved Args]\n…\n\n[Bind Hints]\n…` | JSON `{"timeline":[…]}` (9 ops, schema 검증) | `run_local_ir.py:816`; reject → `JoiGenerationError(ir_invalid \| ir_rejected)` |
| 3B-1 (B) | mapping_device_match | `mapping_device_match` | `[Command]` + `[Command Hints]` + `[Selected Services]` + `[Connected Devices]`(alias `d1,d2,…`) | `<Reasoning>` + JSON `{Cat.Method: {q: one\|all\|any, groups:[[d1,d2],…]}}` | `_parse_device_match_qids` |
| 3B-2 | (Python only) | — | group별 alias ids + alias→tags map + quantifier | `{Cat.Method: ["(#TagA #TagB)", "all(#…)", …]}` | tag 교집합 + quantifier wrap + sub-skill 필터, alias→real id 복원 (`run_local_ir.py:655-710`) |
| 4 | joi_from_ir | `joi_<bucket>` + `joi_common` | IR + Precision Selectors + Service Details (IR-readable 제거됨) | JoI JSON `{name, cron, period, script}` | **active** — bucket router `classify_ir`로 **2개 prompt 중 선택** (noncycle / cycle). cycle prompt는 switchboard로 D-3/D-4/D-5/D-6/D-9/B-2 dispatch. Lowering 후 `_strip_selector_extra_parens` → `_apply_service_prefix` → `_normalize_script_newlines` → `_post_process_joi_any_quantifiers` (any(#X) → all(#X) + ==\|) → **wrapper.period override** (IR cycle.period에서 ms 변환) 순으로 후처리. |

### 2.5 KV-cache 최적화 패턴

`enum_cond_check` / `enum_resolve` / `arg_resolve` 세 follow-up 스테이지는 **공통적으로**
Stage 2의 `(system=service_plan, user=plan_input, assistant=plan_output)` 턴을 재사용한 뒤
새로운 user 메시지만 append (`infer_followup`, `run_local_ir.py:168-179`). vLLM의 prefix
cache가 service_plan 턴까지 hit되어 decode만 새로 일어남.

### 2.6 IR 스키마 (9 ops)

자세한 grammar는 `paper/timeline_ir_extractor.md` 참조. 핵심:

```json
{
  "timeline": [<step>, <step>, ...]
}
```

| op | 의미 | 주요 필드 |
|---|---|---|
| `start_at` | 시나리오 anchor | `anchor: "now"` 또는 `anchor:"cron", cron:"<5-field>"` |
| `wait` | cond 만족까지 블록 | `cond`, `edge: none\|rising\|falling` — `edge`는 **위치로 결정**(top-level→`none`, cycle 안→`rising`). `falling`은 cond 부정으로 표현 |
| `delay` | N 단위 대기 | `duration: "<N> <HOUR\|MIN\|SEC\|MSEC>"` (예: `"5 MIN"`, `"1 HOUR"`) |
| `read` | 값 스냅샷 → local var | `var`, `src:"<Device.attr>"` — 같은 attr을 시점 다르게 비교할 때만 |
| `call` | 디바이스 호출 | `target:"<Device.method>"`, `args:{...}`, `var:"<X>"`(필요 시 bind) |
| `if` | one-shot 분기 | `cond`, `then:[...]`, `else:[...]` — `cond`는 반드시 명시적 비교 |
| `cycle` | body 반복 | `until:"<expr>\|null"`, **`period:"<N> <UNIT>"` (REQUIRED, 2026-05-19~)**, `body:[...]`. Defaults per `timeline_ir_extractor.md` D7b: D-3 edge cycle(body wait rising) → `"100 MSEC"`; D-5 alternation(body 2+ inter-call delays) → 각 delay와 같은 값; 그 외 → NL `every N <unit>`. Validator가 cycle.period 누락 시 reject. Body는 iteration 한 번 (cadence rest-delay 금지; iteration-internal sub-step delay는 허용). |
| `break` | 가장 가까운 cycle 탈출 | — |

**Validator 규칙** (`paper/timeline_ir.py::validate_ir`):
- `timeline[0]`는 `start_at`이어야
- `cycle.body`는 delay 또는 edge-triggered wait가 최소 1개 (무한 spin 방지)
- nested cycle 금지
- 모든 `Device.attr` / `Device.method`가 catalog에 존재해야 (extractor 단계에서 hinting만; 실제 catalog 매칭은 selector 스테이지가)

**IR → 한국어 readable** (`ir_to_readable`):
9 op 각각을 결정론적으로 한국어 bullet으로 매핑 (LLM 없음, paper §3 contract).
사용자가 의도를 확인할 수 있게 만든 표면.

### 2.7 디바이스 룰 파일 (`files/devices/device_rules_<cat>.md`)

각 카테고리 (현재 49개) 별로 한 파일. `# @<SectionName>` 마커로 stage-scoped 섹션을 가른다:
- 마커 이전 → 기본 `service_plan` 섹션 (service_plan 스테이지가 사용)
- `# @arg_resolve` → arg_resolve 스테이지에서 pull
- `# @enum_resolve` → enum_resolve 스테이지에서 pull

`loader.py::get_device_rules_section(category, section)`이 lookup. 섹션 이름은
대소문자/하이픈 무시 (`# @ArgResolve` == `# @arg_resolve` == `argresolve`).

이 구조는 **service catalog 변경에 따른 유지보수 비용**을 줄이기 위함이다 (§5 참조).

---

## 3. Problem: 왜 verification이 어려운가

세 개의 문제(generation, verification, user feedback)가 한 구조적 원인에서 나온다:

```
근본 원인: reactive temporal 의미가 idiom으로 인코딩됨
         (triggered := false, phase := 0 — 문법적으로 평범한 변수)
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
  Generation     Verification  User feedback
  LLM이 NL만     실행기 없음,    JoI idiom 불투명,
  보고 idiom     spec 없음,      사용자가 생성된
  선택 못 함     ground truth 없음  코드 의미 못 읽음
```

### 3.1 JoI에서 직접 FSM을 만들 수 없는 이유

textbook 모델체킹 접근(JoI → FSM)으로는 풀 수 없는 세 가지 이유 (`paper_summary.md` §6.1):

1. **Informal target semantics** — JoI에 small-step semantics가 prose로만 적혀 있고
   형식적 정의가 없다. FSM 추출은 의미부터 새로 정의해야 하는 별도 연구 문제.
2. **Continuous values / time / tag resolution** — 센서값(온도, 밝기), 가상 시간(cron-anchored,
   며칠 스팬), `all/any` 뒤의 동적 디바이스 집합 → 무한/연속 상태 차원.
   유한 추상화는 경계 정밀도(정확히 30°C 버그)를 잃는다.
3. **Idiom 다중성** — 같은 의도(rising edge)를 `triggered` flag / `prev/curr` / `phase` enum
   여러 방식으로 lowering 가능. 정적 코드 분석으로 FSM을 뽑으려면 패턴 카탈로그를
   verifier에 박아야 하는데, LLM이 만드는 새 idiom은 카탈로그 밖. closed-set 가정 회피가
   본 연구 목표라서 자기모순.

### 3.2 NL round-trip(JoI→NL→비교)도 안 된다

이전 시도(`re_translate.md`): JoI→NL 역번역해서 NL과 비교. 실패 이유:
- **JoI ↔ NL은 비대칭** (`paper_summary.md` §4): NL→JoI는 LLM이 패턴 매칭, JoI→NL은
  decompilation 수준 난이도 (idiom 불투명 + 다대다 매핑 + 평가 anchor 부재).
- **Idiom 불투명**: `triggered := false`만 보고 의미적 역할 복원 불가.
- 경험적으로 약 4건에 1건 misinterpret; 새 idiom 합성은 룩업 밖.

→ NL ↔ JoI round-trip을 **버리지 않고 NL ↔ IR로 재배치**. IR ops은 1급 reactive primitive라
NL과 1:1 결정론적 매핑 가능. **이게 user-mediated confirmation을 가능하게 함**.

### 3.3 Standard model checking (SPIN/NuSMV/UPPAAL)도 안 맞음

(`paper_summary.md` §5):
- **No formal φ to check** — spec이 LLM-extracted user-confirmed IR이지 LTL/CTL이 아님
- **State-space explosion** — `period:100ms` × 1시간 = 36 000 ticks, 연속 센서값, persistent
  flag/phase 상태 → ≤2 s edge 런타임 budget 안 됨
- **Bisimulation gap** — IR의 `wait edge:rising`과 JoI의 `triggered` flag idiom은 state shape이
  달라 strict bisim 실패
- **Output mismatch** — 모델체커는 ✓/✗ + counterexample만. 우리는 per-feature transition coverage
  rate + retry signal 같은 양적 신호 필요

→ heavy MC 대신 **lightweight Model-Based Testing**: IR-FSM의 transition obligation을 시나리오로 cover.

### 3.4 우리 해결: IR-FSM transition-obligation coverage (3-layer)

`paper_summary.md` §6 / `whisoo.md` 정리:

```
시나리오 들어옴
   │
   ├─ L1 정적 검사 (≪ ms): flag init 누락, malformed selector 등 AST-level
   │
   ├─ L2 IR-FSM transition coverage (~tens of ms, HERO):
   │     JoI를 시뮬레이터로 실행 → trace 출력 →
   │     IR-FSM의 transition 의무에 어긋나는지 체크
   │
   └─ L3 Differential simulation (≤1초, fallback):
        L2의 transition-locality 가정(A2)이 깨지는 합성 케이스만
        IR 시뮬레이터까지 돌려서 full trace 비교
```

- 모든 verdict path는 **결정론적**, LLM 없음 (trust boundary, circular-judging 회피).
- Coverage claim: **transition-obligation completeness** (assumption A1–A6 하).
  Full equivalence보다 약하지만 ad-hoc 테스트보다 강한 중간 보증.
- 시뮬레이터 인프라는 `paper/simulators/` 에 phase-1 완료 (11/11 E2E pass,
  C01–C07에서 85.1% 통과 — 나머지 23개는 pipeline 버그, 시뮬레이터로 가리지 않음).

---

## 4. Paper plan & target venue

### 4.1 Hero (canonical, `paper_summary.md` §3.2)

> NL→JoI verification은 spec이 없어 한 문제로는 풀리지 않음. NL→IR (LLM, human-confirmable) +
> IR→JoI (deterministic lowering)로 분해하고 **user-confirmed IR을 spec 역할로** 두면, 문제가
> IR↔JoI behavioral equivalence로 변환됨 — 이건 deterministic verdict path 위의
> transition-obligation coverage로 풀린다.

C1–C5 contribution:
- **C1** Timeline IR — 9-op fixed-grammar executable IR (reactive primitive 1급, LLM 추출 + 결정론적
  렌더 + 시뮬레이터/FSM 도출 가능)
- **C2** NL→IR→JoI 분해 — idiom 선택(semantic) ↔ 코드 syntax(mechanical) 분리. 9개 lowering rule이
  관찰된 idiom set 커버
- **C3** IR-mediated user feedback loop — IR→KR 결정론적 렌더로 사용자 confirm. spec grounding의
  구조적 element
- **C4** Transition-obligation coverage on IR-FSM — 검증 메커니즘. L1/L2/L3. LLM-free verdict.
  Position: Model-Based Testing을 NL-derived smart-home DSL lowering에 처음 적용
- **C5** Counterexample-guided self-correction — failed obligation → IR-feature granularity의 retry 신호.
  optional mutation-based 진단 강화는 evaluation-decided

### 4.2 Target venue: SenSys 2027 R1

| 항목 | 값 |
|---|---|
| Abstract | 2026-05-29 (AoE) |
| Full paper | 2026-06-05 (AoE) |
| 분량 | ≤12 pages 본문, refs/appendix 무제한 |
| Format | ACM `acmart.cls` sigconf 2-column 9pt |
| 익명화 | 완전 (위반 시 desk-reject) |

SenSys 합격 패턴 (`sensys.md` §3): system motivation 명료 / 두 자릿수 % 정량 이득 /
재현 가능 벤치마크 부산물 / 실 deployment 또는 high-fidelity sim / 단일 hero abstraction /
case study + ablation 풍부 + failure 정직 / token cost & latency 표 / GPT-4 비교.

**가까운 5편** (`sensys.md` §2): GPIoT (SenSys'25) · TaskSense · Sensor-In-the-Loop ·
ADLGen (SenSys'26) · EdgeTune. 어느 것도 본 연구의 5가지 novelty를 안 풀었음
(reactive DSL idiom 인코딩 정식화 / verification anchor 부재 / user-confirmed IR-as-spec /
IR-FSM MBT 첫 적용 / IR-feature 라벨 self-correction).

**확률 시나리오** (`sensys.md` §13, §22.9):
- 현재(verification + IR + sim only, hub 데이터 없음): 25–35%
- + 실 hub trace evaluation: 35–45%
- + Sensor-noise-aware obligation (옵션 3 = method에 박음): 40–50%
- + VCSC (M1 TRO + M2 minimal CE + M6 budget): 45–55%

대표적인 reviewer pushback 5종 — "primitive 풍부한 플랫폼 쓰면 되잖아?" — 에 대한
5중 방어가 `sensys.md` §11에 정리됨. 핵심: JoI는 산업 배포된 주어진 DSL · primitive 풍부한
플랫폼(HA)도 helper/template idiom으로 long-tail을 떠넘김 · idiom 인코딩은 reactive DSL
전반의 구조적 문제 · JoI는 selector/service 추상화를 얻은 의도된 trade-off.

### 4.3 평가 계획 (E1/E2/E3)

- **E1 — Generation accuracy (RQ1)**: A (9B direct few-shot) / B (9B CoT) / C (Ours NL→IR→JoI) /
  D (GPT-4 direct). `category_v2` 별 stratify. 가설: A/B/C 가 C01–C03(trivial)에서 비등, C가
  C07 이후 (reactive)에서 dominant.
- **E2 — Verification adequacy (RQ2): mutation testing.** GT JoI에 mutation 주입 (semantics-preserving
  50 + semantics-changing 50), 검출률 비교 (BLEU / AST diff / LLM-as-judge / JoI→NL 재번역 sim /
  Ours IR-guided trace). 목표: semantics-changing ≥95%, FP ≤5%.
- **E3 — End-to-end pipeline (RQ3)**: 전체 NL→IR→JoI + simulator-driven self-correction.
  trace-match, retry count 분포, terminal failure 케이스.

데이터셋은 현재 307 commands; 제출 전 ≥600으로 확장 계획 (C04–C18 가중).

---

## 5. 현재 진행 상황 (2026-05-19)

### 5.1 위치

**완료된 부분**:
- **Stage 0/1/1.5/2/3/4 모두 활성** — `test.py target` 실행하면 NL → IR → JoI까지 full 파이프라인
- Timeline IR 추출 + 9-op 스키마 검증 (cycle.period **REQUIRED**) + 결정론적 KR rendering
- ID-aliasing (d1,d2,...) → KV-cache 친화적 follow-up + Python deterministic selector builder
- IR/JoI 시뮬레이터 phase-1 (11/11 E2E)
- 3개 stage-specific judge agents (`upstream-judge`, `structure-judge`, `lowering-judge`) — `~/.claude/agents/`
- **Lowering 신뢰도 high**: C01~C18 모두 sweep, 남은 fail은 대부분 upstream (cron 환각 / IR alternation shape / multi-cron / clock.time 2400 등)

**2026-05-19 세션 핵심 변경** (commit `172c6bd`):
- **Lowering bucket 5→2 consolidation**: classify_ir이 `noncycle`/`cycle`만 반환. 새 `files/joi_cycle.md`가 switchboard 프롬프트로 D-3/D-4/D-5/D-6/D-9/B-2 sub-idiom을 IR 시그널 직접 읽어 dispatch. 옛 4개 bucket prompts(joi_simple_periodic/edge_cycle/state_cycle/break_cycle)는 디스크에 잔존 (rollback용), 코드에서 미참조.
- **`cycle.period` REQUIRED** (IR convention 변경): `timeline_ir.py::validate_ir`가 cycle.period 누락 시 reject. extractor 프롬프트 + 모든 examples + Lexical Cues 표 일괄 마이그레이션. Defaults: D-3 → `"100 MSEC"`; D-5 alternation → 각 inter-call delay 값; 그 외 → NL `every N <unit>`. 옛 "trailing rest-delay = cadence" 패턴 (LLM이 `N - K` 산수 헷갈리는 원인) 폐기.
- **Python deterministic post-process layer 강화** (`run_local.py` + `run_local_ir.py`):
  - `_strip_selector_extra_parens` — LLM 환각 `(any(#X)).Attr` → `any(#X).Attr` (extra wrap 제거). `_apply_service_prefix` 앞에서 호출.
  - `_post_process_joi_any_quantifiers` greedy regex 버그 fix (이전엔 두 번째 any 절을 value capture에 삼킴). 이제 quoted-string-or-bare-token만 매칭. multi-tag any(#A #B) 지원. **LLM이 더 이상 any→all+==\| 변환 부담 없음** — precision의 `any(#X)`를 그대로 emit, post-process가 canonicalize.
  - **wrapper.period override** — IR의 `cycle.period` 문자열을 `parse_duration_to_ms`로 변환해 강제 override. D-3은 항상 100. LLM unit-arithmetic 환각 ("30 SEC" → 1800000) 완전 차단.
- **`joi_common.md` selector rule 강화**: extra paren wrap 금지 + multi-tag bare trap 경고 + compound and/or operand 룰 + ms 변환 cheat-sheet inline + any→all 부담 제거.
- **`joi_edge_cycle.md` Ex1/Ex2 multi-tag bare 예제로 마이그레이션** — Ex3에 multi-step Y (call+delay+call) 예제 추가.
- **`timeline_ir_extractor.md`**: 한글 fragments 7곳 영어로 번역. D7b 재작성. Examples 5/6/7/9/11/12 + Lexical Cues + D3/D5/D6/D7 inline cycle shapes 모두 cycle.period 컨벤션으로.
- **Dataset fix**: C08 #15 IlluminanceSensor → LightSensor (카탈로그에 없는 서비스였음).
- 인계받은 prior session 변경: mapping_device_match pre-anchor critique 포맷, pre_analysis caveman free-form, service_plan refinements.

### 5.2 device_rules 리팩토링 (진행중) — service catalog 유지보수 비용 절감

**문제**: service_list_ver2.0.4.json이 향후 변경(서비스 추가/이름 변경/enum 멤버 변동)될 때마다,
공용 프롬프트(`service_plan.md`, `arg_resolve.md`, `enum_resolve.md`) 안에 박힌 device-specific
예시·룰이 같이 바뀌어야 했음. 거대한 monolithic 프롬프트는 변경 영향 범위가 커서 유지보수
어려움.

**해결**: device 별로 작은 룰 파일 (`files/devices/device_rules_<cat>.md`) 두고, 안에 stage 별
섹션 마커(`# @arg_resolve`, `# @enum_resolve`)로 구획. 공용 프롬프트는 짧고 일반적으로
유지하고, stage별 dispatcher가 필요한 device의 필요한 섹션만 동적으로 합쳐서 주입:

- `service_plan` 스테이지: 연결된 디바이스의 default 섹션을 모두 concat
- `arg_resolve` 스테이지: 선택된 action service들의 카테고리에 대해 `# @arg_resolve` 섹션만
- `enum_resolve` 스테이지: ENUM-value 서비스들의 카테고리에 대해 `# @enum_resolve` 섹션만

→ service 카탈로그가 바뀌면 해당 device의 룰 파일만 손보면 됨. 공용 프롬프트는 안 건드림.

**진행 상태**: 49개 device_rules 파일 작성 완료 (`files/devices/` 디렉토리, 모든 카테고리 커버).
ENUM/ARG section 마커 적용 중. 새 디바이스가 카탈로그에 추가될 때마다 룰 파일도 같이 추가.

### 5.3 즉시 다음 할 일

(우선순위 순; 2026-05-19 세션 종료 시점 기준)

**Lowering 측 잔존** (stochastic, fully fix하려면 추가 작업):
- **C08 #36 second-call args 환각** — `IR: [call(MoveToBrightness 100,0), delay, call(MoveToBrightness 0,0)]`를 LLM이 두 번째 call에 첫 args (100,0)를 복사. service_plan이 두 번째로 Switch.Off를 emit하면 회피되지만 idempotent 아님. 완전 fix는 per-call args injection post-process로 가능 (현재 미구현).
- **D-4 multi-step Y phase 1 branch에 cadence delay 잔류** — cycle.period가 정상 emit되는 한 거의 안 발생. extractor 부적합 출력 시에만 트리거.

**Upstream 잔존** (lowering 외 영역, 별도 트랙):
- Cron 환각 (minute slot, `*/30` 누락)
- IR alternation shape (C13 #3/#6 — 2 calls back-to-back, delay 없음)
- `clock.time >= 2400` off-by-one (C15 #5, C18 #3)
- Multi-cron 분리 안 됨 (C15 #15, C16 #5, C18 #6 — 현재 reject)
- precision builder가 distinct categories를 collapse (C16 #6)
- IR cond tautology (C16 #9 — `X==open or X==open`)
- pre_analysis runaway (capability example list를 yes/no checklist로 loop, max_tokens hit). 다운스트림에 영향 X but token waste.

**다음 우선순위 (사용자 의도: 시뮬레이터 phase-2 시작)**:
1. **시뮬레이터 phase-2** (`paper/simulators/TODO.md`) — trace equivalence 자동화 인프라:
   - **C0** period-aware trigger placement (큰 period D-4 tick aliasing 해결, 필수)
   - **C2** multi-trigger cycles (re-arming 검증)
   - **A1+A2** any/all multi-device world model (C08+ 카테고리 unblock)
   - Lowering 신뢰도가 이제 높아져서 trace divergence가 의미있는 신호 (대부분 upstream IR 또는 simulator 모델 갭).
2. **Trace equivalence judge 자동화** — paper C4 (L1/L2/L3) verdict 메커니즘. 수동 prompt 채점 → 자동 회귀.
3. **IR-FSM transition 지점 수 N 측정** (교수님 요청, `whisoo.md` §5) — C01..C18 IR에 대해 N이 polynomial로 자라는지 empirical 측정. `paper_summary.md` §6.6 affordability argument 근거.
4. **Phase A3 precision-stage IR annotation** — IR이 `target_set`을 들고 있지 않아서 selector 버그가 trace에 안 잡힘. `whisoo.md` §5의 8-step plan 참고 (~1.5-2주 추정).
5. **Judge agent maintenance log 업데이트** — 2026-05-19 sweep에서 발견된 패턴들 (extra paren / any 부분 적용 / period 산수 등 — 이미 fix됨)을 각 judge agent의 Maintenance Log 섹션에 등록.

### 5.4 자주 쓰는 명령

```bash
# IR + precision 단계만 보기 (현재 default)
cd ~/joi && python3 test.py target

# pre_analysis만 빠르게 보기
cd ~/joi && python3 test.py pre

# 단일 custom command (CUSTOM_COMMAND 직접 수정)
cd ~/joi && python3 test.py custom

# 시뮬레이터 E2E
cd ~/joi && python3 -m paper.simulators.test_e2e -v

# 시뮬레이터로 dataset row 평가
cd ~/joi && python3 -m paper.simulators.eval_harness

# 로그 위치
ls -lt /tmp/joi_target_*.log | head
```

### 5.5 외부 환경 (참고용)

`PROJECT_STRUCTURE.md` 참조. 핵심 IP 와 포트:

| 컴포넌트 | 주소 |
|---|---|
| vLLM (우리) | `192.168.0.250:8002` (Qwen3.5-9B-AWQ) |
| app.py (우리) | `192.168.0.250:49999` (JoI 코드 생성 API) |
| joi-agent (우리) | `192.168.0.250:8012` (채팅 에이전트) |
| MCP 서버 (이삭) | `192.168.0.163:48012` |
| Hub Controller (이삭) | `192.168.0.163:48005` |
| IoT Core (이삭) | `192.168.0.163:48001` |

운영 서버(이삭 인프라)는 직접 건드리지 않음. 우리 영역: `vllm`, `app.py`, `joi-agent local 브랜치`.

---

## 부록 A. 파일 맵

```
/home/gnltnwjstk/joi/
├── test.py                          ← entry (target / pre / custom)
├── run_local.py                     ← LLM streaming util, post-processing
├── app.py                           ← FastAPI 49999 (JoI 코드 생성 API)
├── loader.py                        ← PROMPTS + SERVICE_DATA + device_rules section split
├── config.py                        ← vLLM client
├── files/                           ← prompt files (모든 .md가 PROMPTS dict에 로드됨)
│   ├── translation.md
│   ├── pre_analysis.md
│   ├── service_plan.md
│   ├── enum_cond_check.md
│   ├── enum_resolve.md
│   ├── arg_resolve.md
│   ├── mapping_device_match.md
│   ├── command_merge.md
│   ├── joi_common.md                ← lowering 공통 (always loaded)
│   ├── joi_noncycle.md              ← bucket=noncycle 시 사용
│   ├── joi_cycle.md                 ← bucket=cycle 시 사용 (switchboard로 D-3~D-9 dispatch, 2026-05-19~)
│   ├── joi_simple_periodic.md       ← (legacy, 미참조 — 디스크 잔존)
│   ├── joi_edge_cycle.md            ← (legacy, 미참조)
│   ├── joi_state_cycle.md           ← (legacy, 미참조)
│   ├── joi_break_cycle.md           ← (legacy, 미참조)
│   ├── service_list_ver2.0.4.json   ← catalog
│   └── devices/
│       ├── device_rules_switch.md
│       ├── device_rules_light.md
│       └── ... (49개)
├── paper/
│   ├── run_local_ir.py              ← ★ IR-based pipeline (이 문서의 §2가 설명하는 것)
│   ├── timeline_ir.py               ← IR extract + schema + KR rendering
│   ├── timeline_ir_extractor.md     ← extractor 프롬프트
│   ├── joi_from_ir.md               ← legacy lowering 프롬프트 (현재 미사용; 버킷 prompts가 대체)
│   ├── ir_code_example.md           ← 캐논 예시 (legacy syntax 일부)
│   ├── paper_summary.md             ← ★ 논문 plan canonical
│   ├── sensys.md                    ← ★ SenSys 전략, prior art, rebuttal
│   ├── whisoo.md                    ← 의사결정 일지
│   ├── HANDOFF.md                   ← 이 문서
│   └── simulators/
│       ├── README.md                ← sim 패키지 사용법
│       ├── TODO.md                  ← sim 백로그
│       ├── ir_simulator.py
│       ├── joi_simulator.py
│       ├── joi_parser.py
│       ├── event_synth.py
│       ├── comparator.py
│       ├── catalog.py
│       ├── world.py
│       ├── traces.py
│       ├── scenario.py
│       ├── expr.py
│       ├── eval_harness.py
│       └── test_e2e.py
├── dataset_migration/
│   └── local_dataset2.csv           ← 307 rows, C01–C18
├── parser/                          ← JoI validator
└── tools.py                         ← MCP 툴 호출 + AGENT_TOOLS 스키마
```

## 부록 B. 메모리 인덱스 참고

본 프로젝트는 `/home/gnltnwjstk/.claude/projects/-home-gnltnwjstk/memory/` 의 persistent memory를
활용한다. `MEMORY.md` 인덱스를 먼저 확인하고, 특히 다음 5개는 거의 필독:
- `project_paper_framework.md` — canonical paper plan (revised 2026-05-06)
- `project_pipeline_state_2026_05_13.md` — 각 stage 현재 I/O contract (post catalog-agnostic refactor)
- `project_pipeline_handoff_2026_05_12.md` — C01~C09 PASS/FAIL 카운트, 남은 이슈
- `project_precision_pipeline_2026_05_12.md` — 2-step precision (LLM device-match + Python selector) 리팩토링
- `project_joi_dataset_categories.md` — C01–C18 분류표 (다만 카운트 일부는 현재 CSV와 1 row 차이)

문서가 stale일 수 있으므로 항상 현재 코드/CSV로 cross-check.
