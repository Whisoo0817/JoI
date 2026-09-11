# ARTEMIS 정밀 검토

2026-09-09. 논문 내 위치는 Introduction의 문제 설정과 Related Work의 직접 선행 비교다.

## 1. 출판·원문·검토 범위

Daniel Mendoza, Anastasia Mavridou, Andreas Katis, Caroline Trippel. *Automating Requirements Formalization: Using LLMs and Low-Complexity Distinguishing Traces for Semantic Validation*. ICSE 2026, 13 pages. DOI [10.1145/3744916.3787815](https://doi.org/10.1145/3744916.3787815).

- [저자 원문 PDF](https://cs.stanford.edu/people/trippel/pubs/mendoza_ICSE26.pdf): §§2–7, 특히 proxy 정의·생성, balanced trace, 평가 조건을 확인했다.
- [공개 구현](https://github.com/dmmendo/ARTEMIS): commit `9d809bbc95aa55692496c9e7486c65dfc2615d44`의 README, trace generation, 중복 제거 경로와 ProxyCheck 설명을 확인했다.
- 설치·실행 재현이나 코드 전체의 정당성 검증은 수행하지 않았다.

## 2. 방법

ARTEMIS는 자유 NL 요구를 트리로 분해하고 각 노드에 structured NL 후보를 생성한다. 사용자는 분해의 누락·추가를 확인한다. 각 후보를 proxy temporal formula로 변환한 다음 후보를 다르게 분류하는 trace를 제시하고, 사용자의 accept/reject 답으로 후보를 제거한다. 최종 산출물은 선택한 fragment들을 조합한 structured NL/temporal-logic specification이다.

FRETish의 scope, condition, timing, response를 사용하며 `upon`과 `whenever`, 즉시·다음 시점·언젠가·정해진 tick 이내 등을 구별한다. 따라서 temporal 정보를 명시하는 중간 표현 자체를 VETS의 새 기여로 주장할 수 없다.

### Proxy

한 노드의 해석을 결정할 때 전체 요구의 변수를 모두 보여주는 부담을 줄이기 위해 후보 차이를 보존하는 작은 명세를 만든다.

- Standard proxy는 각 부모 문맥에 대해 후보 공통 문맥 trace가 존재하여 proxy와 원 명세 판정이 대응하는 조건 아래 조상 문맥 변수를 제거한다.
- Abstract proxy는 자손 조건을 새 atomic proposition으로 바꾸되 자손 proxy와 일관되게 대응하는 조건을 검사한다. 조건이 성립하지 않으면 standard proxy를 쓴다.
- structured-NL grammar의 유한 template에서 후보 proxy를 만들고 ProxyCheck로 적합성을 검사한다.

### Balanced distinguishing trace

한 trace가 남은 후보를 가능한 한 균형 있게 나누도록 다음 목적을 사용한다.

```text
min(trace를 허용하는 후보 수, trace를 허용하지 않는 후보 수)를 최대화
```

후보들이 상호 배타적이면 최악 응답에서 하나만 제거될 수 있으므로, 매 질문마다 절반 제거하거나 임의 후보 집합에서 로그 질문 수를 보장하지 않는다.

### 의미 동등 후보 제거

공개 코드의 `remove_duplicate_proxies`는 proxy 제약 아래 의미가 같은 후보를 묶어 대표를 남긴다. `remove_equivalent_idx_old`는 설정에 따라 Spot automata equivalence 또는 model-checker 경로를 사용한다. 따라서 의미 동등 후보 제거와 distinguishing trace 자체도 선행으로 인정해야 한다.

## 3. 평가 조건

| 항목 | 실제 평가와 의미 |
|---|---|
| 데이터 | Ventilator 121, Robotics 46, LMCPS 15, DeepSTL 14, Thales 22: 총 218 요구 |
| 표현 변환 | DeepSTL 수치 predicate를 AP로 추상화하고 metric time을 전문가가 이산화하여 FRETish로 변환 |
| 번역 정확도 | 요청마다 10개 후보 중 전문가 specification과 LTL 동등한 것이 적어도 하나 있는 비율; 사용자 최종 선택 정확도는 아님 |
| 후보 생성 실패 | 최대 1,000개 생성 후에도 14.22% 요구에서 plausible 후보를 얻지 못함 |
| 사용자 검증 평가 | 실제 user study가 아니라 전문가 명세로 accept/reject를 시뮬레이션 |
| 정답 존재 전제 | 비교 실험에서 후보 집합에 expert-curated specification을 추가 |
| 질문 수 | 전체 평균 1.74배 감소; 후보가 10개 초과인 부분집합은 평균 2.52배 감소 |
| 표시 복잡도 | trace 변수 수 평균 3.33, baseline 대비 평균 1.40배 감소; trace 길이는 평균 3.1 대 2.61로 더 김 |
| trace 생성 비용 | 평균 18.89초, 표준편차 121.76초, 최대 2437.30초 |

trace 길이 제한 20은 lasso의 prefix와 cycle을 합친 표현 길이다. 이를 20개 시점만 테스트한 결과로 해석하지 않는다. 실제 사용자 이해·선택 정확도를 검증한 연구도 아니다.

## 4. VETS에 주는 함의

ARTEMIS는 요구의 해석을 선택하고 temporal specification을 확정하는 선행이다. VETS의 현재 중심은 올바르게 확정한 Timeline을 출발점으로 플랫폼 JoI를 생성하고, 생성 코드가 기준 timed ACTION을 보존하는지 검사하는 것이다.

따라서 Related Work에서는 다음을 분명히 한다.

1. temporal 정보를 명시하는 structured representation과 semantic validation은 선행이 있다.
2. ARTEMIS의 최종 산출물은 검토된 structured NL/temporal specification이며, 별도로 생성한 플랫폼 코드의 행동 보존 검사는 다루지 않는다.
3. 코드 의미 보존 자체에도 translation validation 선행이 있으므로, VETS의 차이는 스마트홈의 시간·상태 실행 모델, ACTION 관측 계약, 지원 범위와 인증 조건에서 구체화해야 한다.
4. ARTEMIS의 사용자 검토 단계와 VETS의 올바른 Timeline 확정 가정은 구별한다. VETS는 현재 사용자 이해도 향상을 주장하지 않는다.
