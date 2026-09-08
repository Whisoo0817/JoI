# 기존 Gemma4 후보 재검증 — 2026-09-07

기존 388개 ID 전체를 현재 계약으로 재검증했다. LLM 호출은 0회이며 기존 후보 SHA는 모두 일치한다.

| Explorer 판정 | 이전 | 현재 |
| --- | ---: | ---: |
| DIVERGE | 76 | 76 |
| EQUIV-BOUNDED | 208 | 208 |
| GENERATION_ERROR | 59 | 59 |
| PREPARATION_ERROR | 2 | 2 |
| REFUSED | 43 | 43 |

실행 시간 175.9초. 검증 시간 범위는 3.2초, 외부 입력100ms/타이머1ms, 기존 자원 제한 유지.

유한 탐색 비교: 양쪽 완료 267건, 불일치 0건. 기호 인증 4건은 이 비교에 포함하지 않는다.

## 판정 변경

최종 Explorer 판정 변경 없음: 388건 모두 이전과 같다.

## 기호 검증 경로

- C01_006: `smt-linear-trace-v1` → REFUSED. 이유: SMT ACTION domain is not universally valid: SetChannel
- C01_009: `symbolic-value-flow-v1` → EQUIV
- C01_014: `symbolic-value-flow-v1` → EQUIV
- C01_017: `symbolic-value-flow-v1` → EQUIV
- C01_018: `symbolic-value-flow-v1` → EQUIV

## 해석과 다음 작업

기호 인증은 지원하는 전체 입력 도메인을 대상으로 하며 유한 대표값 열거기와의 판정 일치 수치에서 분리한다. 새 경로 진입과 최종 판정 개선은 구분한다.
이전 실행 대비 reference payload 변경은 0건이다. 모델·소스 변경 내역은 protocol과 metrics에 기록했다. 기존 사례를 본 뒤 수행한 개발 재평가이며 독립 표본이나 통제된 성능 실험이 아니다.
남은 REFUSED에는 의도적인 지원 범위 제한과 생성 코드의 계약 위반이 함께 있다. 생성 실패·준비 오류·자원 한계는 모두 전체388건에 남겼다.
다음은 이 동결 결과·지원 범위·증명 근거를 논문의 bounded formal verification 설명에 연결하는 것이다. 미완료 또는 새 불일치가 있으면 먼저 원인을 조사한다.
새 후보 생성/미관측 held-out 평가가 아니며, 기존 사례에 대한 개발 재평가다. 평가 일치만으로 전체 실행기의 형식적 정확성을 증명하지 않는다.

상세 이유·케이스별 변화: [metrics.json](metrics.json). 원시 판정: [case_outcomes.jsonl](case_outcomes.jsonl).
