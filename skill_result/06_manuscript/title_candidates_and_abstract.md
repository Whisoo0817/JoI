# PerCom 2027 title candidates and working abstract

## Status

- The following two titles are the current candidates; no final title has been selected.
- The Korean abstract below is the version fixed during the 2026-09-04 discussion.
- `OVLA` remains in the abstract as a temporary system-name placeholder. Replace it consistently with `BRAVE` or `VETS` after the title is selected.
- The paper scope and terminology are fixed to `smart-home automation` for the current manuscript.
- Bracketed values in the evaluation paragraph are placeholders, not measured results.

## Title candidate 1: BRAVE

**BRAVE: Behavior-Based Reactive Automation Verification for LLM-Generated Smart-Home Code against Executable Timeline Specifications**

- **B**ehavior-Based
- **R**eactive
- **A**utomation
- **V**erification
- **E**xecutable

## Title candidate 2: VETS

**VETS: Behavioral Verification of LLM-Generated Smart-Home Automation Code against Executable Timeline Specifications**

- **V**erification
- **E**xecutable
- **T**imeline
- **S**pecifications

Here, `against` indicates that the executable Timeline Specifications serve as the reference specifications against which the generated code is checked.

## 확정한 한글 초록 작업본

스마트홈 자동화를 직접 작성하려면 플랫폼별 언어와 실행 방식을 알아야 한다. 이러한 어려움 때문에 자연어 요청을 실행 코드로 변환하는 대규모 언어 모델(LLM)이 자동화 작성에 활용되고 있다. 그러나 코드를 생성하는 것과 생성된 코드의 정확성을 검증하는 것은 별개의 문제다. 스마트홈 자동화는 비동기 센서 이벤트에 반응하고 시간 조건과 반복 실행으로 행동이 전개되는 반응형·시간적 프로그램으로, 사용자가 요구한 조건과 행동이 코드 표면에 항상 드러나지 않고 복잡한 실행 논리로 구현된다. 따라서 사람이나 LLM이 코드만으로 실행 논리의 오류와 요청된 행동과의 의미적 일치를 모두 판단하기 어렵다.

본 논문에서는 자연어로 표현된 스마트홈 자동화를 실행 가능한 행동 명세로 구체화하고, 이를 기준으로 생성한 코드를 검증하는 프레임워크인 OVLA를 제시한다. OVLA는 자연어 요청과 생성 코드 사이에 사용자가 확인하는 중간 명세인 Timeline IR을 둔다. Timeline IR은 여러 방식으로 해석될 수 있는 자연어 요청에 암묵적으로 담긴 이벤트·상태·시간 의미를 명시적인 행동 연산자로 나타내고, 정의된 실행 의미에 따라 동일한 초기 상태와 시간 정보가 포함된 입력 시퀀스에 대해 유일한 액션 트레이스를 산출한다. 사용자가 Timeline IR이 자신의 의도와 일치하는지 확인한 후, OVLA는 이 명세로부터 대상 플랫폼의 자동화 코드를 생성한다.

OVLA의 Behavioral Explorer는 생성 코드가 확인된 Timeline IR의 행동을 올바르게 구현하는지 검사한다. Behavioral Explorer는 행동이 달라질 수 있는 입력값과 시간의 경계를 중심으로 탐색 공간을 이산화하고, Timeline IR과 생성 코드의 액션 트레이스를 비교한다. 독립적으로 구현한 tick 단위 완전열거기를 정답 기준으로 사용하여 `[N]`개의 IR–코드 쌍을 평가한 결과, Behavioral Explorer는 잘못된 동등 판정 `[A]건`과 잘못된 비동등 판정 `[B]건`을 기록하였다. 또한 경계 기반 이산화는 완전열거와 동일한 판정을 유지하면서 탐색 전이 수를 `[R%]` 줄이고 검증을 `[T]` 이내에 완료하였다.

## Before registration and submission

1. Select either `BRAVE` or `VETS` and replace the temporary `OVLA` name.
2. Replace `[N]`, `[A]`, `[B]`, `[R%]`, and `[T]` only with audited results from the redesigned system.
3. Produce the English abstract from the final Korean content after the system name is frozen.
