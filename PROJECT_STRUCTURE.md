# joi-llm (joi_new) — 프로젝트 구조

한국어 자연어 명령을 **JoI 자동화 코드(DSL)로 변환하는 독립 API**. joi-agent와 별개이며,
5090 한 박스에서 전부 처리한다(vLLM 추론 + 코드 생성 파이프라인). MCP/허브 제어는 이
레포의 관심사가 아니다 — 생성된 코드를 받아 실행하는 건 소비자(joi-agent) 쪽 일이다.

## 서버 구성 (모두 5090)

```
vLLM        192.168.0.250:8002    Qwen 추론 서버 (start_qwen36/35 스크립트)
app.py      192.168.0.250:49999   JoI 코드 생성 API (FastAPI)
```

## API (app.py, :49999)

| 엔드포인트 | 설명 |
|---|---|
| `POST /generate_joi_code` | 핵심. 명령 → JoI 코드 |
| `GET /health` | 헬스체크 |
| `POST /warmup` | vLLM prefix-cache 웜업 |

- **요청**: `{sentence, model, connected_devices, current_time, other_params?}`
- **응답** (`schemas.JoiLLMResponse`): `{success, error_code, error_message, details, command,
  code:[{name,cron,period,code}], log}` — `error_code`는 숫자 enum(`JoiErrorCode`).
- 매 요청은 `request_log.jsonl`에 "명령→과정→결과/에러" 한 줄로 추적(최근 10개 유지).
- `reload=True`로 `*.py`/`*.md` 편집 시 자동 재시작.

## 코드 생성 파이프라인 (IR 기반, device-first)

진입점은 `paper.run_local_ir.generate_joi_code` (`run_local.py`는 호환 shim). 단계:

1. **디바이스 타게팅** — device_retrieve → ground_targets(LLM, 디바이스 매칭) → device_resolve(서비스 선택) + Python 헬퍼(태그/수량자)
2. **영어 번역** — IR/lowering 프롬프트용
3. **병렬** — A: enum_cond_check → enum_resolve → arg_resolve → IR 추출 / B: precision 셀렉터
4. **lowering** — `joi_from_ir` (IR + precision → JoI, 구조 클래스별 버킷 라우팅)
5. **네이밍** — re_translate → re_translate_kor → scenario_name

프롬프트는 `files/*.md`, 서비스 스펙은 `files/service_list_ver2.0.5.json`.

## 폴더/파일 구조

```
joi_new/
  app.py                 FastAPI 서버 (:49999) — 엔드포인트 + 응답 변환 + 요청 추적
  run_local.py           shim → paper.run_local_ir.generate_joi_code
  schemas.py             JoiErrorCode(enum) + JoiLLMResponse + map_error_code
  config.py              vLLM 클라이언트 / model_id 캐시 / count_tokens
  loader.py              service_list 로딩 (SERVICE_DATA, SUB_SKILL_TAGS)
  pipeline_helpers.py    LLM 추론 호출 + 서비스 상세 추출 + 코드 후처리
  device_ontology.py     결정적 디바이스 타게팅 헬퍼 (태그/수량자, LLM 없음)
  warmup.py              vLLM prefix-cache 웜업
  test.py / run.py       로컬 테스트 / 실행
  request_log.jsonl      최근 요청 추적 로그
  files/                 파이프라인 프롬프트(*.md) + service_list(JSON) + devices/
  parser/                ANTLR JoI 문법(JOILang.g4) + validator (코드 검증)
  paper/                 활성 IR 파이프라인(run_local_ir.py) + 논문용 평가 스크립트
  experiments/           실험 결과 산출물
  dataset_migration/     service_list 마이그레이션 규칙/검증
  start_qwen36_5090.sh   vLLM: Qwen3.6-35B-A3B-NVFP4 (2×5090, 기본)
  start_qwen35_9b_5090.sh vLLM: Qwen3.5-9B-fp8 (1 GPU, 빠른 테스트)
  AGENTS.md              JoI DSL 스펙 (:=, =, any/all 등)
```

## 실행

```bash
cd /home/ikess/joi-llm/joi_new

# 1) vLLM (:8002) — 별도 tmux. 기본은 35B(2 GPU), 가벼운 테스트는 9B
./start_qwen36_5090.sh          # 또는 ./start_qwen35_9b_5090.sh

# 2) 코드 생성 API (:49999) — 별도 tmux
python app.py
```

> vLLM 스크립트는 RTX 5090(sm_120)에 필요한 3개 export를 이미 설정한다:
> `CUDA_HOME`=pip nvcc 13.2, `PATH`, `PYTHONPATH=/home/tester/joi-agent`(CJK logits-processor 플러그인).

## 주요 환경변수

```
LLM_BASE_URL=http://localhost:8002/v1   vLLM 엔드포인트 (config.py / app.py)
LLM_API_KEY=EMPTY                        (기본값)
```

## 참고

- 에러 코드 체계는 `schemas.py`의 `JoiErrorCode` / `map_error_code` (IR·lowering 내부 코드는
  전부 `REASONING_FAILED`로 접힘 — 외부 소비자는 IR 계층을 모른다).
- JoI 언어 문법/의미는 `AGENTS.md`, 문법 검증은 `parser/validator.py`.
