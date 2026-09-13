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

## E1 이 만든 limitation 항목 (2026-09-12)

근거: `../6_Evaluation/E1_adequacy/README.md` §0 결론, §6 경계 probe.

1. **인증 경계가 표현 경계보다 좁다.** 경계 probe 3건이 모두 언어·참조 실행기를 통과하고 Explorer 만 거절했다.
   거절 사유가 셋 다 같은 종류다 — 실행 중 값끼리 비교하는 guard(저장한 시각과의 경과 시간 비교, 반복 카운터와 기기값 비교).
   즉 Timeline 으로 쓸 수 있고 참조 실행기로 정확히 재생되는 요구 중 일부를 VETS 가 인증하지 못한다. **이 절의 1순위 항목이다.**
2. **언어에 남는 구조적 한계 3가지.** 근거 `../6_Evaluation/E1_adequacy/breadth/depth/RESULTS.md` (저자 의미 감사 전).
   단일 제어 흐름 — E1-092 로 시험, 실패 격리가 필요한 병렬 흐름을 표현 못 함(0/1; JoI 도 블록 2개 배포로만 해결) /
   대입 연산 부재 — E1-095 로 시험, 누적 메커니즘은 없고 표본 수가 리터럴일 때만 펼쳐서 같은 trace(부분) /
   유한 상태 — 아직 시험 안 함, 논증으로 표시(E1-028 은 한도 리터럴 2 라 표현됨).
3. **E1 은 선정 사례 중의 건수이며 coverage 가 아니다.** 경계 B2(진짜 병렬 흐름)는 depth E1-092 한 건(실패 이력 하나)뿐이고,
   B5(중첩 반복)는 C07 한 건뿐이다.
4. **현재 NL→IR 프롬프트로는 생성되지 않는 encoding 이 있다.** 12건 중 4건이 `wait.timeout`·중첩 cycle·`period 0` 을 쓰는데
   `files/timeline_ir/extractor.md` 에 없다. 손으로 쓸 수 있는 범위와 현재 파이프라인이 만들 수 있는 범위를 구분해 적는다.
   프롬프트는 388 데이터셋에 맞춰 둔 것이므로 E3 시작 전에 별도로 결정한다.
5. **관측 모델의 경계(언어 한계와 구분해 적을 것).** 입력은 100 ms 격자에서만 바뀌고, t=0 이전의 과거는 이력으로 쓸 수 없으며,
   Clock.Timestamp 는 초 단위다. 참조 실행기는 catalog 에 있는 `Clock.Second` 를 제공하지 않는다(null). 자동화 시작 전 이력은 플랫폼이 기기별 변경 시각을 저장하면 풀리는 문제이므로
   Timeline 의 표현력 한계로 쓰지 않는다.
