# E1 요청 92건의 최종 Timeline IR 연산자 집계

집계 단위: IR에 작성된 정적 `op` 노드. `start_at` 포함. 반복 본문·조건 분기·timeout 처리 내부까지 세되, 반복 실행 횟수는 곱하지 않는다. 조건식과 `for`, `timeout`, `until`, `period` 등의 속성은 별도 연산자가 아니다. 여러 Timeline으로 나눈 요청은 요청 단위로 합산한다.

## 전체 요약

- 요청 92건, Timeline 98개, 연산자 총 10,120개.
- 요청당 최솟값 3, 중앙값 7.0, 평균 110.00, 최댓값 7,803.
- E1-024는 600개 시간 슬롯을 펼친 최종 스프링클러 IR이다. 전체 집계에 포함했다. 이 한 건을 제외한 보조 집계: 91건, 총 2,317개, 중앙값 7, 평균 25.46, 범위 3–905개.

- E1-066(일산화탄소 감지 후 점멸) 905개와 E1-070(초인종 후 점멸) 606개도 150회 점멸을 명시적으로 펼친 IR이다. 이 두 건과 E1-024를 제외한 89건은 3–27개, 중앙값 7, 평균 9.06개이다. 이는 인코딩 방식이 정적 크기에 미치는 영향을 보여주는 보조 설명이며, 전체 92건 집계를 대체하지 않는다.

| 연산자 | 전체 등장 횟수 | 포함 요청 수 / 92 |
| --- | ---: | ---: |
| `start_at` | 98 | 92 |
| `call` | 2277 | 92 |
| `wait` | 750 | 67 |
| `delay` | 1225 | 14 |
| `read` | 3738 | 56 |
| `if` | 1312 | 72 |
| `cycle` | 703 | 88 |
| `break` | 17 | 8 |
| `timer` | 0 | 0 |
| `let` | 0 | 0 |

## 구조 특성

중첩 깊이는 한 경로에 놓인 `if`/`cycle`의 수이며 외부 감시 반복도 포함한다. 독립 Timeline 사이에서는 최댓값을 취한다. 종류 조합은 요청 단위의 동시 포함이며 같은 실행 경로에서 반드시 함께 실행된다는 뜻은 아니다.

| 지표 | 값 또는 분포 |
| --- | --- |
| 제어 중첩 깊이 → 요청 수 | {0: 2, 1: 25, 2: 51, 3: 10, 4: 4} |
| 반복 중첩 깊이 → 요청 수 | {0: 4, 1: 78, 2: 9, 3: 1} |
| start_at/call 제외 종류 수 → 요청 수 | {1: 2, 2: 13, 3: 38, 4: 33, 5: 5, 6: 1} |
| start_at/call 제외 서로 다른 종류 조합 | 18 |
| 기존 R 태그가 2개 이상 (행동 요소 수 아님) | 51 / 92 |
| 기존 요청 분류에서 경계 요소 포함 | 13 / 92 |

기존 R/B 태그는 복합 동작을 누락하거나 하나로 축약한 경우가 있어, 태그 수를 행동 요소 수 또는 복잡도로 해석하지 않는다. 새 92건 전수 검토는 E1_BEHAVIOR_REVIEW_KO.md를 참조한다. 요청의 R/B 태그와 최종 IR의 구조는 별개 지표다. 이벤트 감시나 재무장을 구현하려고 추가한 `cycle`도 구조 집계에 들어가므로, `cycle` 포함 빈도를 반복 행동을 요청한 비율로 해석하지 않는다.

## 요청별 집계

| 요청 | Timeline 수 | 총 연산자 | 종류 수 | 종류별 개수 |
| --- | ---: | ---: | ---: | --- |
| E1-001 | 1 | 10 | 5 | start_at 1, call 3, wait 3, cycle 2, break 1 |
| E1-002 | 1 | 7 | 5 | start_at 1, call 2, wait 2, delay 1, cycle 1 |
| E1-003 | 1 | 4 | 3 | start_at 1, call 2, delay 1 |
| E1-004 | 1 | 6 | 4 | start_at 1, call 1, wait 2, cycle 2 |
| E1-005 | 1 | 11 | 5 | start_at 1, call 3, wait 3, read 2, cycle 2 |
| E1-006 | 1 | 5 | 4 | start_at 1, call 1, wait 2, cycle 1 |
| E1-007 | 1 | 10 | 5 | start_at 1, call 2, read 4, if 2, cycle 1 |
| E1-008 | 1 | 7 | 5 | start_at 1, call 2, wait 2, if 1, cycle 1 |
| E1-009 | 1 | 3 | 3 | start_at 1, call 1, if 1 |
| E1-010 | 1 | 7 | 6 | start_at 1, call 2, wait 1, delay 1, if 1, cycle 1 |
| E1-011 | 1 | 5 | 4 | start_at 1, call 1, wait 2, if 1 |
| E1-012 | 1 | 8 | 6 | start_at 1, call 1, wait 2, read 1, if 2, cycle 1 |
| E1-013 | 1 | 5 | 4 | start_at 1, call 1, wait 2, cycle 1 |
| E1-014 | 1 | 5 | 4 | start_at 1, call 1, wait 2, cycle 1 |
| E1-016 | 1 | 7 | 6 | start_at 1, call 1, wait 1, read 2, if 1, cycle 1 |
| E1-019 | 1 | 7 | 6 | start_at 1, call 1, wait 1, read 2, if 1, cycle 1 |
| E1-020 | 1 | 15 | 6 | start_at 1, call 2, wait 5, read 4, if 2, cycle 1 |
| E1-021 | 1 | 7 | 5 | start_at 1, call 2, wait 2, if 1, cycle 1 |
| E1-022 | 1 | 7 | 5 | start_at 1, call 2, wait 2, if 1, cycle 1 |
| E1-023 | 1 | 11 | 6 | start_at 1, call 1, wait 1, read 5, if 2, cycle 1 |
| E1-024 | 1 | 7803 | 7 | start_at 1, call 1200, wait 600, delay 600, read 3601, if 1200, cycle 601 |
| E1-025 | 1 | 7 | 6 | start_at 1, call 1, wait 1, read 2, if 1, cycle 1 |
| E1-026 | 1 | 9 | 6 | start_at 1, call 1, wait 1, read 4, if 1, cycle 1 |
| E1-028 | 1 | 10 | 7 | start_at 1, call 1, wait 1, read 2, if 2, cycle 2, break 1 |
| E1-029 | 1 | 5 | 4 | start_at 1, call 1, wait 2, cycle 1 |
| E1-030 | 1 | 5 | 4 | start_at 1, call 1, wait 2, cycle 1 |
| E1-031 | 1 | 27 | 7 | start_at 1, call 1, wait 6, read 3, if 6, cycle 3, break 7 |
| E1-032 | 1 | 7 | 6 | start_at 1, call 1, wait 1, read 2, if 1, cycle 1 |
| E1-033 | 1 | 11 | 6 | start_at 1, call 2, wait 1, read 4, if 2, cycle 1 |
| E1-034 | 1 | 6 | 4 | start_at 1, call 2, wait 2, cycle 1 |
| E1-035 | 1 | 5 | 4 | start_at 1, call 1, wait 2, cycle 1 |
| E1-038 | 1 | 7 | 6 | start_at 1, call 1, wait 1, read 2, if 1, cycle 1 |
| E1-039 | 1 | 5 | 4 | start_at 1, call 1, wait 2, cycle 1 |
| E1-040 | 1 | 7 | 5 | start_at 1, call 2, wait 2, if 1, cycle 1 |
| E1-041 | 1 | 7 | 6 | start_at 1, call 1, wait 1, read 2, if 1, cycle 1 |
| E1-042 | 1 | 11 | 6 | start_at 1, call 4, wait 1, read 2, if 2, cycle 1 |
| E1-043 | 1 | 7 | 6 | start_at 1, call 1, wait 1, read 2, if 1, cycle 1 |
| E1-044 | 1 | 8 | 6 | start_at 1, call 2, wait 1, read 2, if 1, cycle 1 |
| E1-045 | 1 | 8 | 6 | start_at 1, call 1, wait 3, read 1, if 1, cycle 1 |
| E1-046 | 1 | 7 | 5 | start_at 1, call 2, wait 2, if 1, cycle 1 |
| E1-047 | 1 | 7 | 6 | start_at 1, call 1, wait 1, read 2, if 1, cycle 1 |
| E1-048 | 1 | 7 | 5 | start_at 1, call 2, wait 2, if 1, cycle 1 |
| E1-049 | 1 | 7 | 5 | start_at 1, call 2, wait 2, if 1, cycle 1 |
| E1-050 | 1 | 7 | 5 | start_at 1, call 2, wait 2, if 1, cycle 1 |
| E1-051 | 1 | 7 | 6 | start_at 1, call 1, wait 1, read 2, if 1, cycle 1 |
| E1-052 | 1 | 7 | 5 | start_at 1, call 2, wait 2, if 1, cycle 1 |
| E1-053 | 1 | 7 | 5 | start_at 1, call 2, wait 2, if 1, cycle 1 |
| E1-054 | 1 | 6 | 5 | start_at 1, call 1, read 2, if 1, cycle 1 |
| E1-055 | 1 | 7 | 5 | start_at 1, call 2, read 2, if 1, cycle 1 |
| E1-056 | 1 | 6 | 5 | start_at 1, call 1, read 2, if 1, cycle 1 |
| E1-057 | 1 | 9 | 5 | start_at 1, call 2, read 2, if 3, cycle 1 |
| E1-058 | 1 | 8 | 5 | start_at 1, call 2, read 2, if 2, cycle 1 |
| E1-059 | 1 | 8 | 5 | start_at 1, call 3, read 2, if 1, cycle 1 |
| E1-060 | 1 | 9 | 5 | start_at 1, call 4, read 2, if 1, cycle 1 |
| E1-061 | 1 | 12 | 5 | start_at 1, call 3, read 4, if 3, cycle 1 |
| E1-062 | 1 | 13 | 6 | start_at 1, call 4, wait 1, read 2, if 4, cycle 1 |
| E1-063 | 1 | 14 | 6 | start_at 1, call 5, delay 4, read 2, if 1, cycle 1 |
| E1-064 | 1 | 7 | 5 | start_at 1, call 2, read 2, if 1, cycle 1 |
| E1-065 | 1 | 7 | 5 | start_at 1, call 1, read 2, if 2, cycle 1 |
| E1-066 | 1 | 905 | 6 | start_at 1, call 600, delay 300, read 2, if 1, cycle 1 |
| E1-067 | 1 | 11 | 5 | start_at 1, call 2, read 4, if 3, cycle 1 |
| E1-068 | 1 | 11 | 5 | start_at 1, call 2, read 4, if 3, cycle 1 |
| E1-069 | 1 | 6 | 5 | start_at 1, call 1, read 2, if 1, cycle 1 |
| E1-070 | 1 | 606 | 6 | start_at 1, call 300, delay 300, read 2, if 2, cycle 1 |
| E1-071 | 1 | 8 | 5 | start_at 1, call 3, read 2, if 1, cycle 1 |
| E1-072 | 1 | 8 | 6 | start_at 1, call 2, wait 1, read 1, if 2, cycle 1 |
| E1-073 | 1 | 6 | 5 | start_at 1, call 1, read 2, if 1, cycle 1 |
| E1-074 | 1 | 8 | 5 | start_at 1, call 2, read 3, if 1, cycle 1 |
| E1-075 | 1 | 17 | 5 | start_at 1, call 6, read 6, if 3, cycle 1 |
| E1-076 | 1 | 6 | 5 | start_at 1, call 1, read 2, if 1, cycle 1 |
| E1-077 | 1 | 6 | 5 | start_at 1, call 1, read 2, if 1, cycle 1 |
| E1-078 | 1 | 15 | 8 | start_at 1, call 2, wait 3, delay 1, read 4, if 1, cycle 2, break 1 |
| E1-079 | 1 | 5 | 5 | start_at 1, call 1, wait 1, read 1, cycle 1 |
| E1-080 | 1 | 6 | 4 | start_at 1, call 1, wait 3, cycle 1 |
| E1-081 | 1 | 10 | 6 | start_at 1, call 1, wait 4, if 1, cycle 2, break 1 |
| E1-082 | 1 | 7 | 6 | start_at 1, call 1, wait 2, read 1, if 1, cycle 1 |
| E1-084 | 1 | 8 | 6 | start_at 1, call 2, wait 1, read 1, if 2, cycle 1 |
| E1-085 | 1 | 8 | 6 | start_at 1, call 2, wait 1, read 1, if 2, cycle 1 |
| E1-086 | 1 | 23 | 6 | start_at 1, call 10, wait 4, if 3, cycle 1, break 4 |
| E1-087 | 1 | 16 | 7 | start_at 1, call 3, wait 3, read 4, if 2, cycle 2, break 1 |
| E1-088 | 1 | 7 | 6 | start_at 1, call 1, wait 1, read 2, if 1, cycle 1 |
| E1-089 | 1 | 13 | 6 | start_at 1, call 4, wait 1, read 1, if 5, cycle 1 |
| E1-090 | 1 | 9 | 6 | start_at 1, call 2, wait 3, delay 1, if 1, cycle 1 |
| E1-092 | 2 | 14 | 4 | start_at 2, call 6, wait 2, delay 4 |
| E1-093 | 3 | 20 | 5 | start_at 3, call 3, wait 9, delay 2, cycle 3 |
| E1-094 | 2 | 20 | 5 | start_at 2, call 6, wait 6, delay 4, cycle 2 |
| E1-095 | 1 | 20 | 6 | start_at 1, call 1, wait 2, delay 5, read 10, cycle 1 |
| E1-096 | 1 | 9 | 5 | start_at 1, call 2, wait 3, if 2, cycle 1 |
| E1-097 | 3 | 22 | 6 | start_at 3, call 4, wait 9, delay 1, if 2, cycle 3 |
| E1-098 | 1 | 7 | 4 | start_at 1, call 1, wait 4, cycle 1 |
| E1-099 | 1 | 12 | 7 | start_at 1, call 1, wait 3, read 2, if 2, cycle 2, break 1 |
| E1-100 | 1 | 7 | 5 | start_at 1, call 1, wait 3, if 1, cycle 1 |

## 근거와 재현

실험을 재실행하지 않고 저장된 IR만 읽었다. 기존 12건은 결과 JSON에 IR이 없어 현재 `irs.py`의 정의를 사용했다. 나머지 80건은 실행 결과에 저장된 IR을 사용하되, E1-024는 최종 실행 기록의 SHA-256과 일치하는 교체 IR을 사용했다. 초기 실패 IR, 별도 진단용 변형, JOI 대체 구현은 중복 집계하지 않았다.

입력 파일 해시·Timeline별 세부 수치는 `e1_operator_counts.json`, 92건의 열별 수치는 `e1_operator_counts.csv`에 저장했다.

재현: `python count_e1_operators.py` (이 파일과 같은 폴더).
