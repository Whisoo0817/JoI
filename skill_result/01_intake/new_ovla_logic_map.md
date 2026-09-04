# New OVLA Logic Map

이 map은 S3 §15의 순서와 S3 §16의 contribution 순서를 그대로 보존한다.

| Flow step | 승인된 논리 | 필요한 연결 | 연결될 contribution | 증거 유형 |
|---:|---|---|---|---|
| 1 | Reactive-temporal code correctness는 source form으로 판정할 수 없다 | syntax-equivalent/behavior-different와 syntax-different/behavior-equivalent 예시 | C1 | motivating example + citations |
| 2 | Behavior comparison에는 timed input별 expected behavior를 생성하는 executable reference가 필요하다 | 자연어와 검증 대상 code가 oracle이 될 수 없는 이유 | C1, C2 | argument + closest-work comparison |
| 3 | User confirmation 이후 Timeline IR이 authoritative specification boundary가 된다 | authoring assumption과 verification guarantee를 분리 | C2 | system contract + anti-claims |
| 4 | Timeline IR semantics는 fixed input마다 유일한 observable reference trace를 낸다 | totality, observation, time/tie/conflict 규칙 | C2, C3 | formal semantics + theorem |
| 5 | 복합 automation에서도 composition rule이 이 성질을 보존한다 | primitive determinism만으로 부족한 conflict 예시 | C3 | merge lemma + constructor induction |
| 6 | Explorer가 finite model/bounds 안의 reachable histories를 열거한다 | environment nondeterminism과 program input-determinism을 분리 | C4 | algorithm/model + scalability evidence |
| 7 | IR과 code를 identical inputs/observation 아래 비교한다 | internal state가 아닌 normalized observable trace로 verdict | C1, C4, C5 | E1~E4 |

## Contribution order

1. C1 Behavioral verification
2. C2 Executable reference specification
3. C3 Determinism-enabling semantics
4. C4 Reachable behavior exploration
5. C5 Evaluation

## 논리적 의존성

```text
source form insufficiency
  -> executable reference requirement
  -> confirmed Timeline IR boundary
  -> unique trace for a fixed input
  -> preservation under composition
  -> reachable finite exploration
  -> IR/code observational equivalence verdict
```

어느 화살표도 새 contribution을 요구하지 않는다. 이후 advice는 해당 화살표를 명확히 하거나 증거를 붙이는 역할만 한다.

