# System Overview and Scope handoff

상태: **full first draft**.

- System figure는 `NL → Timeline+binding → confirmation → LLM lowering / reference execution → Explorer` 흐름으로 다시 그린다.
- repair loop는 구현·평가 범위가 동결될 때까지 본문 주경로에서 제외한다.
- on-device/privacy를 중심 기여로 되살리지 않는다. 실제 배치 근거가 선택되면 구현 또는 Discussion에 제한적으로 배치한다.
- verdict 명칭은 실제 API의 최종 표기와 통일한다. `NON-CERTIFIED`가 umbrella label인지 개별 결과인지 확인한다.
- scope 문장은 `explorer/docs/model/VERIFICATION_CONTRACT.md`와 항상 함께 갱신한다.
- JoI를 유일한 backend로 유지하고 HA 실험은 넣지 않는다. openHAB은 시간이 남아 imperative-code adapter와 평가까지 수행하는 경우에만 선택적으로 추가한다.
