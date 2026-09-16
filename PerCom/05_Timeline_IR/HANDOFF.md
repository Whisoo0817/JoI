# Timeline IR handoff

상태: **full first draft; formal notation pending**.

- 문법 표, well-formedness, state tuple, small-step/reaction relation을 실제 계약에서 옮겨야 한다.
- operator별 예제는 sustain, snapshot, cycle/period를 우선한다. 지원하지 않는 병렬·일반 집계를 예제로 넣지 않는다.
- 결정론 정리는 `explorer/docs/proof/PROOF_OBLIGATIONS.md`의 전제와 정확히 맞춘다.
- `per-automation`, `executable behavioral specification`, `input-deterministic` 용어를 유지한다.
- readability/usability 및 다른 IR보다 표현력이 우월하다는 주장을 넣지 않는다.

## E1 에서 확정된 실행 의미 (2026-09-12, 이 절 본문에 반영할 것)

근거와 재현: `../08_Evaluation/E1_adequacy/` (README §4 계약 절, §6 경계 probe).

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

**쓸 수 있는 것 (E1 depth, 저자 의미 감사 2026-09-13 확정):** `../08_Evaluation/E1_adequacy/breadth/depth/RESULTS.md`
- **Timeline 하나에는 병렬 branch 가 없다. 서로 독립인 흐름은 Timeline 여러 개로 분해해 배포할 수 있다.** E1-092: 한 Timeline 에
  두 흐름을 끼우면 주입한 Alexa 실패가 집 종료 명령까지 멈추고(v1, 0/1), 공유 상태·합류·순서 의존이 없는 두 흐름을 Timeline 두 개로
  나누면 정확히 맞는다(v2, 1/1). **일반 fork–join 이나 공유 상태 병렬성을 지원한다고 넓히지 않는다.**
- **표본 수가 고정된 집계는 표현된다.** E1-095: 시각별 snapshot 변수 5개와 `(v1+…+v5)/5`. Timeline IR 에는 일반 mutable
  accumulator 나 입력 개수에 따라 변하는 집계가 없다 — 이것은 별도 언어 경계로 쓰고, 일반적인 평균·횟수·이력은 backend 서비스
  (예: history/statistics sensor)가 계산하고 IR 은 그 typed 결과를 읽어 orchestration 을 검증하는 방향으로 기술한다.
  이 위임을 IR 의 동적 집계 성공이나 측정하지 않은 효율 향상으로 쓰지 않는다.
- **고정 한도 2 의 rolling window 는 표현된다.** E1-028(시각 슬롯 2개). 실행 시간에 정해지는 N·무제한 이력은 주장하지 않는다.
- **환경 시각은 입력으로 읽는다.** E1-072: 일출·일몰은 플랫폼이 주는 daylight 입력이고 06:00/18:00 은 한 실행의 값이다.

## E2 에서 온 요청 (2026-09-14, whisoo 결정)

- 이 절에 **"Timeline 은 시간·상태·로직을 담고, 어떤 기기를 가리키는지는 사용자가 확정한 binding 이 정한다"** 수준의 문장 하나만 둔다.
- all/any, 셀렉터를 한 줄로 쓸지 나열할지, binding 자리가 여럿일 때의 비교 규칙은 **원고에 쓰지 않는다**(독자에게 noise, 실험 결론에 영향 없음).
  근거 규칙은 `../08_Evaluation/E2_fidelity/BINDING_DECISION_2026-09-14.md` 에만 둔다.

**하지 말 것(추가):** "프로그램이 고정돼 있으니 finite-state" 같은 넓은 문장을 E1 결과처럼 쓰지 않는다(새 probe 없음).
지원하지 않는 병렬·일반 집계를 operator 예제로 넣지 않는다는 기존 방침은 유지한다.

## 결정론성 명제 D의 원고 배치 (2026-09-17)

- **이 절(§5)에 명제 D / input-determinism을 둔다.** 고정된 Timeline IR, 실행 모델, 초기 상태와 timed input history에서 각 정상 반응은 유일하며, 유한 반응·시간 진행 조건을 만족하면 timed action trace가 유일하다. 입력 자체를 하나로 제한한다는 뜻은 아니다.
- 본문은 문법·상태·반응 규칙의 최소 정의 → D의 전제와 명제 → 짧은 증명 개요 순서로 작성한다. 입력과 timer가 동시에 바뀔 때의 순서, 상태 수명, 제어 흐름 결합 규칙을 정의한다.
- **증명 개요:** 원시 연산·명령의 유일성에서 유한 반응 내부 전이 수에 대한 귀납으로 반응 유일성을 얻고, 반응 횟수와 시간 진행에 대한 논증으로 trace 유일성을 얻는다. 상세 규칙별 귀납은 부록에 둔다.
- 기존 [검증 계약 D](../../explorer/docs/model/VERIFICATION_CONTRACT.md), [프런트엔드 §5](../../explorer/docs/proof/FRONTEND_CORRECTNESS.md), [통합 증명 L3·L4](../../explorer/docs/proof/PROOF_OBLIGATIONS.md)가 근거다. 문서에는 수작업 논증이 작성돼 있으며, 이 절의 정리·수식·증명 개요로 편집하는 작업이 남아 있다.
- 실행기·프런트엔드의 신뢰 기반을 명시한다. 전체 Python 구현의 기계 검증, 임의 프로그램의 종료, Explorer의 판정 완료 또는 NL→IR의 의도 정확성을 D로 주장하지 않는다.
- Explorer의 검증 soundness 명제 S는 [§6 HANDOFF](../06_Code_Generation_and_Behavioral_Validation/HANDOFF.md)에 둔다. 같은 실행 모델 정의는 필요한 곳에서 참조하고 중복 설명하지 않는다.
