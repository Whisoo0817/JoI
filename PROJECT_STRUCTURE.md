# 프로젝트 구조 및 운용 가이드

## 전체 서버 구조

```
[팀 공통 인프라 — 이삭 관리]
  MCP 서버          192.168.0.163:48012   허브/디바이스 제어 툴 제공
  Hub Controller    192.168.0.163:48005   IoT 허브 관리
  IoT Core          192.168.0.163:48001   에이전트 등록/상태 관리
  웹 프론트엔드      (이삭 서버)            채팅 UI, 세션 목록

[로컬 LLM 서버 — 우리(5090) 관리]
  vLLM              http://192.168.0.250:8002    Qwen3.5-9B-AWQ 추론 서버
  app.py            http://192.168.0.250:49999   JoI 코드 생성 API
  joi-agent         https://192.168.0.250:8012   채팅 에이전트 API (LocalAgentManager, TLS — self-signed 인증서)
```

## 채팅 데이터 흐름

```
웹프론트
  → GET 192.168.0.250:8012/chat?query=...&session_id=...
  → LocalAgentManager (ReAct 루프)
    → request_to_joi_llm  →  app.py (49999)  →  vLLM (8002)  →  JoI 코드 생성
    → add_scenario / control_thing_directly  →  MCP (48012)  →  허브
  → SSE 스트리밍 응답
```

## 폴더/파일 구조

```
/home/ikess/joi-llm/joi_new/          ← 우리 git 레포 (joi_new 서브모듈)
  app.py                               JoI 코드 생성 FastAPI 서버 (포트 49999)
  run_local.py                         generate_joi_code 핵심 로직
  tools.py                             MCP 툴 호출 + AGENT_TOOLS 스키마
  config.py                            vLLM 클라이언트 설정
  warmup.py                            vLLM prefix cache 웜업
  loader.py                            JoI 프롬프트 파일 로더
  parser/                              JoI 코드 파싱/검증
  files/                               JoI 언어 스펙 파일들
  paper/                               논문용 IR 파이프라인 실험 파일들
    timeline_ir_extractor.md           타임라인 IR 추출 프롬프트
    joi_from_ir.md                     IR → JoI 코드 생성 프롬프트
    ir_code_example.md                 IR 예시 모음
    paper_summary.md                   논문 요약
    timeline_ir.py                     타임라인 IR 추출 파이프라인
    run_local_ir.py                    IR 기반 코드 생성 실험 스크립트
  data/logs/                           에이전트 세션 로그 (session_id.log)

/home/tester/joi-agent/               ← 이삭 레포 clone (local 브랜치) — 직접 수정/커밋
  backend/main.py                      채팅 에이전트 FastAPI 서버
  backend/session_manager.py           세션/메시지 SQLite 관리
  agent/local_agent.py                 ReAct 루프 에이전트 (정본)
  agent/tools.py                       MCP 툴 호출 + AGENT_TOOLS 스키마 (정본)
  agent/config.py                      vLLM 클라이언트 설정 (정본)
  agent/joi_agent.py                   이삭 원본 (Agno 기반, 미사용)
  mcp_server/                          이삭 MCP 서버 코드 (우리가 켜지 않음)
  scripts/run.py                       백엔드 단독 실행 스크립트 (start-backend만)
  scripts/setup.py                     .venv 의존성 설치
  .env                                 환경변수 (직접 수정)
  data/sessions.db                     세션 DB
```

## 서버 실행 방법

```bash
# 1. vLLM (별도 tmux)
cd /home/ikess/joi-llm/joi_new && bash start_vllm.sh

# 2. app.py (별도 tmux) — http, 포트 49999
cd /home/ikess/joi-llm/joi_new && python app.py

# 3. joi-agent (별도 tmux) — https, 포트 8012, local 브랜치
cd /home/tester/joi-agent && git checkout local && ./scripts/run.py
```

> joi-agent는 self-signed 인증서로 HTTPS 제공 — 클라이언트는 `https://...` + 인증서 검증 우회 필요 (curl `-k`, requests `verify=False`).
> 내부 통신(agent → app.py)은 HTTP라 인증서 무관.

## 주요 환경변수 (.env)

```
LLM_BASE_URL=http://localhost:8002/v1       vLLM 서버
JOI_LLM_URL=http://localhost:49999          app.py
MCP_SERVER_URL=http://192.168.0.163:48012/mcp
HUB_CONTROLLER_URL=http://192.168.0.163:48005
IOT_CORE_URL=http://192.168.0.163:48001
JOI_AGENT_PORT=8012
AGENT_LOG_DIR=/home/ikess/joi-llm/joi_new/data/logs
```

## 이삭과의 협업 경계

| 영역 | 담당 |
|------|------|
| MCP 서버, 허브, 프론트 | 이삭 |
| vLLM, app.py | 우리 |
| joi-agent agent/, backend/main.py | 우리 (local 브랜치에서 직접 수정/커밋) |
| joi-agent session_manager.py, mcp_server/ | 이삭 (변경 시 알림 요청) |

## 주의사항

- `agent/local_agent.py`, `agent/tools.py`, `agent/config.py`는 `joi-agent local` 브랜치가 정본.
  수정 후 `git commit` + `git push origin local`.
- MCP 툴 추가/제거 시 `agent/tools.py`의 `AGENT_TOOLS` 스키마도 업데이트 필요.
- `get_weather` 툴은 MCP 서버에 없어 `AGENT_TOOLS`에서 제거됨 (환각 방지).
