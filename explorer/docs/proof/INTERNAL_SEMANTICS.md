# 내부 의미론 검증과 현재 보장 범위

2026-09-07. 최신 사용자 결정: 검증 대상은 **확정한 Timeline IR과 JoI 코드가
정의한 의미론에서 만드는 timed ACTION trace의 동치**다. 실제 허브 실행,
센서 측정, 물리 장치 동작의 관측은 이 보장의 필수 조건이 아니다.
[RUNTIME_CONTRACT.md](../model/RUNTIME_CONTRACT.md)는 그 의미론을 정의하는 계약으로 읽는다.
배포 구현 적합성은 별도의 보장으로 분리한다. 이 결정이 과거 작업 목록보다 우선한다.

**최신 증명 의무 점검:** [PROOF_OBLIGATIONS.md](PROOF_OBLIGATIONS.md)에 O1–O6와
코드를 대응했다. DOUBLE exact 도메인의 int 표현 누락을 수정한 현재 소스로
전체 회귀153개 및 독립 kernel563이력/변이2개를 재검사했다. 최신 E1 결과는
`eval/results/e1_internal_semantics_proof_2026-09-07_v1.json`이다.
검색 추가 근거는 메모 없는 이력 전수 실행과의 대조이며 구체 실행기는 공유한다.

**BOOL 입력 후속 확정:** `strict-two-valued-v1`에서는 catalog BOOL 센서/조회 반환이
true/false만 가진다. 아래 2,673이력 결과는 None을 포함했던 이전 모델 기록이다.
현재 독립 kernel 검사는 BOOL 이력을 2⁵씩, STRING 조회 이력은 종전대로 3⁵씩
열거한다. 비BOOL 결측·타입 미선언 GV 및 아직 대입되지 않은 로컬 변수의 None을
BOOL 센서의 세 번째 값으로 취급하지 않는다.

현재 모델 재검사: BOOL 프로그램10개 × 2⁵=320 + STRING 조회1개 × 3⁵=243,
합계 **563 paired histories / 1,126 trace 대조 일치**. IR-only 중첩 cycle1개,
실행기 오류 주입2개도 검출했다. 결과는
`eval/results/e1_internal_semantics_bool2_2026-09-07_v1.json`이다.
전체 회귀146개, 손 trace14개/기대 거절1개/프로그램 변이3개, catalog 개발8개
기대 결과도 확인했다. 이 감소는 BOOL의 세 번째 값 제거에 따른 이력 공간 변경이며
누락된 BOOL 입력을 임의로 false로 대체해 통과시킨 결과가 아니다.

## 1. 보장과 필요한 조건

고정 프로그램 P(IR), Q(JoI), binding/inventory B, 선언한 초기 GV 집합 I,
입력 모델 U를 둔다. 의미론상의 trace를 T(P,B,i,u)라고 하자. 검증할 명제는
모든 i∈I 및 허용된 입력 이력 u에 대해 다음이 성립한다는 것이다.

```
Obs(T(P,B,i,u)) = Obs(T(Q,B,i,u))
```

Obs는 ACTION의 논리 시각, 호출 경계, 대상·동작·인자·중복·순서를 보존하며
한 호출 안의 독립 기기 순열만 동일시한다. 초기 장치 상태도 u의 최초
snapshot에서 전부 다룬다. 종료 자체는 ACTION이 아니지만 이후 행동은 계속 비교한다.

이 명제를 구현의 긍정 판정에 연결하는 의무는 다음 네 가지다.

1. **의미론 실행:** IR 및 JoI adapter가 각 프로그램의 의미론을 보존한다.
   파서·접지·식 평가·continuation·timer·회차·종료를 포함한다.
2. **입력 포괄:** 공동 술어 대표값이 모든 허용 값을 관찰 보존하게 대표하고,
   원문이 ACTION/미래 상태로 흐르면 필요한 정확한 도메인을 유지한다.
3. **탐색 포괄:** 모든 초기 상태와 입력 이력의 후속 상태를 탐색하고,
   생략한 시간 구간 및 병합한 상태가 미래 ACTION을 보존한다.
4. **판정 경계:** bounded와 fixpoint를 구별하고, cap/오류/미지원은 동치로
   보고하지 않는다. DIVERGE의 반례는 같은 모델에서 재생한다.

1은 FRONTEND_CORRECTNESS.md, 2는 INPUT_COVERAGE.md와 SERVICE_MODEL.md,
3–4는 SEARCH_CORRECTNESS.md에 구현 대응과 조건부 수학적 논증이 있다.
실제 센서가 U를 준수하는지, 배포 허브가 이 실행 의미를 구현했는지는 위
**모델 안의 명제**의 추가 전제가 아니다. 현실 보장으로 확장할 때 별도로 필요하다.
명시한 입력 subset만 검사하고 전체 실제 센서 도메인 검증으로 부르면 안 된다.

## 2. 독립 기준 실행기

`tests/semantic_reference.py`는 표준 Python만 사용한다. Explorer의 parser,
expression evaluator, compiler, runner, scheduler, 입력 추론, 관찰 정규화,
상태 키를 import하지 않는다. Python generator의 남은 실행을 continuation으로
사용하고, delay/period는 절대 deadline, wait는 현재 snapshot의 조건으로 정의한다.

검사 kernel은 literal/input/variable/equality, read, call, Seq, if, wait,
delay, positive period, break와 중첩 유한 cycle이다. 별도 renderer가 같은
구조를 IR JSON 및 JoI 소스로 만든 뒤 각각의 production adapter를 독립 기준과
비교한다. IR와 JoI가 서로 같은 답이라는 사실을 정답으로 사용하지 않는다.
각 1ms의 ACTION과 조용한 반응까지 비교하며 호출자 저장소 비변경도 검사한다.

11개 paired 프로그램에 대해 0/100/200/300/400ms의 다섯 입력 선택을 각각
None/false/true 또는 None/clear/rain에서 전체 열거한다. 프로그램당 3⁵=243,
합계 **2,673개 입력 이력**, 양쪽 실행기 **5,346개 trace 대조**다. 별도로 중첩
finite cycle 재진입은 IR-only 1개 이력으로 검사한다. period는 회차 사이에만
필요하므로 유한 cycle의 마지막 회차 후에는 추가 period 없이 빠져나온다.

### 기준과 production 상태의 대응

기준 generator의 남은 문장열·가지·cycle 인스턴스를 IR의 pc/반복 레지스터,
JoI의 segment/path에 대응시킨다. 사용자 저장소와 유지 입력이 같고, 활성
deadline이 같으며 종료 여부가 같다는 관계 C를 둔다.

- literal/lookup/equality는 같은 피연산자 값을 읽는다.
- call은 같은 값을 평가하여 같은 구체 target의 ACTION 하나를 추가한다.
- read는 같은 snapshot 값을 저장하고 다음 문장으로 이동한다.
- if는 같은 조건값으로 같은 가지의 continuation을 택한다.
- delay는 진입 시각+duration 이전에 정지하고 그 시각부터 다음 문장으로 이동한다.
- wait는 조건이 false이면 현재 continuation을 보존하고 true이면 다음으로 이동한다.
- 회차 완료는 다음 시작 deadline을 만든다. cycle 진입은 새 count를 만들고,
  back edge는 그 count를 유지한다. break는 가장 가까운 cycle 또는 프로그램을 끝낸다.
- 종료는 이후 모든 입력에 대해 무행동이다.

이 원시 규칙에서 한 유한 반응의 내부 실행 길이에 대한 귀납으로 C와 ACTION
관찰이 보존된다. 동일 snapshot/time을 고정하면 각 규칙의 다음 결과가 유일하다.
반응 횟수에 대한 귀납으로 kernel의 trace 대응을 얻는다. production의 실제
분기 구현을 이 규칙에 대응시킨 코드 검토와 아래 차등 검사는 서로 보완하는 근거다.
프로그램 생성 전체를 열거했다는 주장이나 Python 코드의 기계 검증 증명은 아니다.

## 3. 실행기 오류 주입

실제 production 함수 두 곳을 메모리에서만 교체해 검사한다.

- JoI `PauseRunner.step`: 회차 종료 뒤 period를 1ms로 잘못 적용.
- IR `ir_step`: delay 만료 검사를 항상 true로 변경.

예상 trace나 프로그램을 바꾸지 않고 **실행기 함수 자체**를 변경한다. 각 변이는
유효 ACTION 차이로 검출돼야 한다. 문법 오류/실행 예외만으로 검출 성공으로
세지 않는다. context manager로 원래 함수를 복구하며 production 파일을 수정하지 않는다.
이것은 기존 e1_runtime_probe의 프로그램 변이 대조군 3개와 다른 근거다.

```bash
python -m explorer.tests.e1_internal_conformance --output /tmp/joi-e1-internal-new.json
```

최신 결과: `eval/results/e1_internal_semantics_2026-09-07_v1.json`.
fixture IR/code, 도메인/시간 범위, 전체 이력의 관찰 digest, 실패 이력, 변이
목격 trace 및 코드/명세 hash를 남긴다. kernel 밖의 지원 기능은 기존 테스트와
논증으로 보강하며 아래 경계를 유지한다.

## 4. 근거별 범위와 남은 일

| 영역 | 근거 | 범위 |
| --- | --- | --- |
| 제어/시간/조회 조합 | 새 독립 generator 기준과 2,673 paired histories, IR-only 중첩 cycle | 11개 프로그램의 명시 유한 입력 이력. 임의 프로그램 전체 열거가 아님 |
| 초기 회차 `:=`, edge flag, 결측, 반환 거절 | 이전 e1_runtime_probe: 손 ACTION trace 14개, 기대 REFUSED 1개 | 독립 generator kernel 밖은 기존 손 기대값으로 검사 |
| sustain/timeout/edge·동시 입력, clock | contract/정확 시간 회귀와 FRONTEND/SEARCH 논증 | 모든 temporal constructor의 독립 두 번째 구현은 아님 |
| quantifier/binding/문자열/parser | frontend 22개, service 21개, mapping 3개 및 대응 논증 | 고정 binding, 지원 문법에 한정 |
| 입력 분할/초기 GV/D7/상태 병합 | input coverage·soundness·contract·exact tick 회귀와 INPUT/SEARCH 논증 | 지원 모델에서의 조건부 정리. 미인증 패턴은 REFUSED |
| 구현 오류 감지 능력 | 실행기 변이 2개와 기존 프로그램 변이 3개 | 모든 잠재 버그 부재의 증명이 아님 |

현재 작업으로 내부 의미론 기준·구현 대응 논증·독립 kernel 검사·회귀 근거를
연결했다. **전체 지원 언어의 기계 검증이나 모든 프로그램에 대한 테스트 완전성은
주장하지 않는다.** E1의 전체 실험 계획에는 더 넓은 구성별 coverage와 오류
주입을 추가할 여지가 있다. 배포 측정이 없어서 모델 검증 주장이 막히는 것은 아니다.

논문용 다음 작업은 현 모델에서 평가할 초기 GV/입력 범위와 후보 집합을 고정하고,
새 held-out 동치 판정/반례/미지원/시간·메모리를 측정하는 것이다. 과거 v3의 수치를
현 구현 성능으로 재사용하지 않는다. 초록·논문 제출/등록은 이 작업에서 변경하지 않는다.
