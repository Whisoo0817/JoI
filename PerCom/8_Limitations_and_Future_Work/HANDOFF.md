# Limitations and Future Work handoff

상태: **full first draft**.

- 현재 계약의 limitation과 연구 수행상의 threat to validity를 최종본에서 소제목으로 분리할 수 있다.
- multi-automation conflict 검사는 사용자 구상을 보존한 것이며 현재 구현·결과가 아니다.
- cron/period가 conflict detection에 유리하다는 표현은 algorithm과 평가가 생긴 뒤 성능 주장으로 바꾼다.
- stored IR 재사용에는 배포 code와의 version equivalence가 전제임을 유지한다.
- 실제 E1–E4 결과에서 드러난 실패를 숨기지 않고 이 절에 추가한다.
- deterministic compiler를 비교하지 않은 대안과 Future Work로 명시한다.
- HA 실험은 하지 않는다. openHAB은 시간이 있고 imperative adapter·평가를 완료한 경우에만 선택적으로 추가한다.
- JoI 한 backend와 지원 corpus에서 스마트홈 자동화 전체 generality를 주장하지 않는다.
