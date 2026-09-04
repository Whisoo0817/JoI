# explorer/ — 이산화 전수 탐색기 (신규, 자족 패키지)

## 현황 요약 (2026-08-01 마감 시점)

**완성**: 단일 시나리오 파이프라인 전체 — 파싱 → 순수 step → 단편 판정 →
그라운딩(인스턴스 바인딩) → 전수 탐색(BFS+zone+점프) → 동치 곱 →
의무 5종 → cron → 콤보 dedup → E1 표. **코퍼스 10/10** 그래프 닫힘·자기동치
EQUIV·미해명 술어 0. 고장 주입 **7클래스 전부 검출**(경계·시간상수·
엣지→레벨·재알림·재배선·점유겹침·quantifier k=1/k=2). 진짜 발견=재실감지
SEED-DEP 1건. 임의 신규 시나리오도 JoI+period+인벤토리만 있으면 즉시 판정
(온도-조명 예시로 확인). `python -m explorer.e1` 한 번(114s)이 논문 표 생성.

**보류(TODO)**: P4 복합 곱(composite.py 미검증)·전 구역 충돌 깔때기.
**대기**: 실기기 목록·GV 스토어·센서 도메인/단위 (유저 제공).
**다음**: 집필 (ideas.md §0·§11 + runs/e1.md + 본 README의 실측·교훈).

핵심 탐색기는 자족 패키지다. `expr.py`, `joi_parser.py`는 SenSys 시뮬레이터에서
분리된 계보를 유지한다. 단, E3 하네스만 새 후보 생성을 위해 `lowering/`을
호출한다. 과거 시뮬레이터는 `sensys/`에 동결했고, `etc/smt/`는 독립 교차
검산용이라 코드 공유 금지.

| 파일 | 역할 |
|---|---|
| `expr.py` | 표현식 AST + 평가기 (sim/ 복사본) |
| `joi_parser.py` | JoI 스크립트 → 문장 AST (sim/ 복사본 + `loop` 구문·`OP|` 보존) |
| `interp.py` | 순수 1-tick step 함수 (+OpaqueToken, AbortTickStmt) |
| `demo_tick.py` | tick 단위 실행 데모 (`python -m explorer.demo_tick`) |
| `predicates.py` | 변수 3분류(경로-지역 스캔) + 술어 단편 판정 |
| `explore.py` | BFS+메모, zone/포화/달력구간 정규화, 증인 게이트 점프, 축 도출 |
| `product.py` | base×변형 lockstep 곱 = 동치 판정 + 반례 경로 |
| `ground.py` | 셀렉터→인벤토리 바인딩, ForEach/`OP|`/all 언롤, 부유 호명 |
| `obligations.py` | VACUITY·SEED-DEP·OVERLAP·COUNTER-CARRY (그래프만 읽음) |
| `cron.py` | cron→60s tick+달력 가드, 최상위 break→AbortTick |
| `feasibility.py` | 콤보 서명 dedup (지우는 자리=결정론 락) |
| `project.py` | 엣지 몫 — 결정 경로 표 / 액션 역상(필수 조건) 사영 |
| `replay.py` | 배포 로그 재생 → 행동별 생애 상태(ENGAGED/WINDOW/UNMET/NONCONFORM) |
| `e1.py` | E1 전수 표 하네스 → `runs/e1.md` |
| `composite.py` | (보류·미검증) P4 공유-GV 곱 초안 |
| `exact_tick.py` | 명시적 유한 입력 모델의 bounded tick 완전열거 기준선 |
| `ab_eval.py` | 동결 manifest 기반 A/B·완료율·전이 수 집계기 |
| `domain_manifest.py` | 결과를 보기 전 입력 도메인·소스 해시·horizon 직렬화 |
| `differential_sweep.py` | 기존 388개 후보를 이용한 개발 전용 차등 sweep |

## 신규 A/B 평가 경로 (2026-09-04)

`exact_tick.py`는 상태 정규화, 시간 점프, 입력 dedup을 사용하지 않고 명시된
입력 도메인의 모든 tick 시퀀스를 유한 horizon까지 실행한다. `product.py`의
평가 전용 `max_ticks` 모드는 같은 horizon에서 구체 상태와 depth를 보존하며,
Explorer의 입력 경계 이산화만 적용한다. 따라서 두 결과의 차이는 개발 중
false accept/false reject 후보로 취급할 수 있다.

현재 결과와 제한은
`skill_result/05_experiment_plan/ab-evaluation-protocol.md`에 누적한다. 기존
388개 후보를 이용한 sweep은 outcome-visible development evidence이며 최종
abstract 수치가 아니다. 실행기는 다음과 같다.

```bash
python3 -m explorer.tests.test_exact_tick
python3 -m explorer.ab_eval \
  --manifest explorer/eval/ab_development_manifest.json \
  --output-dir skill_result/05_experiment_plan/results/E3/development-pilot
python3 -m explorer.differential_sweep \
  --candidates explorer/candidates/qwen3_5-9b-awq-4bit \
  --output-dir skill_result/05_experiment_plan/results/E3/differential-dev-stress-h8-all \
  --horizon 8 --stress-domain

# 결과를 실행 중 재도출하지 않는 manifest 경로
python3 -m explorer.domain_manifest \
  --candidates explorer/candidates/qwen3_5-9b-awq-4bit \
  --output skill_result/05_experiment_plan/results/E3/domain-manifest-dev-h8.json \
  --horizon 8
python3 -m explorer.differential_sweep \
  --candidates explorer/candidates/qwen3_5-9b-awq-4bit \
  --domain-manifest skill_result/05_experiment_plan/results/E3/domain-manifest-dev-h8.json \
  --output-dir skill_result/05_experiment_plan/results/E3/differential-dev-manifest-h8-all
```

## 게이트 측정 결과 (2026-07-31, 코퍼스 10 시나리오)

- 술어 127건: 즉시 단편 내 109 (85.8%) + GROUND 18 (ForEach 평균/최대 —
  그라운딩 후 선형=단편 ③) + 미해명 0
- 상태 변수: 시나리오당 0~4개 (bool 래치 최대 4 + 타임스탬프 레지스터 1~3)
- `clock.timestamp`는 초 단위 (cooldown 상수들이 초)

## JoI 문법 사실 (2026-07-31 유저 확인)

- `any(...)`는 코퍼스 미사용(0건). exists는 `all(#X).attr OP| c` 형태
  (`==|`, `>|` 등 26건): 태그 집합의 **하나라도** 만족하면 true.
  파서는 `|`를 AST에 보존; 그라운딩이 인스턴스 OR로 언롤; 언롤 전 실행은
  단일 인스턴스 세계로 평가(1대 환경에선 정확).
- 무접미 OP over `all()` = 전 인스턴스 만족(AND 언롤).
- `for (v : all(#X).member) {}` = 태그 집합 기기 **값 순회**(상태 조회,
  그라운딩이 k회 언롤). `loop (cond) {}` = tick 내 while. 서로 다른 구문.
- **무별칭 가정(락)**: 서로 다른 셀렉터는 서로 다른 기기 — 정렬한 태그
  집합이 곧 기기 정체성. 월드 키 = `a+livingroom.switch` 꼴(단일 태그는
  `door.contact` 단축 유지). 가정이 깨져도 과근사 방향이라 EQUIV는 유효,
  DIVERGE만 실현성 재검 대상(비대칭 soundness와 동일 원리).

## explore.py 실측 (2026-07-31, 주기형 8/8 그래프 닫힘)

| 시나리오 | 상태 | 에지 | step | 시간 |
|---|---|---|---|---|
| 문-불 데모 | 168 | 1,008 | 1,178 | 0.05s |
| 보안모드 자동제어 | 188 | 4,512 | 4,708 | 0.39s |
| 보안모드 침입 감지 | 20 | 168 | 192 | 0.01s (이메일 체인 도달) |
| 재실 감지/절전/Section1 | 2~3 | ~8k | ~11k | <0.7s |
| 화재 감지 | 4 | 24 | 32 | 0.00s |

- ForEach 2건(공기질·온습도)=그라운딩 필요로 명시 거부, cron 2건=드라이버 TODO
- t0=28일(월요일 유지): `reg := 0` 초기 cooldown이 "방금 발화"로 오독되는 것 방지
- mirror GV(읽고-쓰는 GV)는 초기값 {미시드, False, True} 열거 — **미시드면 재실
  집계가 영원히 안 쓰는 시드 고장 실물을 idx5에서 발견**(6 고장클래스 실증)
- 외부 GV 입력은 gv 스토어로 주입(월드 아님), 자기 쓰기 GV만 상태 키에 포함

## product.py 실측 (2026-07-31)

- **자기동치 6/6 EQUIV** (주기형 전부, 최대 0.75s/188상태 곱; ForEach 2건 제외)
- **고장 주입 4/4 DIVERGE + 반례 경로**:
  cooldown 30분→3분(240s dwell에서 변형만 재알림) / 엣지→레벨(버튼 유지 시
  변형만 재발화) / **grace `>`→`>=`(dwell 정확히 120s 경계 tick에서 검출 —
  zone successor 정밀도 실증)** / cooldown 600→60(61s 재알림)
- 교훈: mutation no-op 가드 필수(치환 실패 시 base×base=EQUIV로 조용히 오독)
- 반례 email 인자에 `None`=capture 반환값 — 불투명 토큰 처리 예정

## ground.py 실측 (2026-07-31)

- adapt/inventory `base_office()` 14대 소비 (`from_adapt`; 라이브러리는 순수
  데이터만 받음, adapt import는 데모 main만). 매칭=태그∀∈{type,space,itag},
  offline 제외(P2 접점). 셀렉터→인스턴스 언롤: ForEach·`all()` 액션·`OP|`(OR)·
  무접미 all(AND). 0매칭=**부유(floating)로 호명**(예: #SmokeDetector,
  #Switch#Office — base_office에 없는 타입들). 단수 셀렉터 다중 매칭=바인딩
  선택 요구 에러(기본값 발명 금지).
- **주기형 8/8 전부 탐색 가능**: 공기질 2상태/93k에지(콤보 폭발=feasibility
  동기)·온습도 14상태/288에지 편입 성공, 나머지 기존과 일치.
- **★quantifier 고장 × 바인딩 의존 데모**: 화재 `presence ==| true`(∃)를
  특정 1대 `== true`로 바꾼 변형 — **k=1 EQUIV / k=2 DIVERGE**. 반례:
  ps1 부재·ps2 재실·연기 → base는 대피 방송, 변형은 방송 누락(안전 결함).
  "동치는 코드가 아니라 바인딩의 성질"의 실행 가능한 실증. 액션에 인스턴스
  타깃(speaker#sp1) 표시 = 재배포 인증 수준 출력.

## 축 조이기 + obligations.py 실측 (2026-07-31 심야)

- **축 조이기**: 칸 후보를 (op,상수) 진리벡터로 병합 → 공기질 93,312→3,240
  에지(29×), Section1 15× 축소. 판정·상태수 불변(sound).
- **obligations.py** (그래프만 읽는 의무층): 정적 액션 목록 vs 발화 집합.
  - VACUITY: 어떤 입력·시드·무한시간에도 안 발화하는 액션 호명
  - SEED-DEP: 미시드 출발에서 도달 불가 → 인증서의 환경 전제조건
  - 최종 결과: **8 시나리오에서 진짜 발견 1건만 남음** — 재실감지
    `occupancy` 사전 시드 전제 (idx5 시드 고장의 자동 호명)
- 의무층이 잡아준 **탐색기 버그 2개 수정**(가짜 VACUOUS 5건 → 0건):
  1. **stutter 증인**: 점프 허용을 도달 입력(held)이 아니라 "조용히 유지
     가능한 입력의 존재"로 판정. held가 매 tick 발화 입력이면 점프가 막히고
     1-tick 보행은 재방문 즉시 닫혀 30분 임계 영역이 영원히 미탐색이었음
     (절전 phase_2 가짜 VACUOUS 3건의 원인)
  2. **경계 region**: (bisect_left, bisect_right) 쌍 — delta가 임계와 정확히
     같은 tick은 자기만의 region (`>`는 거짓, `>=`는 참인 유일 지점)
  3. duration 변수(`elapsed = now - reg` 후 비교)와 상수-wire(`max_humid`
     계절값) 임계 추출 갭 수정 (`_const_options`: wire의 가능한 상수 집합 전개)
- 회귀: 자기동치 6/6 EQUIV, 고장주입 4/4 DIVERGE 유지

## 이슈·버그 로그 (전체, 시간순)

| # | 증상 | 원인 | 처리 |
|---|---|---|---|
| 1 | idx0 파싱 실패 `loop` | v1 파서에 없는 tick 내 while 구문 | `Loop` AST 추가 + 반복 상한 가드 |
| 2 | cooldown 상수(120/600/3600*3)와 ms 불일치 | `clock_timestamp`는 **초** 단위 | clock_state에서 `now_ms//1000` |
| 3 | `forecast(h)` 조회가 액션으로 기록됨 | 호출=액션 단일 가정 | 표현식 위치 호출=조회(무기록), 문장 위치=액션 |
| 4 | 침입감지 1상태·무발화 | GV 축을 world에 주입했으나 인터프리터는 gv dict에서 읽음 | 입력 분리: 센서→world, 외부 GV→gv 스토어(탐색 후 제거) |
| 5 | 화재 cooldown이 첫 30분 막힘+미탐색 | t0=0이라 `reg := 0`이 "방금 발화"로 읽힘 | t0=28일(월요일 유지, 0-초기값=FAR) |
| 6 | 재실감지 setboolean 영원히 안 씀 | GV `occupancy` 미시드면 양쪽 비교 모두 거짓 | **버그 아님=시드 고장 실물**. mirror GV 초기값 {미시드,F,T} 열거 + SEED-DEP 의무로 자동 호명 |
| 7 | 화재 mutation이 EQUIV | 코드가 `1800`이 아닌 `30*60`이라 치환 no-op | mutation no-op assert 가드 (E3 하네스 규칙) |
| 8 | 변수 18개가 state로 오분류(공기질 등) | 분기 안에서 쓰고-읽는 tick 내부 변수를 경로 무시 스캔이 carried 판정 | 경로-지역(safe set 분기 전파) 스캔 → state 0~4개로 수렴 |
| 9 | k=2에서 단수 셀렉터 grounding 에러 | 2대 매칭인데 단수 읽기 | **의도된 동작**: 기본값 발명 금지, 바인딩이 선택(데모는 instance tag로 명시) |
| 10 | 절전 phase_2 가짜 VACUOUS 3건 | **stutter 게이트 버그**: 점프 허용을 도달 입력(held)으로만 검사 → 매 tick 발화 입력이면 점프 금지 + 1-tick 보행은 재방문 즉시 닫힘 → 30분 임계 영역 영구 미탐색 | **stutter 증인**: "조용히 유지 가능한 입력의 존재"로 판정 (∃-양화) |
| 11 | 경계 tick 뭉개짐 | `bisect_right`가 delta=600을 >600 영역으로 분류 (`>`는 거짓인 지점) | (bisect_left, bisect_right) 쌍 region — `>`→`>=` 변형 검출이 이 정밀도에 의존 |
| 12 | 절전 임계(600/1800) 추출 누락 | `elapsed = now - reg` 후 비교하는 duration 변수 미인식 | duration 변수 판정(def에 `-` 존재) → 상수를 ts_thresholds로 |
| 13 | 온습도 hf.off 가짜 VACUOUS | `max_humid`가 계절 분기 wire라 상수 접기 실패 → 습도 축에 상한 경계 없음 | `_const_options`: wire의 가능한 상수 집합 전개(과분할=안전 방향) |
| 14 | 공기질 93k 에지 | 상수당 3 대표값 무차별 생성 | (op,상수) 진리벡터로 칸 병합 → 29× 축소, 판정 불변 |

| 15 | 주간미팅 목요일에 영영 도달 못 함 (VACUOUS 3) | 점프가 "가장 가까운 사건"만 노리는데 그 사건이 키를 안 바꾸면(월 01:00) 방문 완료로 버려져 시간 진행이 죽음 | `next_key_change_ms`: "키가 실제로 바뀌는 가장 가까운 시각"(요일 사다리)을 점프 후보에 추가. 원 사건(:30 마크)도 유지=에지 커버 |
| 16 | 위 수정 후에도 월 11시에서 사다리 절단 | 달력 키를 hour 술어 진리벡터로 둬서 0시와 11시가 동일 키(둘 다 ==9 F·==10 F)로 병합 — 진리값이 같아도 다음 경계까지의 **위상**이 다름 | 달력 키 = 경계 구간(segment) 인덱스 (bounds={h, h+1}) + 요일. timed automata region이 위상을 담는 이유의 달력판 |
| 17 | cron 시나리오의 최상위 `break` | cron 의미론에선 스크립트 종료가 아니라 이번 창 종료 | `AbortTickStmt` 재작성 (loop 안 break는 loop-exit 유지) |
| 18 | `forecast(h)` 파라미터 조회 축 없음 | 인자가 루프 변수라 키를 정적으로 모름 | 루프 범위 추론(`h=1; loop(h<=6); h=h+1` 패턴) → `forecast(0..6)` 키별 enum 축. 미해석 인자는 param_reads로 호명 |
| 21 | 주기 토글 변형(`last_toggle = now`를 가드 밖으로)에서 탐색기가 **일어날 수 없는 발화**를 보고(off 4건). 구체 tick 2000회 실행은 발화 1회뿐 | **점프 규칙 건전성 결함**: stutter 판정이 정규화 키만 비교하는데, 타임스탬프 칸은 `now - reg` **상대값**이라 매 tick `reg = now`로 갱신되는 레지스터는 delta가 0으로 고정되어 정지해 보임. 점프는 gap 이후 tick을 **점프 전 레지스터 값**으로 1회 재생하므로 실제로는 존재하지 않는 임계 초과를 만들어냄 | `_regs_frozen`: stutter 후보가 키·무발화 조건을 통과해도 carried 타임스탬프 레지스터의 **절대값이 그대로일 때만** 점프 허용. 아니면 점프 억제 + `notes`에 호명(무언의 축소 금지). 억제 후 변형은 VACUOUS off로 정정=구체 실행과 일치. 코퍼스 회귀 없음(상태수·E1 표 전부 불변; 노트 발생 2건은 "재실 유지 중 last_present_ts 추적"이라 억제가 정답이고 present=false 입력이 점프 증인을 계속 제공) |

＃21은 이 로그에서 **유일한 과탐색(over-exploration) 결함**이다. 앞의
under-exploration 오류들은 vacuity가 적발했지만, 과탐색은 반대로 vacuity를
지워버려(없는 발화를 만들어 죽은 액션을 살려놓음) 검사층이 침묵한다.
적발 수단은 자기동치가 아니라 **구체 실행 대조**(1-tick 씩 빠짐없이 돌린
결과와 그래프의 발화 집합 비교)였다. 교훈: 추상화가 상대값(now-기준)을
쓰는 순간 "정지"의 정의가 두 개(추상 정지/구체 정지)로 갈리며, 시간 점프는
**구체 정지**를 요구한다. 회귀 가드로 구체 실행 대조를 상설화할 것.

공통 패턴: 10~13·15·16은 전부 "**탐색이 덜 도는**"(under-exploration) 방향의
조용한 오류였고, 전부 의무층 vacuity 검사("코드에 있는 액션이 그래프에 없다")가
적발했다. 검사 층이 엔진을 검증하는 구조가 자체 개발에서 먼저 작동한 사례.
반대 방향(과탐색)의 오류는 가짜 DIVERGE로 나타나므로 자기동치 6/6 EQUIV가
그쪽의 회귀 가드다. 두 방향 모두 상시 가드가 있는 셈.

## cron.py 실측 (2026-07-31 심야)

- cron→tick 매핑: 60s 그리드 + 달력 가드 래핑(`* * * * 4` → weekday==thursday
  if), `:=`는 최상위 유지, 최상위 break→AbortTickStmt. dom/month는 * 만 지원.
- **강수예보**: forecast(0..6) 7키 × 5셀 enum 축(루프 범위 추론) → 4상태,
  468,750에지, 닫힘 23초, 전 액션 도달 (콤보 축소는 feasibility 남은 몫)
- **주간미팅**: 28상태(7요일×4구간), 닫힘 <0.1s, 목 9:30·10:00 알림 도달
- **이로써 코퍼스 10/10 전부 탐색+의무 판정 가능** (주기형 8 + cron 2)

## feasibility.py 실측 (2026-08-01)

- **콤보 서명 dedup**: 조합을 넣기 전에 (①모든 조건식의 최대 순수 부분트리
  진리값 ②상태/액션 인자로 값이 흘러가는 키의 원시값)으로 서명을 만들어
  같은 서명은 대표 1개만. 지우는 쪽은 전부 결정론(LLM 금지 락 준수);
  불확실하면 항상 "유지"로 강등.
- 루프 파라미터 조회(`fc=forecast(h)`)는 조건식을 h∈1..6마다 평가해
  wet/dry 패턴이 서명에 편입 — **강수 468,750→768 에지(610×), 24s→11s**.
  Section1 곱 192→24, 침입 곱 4→2. 판정·상태수·반례 전부 불변.
- 이슈 ＃19: `{"==": a==b, "<": a<b}[op]` dict 리터럴이 전 항목을 즉시
  평가해 `1 < 'rain'` TypeError → 전 조건 Impure 오판(dedup 무효화).
  if-체인으로 교체. 교훈: eager evaluation이 조용히 dedup만 죽였고 판정은
  안 건드림(불확실=유지 설계 덕) — 실패가 안전 방향으로 떨어지는 것 확인.
- 남은 것: k≥2 환경의 결합 칸 극값 대표(avg 조합의 정확 분할) — 실물
  k≥2 인벤토리 도착 시.

## 의무층 확장 실측 (2026-08-01)

- **불투명 토큰**: 축 없는 조회(capture)는 `⟨capturevideo@cam1⟩` 출처 토큰
  반환 → 액션 인자로 흘러 곱 비교가 자동으로 데이터 출처를 검사.
  **카메라 재배선 변형(P2) DIVERGE 실증**: base 이메일=⟨…@cam1⟩ vs
  변형=⟨…@cam2⟩. 미사용 캡처는 비가시(호명된 한계).
- **OVERLAP**(그래프 위 Dijkstra, dwell 합 < 점유시간): 침입 cooldown
  600→5 변형에서 "capture 10s 점유 중 6s 만에 재발화" 검출, base는 무결.
  duration 출처=DURATION_ARGS 카탈로그 표 (현재 capturevideo=arg0).
- **COUNTER-CARRY**(달력 경계를 비초기값으로 넘는 카운터): 문-불 데모에서
  count=1..3 주말 경계 생존 표면화("통산 3회 vs 주말당 3회 — 의도?").
  코퍼스 8개는 해당 없음(정상).
- 이슈 ＃20: `isinstance(False, int)==True`라 bool 래치가 counter_caps에
  오분류(synced/was_pushed/done 가짜 COUNTER-CARRY + normalize가 True를
  1로 포화) → bool 명시 제외.
- 회귀 전green: 자기동치 6/6·고장주입 4/4·k데모·cron 불변.

## 엣지 사영(project.py) 실측 (2026-08-03)

문제: 엣지 = 상태 × 입력조합 × dwell 이라 **입력 차원의 곱**으로 폭증한다
(온습도 278,516). 엣지 수는 시나리오의 복잡도가 아니다(같은 시나리오의
상태는 17개). 따라서 엣지는 기계용 원재료이고, 사람에게는 **몫**을 준다.

구현: 인터프리터가 tick마다 `IfStmt` 분기 판정을 `(id(stmt), taken)`으로
기록(`StepResult.guards`) → 탐색기가 엣지별로 보관(`Graph.edge_guards`) →
`project.paths()`가 (결정 경로, 액션 집합)으로 엣지를 분할.
**코드 자신의 조건이 열이므로 내포적(intensional)이다**: `temp_avg > max_temp`
같은 결합 가드가 열 하나로 들어와, 축별 값 나열이 실패하던 문제가 사라진다.

| 시나리오 | 상태 | 원시 엣지 | 경로행(발화) | 압축 |
|---|---|---|---|---|
| 온습도 자동 제어 | 17 | 278,516 | 21 (14) | 13,262× |
| 보안모드 자동제어 | 320 | 7,680 | 40 (22) | 192× |
| 재실기반 절전 제어 | 6 | 2,560 | 162 (157) | 16× |

절전의 압축률이 낮은 이유가 중요하다. 폭증 원인이 둘이기 때문이다.
①입력 곱(경로 사영이 제거) ②**그라운딩 언롤**(제거 못 함) — 절전은 기기
그룹 4종의 멱등 검사(`==| True`)를 각각 켜져 있는지 따지므로 2^k 조합이
그대로 행이 된다. 즉 사영은 하나로 끝나지 않고 질문마다 달라야 한다.

그래서 **액션 역상 + 필수 조건**(`render_action`): 한 액션을 내는 모든
경로의 가드 리터럴 교집합 = 필요조건, 나머지는 "이 액션과 무관"으로 분리.

- `#Plug#Office.off` ← `all(#Plug#Office) ==| True ∧ elapsed > phase_1 ∧
  elapsed > phase_2 ∧ ¬(occupancy == True)` (경로 64개·엣지 192가 한 문장)
- `#Plug#Office#NoneNecessary.off`는 `phase_1`만 요구 — 2단 절전의 계층이
  역상 비교만으로 드러남
- `security_mode.setboolean` ← `desired != armed ∧ ¬(synced == False)`
  = write-on-change 관용구가 그대로 문장이 됨

주의: 첫 구현에서 GV 쓰기가 역상 매칭에서 빠져 "VACUOUS"로 잘못 표시됐다
(문자열로 타깃을 맞춰서). `fired_key` 동일성으로 교체. 사영은 반드시
**분할**이어야 한다(행이 커버한 엣지 수를 항상 같이 보고 = 무언의 누락 금지).

## 배포 재생(replay.py) 실측 (2026-08-03)

목적: "이 시나리오가 며칠째 안 돌았다"를 **원인별로 분해**. 플랫폼의
`last_triggered`는 자동화 단위 1개 값이고 이유를 말하지 못한다. 여기서는
인증 그래프의 **행동(액션) 단위**로 생애 상태를 붙인다.

- `VACUOUS` 정적 불가능(데이터 무관, 기존 의무층) → 유일한 "판정"
- `WINDOW` 도달 가능하지만 발화 엣지가 요구하는 **달력 칸이 관측 창에 없음**
  (여름 로그로 난방 분기를 물을 수 없다). 창 한계이지 코드 결함이 아니다
- `UNMET` 창 안인데 **이 집에서 가드 칸이 한 번도 성립 안 함** (축과 값을
  이름으로: `@gv:occupancy ∈ [True] 미관측`). 임계 오적합·죽은 전제조건이
  여기서 표면화
- `NONCONFORM` 가드가 성립해 코드가 발화했어야 하는데 **플랫폼 로그에 없음**
  = 배포 측 결함(코드 결함 아님)
- `ENGAGED` 발화 횟수 + 마지막 발화로부터 경과일

핵심 구현 포인트: 관측값은 **원시값이 아니라 칸으로** 기록해야 한다.
`clock.month=7`은 축 대표값 4.0과 다른 값이지만 같은 칸(여름)이라
원시 비교로는 "여름 미관측"이라는 거짓 결론이 났다(초기 실행에서 실제
발생). `Axes.cell_preds` + `cell_of()` 추가로 해결. 원인 우선순위는
환경(UNMET) > 창(WINDOW): 둘 다 막혀 있으면 집에 관한 사실이 더 유용하다.

합성 로그 3종 실측(온습도, 30일, 43,200 샘플, period 60s):

| 트레이스 | 결과 |
|---|---|
| 여름·정상 재실 | 냉방 4행동 ENGAGED(on ×638, off ×132), 가습 3행동 WINDOW(`month ∈ [3.0]` 미관측) |
| 여름·occupancy 항상 거짓 | 7행동 전부 UNMET(`@gv:occupancy ∈ [True] 미관측`) — 정적 VACUOUS와 구분됨 |
| 여름·배포 고장 주입 | 해당 행동만 NONCONFORM(638회 중 638회 로그 없음), 나머지는 불변 |

주의(논문에 반드시 명시): **미발화≠무효**. 화재 경보가 30일간 조용한 것은
정상이다. 따라서 무효 판정은 자동화하지 않고 분류만 제시한다(K1 규율).
결측 구간·창 길이를 함께 보고해 "증거의 부재"를 "부재의 증거"로 읽지
않게 한다. 실기기 로그가 도착하면 `_july_office` 합성기만 갈아끼우면 된다.

## e1.py — E1 전수 판정 표 하네스 (2026-08-01, 단일 시나리오 마감)

- `python -m explorer.e1` 한 번(114s) → `runs/e1.md` 기계 생성.
- 표 1: 시나리오 10행 전수 — 술어(단편/GROUND/미해명), 상태·에지·닫힘,
  자기동치, 의무 판정, 비고(cron·부유). **10/10 닫힘·EQUIV, 발견은
  SEED-DEP 1건뿐, 미해명 0.**
- 표 2: 고장 주입 7클래스(경계·시간상수·엣지→레벨·재알림·재배선·점유겹침·
  quantifier) 전부 검출 + 검출 층 + 반례 요지. quantifier 행이 k=1 EQUIV /
  k=2 DIVERGE로 "동치는 바인딩의 성질"을 표 안에 내장.
- 스코프 밖은 표 하단에 호명(% 없는 eval 원칙).
- 관찰: 온습도 에지 278k(솔로 144→의무 하네스 경로)는 상태 혼합 조건이
  많아 dedup이 덜 먹는 케이스 — 수 초 내 완주라 방치, 원인은 기록.

## 다음 단계
- 유저 제공 대기: 실기기 목록·GV 스토어·센서 도메인/단위
  → 부유 셀렉터 해소 + k≥2 결합 칸 + 실물 quantifier 데모

## TODO (보류, 2026-08-01 유저 결정)
- **P4 복합 시나리오** — `composite.py` 초안 작성됨(공유 GV lockstep,
  미시드 연쇄, 충돌, 순서 민감성) **단 미실행·미검증**. 채택 시 검증부터.
- **전 구역 충돌감지 깔때기** (설계 합의): ①정적 스크리닝 = static_actions로
  같은 액추에이터 건드리는 쌍만 추출(즉시; 예: 절전 AC-off vs 온습도 AC-on)
  ②후보 쌍만 곱 탐색(쌍당 초~분; 제3자 GV는 자유 입력=충돌을 놓치지 않는
  과근사) ③반례의 GV 패턴 실현성만 관련 시나리오 소형 곱으로 확인.
  전체 10-way 곱은 상태 곱+교차 타이머 순서로 위험 — 쓰지 않음.
  선행 작업: composite 검증 + 다중 period(gcd 그리드+위상 셀).
