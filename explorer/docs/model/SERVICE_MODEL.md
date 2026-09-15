# 서비스 명세와 Explorer의 연결

후속 [SMT 산술 지원](../proof/SMT_VERIFICATION.md)에서도 같은 catalog snapshot을 사용한다.
숫자 입력 bounds·타입·결측 정책과 ACTION 인자 type/range를 기호적으로 검사한다.
숫자→문자열 자동 연결 규칙과 서비스 호출의 STRING 요구를 구별한다. 실제 C01_006은
SMT 경로에 진입하지만 최소 채널에서 `Channel-1`이 SetChannel 범위를 벗어나므로
여전히 REFUSED다. 이를 산술식 자체가 불가능하거나 동등 인증된 것으로 해석하지 않는다.

2026-09-07. `gate.prepare_pair` / `gate_pair`는 기본적으로 실제 카탈로그를
읽는다. `timeline_ir.catalog.load_service_specs`는 descriptor, return_type,
arguments, values, enums를 보존하는
스냅샷을 제공한다. 파싱한 바로 그 바이트의 SHA-256을 기록한다.
상위 IR 검사를 위해 `load_catalog` 인덱스에도 `return_types`를 추가했다.
기존 `functions`의 인자 순서 목록 인터페이스는 유지한다.

- 명세: `files/service_list_ver2.0.7.json` (55 skills, 114 functions).
- 현재 SHA-256: `e69e5e442441197ff7d8eece70ad59fe966d82469fb07fc9dfc57c2446c4df9c`.
- 로컬 명세 개정 `cloud-availability-v1`: 사용자 확정으로 IsAvailable의
  ServiceName 인자를 제거했다. 파일명 v2.0.7은 유지하며 SHA로 개정을 구별한다.
  기존 `ac35c8b78c05ce7f379b7fe7b8dfa49b18172d68f69aec169169768c49e5a221`은
  과거 평가의 명세다. 전체 구조 대조로 이 함수의 descriptor/arguments만
  바뀌고 반환 BOOL 및 나머지6개 읽기 함수는 그대로임을 확인해 읽기 역할을 재인증했다.
- 구현: `service_model.py`; IR/binding 스키마 변경 없음.
- 이것은 명세와 검증 모델의 연결이다. 실제 서버의 구현 적합성 증명이 아니다.

## 1. 이름, 바인딩, 인자

IR와 JoI 모두 공식 value/function을 구별해 조회한다. 기존 case-insensitive,
service-prefix 정규화를 사용하되 catalog alias 충돌과 concrete input member
충돌은 거절한다. 함수 이름을 괄호 없는 property로 사용하는 것도 거절한다.
기기 ID에 해당 capability가 `category`로 선언되어 있는지 확인한다. JoI의
property는 grounding으로 서비스 정보가 사라지기 전에 selector와 capability를
대조한다. Main/첫 후보의 기존 고정 선택, any/all 및 OP|의 확장 규칙은 유지한다.

IR named args의 이름 집합이 정식 arguments와 일치해야 한다. 대소문자 별칭은
허용하되 중복·누락·알 수 없는 인자는 거절한다. 명세의 인자 순서로 위치 인자를
만든다. **binding의 원래 등장 순서로 접지한 뒤** 인자를 재정렬한다. 먼저
재정렬하면 같은 서비스의 두 읽기가 서로 다른 장치로 뒤바뀔 수 있기 때문이다.

리터럴 인자는 준비 때, 변수에서 전달되는 ACTION 인자는 매 실행/재생 때
타입·범위·ENUM을 검사한다. INTEGER는 bool/float를 받아들이지 않고,
DOUBLE은 bool을 제외한 int/float를 허용한다. int/float나 signed zero를
관찰값에서 임의로 변환하지 않는다. API의 암묵적 형변환은 가정하지 않는다.
명세가 구조화한 optional/default 규칙이 없으므로 모든 arguments를 요구한다.

## 2. 반환값이 있다는 이유로 ACTION을 지우지 않는다

`query`는 공식 서비스 종류가 아니다. 카탈로그에는 전용 부작용 필드가 없다.
다음 7개 함수만 descriptor를 검토한 **모델상 읽기 역할**로 허용한다:

- WeatherProvider: Forecast, GetWeatherInfo
- ArmRobotDetail: GetMotion, ListMotions
- MenuProvider: GetMenu
- CloudServiceProvider: ChatWithAI (`chat-string-return-v1`; unrestricted,
  non-null STRING used only through identity-preserving symbolic flow)
- NewsProvider: GetNewsDigest
- CloudServiceProvider: IsAvailable

**IsAvailable() 확정 의미:** 선택된 provider의 사용 가능 여부를 인자 없이
조회하고 true/false를 반환한다. ServiceName/암묵적 기본값/None은 없다.
C03_002는 Main을 조회하고 true일 때 Main에만 업로드하도록 NL과 binding을
교정했다. Backup은 연결 목록에 남지만 이 시나리오에서는 조회·업로드하지 않는다.
이는 이 행의 대상 정책이며, 모든 클라우드 요청을 Main에 강제하는 규칙은 아니다.
단일 selector의 unique Main/첫 후보 규칙과 고정 binding은 유지한다.

상위 `validate_ir_against_catalog`도 필수 인자 누락과 VOID call.var를 거절한다.
이름/서명 검사 통과가 전체 타입·동작 적합성이나 Explorer EQUIV를 뜻하지 않는다.

이들은 표현식/반환값 대입 위치에서 외부 입력으로 읽는다. 읽기 역할 검토는 위
catalog hash에 고정하며 파일이 달라지면 재검토 전 REFUSED한다. 이것은 서버에
부작용이 전혀 없다는 증명이 아니다. GV get/set은 별도 저장소 계약을 따른다.

다른 함수는 문장 위치에서 ACTION으로 관찰할 수 있다. 반환값 대입/표현식
위치에서는 거절한다. 예를 들어 `Switch.Toggle()`과 `Speaker.SetVolume(30)`은
반환값이 있어도 기기를 조작한다. 문장 호출은 ACTION이며, `x = Toggle()`을
아무 ACTION 없는 입력 읽기로 통과시키지 않는다. **ACTION과 결과를 함께
모델링하는 지원은 아직 없다.** 검토한 읽기 함수의 결과를 버리는 문장 호출도
현재 명시적으로 거절한다. 의미를 임의로 바꾸는 대신 지원 범위를 좁힌다.

Forecast의 Hour는 INTEGER [0,120], 반환 타입은 STRING이다. descriptor가
WeatherEnum 이름을 반환한다고 명시하므로 그 15개 문자열을 반환 도메인으로
연결한다. 별도 공식 query 타입이나 숫자 Forecast를 발명하지 않는다.
STRING 반환 전부를 유한 ENUM으로 가정하지 않는다. GetWeatherInfo 등 일반
STRING은 조건 비교에만 쓰이면 문자열 분할, 원문이 관찰되면 명시 유한 도메인이 필요하다.

## 3. 실제 타입 안에서 입력 대표값을 다시 구성한다

양쪽 프로그램의 출처/술어를 합친 뒤 각 concrete input key를 catalog domain에
연결한다. 기존 mixed-scalar 대표값을 단순 필터링하지 않는다. 예를 들어 False가
정수 0의 조건 결과를 대표하고 있었다면 bool을 제거하는 순간 0의 경우를 놓친다.

조건 전용 값에는 다음 방법으로 **허용 타입에서 새 대표값**을 만든다.

- BOOL/BOOLEAN: 사용자 확정에 따라 **[false, true] 두 값만 모두 열거**한다.
  None을 포함하지 않고 명시 domain이나 직접 runner 재생의 누락/None/0·1도
  거절한다. None을 false로 변환하지 않는다. `clock.isholiday`도 BOOL이다.
- ENUM/Forecast: 선언된 모든 값에 대해 공동 술어의 truth vector를 구해
  vector당 대표 하나를 남긴다.
- INTEGER: 임계값 직전/바로 위의 정수, 0 주변과 선언 범위 양 끝점을 후보로 한다.
- DOUBLE: 사용자 합의인 0.1 격자에서 임계값 전후와 범위 끝점을 후보로 한다.
- STRING: 비교 문자열, 빈 문자열, 각 문자열의 즉시 후속 문자열(s + NUL)을
  후보로 한다. mixed ordered comparison 등 해석할 수 없는 경우는 거절한다.
- None은 **비BOOL** 기본 catalog 입력 도메인에 결측 전제로 포함한다.

ACTION 인자나 미래 관찰 상태로 원문이 전달되는 값은 축약하지 않는다.
BOOL/ENUM/유한한 작은 numeric domain은 전체 값을 열거한다. 큰/무경계 numeric,
일반 STRING 등은 명시적 유한 입력 선언을 요구한다. DOUBLE exact domain은
관찰 가능한 +0.0/-0.0을 모두 보존한다. D7 산술식/결합식 거절은 그대로 적용한다.
DOUBLE exact 경로는 같은 범위의 **int 표현도 모두 열거**한다. DOUBLE 인자로
허용한 1을 누락하고 1.0만 검사하면 문자열 변환의 차이를 놓친다. 2026-09-07
증명 의무 검토에서 이 누락을 재현하고 수정했다([상세](../proof/PROOF_OBLIGATIONS.md)).
명시 input_domains가 있으면 그 목록의 모든 값을 검사하며 카탈로그와 맞지 않는
타입·범위는 거절한다. **그 목록이 실제 센서 도메인을 모두 포괄한다고 주장하지 않는다.**

동적 ACTION 인자가 허용 도메인에 맞지 않는 실행도 REFUSED다. 결측값을 문자열
인자로 그대로 전달하는 프로그램이 여기에 해당한다. 결측 제외가 실제 계약이면
그 제한을 명시 domain과 근거에 기록해야 하며 임의로 None을 제거하지 않는다.

`timed_product`와 `exact_timed_product`도 catalog-prepared runner의 도메인 연결을
강제한다. gate를 거치지 않고 실행기를 직접 호출해 검사를 우회할 수 없다.
직접 만든 bare runner나 `service_catalog=False`는 별도의 synthetic model이며
실제 명세 적합성 결과로 사용하지 않는다. 기존 언어 회귀 fixture는 이 모드를
명시했다. 기본 gate가 알 수 없는 서비스를 묵인하는 fallback은 없다.

## 4. 조건부 포괄성 연결

각 입력 k의 명세·모델상 도메인을 U_k, 양쪽 프로그램에서 추출한 단항 술어의
합집합을 P_k라 하자. x~y를 모든 P_k의 결과가 같은 관계로 정의한다.
지원 비교에서 truth vector가 변하는 지점은 임계값뿐이다. 각 비어 있지 않은
격자 구간과 임계점에는 임계값 이웃 또는 범위 끝점 후보가 있다. 문자열은 빈
문자열과 즉시 후속 문자열이 각 비어 있지 않은 lexical interval을 증언한다.
BOOL은 U={false,true}를 그대로 모두 검사한다. 유한 ENUM도 전체 열거이므로
분명하다. 비BOOL 모델의 None도 직접 포함된다. 따라서
생성된 대표 집합 R_k는 U_k/~의 모든 동치류와 만난다.

출처 인증이 조건 전용이라고 보장한 입력에만 이 축약을 적용한다. 원문이
관찰되는 입력에는 R_k=U_k를 요구하거나 명시 도메인으로 제한한다. 그러면
[INPUT_COVERAGE.md](../proof/INPUT_COVERAGE.md)의 식/전이 관찰 보존 귀납을 그대로
적용하여 [SEARCH_CORRECTNESS.md](../proof/SEARCH_CORRECTNESS.md)의 BFS 정리에 연결한다.
이는 정의한 타입·격자·결측·읽기 역할 아래의 논증이며 기계 검증된 증명이 아니다.

## 5. 근거와 아직 남은 의무

평가 결과에 catalog hash, 사용한 실제 member spec, 입력 목록, 입력 출처 구분,
시간 범위, 초기 GV 모델을 기록한다. evaluator hash에는 새로 사용하는
`timeline_ir/catalog.py`도 포함한다. 기본 가정은 다음과 같이 남긴다:

- 0.1 입력 정밀도는 사용자 합의다. catalog DOUBLE 자체의 정밀도 선언은 아니다.
- nullable은 대부분 명세에 없다. 비BOOL의 missing-inclusive와 BOOL의
  strict-two-valued-v1은 사용자 확정 검증 모델 전제다.
- 초기 GV 타입/범위는 서비스 values에서 얻을 수 없다. 별도 선언/계약을 유지한다.
- 같은 device/member/인자 key는 한 입력 시점에 같은 값을 반환한다. 서로 다른
  입력은 독립이며 입력 이벤트 사이에는 고정된다. 실제 호출별 반환·지연 근거는 남았다.
- 단수 selector의 실제 랜덤 선택 시점/지속성, 초기화, period, blocking, edge,
  동시 이벤트 및 네트워크/장치 반응은 실제 runtime E1로 확인해야 한다.

개발 검증: 새 회귀 21건 + 기존 121건 = **142건 통과**. numeric/BOOL/ENUM의
대표값 포괄성은 독립적인 작은 전체 도메인의 truth vector와 대조했다.
개발 평가 기존 12건 + catalog 8건 = **20건 기대 결과 일치**. catalog 8건 중
2건은 기대 REFUSED이며 나머지 6건만 두 탐색기의 판정 비교다.

최신 결과:

- `eval/results/contract_v1_input_coverage_2026-09-07_v6.json`
- `eval/results/contract_v1_frontend_2026-09-07_v4.json`
- `eval/results/contract_v1_service_catalog_2026-09-07_v1.json`
- `eval/results/catalog_preparation_2026-09-07_v1.json`: 현재 IR와 일치하는 정답
  캐시 178쌍의 **준비 단계만** 확인. 175 PREPARED, 3 REFUSED(C01_015 GenerateImage,
  C01_017 Speak 반환 대입, C01_019 ChatWithAI). BFS/D7 전체 검사를 실행한
  동등성·coverage·held-out 수치가 아니다.

2026-09-07 후속 지시로 [목표 런타임 계약](RUNTIME_CONTRACT.md)을 확정했다.
위 missing-inclusive·0.1 lattice·고정 binding·조회 snapshot 가정은 이제 목표
런타임/adapter가 지켜야 할 요구사항이다. 기존 서버에서 관측해 입증한 성질로
바뀐 것은 아니다. 특히 조회는 현재 snapshot을 즉시 읽으며 새 네트워크 응답은
허용 입력 경계에 반영한다. 호출별 동기 응답 대기는 이 목표 계약에 포함하지 않는다.
초기 GV 범위 및 명시 유한 subset의 포괄성 근거는 여전히 개별 평가 계약에 필요하다.
최신 사용자 결정상 실제 runtime 일치 측정은 필수가 아니다. 확정한 의미론의
IR/code ACTION 동치를 위한 내부 실행기 적합성이 대상이다. 독립 E1 kernel 검사와
논증 연결은 [INTERNAL_SEMANTICS.md](../proof/INTERNAL_SEMANTICS.md)에 완료 기록을 남겼다.
그다음은 평가 모델/소스 동결과 새 held-out 평가다. 기존 v3 결과는 재사용하지 않는다.

## Symbolic observable-domain fallback (2026-09-07)

`symbolic-value-flow-v1` can certify sequential one-shot copies and string
interpolation over full catalog inputs when exact materialization is unavailable.
See [SYMBOLIC_VALUE_FLOW.md](../proof/SYMBOLIC_VALUE_FLOW.md). It preserves the existing
non-BOOL missing policy: converting None to text yields empty text, while passing
raw None to a required STRING ACTION remains REFUSED (currently C01_018).
No catalog, dataset, query signature or binding policy was changed by this work.

## MenuProvider.GetMenu non-null return (2026-09-07)

사용자 결정 `menu-string-return-v1`: catalog의 GetMenu 반환형 STRING을 기준으로
이 조회는 항상 문자열을 반환한다. None은 반환 입력 도메인에 포함하지 않으며
빈 문자열은 유효하다. catalog 자체의 nullable 선언으로 오인하지 않도록 adapter의
`return_spec.nullable=false`와 사용자 계약 근거를 평가 evidence에 기록한다.
자동 대표값·명시 도메인·기호 입력·실행/반례 재생에 동일하게 적용한다.
C01_018은 이제 전체 문자열 도메인에 대해 EQUIV-BOUNDED(3200ms)다.
다른 서비스/property의 비BOOL 결측 정책은 이 결정의 범위가 아니다.

## 자동 입력 cap 후 인증 전략 (2026-09-07)

catalog 도메인을 유한하게 구성할 수 있어도 입력 조합 상한을 넘으면 기존 기호
값 흐름의 전제를 확인한다. C01_014는 catalog/반환 정책 변경 없이 인증된다.
명시 domain은 원래 범위를 유지한다. 이 변경으로 nullable·타입·정밀도·ACTION
검사를 우회하지 않으며, 고정 입력 격자/타이머/바인딩 계약도 같다.

## 후속 연결: 구조화된 Clock 범위 (2026-09-08)

사용자 승인으로 catalog `Hour: INTEGER, bound:[0,23]`, Minute/Second `[0,59]`를 정정했다.
기존 bound 스키마를 그대로 사용하며 실제 시간 범위와 맞지 않는 24/60 상한을 수정했다.
모든 서비스 함수 명세는 이전과 같아 read-role review hash만 새 catalog SHA로 갱신했다.
`ServiceModel.clock_integer_range`가 준비된 선언을 읽고, `range_analysis.py`의 정수 비교
충분조건과 `timed.py`의 시간 의존성 분석에 연결된다. 직접 clock 읽기는 비-null 정수라는
실행기 전제를 확인한다. IR numeric HHMM은 Hour/Minute에서 도출하며 STRING Clock.Time과
혼동하지 않는다. [구현·증명·검증](../proof/CATALOG_RANGE_ANALYSIS.md).
