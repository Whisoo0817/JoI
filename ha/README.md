# HA platform profile (W4, 2026-08-14)

Timeline IR의 두 번째 lowering 타깃 — Home Assistant(HA) 자동화.
캐논은 percom.md §4·§9.13. IR·탐색기 본체는 무변경이고, HA 종속물은
전부 이 디렉토리(= platform profile)에 있다.

## 구성

| 파일 | 역할 |
|---|---|
| `skill_map.json` | 스킬 55종 → HA domain / 서비스 이름 / 속성 entity 종별 |
| `lower_ref.py` | 참조 lowering: IR + 바인딩 표(binding_gt) + 인벤토리 → HA YAML (규칙 기반, LLM 불사용) |
| `ha_step.py` | 제한 문법 파서 + HA 한-걸음 실행기(HaRunner). 탐색기 실행기 계약(vars_info/axes/check_finite/step)을 충족 |
| `gt/*.yaml` | 388행 참조 lowering 산출물 (행 키 = C##_###) |

## 산출물 2종 (행 종류 → HA 아티팩트)

- **원샷 행(246) → script**: 한 번 실행되는 sequence.
  레벨 wait → `wait_template`(이미 참이면 즉시 통과 = IR edge=none),
  엣지 wait → `wait_for_trigger`(전이만 = IR rising),
  타임아웃 wait → `timeout:` + `continue_on_timeout: true` 명시 + `wait.completed`/`wait.trigger` 분기.
- **cycle(111)·cron(31) 행 → automation**: 흡수 규칙 —
  cycle[wait-엣지 …] → state/numeric_state **trigger**(HA에선 엣지가 primitive),
  cycle[if …] → `time_pattern`(/period) trigger + condition,
  cron 앵커 → `time` trigger(+weekday/날짜 가드; 게이트가 IR 쪽 cron과 표기
  무시 정규화 대조 후 공통 소거). `mode: single` 명시 고정.
- **run 간 기억**(cycle의 count/until)은 helper 엔티티(counter / input_boolean 래치)로.
  이름 카운터(회차 번호를 조건이 읽는 행)는 counter + `states()|int`,
  "이름 카운터 + until n ≥ k"는 그냥 k회 반복(repeat count)으로 접는다.
- **script 안 반복의 주기 맞춤**: 반복 끝을 `delay`가 아니라
  `wait_for_trigger: [time_pattern /P]`(벽시계 정렬 대기)로 닫는다 —
  delay 사슬은 몸통 지연이 다음 회차로 번지지만(표류), 정렬 대기는 회차
  시작을 주기 눈금에 고정한다(IR cycle의 회차 앵커와 동일, 위상 추상화).
- **시계 조건**: `clock.time ≥ HHMM`·`Weekday ==`는 템플릿이 아니라 HA
  고유 time condition(after/before/weekday, 부정은 `not` 감싸기)으로.

## 제한 문법 조각 (fragment) — 이 밖은 전부 REFUSED

HA 2025.8 문법(복수형 `triggers:/conditions:/actions:`) 기준.

| 구획 | 수용 | 거부(REFUSED) |
|---|---|---|
| trigger | state(to/from/for), numeric_state(above/below/for), time, time_pattern, template(제한식) | sun/calendar/webhook/mqtt/event 등 전부, trigger id 분기 |
| condition | state, numeric_state, template(제한식), time(after/before/weekday), and/or/not | zone/sun 등 |
| action | 서비스 호출(target+data), delay, wait_template / wait_for_trigger(+timeout — `continue_on_timeout` 명시 필수; 반복 끝 주기 맞춤은 `wait_for_trigger[time_pattern]`), if/then/else, repeat(count/while/until), stop, variables | parallel, scene, script 호출, event 발화, choose(v1은 if/else로) |
| 템플릿 | `states()`, `is_state()`, 리터럴, 비교 6종(==/!=/>/>=/</<=), and/or/not, +/-, 변수 참조, `float`/`int` 필터 | 그 외 전부(루프·매크로·now() 산술 …) |
| mode | `single`만 | restart/queued/parallel (겹침 의미론 모델링은 보류 — §9.13 todo) |
| helper | counter, input_boolean | timer, input_number 등 |

예외 하나: 달력 가드 한정으로 `{{ now().day == D and now().month == M }}`
형태만 허용 — cron 앵커의 일부로 인식되어 게이트의 앵커 소거 대상이며,
조각 안 일반 템플릿에서는 now() 금지 유지.

시간 해상도는 1초(게이트 그리드 바닥) — IR의 밀리초 주기는 "매 tick"으로
양자화된다. wait 결과 변수(`wait.completed`/`wait.trigger`)는 정해진 분기
꼴(타임아웃 분기·지속 관용구)에서만 수용, 그 외 위치는 REFUSED.
trigger의 엣지 래치 초기값은 False("시작 시 이미 참이면 첫 평가에 발화") —
HA 재시작 때 엔티티가 unknown→실제값 전이를 겪어 trigger가 발화하는
실동작과 같다(ha_step.py 머리말).

## 명명 규칙 (기기 ↔ entity)

- 기기 entity: `<domain>.<기기id의 snake_case>` — 예: `Living_Light` → `light.living_light`
- 속성 entity: `<sensor|binary_sensor>.<기기id snake>_<속성 snake>` — 예: `sensor.living_airsensor_temperature`
- BOOL 값은 binary_sensor `on`/`off`로 표기 (true↔on). 역변환은 행별
  인벤토리로 만든 대응표로 하므로 표기 왜곡 없음.
- 다기기 호출은 `target.entity_id` 리스트 — 실행기가 기기별 액션으로
  언롤(JoI `all()` 언롤과 같은 관찰 모델).

## 왜 참조 lowering인가 (GT 순환성 방어)

E4에서 GT의 역할은 ① "같은 IR, 두 번째 타깃, 게이트 EQUIV" 실증
② fault 주입의 원본. 참조 lowering(YAML 생성)과 ha_step(의미론 실행)은
독립 구현·코드 비공유이므로 EQUIV 388/388은 전제가 아니라 측정 —
어긋나면 어느 한쪽 결함이 드러난다(그 자체가 TCB 검사).
