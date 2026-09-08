# 정답 IR·서비스 명세 불일치 6건 원인 분석 (2026-09-07)

**후속 반영 완료 — 사용자 승인 이후:** 아래는 수정 전 분석 기록이다.
사용자가 추천안(Main 확인→Main 업로드, 무인자 BOOL)에 동의해 현재 catalog와
dataset에 반영했다. VOID 반환 대입5건과 추가 발견 C14_007도 교정했고,
상위 validator에 반환형/필수 인자 검사를 추가했다. 현재159회귀/E1 563이력 통과.
[반영 근거 JSON](results/reference_catalog_repair_2026-09-07_v1.json)에
변경 전후7행·SHA·테스트 출력·수작업 참조 코드 결과를 기록했다.
과거 평가와 원래 후보는 유지했으며, 아래 “아직 미적용”은 분석 당시 상태다.

6건의 첫 거절은 모두 현재 계약에 근거가 있다. 5건은 정답 IR의 잘못된 VOID
반환 대입이고, 1건은 클라우드 조회의 불완전한 명세/호출이다. 이번 분석에서
이 거절을 Explorer의 잘못된 동등 판정이나 새 Gemma의 정답 IR 생성 오류로
볼 근거는 발견하지 않았다. 정답 기준의 품질과 검증기 자체의 soundness는
구분해야 한다.

원본 `dataset.csv`, 카탈로그, 후보, production 코드와 과거 평가 결과는
변경하지 않았다. [행별 근거 JSON](results/reference_catalog_analysis_2026-09-07_v1.json)에
원본 행, 명세, Git 이력, SHA, 5개 최소 IR 수정 제안과 복사본 진단을 저장했다.
진단은 준비/거절 확인이며 새 성능 평가나 formal proof가 아니다.

## 어디서 생겼고 왜 이전 검사를 통과했나

- 6건 모두 `dataset.csv`의 `ir_gt`/`binding_gt`/기기 목록과 frozen manifest를
  대조했다. 후보에 주입된 IR도 정답과 같고 후보 SHA도 기존 기록과 일치한다.
  case ID는 `category_v2`와 `index`로 만든다.
- VOID 대입 5건은 현재 ID 체계가 있는 `d886015:dataset.csv`부터 이미 존재한다.
  당시 v2.0.4 카탈로그도 해당 4개 함수의 반환형은 VOID였다. v2.0.7에서
  반환형이 갑자기 바뀌어서 생긴 문제는 아니다. 실제 작성자/생성 호출까지
  특정할 근거는 없으므로 이를 특정 모델이나 사람의 실수로 단정하지 않는다.
- C03_002는 처음에는 함수 `IsAvailable`을 값처럼 조건에서 읽었다.
  `c264425`에서 `call(..., args={}, var=IsAvailable)`로 바뀌었다.
  변환은 `sensys/reaudit/regroundings.py`의 `_c03_002_ir`에 남아 있다.
  같은 커밋의 `percom.md` §9.2는 인자 생략을 **“기본값 규약으로 허용”**했다고
  명시한다. 그러나 v2.0.4/2.0.7 해당 인자 정의에는 optional/default가 없다.
  과거의 허용 가정이 현재의 명시적 필수 인자 계약과 충돌한다.
- 이전 감사 `sensys/reaudit/catalog_audit.py`는 서비스·함수·제공된 인자 이름을
  검사한다. 반환형은 인덱스에 보관하지 않으며, **필수 인자가 빠졌는지**도
  검사하지 않는다. 따라서 당시 “카탈로그 감사 0건”은 이 6건의 정합성을
  보장하지 않았다. 현재 `timeline_ir.timeline_ir.validate_ir_against_catalog`
  역시 이름 중심 검사라 `call.var`/VOID와 필수 인자 누락 검사가 없다.
- `files/timeline_ir/extractor.md`는 `call.var`를 반환값 바인딩으로 정의한다.
  인자로 사용할 변수나 서비스 이름을 표시하는 필드가 아니다. lowering의
  Bind Hints는 `$Name` 참조를 정규식으로 수집하므로 반환값/기존 read 변수/
  `$Service.Attr`를 혼동할 위험은 있다. 다만 이것이 과거 5행을 실제로 만든
  경로라는 증거는 없으며, 후속 생성 방지 점검 지점으로만 기록한다.

## 행별 원인과 최소 수정 방향

| ID / 원래 요청 | 확인된 결함 | 최소 수정 제안과 남는 문제 |
| --- | --- | --- |
| C01_006 / TV 채널 하나 내리기 | `SetChannel`은 VOID인데 `var: Television.Channel` 지정 | 해당 `var`만 제거. 현재 채널을 읽는 `$Television.Channel - 1`은 유지할 수 있지만 D7 산술 ACTION 인자로 계속 거절된다. |
| C01_017 / 오늘 메뉴 말하기 | 앞선 `read`로 TodayMenu를 얻었는데 VOID `Speak`의 반환을 다시 TodayMenu에 저장하도록 지정 | **Speak의** `var`만 제거하고 `read.var`와 Text는 보존. 카탈로그 준비는 통과하나 일반 STRING TodayMenu가 ACTION으로 흘러 전체 자동 입력 영역을 만들 수 없어 계속 거절된다. C01_018과 같은 종류의 입력 모델 문제다. |
| C14_001 / 버튼1마다 복도 밝기 +10, 최대100 | VOID `MoveToBrightness`에 `var: Light` 지정 | 해당 `var` 제거. `min(현재 밝기+10,100)`의 산술과 코드의 파생 조건은 D7 대상. IR period100ms와 후보1000ms의 차이도 남는다. |
| C14_005 / 버튼3마다 침실 밝기 +5, 최대80 | VOID `MoveToBrightness`에 `var: Light` 지정 | 해당 `var` 제거. D7 및 period100ms/1000ms 차이 유지. **LevelControl 태그로 Light 서비스를 쓰는 것은 이 inventory에서는 적법**하다. Bedroom_Light가 두 capability를 모두 가진다. |
| C14_006 / 버튼4마다 거실 밝기 −15, 최소10 | VOID `MoveToLevel`에 `var: LevelControl.CurrentLevel` 지정 | 해당 `var` 제거. D7 및 period100ms/1000ms 차이 유지. 현재 fresh-v4 코드는 실제로 LevelControl 서비스를 사용하므로 과거 후보의 Light 오용과 혼동하지 않는다. |
| C03_002 / 클라우드 활성 시 파일 업로드 | `IsAvailable`의 필수 ServiceName이 IR/코드 모두 누락. 인자 설명은 “서비스 이름”인데 타입은 BOOL. IR은 두 provider의 반환을 한 scalar로 받음 | API 의미부터 정리해야 한다. 인자 하나를 임의로 채우는 수정은 불충분하다. 이름별 조회를 유지한다면 STRING/이름값/기본값을 명세화해야 하고, 선택한 provider 자체의 상태 조회라면 무인자 BOOL 함수로 명세화할 수 있다. 어느 쪽이든 Main만 볼지, any/all로 집계할지와 업로드 대상을 별도로 확정해야 한다. |

5개의 `var` 제거는 원래 요청에 필요 없는 반환 대입만 없애는 **reference 교정
제안**이다. 잘못 정의된 기존 IR과 의미적으로 동등하다는 주장이 아니다.
최소 패치는 JSON에 경로별로 저장했고 원본에는 적용하지 않았다.

C01_006은 추가로 Channel이 0이면 `SetChannel(-1)`이 선언 범위 [0,10000]을
벗어난다. 이 경계 처리는 별도 정의가 필요하다. 카탈로그의 `ChannelDown()`을
사용하는 대안은 원래 자연어와 잘 맞지만 ACTION 이름 자체를 바꾸므로 기존
`SetChannel(current-1)`과 동등한 것으로 취급하거나 평가 통과 목적으로
자동 치환해서는 안 된다.

C14 세 행의 period 차이는 정적 명세 차이로 확인했다. 100ms와 1000ms의
관측 빈도가 다르면 짧은 버튼 눌림을 놓칠 수 있다. 다만 현재 D7에서 먼저
거절되므로 이번 분석에서 이 후보들에 재생 확인된 DIVERGE 라벨을 붙이지 않았다.
NL은 polling 주기를 명시하지 않으므로 기준은 확정한 IR의 100ms다.

C14_005/006의 후보 `precision` 메타데이터에는 Button1 등 실제 IR/코드와
다른 이름도 남아 있다. 현재 평가는 독립 `binding_gt`로 접지하므로 이 메타데이터를
실제 ACTION 오류로 단정할 수 없다. 생성 파이프라인의 별도 정합성 점검 대상이다.

## 복사본 확인 결과

원본 6건은 현재 Explorer에서도 기존 첫 REFUSED 사유를 그대로 재현했다.

- VOID 5건에서 해당 `call.var`만 제거하면 catalog normalization과 pair 준비가
  모두 통과한다. gate를 0ms로 호출해도 4건은 D7, 메뉴 1건은 observable STRING
  전체 도메인 부재로 REFUSED다. 탐색 시간을 늘려 해결되는 문제가 아니다.
- C03_002는 **진단 목적으로만** IR/코드 양쪽에 `ServiceName=true`를 넣었다.
  현재 BOOL 서명을 형식상 만족시키자 다음 단계에서
  `query result requires exactly one bound device`가 나왔다.
  `true`가 서비스 이름이라는 뜻이나 수정 권고가 아니며, 임시로 첫 장벽을
  제거해 다중 반환 문제를 확인한 것이다. 원본 binding은 Main/Backup 두 대다.
- C14_005의 수정 복사본은 catalog/device capability 검사를 통과했다.
  이전 triage의 “selector/service 추가 확인 필요”는 이 부분에 한해 해소했다.

## 후속 작업과 formal 주장에 미치는 의미

1. 데이터 교정 시 위 5개 불필요한 반환 대입을 별도 변경으로 반영하고,
   입력/산술 문제는 후속 원인으로 유지한다. 오래된 원시 평가 수치는 보존한다.
2. C03_002는 현재 REFUSED를 유지하면서 API 서명·기본값·반환 집계·대상을
   일관되게 설계한다. 카탈로그 변경 시 Explorer의 읽기 역할 인증이 전체
   catalog SHA에 고정되어 있으므로 재검토/회귀/새 snapshot이 필요하다.
3. 상위 IR/catalog 검사에도 VOID 대입과 필수 인자 누락 검사를 추가하는 것이
   재발 방지의 작은 우선 작업이다. Explorer의 현재 거절을 완화할 사안이 아니다.
4. 입력 모델 검토에는 원래 C01_009/C01_018 외에 **C01_017도 같은 STRING
   유형으로 포함**한다. 기존 46건의 주원인 집계(명세 불일치6/입력한계2)를
   소급 변경하지 않는다. D7 네 건을 지원 확대할 필요는 없다.

formal verification은 잘 정의한 명세와 코드 사이의 관계를 보장한다.
정답 IR 자체가 서비스 계약과 모순되면 그 행을 유효한 검증 문제로 사용할 수
없다. 이 6건의 거절은 그 경계를 지킨 것이며, 이번 분석은 명세 신뢰성의
보완 근거다. 자연어 의도 전체의 정확성이나 Explorer 구현 전체의 증명을
대신하지는 않는다.
