# New Direction Scope

## 고정된 중심 문제

LLM-generated IoT automation은 asynchronous events, persistent state, timers, concurrency와 history에 따라 행동하는 reactive-temporal program이다. 서로 다른 code idiom이 같은 행동을 만들고, 표면적으로 그럴듯한 code가 다른 trace를 만들 수 있으므로 generated code correctness는 source similarity가 아니라 observable behavior로 판단한다. 근거: S3 §0, §2.

## 검증 경계

- 사용자 확인 전: natural-language interpretation과 authoring.
- 사용자 확인 후: confirmed, well-formed Timeline IR을 authoritative specification으로 고정.
- OVLA verdict: 동일한 initial configuration과 timed exogenous-input trace 아래에서 IR과 generated code의 normalized observable action trace가 같은지 판단.
- 전체 보장: finite environment model과 명시된 exploration bounds 안의 reachable inputs에 한정.

## 범위 안

- Timeline IR의 formal syntax, typing, well-formedness.
- executable, input-total, observationally deterministic operational semantics.
- composition 이후 determinism 보존.
- finite modeled environment에서 reachable history exploration.
- IR/code execution의 동일 입력 및 동일 observation contract.
- expressiveness, interpreter conformance, equivalence checker, Explorer scalability 평가.

## 범위 밖

- NL→IR이 latent user intent와 일치하는지에 대한 보장.
- 임의 사용자의 IR 이해도 또는 usability.
- network/device failure를 포함한 physical-world correctness.
- post-deployment localization, repair 또는 self-healing.
- unbounded arbitrary reactive program equivalence.
- single backend evidence만으로 얻는 backend portability.

## 정확히 사용할 guarantee 문장

> For a user-confirmed, well-formed Timeline IR and generated code, OVLA checks whether both produce the same observable action trace for every reachable timed input explored within the declared finite environment model and exploration bounds.

이 문장은 intent correctness, physical correctness, unbounded equivalence를 포함하지 않는다.

