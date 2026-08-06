# mapping_v2 — 제약 추출 + 조인 기반 디바이스 매핑 재설계

2026-07-20 Phase 0/1 산출물. 목표: 현행 3-step(retrieve→ground→resolve)의
프롬프트 박제 지식을 데이터 파생으로 교체 — SLM은 환경 무지 제약 추출만,
매핑은 오프라인 컴파일된 효과 인덱스 + 연결 디바이스 조인이 결정론적으로.

## v1 / v2 경계

파이프라인은 **매핑 단계에서만** 갈라지고 하류(IR·lowering·naming)는 공유한다.

```bash
python3 run.py        # v1 — 현행 매핑 (device_retrieve → ground_targets → device_resolve)
python3 run.py v2     # v2 — 이 디렉터리의 제약추출 + 접지선택
```

- 스위치는 환경변수 `JOI_MAPPING` (`v1` 기본 / `v2`) 하나뿐이다. run.py의 인자는
  이 변수를 세팅할 뿐이고, 서버(app.py)에서 v2를 쓰려면 같은 변수를 export 하면 된다.
- 접점은 `joi/generate.py`의 분기 블록 **한 곳**뿐이다 (resolver_v3 → pipeline_adapter로
  하류 계약을 그대로 만들어 넘긴다). v2 코드는 이 디렉터리 밖으로 새지 않는다.
- 반대로 이 디렉터리의 **라이브러리 모듈**(resolver_v3 / join_engine / extract_runner /
  gate_check)은 run.py를 import 하지 않는다. 연결 디바이스는 항상 호출자가 넘긴
  페이로드에서 온다 — 그래서 실서버 요청에도 그대로 동작한다. run.py를 읽는 것은
  각 파일의 `__main__` 하네스뿐이다.

## 파일

- `baseline_2026-07-20.jsonl` — Phase 0: run.py의 COMMANDS_1~4 전체(43개)를
  현행 파이프라인에 돌린 스냅샷 (명령/코드/로그/시간). 섀도 비교(Phase 4)의 기준.
  ok 40, 의도된 no_suitable_device 3 (커튼×2, 도어락 — 미연결 네거티브 테스트).
  ⚠️ ok=예외 없음일 뿐, 코드 정합성 판정은 아님 (COMMANDS_4는 증상 있는 성공들).
- `effects.json` — Phase 1a: 카탈로그 55스킬 · 247개 value/function 전수의
  효과 주석 {svc, kind, role, returns, effects[], ko_triggers[]}.
  카탈로그 대비 누락 0, 환각 id 0. (검증: gate_check.py)
- `rules_migration.json` — Phase 1b: device_rules 55개 파일의 기본 섹션을
  4버킷으로 분류: service_preference 53 / chaining 12 / ko_grounding 85 /
  unstructured 57 (+ arg-stage 섹션 목록은 현행 유지 대상으로 표기만).
  구조화율 72%. source_quote로 원문 검증 가능.
- `gate_check.py` — Phase 1 관문 스크립트 (재현: venv python으로 실행).

## 관문 결과 (2026-07-20)

순수 substring 매칭(임베딩 없음 = 최저 성능 floor) 기준:

| 조건 | 성적 |
|---|---|
| 전역 어휘, 필터 없음 | hit@1 64%, hit@3 84% |
| + 연결 디바이스 조인 필터 | recall@5 97% |
| + 어휘 2회 보강, STOP 동사 정책 | **recall@5 100% (30/30), 20/20 케이스 완전충족** |

핵심 발견: 어휘 매칭 오류의 대부분은 **미연결 카테고리**(DoorLock/Valve/ArmRobot)가
후보에 낀 것 → 조인 필터가 설계 의도대로 제거함. 잔여 갭 2건은 렉시콘 문제
(조건형 변형 "5분 이상 열려", 토큰 경계 "토스트로")로, 컴파일 정책 수정으로 해소.
임베딩 매처를 쓰면 이 클래스는 체계적으로 사라질 것.

수작업 라우팅 규칙(device_retrieve.md:42-47 — 메일/문자/챗봇/뉴스/시각) 전부
효과 인덱스에서 재현됨 → **"카탈로그가 바뀔 때 .md를 사람이 고친다"를
"컴파일 재실행"으로 대체 가능하다는 1차 증거.**

## device_rules 마이그레이션 요약

- 13개 파일은 규칙 자체가 없음 (Device Summary XML만).
- 처방 규칙(CaptureVideo>StartRecording, Switch-first on/off, SendSms>SendKakaoTalk,
  GreetMotion>Hello 등) 53건 → 효과 인덱스의 preference 주석 후보.
- 체이닝 12건($Chat/$GetNewsDigest→Speaker/Toast 등) → 합성 규칙 후보.
- unstructured 57건 = usage_note 후보 (인자 처방이 기본 섹션에 섞인 경우 다수:
  ChatProvider Message VERBATIM, MenuProvider GetMenu Command 스펙, NewsProvider Topic).
- 발견된 부채: DoorLock만 스테이지 헤딩이 소문자 `@enum_resolve`(비표준),
  RobotVacuumCleaner/Siren은 XML 안에 산문 규칙이 박혀 있음.

## Phase 2 결과 (2026-07-20) — 제약 추출, 관문 통과

- `constraint_extract_prompt.md` — 환경 무지 상수 프롬프트 (디바이스/카탈로그 0토큰).
- `extract_runner.py` — vLLM guided_json(+`enable_thinking:false`)으로 추출 →
  **단서 단위** 어휘 조회(∩ 연결 디바이스) → 카테고리 복원 측정.
- 성적: **카테고리 recall 30/30 (100%), 20/20 케이스 완전충족.**
  (1차 93% → 프롬프트 few-shot 1개 추가 + 질문형 전체 스팬 규칙 +
   TemperatureSensor 렉시콘 보강으로 100%)
- 관찰: 추출 그룹의 role/hard/quantifier가 대체로 정확
  ("모든 재실 센서" → q=all, 이메일 주소·전화번호가 args_text로 분리됨).
- 서버 주의: reasoning 파서가 켜져 있어 `chat_template_kwargs.enable_thinking:false`
  없이는 사고가 max_tokens를 소진해 content=None이 됨 (pipeline_helpers.py:28과 동일 처리).

정직한 캐비앳: (1) 복원 집합에 잉여 후보 포함 — recall 지표만 관문이고,
정밀도는 Phase 3 엔진(role/preference 필터)의 몫. (2) 렉시콘 보강을 측정에
쓴 20케이스에 대해 했으므로 과적합 위험 — Phase 4 섀도(43명령 전체 + 신규
명령)가 실제 시험대.

## 능력 체크 (2026-07-20) — Phase 3 엔진 프리뷰 (check_capabilities.py는 v3로 대체·삭제, 케이스는 test_v3_cases.py와 벤치마크 §1·§7에 승계)

두 급소 케이스를 디바이스 수준까지 실측:

- **"챗봇에게 ~ 물어봐줘" → Speaker 유도**: ✅ ChatProvider.Chat(role=read_action,
  returns STRING) + 명령에 sink 없음 → 체이닝 규칙(rules_migration의 ChatProvider
  chaining)으로 Speaker.Speak($Chat) 자동 추가, 태그는 자체 #Speaker.
  베이스라인의 라이브 버그(speaker_speak가 #ChatProvider에 핀됨, 4/4 재현)가
  새 구조에선 구조적으로 발생 불가.
- **"불 켜줘" → Light ∪ Switch[LightSwitch]**: 1차 ❌(23대 과선택 — Switch
  카테고리 어휘에 '불'이 있어 플러그/공기청정기/가습기까지 점화) →
  **어휘 분해 원칙 확정: 배선 의존 의미('불')는 카테고리가 아니라 TAG 어휘에만**
  (extrinsic affordance). Switch 카테고리 트리거에서 불/전등/조명 제거,
  TAG_LEXICON[LightSwitch]에만 유지 → ✅ 16대 (Light 10 + LightSwitch 벽스위치 6),
  비조명 Switch 호스트 7대 정확히 제외. 두 관문 회귀 없음 (둘 다 100% 유지).

새 컴파일 산출물: TAG_LEXICON (태그 수준 affordance 어휘) — 지금은
check_capabilities.py에 인라인, Phase 3에서 별도 파일로 승격 필요.

## 직접 돌려보기 — try_command.py (v3 기반)

명령 하나가 ①제약 추출(LLM #1) → ②지시 해소(후보 합집합 → LLM #2 선택) →
③최종 매핑(능력검사/selector/수량/체이닝)까지 어떻게 흘러가는지 단계별로 출력.
대화형 모드에는 벤치마크 대표 예제 10개가 번호 메뉴로 내장돼 있다
(등가성/능력필터/대조한정어/id분해/체이닝/복합문/에러귀속/부재all/구역스코프).

```bash
cd mapping_v2
V=/home/ikess/joi-llm/venv/bin/python
$V try_command.py                               # 대화형: 1~10 또는 임의 명령, q 종료
$V try_command.py "불 켜줘"                     # 단건
$V try_command.py "..." --base --devices        # 베이스라인 비교 + 디바이스 목록
```

## Phase 3 — 조인 엔진 (join_engine.py)

LLM 없음. 입력은 추출된 제약 그룹, 출력은 (quantifier, selector 태그, 서비스) 클러스터.

- 선호/처방 규칙은 `preferences.json`이 공식 저장처 (2026-07-20 승격 — 구
  device_rules 기본 섹션의 후계. 새 규칙은 .md 산문이 아니라 여기에 한 줄).
  rules_migration.json의 53건 중 3건 활성, 나머지는 검토 후 승격 대기.
- 어휘 3층 분리 — **왜 나눴는지가 핵심**:
  `effects.json`(효과 트리거, 서비스 선택용) / `category_aliases.json`(디바이스를
  부르는 명사, 식별 전용) / `tag_lexicon.json`(태그 수준: 외재적 affordance
  LightSwitch, 브랜드, 구역, fixture Door/Window). 효과 트리거를 식별에 쓰면
  "카메라 사진 메일로 보내줘"처럼 타 디바이스 이름이 문맥으로 섞여 오염된다.
- **특이성 규칙**: 태그 집합이 카테고리 집합의 진부분집합이면 태그가 이긴다
  ("문" → ContactSensor 4대 ⊃ Door 1대 → Door). 서로소면 합집합
  ("불" → Light 10 ⊍ LightSwitch 6 → 16). 이 한 줄이 두 상반된 케이스를 모두 처리.
- 토큰 정밀도: 1글자 토큰("문")은 트리거와 정확 일치만 — 부분문자열이면
  "창문"의 Window 태그까지 오염됨 (실제로 밟은 버그).
- 서비스 선택: 밝기/레벨 > on/off 축약(Switch-first, Light 폴백) > 트리거 스코어
  > preference(CaptureImage>CaptureVideo>StartRecording, SendSms>KakaoTalk)
  > 단일 서비스 폴백 > 조건절 대표 read.
- 체이닝: read_action+STRING & sink 없음 → Speaker.Speak(자체 태그);
  read_action+BINARY 상류 → 하류 SendMail을 SendMailWithBinaryFile로 승격.
- 실현 불가 클러스터 드롭: 밝기 지정 시 LightSwitch 클러스터 제외(On/Off만 가능),
  전원 의도에 Switch/Light 없는 클러스터 제외(투야 버튼/화재센서/카메라).
- selector/quantifier는 프로덕션 `minimal_tags_for` / `quantifier_for` 그대로 재사용.

## 태그로 분리 불가능한 형제 디바이스 (2026-07-20, KT 공기청정기 케이스)

페이로드에 KT 공기청정기를 추가하면 삼성 큰거/작은거와 **의미 태그가 완전히
동일**해진다 (셋 다 Smartthings/AirPurifier/Switch/lindytest, 브랜드 태그 없음).
"삼성 공기청정기를 모두 꺼줘"에서:

- 조인은 처음부터 정확했다 — 닉네임 '삼성' ∩ 카테고리 '공기청정기' = 삼성 2대,
  KT 제외. 문제는 **selector 렌더링**이었다.
- `minimal_tags_for`는 이 경우 `exact=False`(어떤 태그 조합도 이 집합만 못 고름)로
  공통 태그를 돌려주는데, 엔진이 그 플래그를 무시하고 `#AirPurifier #Smartthings
  #Switch`를 찍어 런타임에 KT까지 포함시켰다.
- 수정: `exact=False`면 클러스터를 **디바이스별 id selector로 분해**한다
  (`(#tc0_01df…).Switch.Off` + `(#tc0_efb0…694).Switch.Off`). 3줄 변경.

검증: 삼성 2대 → id 2줄(KT 제외) / "KT 공기청정기 꺼줘" → id 1줄 /
"공기청정기 다 꺼줘" → `all(#AirPurifier)` 3대(태그로 정확히 표현 가능하므로 유지).
섀도 35/40, 관문 100% 회귀 없음.

## Phase 4-엄격판 (2026-07-20 재측정) — 교체 판단의 근거 수치

이전 34/40은 계측이 물렀다: 서비스를 카테고리로 뭉갬(On≡Off), id를 '<id>'로
정규화(다른 기기 선택도 일치 처리). 엄격판은 **전체 서비스 id + selector를
실제 디바이스 집합으로 해석**해 비교하고, 역할(read/action)은 렌더링이 아니라
서비스 속성에서 유도한다 (지속 조건이 if-폴링으로 렌더되는 비대칭 제거).

**결과: 일치 32/40 (거부일치 2) | 불일치 8** — 잔여 diff 전수 판정:

| diff | 판정 |
|---|---|
| 챗봇 Speak 대상: base=AI 챗봇(라이브 버그) vs v3=JOI 스피커 | **v3 우세** — 엄격판이 디바이스 수준에서 버그를 가시화 |
| Toast 누락 2건 (알림도 띄워줘 / 경제 뉴스) | ✅ 수정 완료 (리졸버 채널별 클러스터 + 추출 규칙) |
| 메일 첨부 승격 3건 ("녹화 시작하고 메일") | ✅ **정책 승격** (2026-07-20): 녹화+메일 = 파일 전송 의도. CaptureVideo(기본 10초)→SendMailWithBinaryFile이 정답, 베이스라인 SendMail이 구식 |
| Clock: base=Hour+Minute 2회 읽기 vs v3=Datetime 1회 | ✅ 수정 완료 (CLOCK_TIME_EXPAND 정책) |
| 미세먼지: base=FineDustLevel vs v3=DustLevel | ✅ 수정 완료 (렉시콘 정책 정렬) |
| 무지칭 "~라고 알려줘" +Toast 4건 | **정책 확정 diff** — 무지칭 notify는 무조건 양채널, 베이스라인 Speaker-only가 구식 |
| 커튼 거부 방식 (전체 거부 vs 조건 유지+귀속 에러) | 정책 미결 (4-5) — 유일하게 남은 항목 |

**2026-07-20 최종 판정: 엄격 섀도의 모든 diff가 해소되거나 판정됨.**
32 일치 + 의도된 정책 diff 7 (채널 4, 메일 첨부 3) + v3 우세 1 (챗봇) =
**정책 기준 40/40**, 잔여 미결은 커튼 부분-실현 정책 1건뿐.

발견 부수효과: 엄격판이 '녹화 시작'→StartRecording 오선택(반환값 없음)을
드러냈고 CaptureVideo 트리거 보강으로 해소 — 무른 계측에선 3케이스 모두
"일치"로 숨어 있었다.

교체 전 필수 수정 3: ①추출기 notify 채널 병합, ②메일 승격 조건(연결어),
③Clock 다중 읽기. ①③은 국소 수정, ②는 추출 스키마에 dataflow 표지 추가.

## Phase 4 — 섀도 비교 (shadow_compare.py) 결과 (구판 — 계측 물렀음, 참고용)

베이스라인 43명령을 (quantifier, selector 태그셋, 카테고리) 삼중항으로 투영해 비교.
**일치 35/40, 불일치 5 (거부 일치 2 별도).**

남은 5건 판정:
- ✅ **신규 우세 1건** — "챗봇에게 물어봐줘": base가 speaker_speak를 `#ChatProvider`
  태그에 핀(라이브 버그, 4/4 재현), 신규는 `#Speaker`. 구조적으로 재발 불가.
- ❌ **신규 열세 1건** — "경제 뉴스 알려줘": 채널 미지정 기본값이 Speaker+Toast인데
  추출이 notify 그룹을 병합해 Toast 누락. 추출 프롬프트 보강 필요.
- ⚖️ **동등/표현차 3건** — 투야(같은 8대를 base는 `#Tuya #Switch` 한 클러스터,
  신규는 LightSwitch+SharedLight 두 클러스터), 단일 디바이스 조건의 all 접두사
  유무, 하나라도 조건의 any/all(1대라 동일).
- 별도: "커튼" 명령에서 base는 전체 거부, 신규는 조건절만 살리고 커튼에 귀속 에러.
  제품 결정 사항(부분 실현 허용 여부).

하네스 주의: 조건절 selector는 항상 `all(...)`로 렌더되고 any/all 구분은 비교
연산자(`==` vs `==|`)가 담당 — 초기에 이걸 몰라 불일치 29건으로 과대 집계됐다.

정직한 캐비앳: 어휘(별칭/트리거)를 이 43명령 diff를 보며 보강했으므로 이 수치는
과적합 상한이다. 진짜 검증은 미본 명령 세트 + 다른 디바이스 구성.

## v3 — 지시 해소에 모델 판단 복원 (resolver_v3.py, 2026-07-20)

v2의 한계(대조적 의도 "KT 말고 삼성", 표기 불일치 samsung↔삼성, 실현 가능성
판단)를 해소하기 위해 **두 번째 LLM 호출을 추가하되, 출력을 후보의 부분집합으로
가둔** 구조. 3-step 회귀가 아닌 이유가 이 제약에 있다.

역할 분담:
- **A. 제약 추출** (LLM #1, 환경 무지) — 발화→그룹. v2와 동일.
- **B. 후보 생성** (Python, recall 지향) — 어휘 3층으로 후보를 **합집합**으로
  넓게 수집 (v2의 AND 조인과 달리 좁히지 않음. 좁히기는 LLM 몫).
- **C. 지시 해소** (LLM #2, `select_devices_prompt.md`) — 후보 목록
  `dN | nickname | categories | tags` + 명령 전문을 보고 사용자가 가리킨
  부분집합 선택. guided decoding enum이 후보 dN으로 고정 → 환각 구조적 불가.
  후보 0~1개면 호출 생략. 출력은 `{"selected": [...]}`뿐 (자유 산문 금지 —
  reason 필드를 뒀더니 잘려서 JSON이 깨졌음. 제외 목록은 Python이 역산).
- **D. 검증·표현** (Python) — 선택 재검증 → 실현 가능성 검사 3종(채널 부재/
  지칭 불일치/능력 없음 → 귀속 에러) → 서비스·selector·수량·체이닝 (v2 재사용).

프롬프트에서 얻은 교훈 2개:
1. **조건절은 감지 대상을 말한다** — "사람이 감지되면"의 '사람'을 보고 LLM이
   "재실 센서는 사람이 아니다"라며 전부 거부(과잉 거부). "condition 그룹은
   현상을 측정하는 디바이스가 정답" 규칙 추가로 해소.
2. **대체 금지 원칙** — "삼성 에어컨"에 에어컨이 헤이홈뿐이면 빈 선택이 정답
   (가장 비슷한 기기로 대체하지 않음). 명시 지칭에만 적용, 조건절엔 미적용.

검증 (test_v3_cases.py, 7/7):
- 삼성 지정 → KT 제외 (대조적 의도) / 한정어 없음 → KT 포함 전체
- 태그 `samsung`·닉네임 영문 기기를 한글 "삼성"으로 지칭 → 매칭 (표기 초월)
- 스피커·토스트 모두 미연결 + "알려줘" → 귀속 에러 (조용한 성공 방지)
- 기존 능력 회귀: 불→16대, 챗봇→Speaker 체이닝, 에어컨×습도 에러

섀도 (shadow_compare.py --v3): **34/40 일치**, 잔여 diff는 v2와 동일 부류
(챗봇=신규 우세, 투야/단일디바이스=표현차, 경제뉴스 Toast=추출 이슈).
비용: 그룹당 최대 1회 추가 호출(후보 2개 이상일 때만), 프롬프트는 후보 수에
비례하는 소형. 메인 추출 프롬프트는 여전히 상수라 prefix cache 유지.

## 다음 단계

0. v2(join_engine 단독) vs v3(선택 LLM 포함) 중 v3를 주 경로로: 어휘는 후보
   생성(recall)만 책임지므로 완벽할 필요가 없어져 유지비가 급감한다.
1. 어휘 자동 컴파일 — 지금 category_aliases/tag_lexicon은 수작업 시드다.
   카탈로그 descriptor + 페이로드 태그에서 LLM 배치로 생성하도록 전환해야
   "카탈로그 바뀌면 재컴파일" 주장이 완성된다.
2. 임베딩 매처로 교체 (현재는 substring floor).
3. 미본 명령 세트로 재측정 → 승률이 유지되면 플래그 뒤 단계적 교체.

미결(사용자 결정 필요): quantifier 정책 테이블 — 출력 계열 디바이스 기본값
any vs 되묻기.
