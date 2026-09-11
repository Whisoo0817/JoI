# 유사 파이프라인 논문의 평가 방식과 VETS 비교 후보

2026-09-10. 사용자 질문: 다른 논문과 비교해야 하지 않는가? 의도 확정과 구현 보존을 함께 다루는 시스템은 무엇으로 평가하는가?
위치: Evaluation의 외부 baseline 선택 및 전체/단계별 평가 계약. **검토 및 제안이며 프로토콜 확정이 아니다.**

## 1. 확인한 선행의 실제 실험

### ChatIoT — IMWUT 2024

- [저자 원문](https://www.emnets.cn/zh/publication/ubicomp-24-chatiot/chatiot.pdf), §§5.1–5.3, 5.5.3; 기존 로컬 변환본 `/tmp/vets-related-20260909/ChatIoT.txt` 확인.
- 생성 비교: Zero-shot, 3-example CoT, ReAct, context 압축을 제거한 ChatIoTLite, 전체 ChatIoT.
- 요청별로 사람이 TAP 정답을 미리 만들고 생성 정확도와 token 비용을 평가한다. 확인한 문구만으로 이 정확도를 전 입력 timed ACTION 동등성으로 해석하지 않는다.
- Home Assistant 환경을 기기 수 5/10/20/30으로 나누고 카메라 관련/비관련 요청을 구별한다.
- preprocessor/evaluator 유무 ablation 및 별도 모델 customization 실험도 수행한다.
- 사용자 15명의 요청 60개와 수작업 정답 규칙을 사용한 평가도 있다. 이 사실을 대조군이 있는 사용자 이해도 실험이라고 확장하지 않는다.
- 함의: 외부 방법(ReAct 등), 기본 생성 방법, 자기 시스템 ablation을 함께 사용한다. 비교 대상이 반드시 동일한 전체 시스템일 필요는 없다.

### AwareAuto — arXiv 2024 검토본

- [원문](https://arxiv.org/html/2408.12687v1), §§5.1–5.4.
- 단계별 지표: Intent Consistency(논리 correctness + completeness), Feasibility(실행 가능성과 환경 적합성), 전체 Inference Success Rate.
- 205개 복합 요청을 평가하고 시간 trigger, 시간 의존 action, 분기, 복합 구성 등으로 나눠 오류를 분석한다.
- **grounding 단계만 평가할 때 앞단 NL 규칙을 수작업으로 수정해 의도 일치를 확보한다.** 이는 oracle intermediate를 이용한 단계 분리 평가이며 자동 end-to-end 결과와 다르다.
- 사용자 10명, 50개 규칙 작성 과정에서 성공까지의 상호작용 횟수를 평가한다.
- 해당 평가 절에서는 여러 외부 시스템의 종합 순위표보다 단계별 성공·오류 분석·상호작용 평가가 중심이다. arXiv 원고이므로 이 구성이 PerCom의 충분조건이라고 추론하지 않는다.
- 원문의 48/50 옆 94% 표기 등 숫자 불일치가 있어 이번 제안에서는 headline 수치 재인용을 피한다.
- 함의: 의도 확인이 개입되어도 앞단 품질, 정답 중간 표현을 조건으로 한 뒤쪽 성능, 실제 상호작용 성공을 구별해 평가할 수 있다.

### AutoTap — ICSE 2019

- [저자 원문](https://hewj.info/papers/autotap.pdf), §VI A–D; `/tmp/formal_prior_read/autotap.txt` 대조.
- 의도 표현: 같은 과제를 TAP 규칙 UI 또는 property UI로 표현하게 하는 사용자 간 무작위 배정 비교. 유효 참여자 78명, 총 14개 과제 중 개인별 7개.
- 두 연구자가 정답/부분 정답/오답으로 독립 판정하고 불일치를 조정한다. 자신감·난이도·SUS도 평가한다. 과제 모집단이 property에 유리할 수 있음을 논문이 인정한다.
- 합성: 전문가가 작성한 명세의 14개 과제와 사용자가 올바르게 작성한 158개 property set으로 평가; 후자는 157개 합성 성공.
- 수정: 10개 올바른 프로그램에서 만든 25개 mutation에 대해 23개 수정 성공. 이는 property 만족 기준이며 원래 프로그램과의 동등 복원을 뜻하지 않는다.
- 다중 property 결합과 충돌 시나리오도 평가한다.
- 함의: 명세 만족을 보장하는 알고리즘도 모든 입력을 해결할 수 있는 것은 아니다. 성공률/지원 범위/실패 사례와 사용자 표현 정확도는 별도 평가 대상이다.

### ARTEMIS — ICSE 2026

- [저자 원문](https://cs.stanford.edu/~trippel/pubs/mendoza_ICSE26.pdf), §§7.1–7.3; 기존 `artemis_deep.md`와 `/tmp/formal_prior_read/artemis.txt` 대조.
- 번역: directTL 계열, nl2spec, SynthTL, NL2TL+ 및 fine-tuned 변형과 비교. 일부는 공통 과제에 맞게 adaptation한다.
- 정답: 전문가가 인정한 plausible 명세들과 LTL 동등성으로 비교. k=10 후보 중 하나 이상 정답이 포함되는 요청 비율이며 top-1 또는 인간의 최종 선택 정확도가 아니다.
- 복잡도별 번역 효과 및 구별 trace 수/표시 변수 수/생성 비용을 측정한다.
- 사용자 응답은 plausible 명세로 시뮬레이션한다. 질문 수 감소를 실제 인간 이해도 향상과 동일시하지 않는다.
- 함의: 명세 validation을 포함한 시스템도 validation 이전 생성 성능과 validation의 비용을 분리한다.

## 2. 기존 제안에 대한 정정

Direct NL / 정보가 같은 prose / flat / Timeline은 기본 비교와 표현 ablation이다. 기존 연구 대비 효과를 모두 대신하지 않는다.
반대로 다른 논문 이름이 붙어 있다는 이유만으로 다른 목적의 도구를 같은 숫자로 비교하는 것도 부적절하다.

현재 가까운 외부 생성 방식 후보는 ChatIoT의 요청 전처리 → 생성 → evaluator 절차다. JoI에 맞게 적용한다면 `ChatIoT-inspired/adapted`임을 명시하고 핵심 기능, API/doc 및 budget 조건을 기록한다. 재현 가능성과 공통 표현 범위는 아직 확인하지 않았다. 원래 HA 결과와 JoI 결과를 단순 정확도 비교하지 않는다.
AwareAuto도 authoring/grounding 단계 비교 후보이지만 공개 구현과 동일 과제 처리 가능성을 확인한 후 채택한다.
ARTEMIS는 명세 후보 생성 단계의 공통 subset 비교 후보이며, 코드 생성 end-to-end baseline으로 바로 사용할 수 없다.
AutoTap은 사용자 표현 평가 및 합성 평가 설계의 참고 선행이다. property satisfaction 도구를 timed ACTION 동등성 검사의 직접 정확도/속도 baseline으로 삼지 않는다.

## 3. VETS가 측정할 수 있는 두 계약

입력 요청 R, 독립적으로 확정한 과제 행동 G, 시스템 생성 Timeline S, 생성 플랫폼 코드 P를 구별한다.

1. 의도 일치: S가 G를 표현하는가? R이 모호하면 허용 gold 집합 또는 실제 사용자의 명시적인 선택이 필요하다. 선택 버튼 자체를 정답 oracle로 사용하지 않는다.
2. 구현 보존: P가 확정 S의 timed ACTION을 보존하는가? 올바른 명세를 사람이 미리 제공하는 실험은 이 단계의 조건부 평가다.
3. 전체 성공: 최종 P가 G에 맞으며 시스템이 정해진 예산 내 결과를 제공하는가? 뒤쪽이 S를 완벽히 보존해도 S가 G와 다르면 전체 실패다.

검증기의 EQUIV 결과를 같은 검증기의 정확성을 입증하는 독립 정답으로 사용하지 않는다. reference/target interpreter 적합성, 독립 소형 oracle 및 반례 replay 등의 검증 근거를 별도로 둔다. 통과율은 외부 baseline보다 잘했다는 성능 지표와 동일하지 않다.

## 4. 권고하는 중심 성과와 보완 실험

강제로 “Timeline이면 LLM 생성 정확도가 더 높다”를 주기여로 만들 필요는 없다. 표현 효과는 검증할 가설이다.
본체 성과 후보: **명시적으로 확정한 행동에 대해, 구현 불일치를 검출하면서 충분한 수의 요청에 검증된 코드를 제공하는가?**

이를 함께 측정한다:

- 요청 전체 중 올바른 결과를 제공한 비율(명세 확정 비용의 조건을 명시).
- 통과시킨 코드 중 잘못된 코드의 비율 및 독립 평가 근거.
- 올바른 코드의 거절, 지원 밖, 탐색 미완료, timeout의 구분.
- 전체/단계별 시간, token, 필요한 경우 수정 횟수.

전부 거절하면 통과된 오류가 없어도 유용한 시스템이 아니므로 결과 제공률과 함께 제시한다.
검증만으로 원래 생성 코드가 수정되지는 않는다. repair를 구현하지 않으면 검증의 효과는 오류 발견/거절과 보장 제공이며 생성 성공률 증가로 쓰지 않는다.

최소 후보 구성:
1. 외부 방식과의 비교: 가장 가까운 재현 가능한 authoring/code-generation 방식 하나 + Direct NL.
2. 자기 시스템 ablation: Timeline만/Timeline+Explorer, 필요하면 information-matched prose로 표현 효과 분리.
3. 구현 보존 평가: 공통 확정 명세와 code pairs에서 오류 검출, 완료율, 비용; 동일 문제의 replay/testing/LLM review 비교 가능성을 검토.
4. end-to-end 실제 JoI 실행 사례: 복합 시간·상태 행동과 검증 반례가 플랫폼 동작에 연결됨을 확인. 전 입력 보장을 실제 장치 사례만으로 주장하지 않는다.

사용자 의도 확인의 효과를 본문 주기여로 주장하려면 사용자 실험 또는 적절히 제한된 대리 평가가 필요하다. 현 구조만으로 사용자 확인의 정확성 향상을 증명했다고 쓰지 않는다.

이 문서는 외부 baseline 선정의 필요성을 보완하는 검토다. baseline 구현, 새 실험 실행 또는 기존 프로토콜 변경은 수행하지 않았다.
