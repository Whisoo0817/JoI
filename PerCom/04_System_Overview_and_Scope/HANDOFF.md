# System Overview and Scope handoff

상태: **SenSys 원문 기반 O1–O5 수정 초안; 기존 시스템 그림 임시 배치** (2026-09-17).

- 현재 사용자 요청에 따라 `../../docs/figs/system.pdf`를 `PerCom_version.md`의 figure 환경에 임시 배치했다. 새 그림은 아직 작성하지 않는다. 기존 그림의 rendering·event synthesis·두 phase 표기는 현재 본문과 차이가 있으므로 최종 교체 대상이다.
- 최종 System figure는 `NL → LLM-proposed Timeline IR ↔ user review/edit → confirmed IR+binding → LLM lowering / reference execution → Explorer` 흐름으로 정리한다. Semantic Parsing과 IR Rendering은 독립 모듈로 두지 않는다.
- repair loop는 본문 O5의 선택적 반례 활용 경로다. 생성 코드만 수정하고 같은 확정 IR·binding으로 재검증한다. 최종 그림에서는 counterexample에서 LLM lowering으로 점선 화살표를 둔다. 자동 repair 구현·성공률·budget 정책은 현재 결과로 주장하지 않는다.
- 원문 재사용 기준은 `../../docs/ovla0606.tex`의 System Overview다. `SenSys_version.md`는 요약이므로 실제 원문으로 혼동하지 않는다. 문단 대응은 `OVERVIEW_FLOW_COMPARISON.md`에 기록했다.
- Overview는 전체 흐름·JoI 대상·IR 확정과 코드 생성·검증·feedback의 5문단이다. Timeline IR의 실행 의미와 결정론성 명제는 §5에 유지한다.
- on-device/privacy를 중심 기여로 되살리지 않는다. 실제 배치 근거가 선택되면 구현 또는 Discussion에 제한적으로 배치한다.
- verdict 명칭은 실제 API의 최종 표기와 통일한다. `NON-CERTIFIED`가 umbrella label인지 개별 결과인지 확인한다.
- scope 문장은 `explorer/docs/model/VERIFICATION_CONTRACT.md`와 항상 함께 갱신한다.
- JoI를 유일한 backend로 유지하고 HA 실험은 넣지 않는다. openHAB은 시간이 남아 imperative-code adapter와 평가까지 수행하는 경우에만 선택적으로 추가한다.
