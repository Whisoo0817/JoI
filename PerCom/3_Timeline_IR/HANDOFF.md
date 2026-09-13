# Timeline IR handoff

상태: **full first draft; formal notation pending**.

- 문법 표, well-formedness, state tuple, small-step/reaction relation을 실제 계약에서 옮겨야 한다.
- operator별 예제는 sustain, snapshot, cycle/period를 우선한다. 지원하지 않는 병렬·일반 집계를 예제로 넣지 않는다.
- 결정론 정리는 `explorer/docs/proof/PROOF_OBLIGATIONS.md`의 전제와 정확히 맞춘다.
- `per-automation`, `executable behavioral specification`, `input-deterministic` 용어를 유지한다.
- readability/usability 및 다른 IR보다 표현력이 우월하다는 주장을 넣지 않는다.

## E1 에서 확정된 실행 의미 (2026-09-12, 이 절 본문에 반영할 것)

근거와 재현: `../6_Evaluation/E1_adequacy/` (README §4 계약 절, §6 경계 probe).

- `cycle.period` 는 **회차 종료 후** 대기다. 정각마다 시작하는 fixed-rate schedule 로 쓰지 않는다.
  "매 N" cadence 가 필요하면 회차 시간을 빼야 한다. body 의 timeout 이 이미 cadence 를 담당하면 `period: "0 MSEC"` 가 맞다.
- edge 대기는 첫 평가에서 조건이 이미 참이면 **발화한다**. "사건" 의미가 필요하면 선행 level 대기를 둔다.
- 다른 대기가 도는 동안 일어난 edge 는 latch 에 반영되지 않는다.
- 실행기는 `start_at.anchor == "cron"` 을 거절한다. 앵커를 소거하고 한 발화 창만 실행한다.
- 미초기화 변수는 `null` 이고 null 산술은 0 으로 강제된다. 현재 검증 계약에 명세돼 있지 않다.
- `Clock.Timestamp` 는 초 단위(`now_ms // 1000`), `Clock.Hour/Minute` 은 분 단위다.

## 표현 경계로 쓸 문장 (E1 근거)

**하지 말 것:** 아래 셋을 Timeline 의 한계로 쓰면 틀린다. E1 에서 전부 표현됐다.
- 가변 반복 간격 — duration 피연산자는 리터럴이지만 `cycle(until "k >= $n", count "k"){ delay "1 단위" }` 로 펼치면 된다.
  단위가 곧 해상도이자 상태 수라는 **비용**으로 쓰고, 불가로 쓰지 않는다.
- 도는 중 일어난 사건의 기억·시간창 — `Clock.Timestamp` 스냅샷 + `$t != null` 로 표현된다.
- 자동화가 켜지기 전의 과거 — 언어가 아니라 **서비스·카탈로그** 문제다. 기기별 변경 시각 서비스가 있으면 `read` 한 줄이다.

**쓸 수 있는 것 (E1 depth 2026-09-13 로 시험, 저자 의미 감사 전):** `../6_Evaluation/E1_adequacy/breadth/depth/RESULTS.md`
- **단일 제어 흐름 — 시험함, 경계 맞음.** E1-092: 두 명령 흐름을 한 흐름에 끼워 넣으면, 주입한 Alexa 명령 실패가 그 인스턴스를
  끝내면서 집 종료 명령(Alarm.Set)까지 멈춘다(참조 실행 0/1). JoI 도 스크립트 안 병렬 문법은 없고, 블록 두 개를 따로 배포해야
  맞는다(1/1). 실패 없는 이력은 frozen 기록에 없어 시험하지 않았다.
- **대입 연산 부재 — 시험함, 부분.** E1-095: `sum += value` 는 쓸 수 없다(`read` 출처는 catalog 속성뿐, 시도 거절 재현).
  표본 수가 리터럴 5 라 read 5쌍을 펼치고 인자에서 평균하면 trace 는 정확히 맞는다. 표본 수가 입력에 따라 바뀌는 집계는 여전히 논증 상태.
- **유한 상태 — 아직 시험 안 함.** E1-028 의 "최근 4시간 2회 미만" 은 한도가 리터럴 2 라 시각 슬롯 2개로 표현됐다(한도 N → 슬롯 N).

지원하지 않는 병렬·일반 집계를 operator 예제로 넣지 않는다는 기존 방침은 유지한다.

실행 사실 추가: 참조 실행기의 시계는 timestamp·hour·minute·weekday 만 준다. catalog 의 `Clock.Second` 는 null 로 읽힌다(실행기 빈틈).
