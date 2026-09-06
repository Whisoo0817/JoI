# VETS formal verification 범위와 Behavioral Explorer 보완 계획

작성일: 2026-09-05

## 1. 문서 목적

이 문서는 다음 논의의 경과와 현재 결론을 정리한다.

1. Behavioral Explorer의 bounded 비교 실험과 초록용 결과
2. 초록에서 `formally verifies`를 사용할 수 있는 조건
3. 입력 경계 이산화에서 발견한 Speaker 반례와 해결책
4. 32단계 execution window의 의미와 BFS/memoization의 관계
5. bounded 검증을 강화하거나 실행 길이 제한을 제거하기 위한 계획

## 2. 완료된 실험과 현재 증거 범위

동결된 v3 평가에서는 총 388회의 코드 생성 시도 중 311개의 IR-code 쌍을
평가할 수 있었다. 나머지는 생성 오류 61개, 지원하지 않는 코드 15개,
준비 오류 1개였다.

평가 가능한 311개 쌍을 32개의 연속 실행 단계까지 검사한 결과는 다음과
같았다.

- 완전 tick-by-tick 열거 결과: 동치 231개, 비동치 80개
- Behavioral Explorer와 완전 열거의 판정 일치: 311/311
- 관측된 false accept: 0/80
- 관측된 false reject: 0/231
- 동치 쌍에서 state-transition 평가 감소: 73.4%
- Behavioral Explorer 분석 시간: median 0.65 ms, p95 52.1 ms, maximum 280.1 ms

이 결과가 직접 지지하는 주장은 제한적이다. 동결된 유한 입력 모델과
32단계 범위에서 Behavioral Explorer가 완전 열거와 같은 판정을 냈다는
경험적 결과다. 완전 열거기와 Explorer는 IR 및 코드의 한 단계 실행기를
공유하므로, 이 실험만으로 실행 의미 자체의 정확성이나 Explorer 알고리즘의
일반적인 soundness를 증명하지는 않는다.

관련 기록:

- [초록용 결과 문구](../skill_result/05_experiment_plan/results/E3/heldout-gemma-v3-h32/abstract-result-wording.md)
- [결과 감사](../skill_result/05_experiment_plan/results-audit/results-audit.md)
- [A/B 평가 프로토콜](../skill_result/05_experiment_plan/ab-evaluation-protocol.md)

## 3. `formally verifies`에 대한 판단

Bounded model checking도 형식 검증이므로, 실행 범위가 유한하다는 이유만으로
`formally verifies`를 사용할 수 없는 것은 아니다. 다만 다음 근거가 모두
필요하다.

1. Timeline IR과 생성 코드의 실행 의미가 명확히 정의되어야 한다.
2. 두 프로그램의 action trace가 같다는 검증 속성이 수학적으로 정의되어야
   한다.
3. Explorer가 선택한 입력값과 시간 경계가 선언된 검증 영역 전체를
   빠짐없이 대표한다는 soundness/completeness 근거가 있어야 한다.
4. 구현이 논문에 정의한 탐색 절차를 그대로 수행해야 한다.

현재는 1과 2에 해당하는 설계와 정의가 존재하고, Timeline IR의
결정론성에 대한 proof sketch도 있다. 그러나 입력 분할, 상태 병합, 시간
점프를 포함한 Explorer 전체에 대한 완성된 정리와 증명은 아직 없다.
Timeline IR의 결정론성은 고정된 입력에서 reference trace가 하나임을
보장하지만, Explorer가 가능한 입력을 모두 포괄한다는 사실까지 보장하지는
않는다.

따라서 현재 실험만을 근거로 `formally verifies generated code`라고 일반화할
수는 없다. 현 상태에서는 다음과 같은 표현이 안전하다.

> VETS systematically checks generated code against a confirmed Timeline IR.

아래 보완과 증명이 끝난 뒤에는 다음과 같이 쓸 수 있다.

> VETS performs bounded formal verification of generated code against a confirmed Timeline IR.

구체적인 범위는 이어지는 문장에서 선언한다.

> The guarantee holds within the supported language fragment, declared finite input model, and bounded execution window.

## 4. 입력 경계 이산화에서 확인한 Speaker 반례

현재 Explorer는 주로 조건문의 참과 거짓이 바뀌는 입력 경계를 이용해
대표값을 선택한다. 하지만 센서값이 action argument로 전달되면 같은 조건
구간 안에서도 관찰되는 출력이 달라질 수 있다.

최소 반례는 다음과 같다.

```text
Timeline IR: temperature < 10이면 speaker.speak(temperature)
생성 코드:   temperature < 10이면 speaker.speak(9)
```

조건 경계만 고려한 Explorer는 대표값 `9`와 `10`을 검사한다. `9`에서는 양쪽
모두 `9`를 말하고, `10`에서는 조건이 거짓이므로 동치로 판정할 수 있다.
그러나 선언된 유한 입력 모델에 `9.9`가 있으면 IR은 `9.9`를, 코드는 `9`를
출력하므로 실제로는 비동치다.

이 반례는 기존 311개 쌍에서 판정이 일치했다는 사실을 바꾸지는 않는다.
하지만 그 표본 밖에서도 경계 탐색이 항상 완전하다는 일반적인 주장은
성립하지 않음을 보여준다. 따라서 현재 수치는 수정 전 구현의 경험적
결과로 보존하되, 수정된 Explorer의 최종 초록 수치로 재사용해서는 안 된다.

## 5. Speaker 반례의 해결책

입력이 프로그램 행동에 미치는 영향을 데이터 흐름에 따라 구분한다.

### 5.1 조건 판단에만 영향을 주는 입력

입력값이 조건의 참과 거짓에만 영향을 주고, 상태나 observable action으로
흘러가지 않는다면 같은 조건 결과를 만드는 값들을 하나의 동치 클래스로
묶을 수 있다. IR과 코드 양쪽에 나타나는 모든 조건을 합쳐 partition을
만들고, 각 클래스에서 하나의 대표값을 검사한다.

### 5.2 관찰 가능한 행동에 영향을 주는 입력

입력값이 다음 요소에 직접 또는 간접적으로 영향을 준다면 조건 경계만으로
묶지 않는다.

- action argument 또는 target
- action의 발생 횟수와 순서
- 이후 action에 영향을 주는 persistent state
- timer 설정, 취소, 지연 시간

이 입력은 선언된 유한 도메인의 값을 모두 열거한다. 데이터 흐름을 안전하게
분석할 수 없거나 지원 범위를 벗어난 연산이 있으면 `EQUIV`가 아니라
`REFUSED` 또는 `INCONCLUSIVE`를 반환한다. 이후 확장안으로는 SMT를 이용해
action argument 식의 동치를 기호적으로 검사할 수 있지만, 초기 보완에는
유한 도메인 전수조사가 더 단순하고 증명하기 쉽다.

여기서 전수조사는 현실 세계의 모든 실수 센서값을 의미하지 않는다. 논문과
도구가 명시적으로 선언한 유한 입력 도메인의 모든 값을 의미한다. 연속값
전체에 대한 보장이 필요하면 별도의 기호 실행 또는 더 강한 추상화 증명이
필요하다.

## 6. 32단계가 의미하는 것

32단계는 상태가 32번 반복되는지 관찰한다는 뜻이 아니다. 가능한 센서 입력이
순서대로 들어오고, IR과 코드가 반응하며, 내부 상태와 타이머가 다음 실행으로
전달되는 과정을 최대 32번까지 탐색한다는 뜻이다.

예를 들어 입력이 `open`과 `closed` 두 개라면 탐색 트리는 다음처럼 증가한다.

```text
1단계: open, closed
2단계: open-open, open-closed, closed-open, closed-closed
3단계: 위 각 경로에서 다시 open 또는 closed
...
32단계: 길이 32 이하의 모든 modeled input sequence
```

따라서 32는 초나 분 같은 고정된 실제 시간이 아니며, 각 자동화의 실행
주기에 따른 32개의 연속 입력 및 실행 시점을 뜻한다. 33번째 단계 이후에만
나타나는 오류는 현재 평가로 보장할 수 없다.

32는 의미론으로부터 도출된 completeness bound가 아니다. 개발 중 4, 8,
32단계로 범위를 늘려 확인한 뒤, 완전 열거가 가능한 현실적인 평가 한도로
선택하고 held-out 실험 전에 동결한 값이다.

## 7. BFS, memoization, 시간 점프와 32단계의 관계

32단계는 BFS, memoization 또는 시간 점프의 판정 기준이 아니다.

- BFS는 입력 시퀀스의 길이가 짧은 상태부터 차례로 탐색한다.
- memoization은 같은 탐색 깊이에서 IR 상태, 코드 상태, persistent state,
  timer 상태가 동일한 노드에 여러 경로가 도달하면 즉시 하나로 합친다.
- 동일 상태가 32번 반복될 때까지 기다린 뒤 합치는 방식이 아니다.
- 32단계 bounded A/B 평가에서는 안전성을 위해 한 단계씩 전진하며,
  서로 다른 깊이의 상태를 같은 상태로 추상화하거나 긴 시간 점프를 사용하지
  않았다.

기존 unbounded/fixpoint 모드의 시간 점프는 별도 기능이다. 한 단계 동안
observable action과 미래 관련 상태가 변하지 않는 stutter 조건을 확인하고,
다음 timer 또는 시간 조건 경계로 이동한다. 이 최적화를 형식 검증 주장에
포함하려면 stutter 구간을 건너뛰어도 action의 누락, 중복 또는 순서 변화가
없다는 별도의 증명이 필요하다.

## 8. `count`에서 동적으로 horizon을 정하는 방안

Timeline IR의 `count` 값을 정적으로 읽어 자동화마다 horizon을 다르게 정하는
방식은 고정된 32보다 낫다. 그러나 `count`만으로 충분하지는 않다.

- `delay`, `duration`, `repeat`, timer cancellation도 긴 실행 이력을 만든다.
- 여러 시간 연산이 순차 또는 중첩되면 필요한 길이는 상수의 최댓값이 아니라
  합이나 곱이 될 수 있다.
- 생성 코드가 Timeline IR에 없는 더 큰 counter나 timer를 도입할 수
  있으므로 IR과 코드 양쪽을 분석해야 한다.
- 정적으로 선택한 horizon이 모든 미래 행동을 포괄하는 completeness bound임을
  증명하지 못하면 결과는 여전히 bounded equivalence다.

따라서 동적 horizon은 탐색 예산이나 보조 평가 범위를 정하는 데 사용하고,
실행 길이 제한을 제거하는 최종 기준으로는 product state graph의 fixpoint를
사용하는 것이 적절하다.

## 9. 실행 길이 제한을 제거하는 방향

지원하는 언어와 입력 모델에서 product state가 유한하게 표현될 수 있다면,
BFS와 memoization으로 더 이상 새로운 상태가 나오지 않을 때까지 탐색할 수
있다. 이 fixpoint에 도달하면 이미 본 상태 이후의 행동을 반복 탐색할 필요가
없으므로 임의 길이의 modeled input sequence를 포괄할 수 있다.

권장 verdict는 다음과 같다.

- `DIVERGE(counterexample)`: 실제 실행 가능한 반례를 발견함
- `EQUIV-FIXPOINT`: 유한 product graph가 닫혀 모든 실행에 대해 동치임
- `EQUIV-BOUNDED(H)`: 길이 `H` 이하의 모든 modeled execution에 대해 동치임
- `INCONCLUSIVE`: 상태, 전이, 시간 또는 메모리 한도 때문에 탐색을 완료하지
  못함

`EQUIV-FIXPOINT`가 반환된 사례에는 `bounded execution window`를 붙일 필요가
없다. 다만 지원 문법과 선언된 입력 모델의 범위는 계속 밝혀야 한다.

> VETS formally verifies behavioral equivalence for all executions within the supported language fragment and declared finite input model.

Fixpoint에 도달하지 못한 사례를 동치로 처리해서는 안 된다. 이 경우에는
`EQUIV-BOUNDED(H)`로 범위를 제한하거나 `INCONCLUSIVE`로 보고한다.

## 10. 필요한 정리와 증명

`formally verifies`를 최종 논문에서 사용하려면 최소한 다음 내용을 본문에
제시해야 한다.

1. **Timeline IR determinism:** 동일한 초기 상태와 timed input sequence는
   하나의 action trace를 만든다.
2. **Trace-equivalence definition:** IR과 코드의 observable action, argument,
   multiplicity, order를 포함한 trace equality를 정의한다.
3. **Input-partition preservation:** 같은 대표 구간으로 묶인 입력은 조건 판단,
   다음 abstract state, observable action에서 구별되지 않음을 보인다.
4. **Observable-flow coverage:** action과 미래 상태에 영향을 주는 입력은 모두
   열거되거나 동치가 기호적으로 증명됨을 보인다.
5. **Successor coverage:** 모든 modeled environment transition이 Explorer의
   successor 중 하나에 대응함을 보인다.
6. **State-merge soundness:** 같은 memoization key를 가진 product state는 이후
   동일한 observable behavior를 가짐을 보인다.
7. **Temporal-boundary preservation:** 시간 점프를 사용한다면 건너뛴 구간에서
   action이나 상태 변화가 없음을 보인다.
8. **Bounded theorem:** `EQUIV-BOUNDED(H)`이면 모든 길이 `H` 이하의 modeled
   input sequence에서 두 trace가 같음을 실행 길이에 대한 귀납법으로 보인다.
9. **Fixpoint theorem:** product graph가 닫히면 임의 길이의 modeled input
   sequence에서도 두 trace가 같음을 보인다.
10. **Implementation correspondence:** 논문의 알고리즘과 실제 구현의 각 단계가
    대응함을 설명하고, 회귀 테스트와 완전 열거 비교를 보조 증거로 제시한다.

## 11. 권장 작업 순서

### 단계 A: sound bounded formal verification

1. Speaker 반례를 회귀 테스트로 고정한다.
2. 입력의 transitive data flow를 분석해 predicate-only와 observable-flow
   입력을 분리한다.
3. observable-flow 입력의 유한 도메인을 전수조사하고, 불명확한 경우
   fail-closed한다.
4. 시간 점프 없이 `H`단계 BFS의 coverage theorem을 작성한다.
5. 수정된 구현을 새로운 완전 열거기 평가와 held-out set으로 다시 측정한다.

이 단계가 끝나면 `bounded formal verification`을 주장할 수 있다.

### 단계 B: fixpoint-based formal verification

1. 미래 행동에 필요한 product state key를 형식적으로 정의한다.
2. state normalization과 시간 영역 추상화가 future behavior를 보존함을
   증명한다.
3. 시간 점프의 stutter-preservation을 증명한다.
4. fixpoint 완료율, state/transition 수, p95 latency, timeout 및
   `INCONCLUSIVE` 비율을 측정한다.

이 단계까지 완료하면 fixpoint가 닫힌 사례에 대해 bounded execution window를
제거할 수 있다.

## 12. 현재 결론

- 기존 311쌍 실험은 H=32에서의 강한 경험적 검증 결과지만, 그 자체가
  Explorer의 형식적 완전성 증명은 아니다.
- Speaker 반례는 해결 가능한 입력 추상화 문제이며, 연구 방향을 무효화하지
  않는다.
- 우선 observable-flow 전수조사와 fail-closed 정책으로 bounded verifier를
  sound하게 만드는 것이 가장 현실적이다.
- 그다음 product graph를 fixpoint까지 탐색하고 상태/시간 추상화를 증명하면,
  완료된 사례에서는 실행 길이 제한 없는 형식적 행동 동치를 주장할 수 있다.
- 알고리즘을 수정하면 현재의 311, 73.4%, 52.1 ms는 다시 측정해야 한다.

## 명칭 메모

최근 논의와 초록 문안은 시스템 이름으로 `VETS`를 사용했다. 직전 커밋의
영문 초록은 `VESTA` 명칭을 사용했으므로, 최종 이름이 확정되면 파일명과
본문 표기를 한 번에 통일해야 한다.
