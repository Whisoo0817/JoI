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

**쓸 수 있는 것(단, 아직 probe 미실시 — 논증 상태로 표시):** 유한 상태, 대입 연산 부재, 단일 제어 흐름.
셋 다 정의에서 유도했고 Stage B 에서 실제 요구로 시험한 뒤 단정한다.

지원하지 않는 병렬·일반 집계를 operator 예제로 넣지 않는다는 기존 방침은 유지하되,
"집계 불가" 를 결과 문장으로 쓰려면 probe 가 먼저 있어야 한다.
