# Results Audit

`results-audit.json` is the canonical machine-readable audit record. This Markdown file is the explanatory view and must not contradict the JSON verdicts.

## Audit E2-extension-v4

- Claim ID: E2-decision-coverage
- Bounded verdict: supports_exploratory_follow_up
- Attained assurance class: exploratory
- Audited claim effect: strengthen
- Paper ID: VETS-PerCom-2027, identity version 1

전체 142쌍을 같은 120초 예산으로 실행했다. 43 EQUIV, 82 DIVERGE,
5 TIMEOUT, 12 REFUSED다. 사용자 결정에 따른 입력 부적합 2쌍을 따로
집계하면 유효 140쌍 중 125쌍 판정 완료(89.3%)다. 미결정 15쌍은 계산된
수치 상태의 관계 추론 10쌍, 유한 곱 상태의 폭증 5쌍이다.
E1-095의 합계는 매일 초기화되므로 “모든 미지원 수치가 무한히 증가한다”는
설명을 지지하지 않는다. 공통 한계는 출력/기한을 결정하는 수치 계산의 관계다.

기존 판정 104쌍의 변화는 없고, 동결 REF-DIVERGE에 대한 새 EQUIV는 없다.
기존 지정 회귀와 새 25개 timer 관련 테스트가 통과했다. 결과와 소스 해시,
입력 제외 규칙, 모든 개발 실패/재시도 기록을 JSON의 evidence_artifacts와
run_selection에 묶었다. standalone 감사이므로 가짜 work-item/episode/독립
verifier 기록을 만들지 않았고 실제 실행 아티팩트를 직접 근거로 삼았다.

선호하는 해석에 대한 가장 큰 제약은 독립 재검증 부재다. 새 반례는 Explorer의
구체 재생을 통과했지만 독립 reference를 실행하지 않았다. 특히 C15/fault1,
C14_003/llm은 동결 REF-EQUIV-CHECKED 이력에 없던 차이를 드러냈다.
동결 이력의 무차이는 전칭 동등성 증명이 아니며, 새 차이도 아직 독립 검증된
E2 정답으로 세지 않는다. 구현자와 감사자가 같으므로 self-review다.

실패 사례를 보고 구현을 개선했고 평가 모집단도 명시적으로 수정했다.
이는 기술적으로 재현 가능한 개발 후속 결과이며, 독립 표본 기반 일반화
주장이나 확증 실험을 지지하지 않는다. 두 한계 유형은 이 140쌍에서 남은
원인을 설명하며 모든 JoI 프로그램의 지원 범위를 정의하지 않는다.

최소 후속 조치: E2 담당자가 새 DIVERGE witness를 기존 시간/바인딩 모델의
독립 reference에서 확인하고, 142→140 모집단 수정 근거를 포함한 새 E2
결과를 확정한다. 해당 작업 전에는 판정 완료율을 정확도나 독립 검증 일치율로
표현하지 않는다.

최종 v4 실행은 timestamp 별칭을 대기문 너머로 유지하는 형태를 거절하도록
범위를 좁힌 뒤 전체 142쌍을 재검사한 것이다. v3 전체 실행은 개발 선행
기록으로 보존하며 독립 반복 실험으로 세지 않는다.
