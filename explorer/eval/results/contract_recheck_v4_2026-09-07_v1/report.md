# 기존 Gemma4 후보 재검증 — 2026-09-07

기존 388개 ID 전체를 현재 계약으로 재검증했다. LLM 호출은 0회이며 기존 후보 SHA는 모두 일치한다.

| Explorer 판정 | 이전 | 현재 |
| --- | ---: | ---: |
| DIVERGE | 77 | 76 |
| EQUIV-BOUNDED | 203 | 207 |
| GENERATION_ERROR | 59 | 59 |
| INCONCLUSIVE | 1 | 1 |
| PREPARATION_ERROR | 2 | 2 |
| REFUSED | 46 | 43 |

실행 시간 171.1초. 검증 시간 범위는 3.2초, 외부 입력100ms/타이머1ms, 기존 자원 제한 유지.

유한 탐색 비교: 양쪽 완료 267건, 불일치 0건. 기호 인증 3건은 이 비교에 포함하지 않는다.

## 판정 변경

- C01_009: REFUSED → EQUIV-BOUNDED. 이전 이유: explicit input domain required for observable large/unbounded catalog value
- C01_017: REFUSED → EQUIV-BOUNDED. 이전 이유: return-assigned/effectful or unreviewed function cannot be a silent input: ('Speaker', 'Speak')
- C01_018: REFUSED → EQUIV-BOUNDED. 이전 이유: explicit input domain required for observable STRING return/value
- C21_001: DIVERGE → EQUIV-BOUNDED. 이전 이유: None

## 해석과 다음 작업

기호 값 흐름 지원으로 출력값을 전부 열거할 수 없던 사례를 인증한다. C01_017은 정답 IR의 VOID 반환 대입 교정도 포함하며, C01_018은 사용자가 확정한 non-null STRING 반환 계약에 따른다.
BOOL 두 값 정책·정답 교정·검증기 개선이 함께 반영됐으므로 판정 변화는 단일 변경의 효과를 측정한 ablation이 아니다.
남은 REFUSED에는 의도적인 지원 범위 제한과 생성 코드의 계약 위반이 함께 있다. 생성 실패·준비 오류·자원 한계는 모두 전체388건에 남겼다.
다음 우선순위는 C01_014 입력 조합 상한(UNKNOWN) 처리 검토와, 이 동결 결과·지원 범위를 논문의 bounded formal verification 설명에 연결하는 것이다.
새 후보 생성/미관측 held-out 평가가 아니며, 기존 사례에 대한 개발 재평가다. 평가 일치만으로 전체 실행기의 형식적 정확성을 증명하지 않는다.

상세 이유·케이스별 변화: [metrics.json](metrics.json). 원시 판정: [case_outcomes.jsonl](case_outcomes.jsonl).
