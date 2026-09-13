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
2. **언어 경계(저자 의미 감사 2026-09-13 확정).** 근거 `../6_Evaluation/E1_adequacy/breadth/depth/RESULTS.md`.
   Timeline 하나에는 병렬 branch 가 없다 — 서로 독립인 흐름만 Timeline 여러 개로 분해해 배포한다(E1-092); fork–join·공유 상태
   병렬성은 지원하지 않는다 / 일반 mutable accumulator·입력 개수에 따른 동적 집계·무제한 이력은 IR 안에 없다 — 고정 개수 집계
   (E1-095)와 고정 한도 2(E1-028)만 표현을 보였고, 일반 통계는 backend 서비스에 위임하는 방향으로만 적는다(효율 주장 없음).
   finite-state 성질은 E1 에서 시험하지 않았으므로 결과처럼 쓰지 않는다.
3. **E1 은 선정 사례 중의 건수이며 coverage 가 아니다.** 두 기준을 섞지 않는다.
   - depth 20건(실행 검사한 사례): B2(독립 흐름)를 실행으로 확인한 사례는 C11(단일 흐름으로 환원)과 E1-092(Timeline 두 개로 분해,
     실패 이력 하나)뿐이고, B5(중첩 반복)는 C07 한 건뿐이다.
   - breadth corpus(IN_SCOPE 92건, 저자 R/B 코딩): B2 5건·B5 1건·B4 0건. 코딩 건수이며 실행 결과가 아니다
     (근거 `../6_Evaluation/E1_adequacy/breadth/audit/AUTHOR_RB_CODING_2026-09-13.md`).
4. **관측 모델의 경계(언어 한계와 구분해 적을 것).** 입력은 100 ms 격자에서만 바뀌고, t=0 이전의 과거는 이력으로 쓸 수 없으며,
   Clock.Timestamp 는 초 단위다. 자동화 시작 전 이력은 플랫폼이 기기별 변경 시각을 저장하면 풀리는 문제이므로
   Timeline 의 표현력 한계로 쓰지 않는다.
