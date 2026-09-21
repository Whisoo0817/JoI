# 파서·grounding·실행기 대응 논증

2026-09-07. 대상은 `gate.prepare_pair`가 구성하는 contract-v1 실행기다.
아래는 **정의한 모델 안의 조건부 수학적 논증과 구현 검토**다. 기계 검증된
증명이나 실제 JoI 서버와의 동작 일치 증명이 아니다. 입력 대표값 논증은
[INPUT_COVERAGE.md](INPUT_COVERAGE.md), 탐색 정리는
[SEARCH_CORRECTNESS.md](SEARCH_CORRECTNESS.md)에 연결한다.

**최신 사용자 범위:** 실제 배포 런타임 측정은 필수가 아니다. 확정한 모델의
IR/code ACTION 동치를 보장하는 내부 의미 보존이 대상이다. 독립 kernel 실행기와
양쪽 adapter의 2,673개 입력 이력 대조 및 실행기 변이 검사는
[INTERNAL_SEMANTICS.md](INTERNAL_SEMANTICS.md)에 정리했다.

## 1. 무엇을 원본 의미로 삼는가

**용어 정정 (후속 사용자 질의):** `query`는 service list의 공식 종류나 반환
타입이 아니라 기존 Explorer가 값 읽기 호출에 붙인 내부 명칭이다.
`files/service_list_ver2.0.7.json`은 `values`와 `functions`를 구분하며 함수에는
`arguments`, `return_type`, `descriptor` 등이 있다. 별도 query/부작용 분류
필드는 없다. `WeatherProvider.Forecast`는 Hour(INTEGER, 0–120)를 받아
WeatherEnum 이름 문자열(예: rain, clear)을 반환하며 return_type은 STRING이다.
문자열을 반환한다는 사실과 읽기/동작 역할은 별개다. 후속 구현에서 기본 gate에
[서비스 명세 연결](../model/SERVICE_MODEL.md)을 추가했다. 아래 실행기의 위치 기반
처리를 허용하기 전에 명세와 검토된 읽기 역할을 검사하며 공식 분류를 새로
도입하지 않는다. 실제 서버의 부작용 적합성은 여전히 조건이다.

프로그램과 고정 inventory/binding, 입력 이력, 초기 GV, 시간 원점이 주어진다.
외부 값은 입력 이벤트에서만 바뀌고, 한 반응 도중에는 동일한 snapshot이다.
장치 ACTION은 호출의 관찰값이며 현재 snapshot을 직접 수정하지 않는다.
성공/실패·네트워크 지연·물리 장치의 반응은 이 모델의 별도 상태가 아니다.

계약에서 사용하는 호출 분류는 JoI의 표현식 위치 호출과 IR의 `call.var`를
query로, JoI 문장 위치 호출과 `var` 없는 IR call을 ACTION으로 해석하는 것이다.
반환값을 사용하지 않아도 query는 query다. query 답은
`device.member(repr(arg1),...)`에 대응하는 외부 입력이다. 무인자 query는
같은 장치 property와 같은 입력 축을 쓴다. GV get/set은 별도의 저장소 연산이다.
기본 gate는 검토된 읽기 함수만 query 위치에 허용한다. Toggle/SetVolume처럼
값을 반환하면서 기기를 바꾸는 호출의 반환 대입은 REFUSED이며 문장 위치의
ACTION은 보존한다. 모든 non-VOID가 읽기라고 가정하지 않는다. 카탈로그의
descriptor 검토와 실제 서버의 부작용 부재 증명은 구별한다.

기본 gate는 원래 등장 순서로 binding을 접지한 뒤 named args를 실제 명세의
순서로 재정렬한다. 이름/인자 집합/타입/범위와 capability를 확인하고 이름 충돌은
거절한다. bare runner와 명시 synthetic fixture에는 기존 adapter 규칙이 남지만
그 결과를 실제 서비스 적합성 증거로 사용하지 않는다. 단수 selector의
Main/첫 후보 선택은 기존 고정 binding 모델이며 실제 선택 정책 확인은 남았다.

## 2. 파싱과 표현식

JoI tokenizer는 현재 위치부터 다음 token 하나를 소비하고, 인식할 수 없는
문자를 넘기지 않는다. selector 전체를 허용 문법과 대조한다. 이전처럼
`(#Switch-broken)`을 `#Switch`로 일부만 읽거나 selector 안 쓰레기 문자를
무시하지 않는다. 괄호/블록/인자 목록의 종료를 요구한다.

두 조건식 파서의 우선순위는 괄호, 산술 단항 음수, 곱셈, 덧셈, 비교,
논리 `not`, `and`, `or` 순서다. 따라서 `not x > 10`은 `not (x > 10)`이다.
각 우선순위 함수가 더 강하게 결합하는 부분식을 먼저 소비하므로, token
소비 길이에 대한 귀납으로 이 문법의 구문 트리와 파싱 결과가 일치한다.
완전한 식 뒤의 token은 거절한다. IR parser의 닫는 괄호 검사는 Python
`assert`에 의존하지 않는다. 음수 float 리터럴의 부호 있는 0도 보존한다.

문자열은 데이터다. IR의 selector 표기 치환이 따옴표 안까지 침범하지 않는다.
ACTION의 일반 문자열 `Sensor.Value`도 그대로 보존하고, 템플릿에서는 `$`로
표시한 읽기만 binding한다. 문자열 본문을 장치 참조로 오인해 바꾸지 않는다.
소스 문자열의 backslash escape는 decoding 규약을 확인하지 못했으므로 거절한다.
IR JSON 인자의 이미 decoding된 문자열 값과 소스 식의 문자열 리터럴은 구별한다.

표현식 평가의 기저는 리터럴, 저장소 lookup, 외부 입력 lookup, 파생 clock이다.
복합식은 부분식 결과에 고정된 순수 연산을 적용한다. 현재 논리식 평가기는
양쪽을 평가한다. GV 쓰기가 표현식에 들어가면 `input_coverage`가 거절하므로
조건 평가가 숨은 ACTION/GV 변경을 만들어 runner의 임시 조건 평가에서
사라지는 경우를 허용하지 않는다. 미지원 타입 연산·잘못된 상수 계산은
긍정 판정의 근거가 되지 않는다. 산술 관련 기존 D7 거절은 그대로 적용한다.

## 3. 고정 binding의 의미 보존

태그 집합 T의 매칭 결과를 고정 inventory 순서의 장치 열 B(T)라 하자.
원래 selector의 직접 의미도 이 B를 사용한다는 전제 아래:

- 단수 읽기는 선택 규약이 정한 장치 d의 `d.member` lookup으로 바뀐다.
- `any(T).m op c`와 `all(T).m op| c`는 각 d에 대한 비교의 OR다.
  `all(T).m op c`는 AND다. 반대쪽에 selector가 와도 피연산자 위치를 유지한다.
- 여러 기기의 일반 scalar/group call은 임의로 첫 기기로 줄이지 않는다.
  미지원 집합값 사용은 거절한다. 단수 선택 규약 자체는 기존 계약을 유지한다.
- `all(T).act(args)`는 같은 반응의 동일 값 인자로 기기별 ACTION을 만든다.
  호출 경계와 중복은 보존하며, 장치 사이 순열만 관찰 정규화로 제거한다.
- query도 property와 같이 장치 ID를 보존한다. `CallExpr.input_key`는 grounding
  결과의 내부 메타데이터다. IR/binding 스키마를 바꾼 것이 아니다.
  서로 다른 센서의 같은 query/인자가 더 이상 한 서비스 입력에 합쳐지지 않는다.
- `for`의 정적 펼침은 고정 장치 열을 순서대로 방문한다. iterator 쓰기,
  중첩 foreach, break, blocking을 포함하면 거절한다. 이 제한 아래 반복 변수는
  읽기 전용이며 반응 중 snapshot이 고정되므로 장치 읽기로 치환해도 값이 같다.

각 잎의 lookup/비교가 같다는 사실에서 식의 구조 귀납으로 복합 조건도 같다.
문장열에 대한 귀납으로 선택된 분기, ACTION 호출열과 저장소 갱신이 보존된다.

gate는 쓰이는 서비스 binding 누락, 빈 장치 목록, inventory에 없는/offline
장치, 불명확한 quantifier, 사용 중인 자리 수 불일치, 부유 selector를 거절한다.
`Service#2`는 JSON key 나열 순서와 무관하게 두 번째 자리다. 단일 자리의
모든 등장 재사용 규칙은 유지한다. IR에서 전혀 쓰지 않는 여분 서비스 binding은
메모만 남긴다. 직접 `IrRunner`/`PauseRunner`를 만드는 추상 단일 서비스 테스트는
gate의 실제 inventory 검증을 수행한 것으로 간주하지 않는다.

## 4. 제어 흐름을 실행 상태로 옮기는 대응

원본 프로그램의 남은 문장열/선택된 분기/활성 반복을 continuation으로 본다.
컴파일된 PC 또는 JoI runner의 경로가 그 continuation을 가리킨다는 관계 C를 둔다.
사용자 변수/GV 값과 각 활성 타이머 시작 시각도 C에서 같아야 한다.

| 원시·합성 | 코드 대응과 보존 이유 |
| --- | --- |
| read/query | 같은 입력 key와 인자 타입으로 lookup하고 지정 변수에 저장한다. 반환값 liveness로 ACTION 여부를 바꾸지 않는다 |
| ACTION/GV set | 인자를 왼쪽부터 평가하고 호출/쓰기를 순서대로 기록한다. `argv`가 float를 int로 바꾸지 않는다 |
| 대입/초기화 | `=`는 도달할 때 평가한다. `:=`는 실행기 first-iteration 규칙에 따라 평가한다. period 재시작/차단 재개 플래그가 상태에 남는다 |
| if | 참 가지는 fall-through, 거짓 가지는 IF.succ로 이동한다. 참 가지 뒤 GOTO는 else를 건너뛴다 |
| delay | 시작 시각을 한 번 저장하고 만료 전에는 해당 PC/경로에 머문다. 만료 후 다음 문장으로 이동한다 |
| wait | 같은 조건을 평가하며 성공하면 continuation으로 이동한다. sustain/edge/timeout 상태를 유지한다. `edge`와 양의 `for`를 동시에 지정하면 미정의 조합으로 거절한다 |
| cycle | ENTER_CYCLE이 진입마다 카운터/완료 시각을 초기화한다. END_ITER는 완료 시각을 기록하고 TOP으로 돌아가므로 회차마다 초기화하지 않는다 |
| break/timeout | 컴파일러가 해당 cycle 출구/회차 끝을 패치한다. JoI loop 안 break는 loop를 벗어나고 최상위 break는 종료한다 |
| 중첩 if의 blocking | PauseRunner는 선택된 가지 경로를 저장한다. 재개할 때 바깥 조건을 다시 평가하지 않고 그 가지 뒤의 바깥 continuation까지 진행한다 |
| 종료 | END/종료 wrapper가 흡수 상태를 기록한다. 이후 ACTION은 없다 |

기저 문장에서 C가 보존됨을 위 전이로 확인하고 문장열·if의 크기에 대해
귀납한다. 반복은 유한한 실제 전이 횟수에 대해 귀납한다. 중첩 cycle 재진입의
초기화도 이 단계에 필요하다. 이전 구현은 안쪽 count가 이미 끝난 채 남아
두 번째 외부 회차의 ACTION을 누락했고, ENTER_CYCLE로 이를 수정했다.

사용자의 2026-09-07 후속 지시에 따라 `:=`는 목표 런타임의 **초기 회차 전용
대입**으로 확정했다. 첫 회차에서 문장에 도달한 때 평가하며, 첫 회차에서 건너뛴
가지의 초기화는 이후에도 실행하지 않는다. delay 뒤의 초기화는 재개 시점 값을
읽는다. 시작 시 모든 선언을 hoist하거나 선언별 first-encounter bit를 추가하지
않는다. [RUNTIME_CONTRACT.md](../model/RUNTIME_CONTRACT.md)의 R8과 경계 예제를 따른다.
이는 기존 서버 관측 결과가 아닌 목표 명세다. JoI loop 내부 blocking은 기존대로 거절한다.

## 5. 반응의 결정론성과 unique trace

허용 상태 s, snapshot u, 정수 ms 시각 t가 같다고 하자. lookup과 순수 연산은
결과가 유일하다. 문장/명령마다 다음 제어 위치·저장소·ACTION이 유일하고,
분기나 만료 여부도 s,u,t로 정해진다. 복사한 변수/GV 사전만 갱신하므로 동일한
입력 상태를 재사용해도 결과가 달라지지 않는다. 지원 입력은 scalar이고 실행에
저장되는 복합 값은 읽기 전용 토큰/제어 메타데이터이므로 얕은 사전 복사로
호출자 저장소의 중첩 가변 객체를 바꾸는 연산도 없다.

따라서 유한 반응의 내부 전이 수에 대한 귀납으로 결과 R(s,u,t)가 유일하다.
무한/과도한 내부 반복은 연료/loop 한도에서 거절되며 성공 반응으로 간주하지
않는다. 정상 반응은 차단, period 대기, 종료 중 하나에 도달한다.

반응 종료 후 입력·파생 clock·활성 만료가 바뀌기 전에는 현재 차단 위치에서
나올 이유가 없다. 조건 평가에 숨은 쓰기도 없으므로 이 구간을 다시 평가해도
ACTION이나 미래 관련 상태가 새로 변하지 않는다. 이는 SEARCH_CORRECTNESS의
이벤트 생략 보조정리 전제와 연결된다.

초기 상태와 입력 이력을 고정하면 첫 반응이 유일하고, 유일한 후속 상태에
다음 입력을 적용한 반응도 유일하다. 반응 횟수에 대한 귀납으로 timed ACTION
trace가 유일하다. C의 보존과 입력 대표값의 보존 전제를 함께 적용하면
탐색 정리의 bounded/fixpoint 결론을 **이 정의된 프로그램 모델**에 연결할 수 있다.

## 6. 검증 근거

`tests/test_frontend_conformance.py` 22건은 손으로 정한 값/ACTION/거절을 검사한다.
주요 반례: 두 번째 센서만 참인 any, 서로 다른 두 장치의 동일 query,
`not` 우선순위, 누락 binding, slot 순서, unused query, 중첩 cycle 재진입,
중첩 if 차단 후 바깥 continuation, 순서 있는 foreach, 입력 사전 비변경.
검색기끼리 같은 답을 내는 것만 기대 결과의 근거로 쓰지 않았다.

기존 99건과 합쳐 121건이 통과했다. features 및 IR 자가 점검도 통과했다.
새 개발 manifest `eval/contract_v1_frontend_development.json`에는 독립 기대 판정을
가진 4개 사례를 추가했다. 결과 파일은 manifest와 evaluator SHA를 포함한다.
공유 파서/실행기의 모든 오류가 테스트로 배제됐다는 뜻은 아니다.

## 7. 모델 내부 근거와 선택적 외부 연결

1. **서비스 구현 대응:** catalog 이름/인자 순서/타입/범위 연결과 충돌 검사는
   완료했다([SERVICE_MODEL.md](../model/SERVICE_MODEL.md)). 검토한 읽기 역할의 실제
   부작용·반환 동작과 암묵적 형변환의 배포 구현 확인은 현실 보장 확장 시 별도 작업이다.
2. **남은 도메인 전제:** catalog values 및 검토한 함수 반환 도메인은 manifest에
   연결했다. 현재 catalog BOOL은 strict-two-valued-v1(true/false)이고 비BOOL만
   결측을 허용한다. 0.1 정밀도, 초기 GV, 명시 유한 subset의 실제 근거는
   별도 계약으로 남으며 카탈로그에서 발견했다고 주장하지 않는다.
3. **E1 내부 실행기 적합성:** 정책은 RUNTIME_CONTRACT.md의 정의를 따른다.
   손 trace 14개/기대 거절 1개에 더해 독립 기준으로 11개 프로그램의 2,673개
   이력을 양쪽 adapter와 대조하고 IR-only nested cycle 및 실행기 변이 2개를
   검사했다. 전체 언어의 기계 검증 증명은 아니며 kernel 밖은 기존 회귀/논증의
   근거를 따른다. 실제 scheduler 측정은 현재 보장의 필수 조건이 아니다.
4. 위 범위와 소스가 동결된 뒤 새 held-out 평가. 이전 결과의 입력 키와
   query/바인딩 지원 범위를 현재 구현에 그대로 적용하지 않는다.
