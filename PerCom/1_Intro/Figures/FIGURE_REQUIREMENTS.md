# Introduction Figure 1·2 및 Table 1 후속 작업 체크리스트

작성일: 2026-09-12. 사용자 요청을 정리한 작업 기준이며 실제 그림·코드·실험은 아직 변경하지 않았다.

## 배치 결정

Figure 1, Figure 2, Table 1은 모두 **Introduction**에 둔다.

| Exhibit | Introduction에서 하는 일 | 상세 근거 위치 |
| --- | --- | --- |
| Figure 1 | 같은 행동의 서로 다른 구현 idiom과 그럴듯한 오류를 보여주어 syntax만으로 행동 보존을 판단할 수 없음을 설명 | 예제 의미와 trace는 Introduction 본문 및 Method의 관찰 계약 |
| Figure 2 | trace-equivalent rewrite에 따라 LLM judge 판정이 달라지는 양상을 rewrite 유형별로 제시 | 전체 protocol·pair 수·통계·robustness는 Evaluation 또는 Appendix |
| Table 1 | judge 설정별 전체 판정 flip과 identity baseline을 압축해 Figure 2의 동기 결론을 뒷받침 | 전체 결과표와 재현성 자료는 Evaluation 또는 Appendix |

Figure 2와 Table 1은 VETS의 성능 평가가 아니라 **왜 LLM judge를 deterministic deployment gate로 채택하지 않는가**를 뒷받침하는 motivating experiment다. 따라서 독자가 설계 선택을 만나기 전에 Introduction에서 제시한다. 결과를 재현하고 통계적으로 판단하는 데 필요한 세부 방법까지 Introduction에 밀어 넣지는 않는다. Evaluation에는 이 실험이 core E1–E4와 다른 motivation study임을 표시하고 상세 protocol 또는 Appendix 링크를 둔다.

최종 원고에서 Figure 1·2와 Table 1보다 앞에 다른 numbered exhibit를 배치하지 않는다. System Overview 그림은 이 셋 뒤의 다음 Figure 번호를 사용한다.

## Fig1 — 코드 형태와 시간 행동의 관계를 읽히게 하기

목적: 의미적으로 같은 다른 idiom과, 겉보기에는 그럴듯하지만 행동이 다른 구현을 함께 보여준다. 핵심은 문법 모양과 timed ACTION 보존이 일치하지 않는다는 점이다.

- [ ] 코드 폰트를 통일하고 최종 논문 크기에서 읽히도록 조정한다.
- [ ] 특정 단어·핵심 줄을 일관된 강조색으로 표시한다. 색에만 의존하지 않고 설명·라벨을 함께 둔다.
- [ ] 코드 line number를 추가해 본문과 캡션에서 참조한다.
- [ ] 각 구현에 중복된 cron boilerplate를 제거하고 필요한 공통 실행 전제는 캡션에 한 번 명시한다.
- [ ] 코드 블록의 period 표기를 제거하고 공통 문구 `All implementations execute every 1 s`를 표시한다.
- [ ] `:=`에 `persistent initialization` 주석을 붙여 매 회차 재초기화와 구분한다.
- [ ] 첫 구현의 `prev ≤ 25 && current > 25`를 강조한다.
- [ ] 다른 구현의 `!triggered`를 강조한다.
- [ ] 대비 구현의 level condition 또는 `wait until`을 강조한다.
- [ ] `Platform boilerplate is omitted.`를 명시한다.
- [ ] 올바른 구현들이 공유하는 행동과 대비 구현이 어긋나는 입력 이력·ACTION을 캡션 또는 본문에서 연결한다.

주의: `!triggered`만으로 rising-edge 재무장 의미가 결정되지 않는다. flag reset·이전 값 갱신 순서도 확인한다. level/wait 자체를 항상 잘못된 연산처럼 표시하지 않고, 해당 요청에서 원하는 행동과의 차이를 설명한다.

`All implementations execute every 1 s`는 모든 예제에 실제로 같은 1초 평가 일정이 성립할 때 사용한다. 현재 JoI 모델의 period는 회차 종료 후 대기이므로, 그림에 blocking wait/delay가 포함되면 이 문구가 맞는지 먼저 확인한다. 문구에 맞추기 위해 실행 의미를 조용히 바꾸지 않는다. 실행 전제와 생략 범위를 캡션에서 정확히 한정한다.

## Fig2 — 의미 보존 변환에 대한 judge 판정 불변성

### 목적과 선행연구 위치

검사 질문: **같은 요청에 대한 trace-equivalent code의 표현만 달라졌을 때 deploy/reject 판정이 얼마나 바뀌는가?**

`Don’t Judge Code by Its Cover: Exploring Biases in LLM Judges for Code Evaluation`은 코드의 의미와 무관한 표면적 변화가 LLM judge 평가에 영향을 줄 수 있음을 다룬다. 이를 새로운 일반 현상으로 재주장하지 않는다. 우리 초점은 reactive-temporal IoT code, 확정된 행동, temporal/logic idiom, 배포 허용 판정의 관계다. [EACL 2026 원문 및 서지](https://aclanthology.org/2026.findings-eacl.70/)

### 기본 절차

1. 원본 프로그램, 요청, 확정 행동·binding, 변환 규칙을 선정·동결한다.
2. 의미 보존 변환을 적용하고, 같은 입력·초기 상태·시간·ACTION 계약에서 원본과 변환본의 동등성을 확인한다.
3. judge에게 NL과 원본 code를 주고 deploy/reject 판정을 받는다.
4. 동일한 요청·설정으로 변환 code를 독립적으로 제시해 판정을 받는다. 앞선 응답이 다음 응답에 노출되지 않게 한다.
5. 원본–변환본의 판정 불일치 비율을 집계하고, **동일 code를 반복 제시한 identity baseline**과 비교한다.

원래 사용자 구상의 NL+code 조건을 보존한다. 다만 `confirmed specification에 대한 deployment`까지 결론을 내리려면 judge가 받은 NL이 초기 상태·재무장·시간 의미를 충분히 고정하는지 확인해야 한다. 필요하면 같은 확정 계약·binding을 제공하는 조건을 별도로 설계한다. 자연어의 미해결 모호성을 code surface 효과로 계산하지 않는다.

### 변환 후보와 의미 보존 조건

| 변환 | 먼저 확인할 사항 |
| --- | --- |
| Variable renaming | 이름 충돌·scope·서비스명·문자열 참조·persistent 변수 대응 |
| Comparator 반전 | 예: `a > b`와 `b < a`; 타입·결측·평가 부작용 보존. 단순 논리 부정은 별도 검증 |
| if/else branch 교환 | guard 부정, 평가 시점·횟수, short-circuit·부작용 보존 |
| Loop unrolling | 유한 회차 수, break, snapshot, timer, period, ACTION 순서·시각 보존 |
| Temporal/logic idiom 교체 | edge·재무장·sustain reset·flag 갱신과 호출 시각까지 동등해야 함 |

이들은 후보 목록이며 아직 모든 변환의 의미 보존이 확인된 것은 아니다. 최종 출력값이 같거나 nominal trace 하나가 같다는 이유로 timed trace equivalence를 선언하지 않는다.

### 재현성 필수 기록

- [ ] 원본 프로그램의 출처·선정 규칙, 난이도·행동 유형, 원본 수와 rewrite별 pair 수.
- [ ] 원본·변환 code, 변환 도구/규칙 버전, 코드 hash, 제외 사례와 이유.
- [ ] 원본 프로그램이 확정 명세에 맞는지에 대한 별도 근거. 원본–변환본의 동등성은 둘의 정답성을 뜻하지 않는다.
- [ ] judge의 정확한 system/user prompt와 제공한 NL·명세·API·binding 자료.
- [ ] 모델의 정확한 버전, temperature 등 생성 설정, 반복 횟수, 실행 시각·호출 조건.
- [ ] 원본/변환본 제시 순서, 독립 세션 여부, 순서 효과 통제.
- [ ] 동등성 확인에 사용한 모델·입력 영역·초기 상태·입력 간격·horizon 또는 폐쇄 조건·자원 상한.
- [ ] ACTION 비교 기준: 대상·인자·중복·순서·시각, 시간 오차 허용 여부.
- [ ] bounded trace equivalence라면 그 H 밖의 동등성은 미확인으로 표시.
- [ ] 검증기와 oracle의 공유 구현·순환 평가 가능성. 독립 변환 논증·검토가 있는지 표시.
- [ ] temperature 0에서도 동일 prompt/code를 반복한 identity baseline. temp 0을 응답 불변성의 증명으로 취급하지 않음.
- [ ] deploy→reject와 reject→deploy를 구분하고 malformed/abstain/error 처리·전체 분모를 공개.
- [ ] pair별 판정과 집계 코드, confidence interval 또는 사전 선택한 통계 검정.
- [ ] 같은 원본에서 만든 여러 rewrite·반복 응답을 독립 표본으로 간주하지 않는 불확실성 추정. 예: 원본 프로그램 단위 cluster bootstrap.

핵심 지표는 유효한 paired 판정에서 `J(original) ≠ J(rewrite)`인 비율이다. 유효 pair의 수와 전체 시도 수를 함께 보고한다. identity 반복에도 같은 집계 규칙을 적용하며, rewrite 효과와 반복 호출 변동을 구분한다. figure 형식은 rewrite별 flip rate와 identity baseline, 불확실성 구간을 비교할 수 있게 선택한다.

### 결론의 강도

유지할 논점: **LLM judge의 판정을 곧바로 행동 보존 보증을 주는 deployment gate로 취급할 수 있는가?**

조건을 충족한 실험에서 판정 차이가 관찰되면, 평가한 judge·프로그램·변환·설정에서 의미 보존에 대한 판정 불변성이 깨졌다고 쓸 수 있다. identity baseline보다 높은 차이가 확인되면 표면 변환 효과의 근거가 더 강해진다.

그러나 다음은 구분한다.

- 같은 입력 반복에서의 재현성과 의미적으로 같은 다른 입력에 대한 불변성은 다른 성질이다. 결정적인 함수도 표현에 편향될 수 있다.
- flip은 두 코드 중 어느 쪽이 올바른지 알려주지 않는다. false deploy/reject 주장은 독립 정답이 있어야 한다.
- 이 결과만으로 모든 LLM judge를 원리적으로 deployment gate에 사용할 수 없다고 증명하지 않는다.
- 권장 결론은 “검사한 조건에서는 judge 판정만으로 의미 보존을 보증하기 어렵고, 확정 executable reference를 이용한 별도의 행동 검증이 필요하다”다.
- 실행 trace 하나의 일치도 배포 보증은 아니다. Explorer의 인증은 선언 모델·지원 범위·완료 조건 안에서 해석하며 물리적 배포 안전성 전체를 뜻하지 않는다.
- 기존 생성 파일럿·judge 비교 결과가 이 rewrite protocol을 충족하는지 대조하기 전에는 Fig2 결과로 전용하지 않는다.

영문 결과 문장은 실제 근거를 확보한 뒤 모델·표본·효과 크기를 넣어 작성한다. 현재는 수치나 유의성, temporal idiom 변환의 성공을 확정하지 않는다.

## Table 1 — judge 설정별 판정 불변성 요약

Table 1은 Figure 2와 같은 paired rewrite 실험의 집계표다. 별도 데이터셋이나 별도 성능 평가처럼 보이지 않게 캡션과 본문에서 동일 protocol을 참조한다.

권장 열:

| Judge/model | Decoding and repetitions | Valid original–rewrite pairs | Deploy→reject | Reject→deploy | Total flip rate | Identity flip rate | Uncertainty interval |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |

- 모델명은 `9B`, `cloud model` 같은 별칭만 쓰지 않고 정확한 model/version을 적는다.
- temperature 0, sampling, majority vote를 비교한다면 각 조건의 반복 횟수와 aggregation rule을 공개한다.
- identity baseline과 rewrite flip을 같은 유효-pair 규칙으로 계산한다.
- 원본 프로그램 단위로 의존성을 반영한 confidence interval 또는 사전 선택한 paired/cluster-aware 검정을 사용한다.
- malformed, abstain, API error를 제외해 flip rate를 낮추지 말고 별도 열 또는 전체 분모로 공개한다.
- 과거 SenSys 표의 27.0%, 10.6% 등은 새 protocol 검증 없이 가져오지 않는다.

캡션 작업문:

> LLM-judge verdict consistency for trace-equivalent reactive-temporal code rewrites. Identity repetitions quantify verdict variation without a rewrite; uncertainty intervals are clustered by the original program.
