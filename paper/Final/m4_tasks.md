# Mac mini (M4) 작업 지시 — OVLA RQ4 on-device 측정

**컨텍스트**: SenSys 논문 OVLA의 RQ4(On-Device Cost) 실측. 이 기기(Mac mini M4 16GB)가
논문의 primary edge device다. vLLM-MLX 서버가 `localhost:8000`에 떠 있다 (모델 `qwen3-8b`,
API key는 서버를 띄운 터미널 명령에서 확인; **키를 절대 파일로 커밋하지 말 것**).
시작 전 `git pull` (브랜치 `paper`, 커밋 `f63681e` 이상 필요).

**먼저 읽을 파일**:
- `paper/Final/rq4_experiment_plan.md` — 전체 측정 프로토콜 (DESIGN A 절)
- `paper/bench_verifier_m4.py` — verifier latency 벤치 도구 (docstring 포함)
- `paper/Final/overleaf_changes.md` C2–C4 절 — 측정값이 논문 어디에 들어가는지

**공통 규칙**:
- 결과는 전부 `paper/Final/evaluation/results/` 아래 JSON/텍스트로 저장 후 커밋
- verifier/시뮬레이터 코드(`paper/verifier/`, `simulators/`)는 절대 수정 금지
  (논문 결과와 묶여 있음). 측정용 코드 추가만 가능
- 각 결과 JSON에 측정 환경 메타데이터 포함: 맥 모델/RAM/macOS 버전/vLLM 버전/모델 ID
- 끝나면 결과 JSON들만 커밋 (메시지 "M4 RQ4 measurements") 후 push

---

## 작업 (순서대로)

### 1. Verifier latency 382 전수 (LLM 불필요, ~15분 예상)
```bash
PYTHONPATH=. python3 paper/bench_verifier_m4.py \
  --bundle paper/Final/evaluation/results/m4_bench_input.json --reps 10 \
  --out paper/Final/evaluation/results/m4_verifier_latency.json
```
- 참고 (x86 예비측정): p50 1.7ms / p95 0.92s / worst ~21s. worst는 전부 C19
  (짧은 period × 7-day horizon → tick 폭발) 클래스. M4 분포가 논문 헤드라인 수치가 된다.
- 스킵 2건(C09_3, C03_24)은 정상 (reject된 행이라 joi_block 없음).

### 2. LLM judge per-check latency ~20건
- `paper/run_judge_compare.py`의 `_judge_prompt(ir, joi)` 방식 그대로: IR + JoI + 문법 +
  동치 정의를 `localhost:8000`의 8B에 보내 판정 1건당 wall-clock 측정.
- 입력: 1번과 같은 번들(`m4_bench_input.json`) + `dataset.csv`의 `ir_gt` 칼럼.
  카테고리 골고루 20건. temperature 0, 단일 질의, `enable_thinking: False`.
- 20건의 per-check p50/p95/min/max 저장 → `m4_judge_latency.json`.
- 용도: fig:rq4(a)의 가운데 바 ("local 9B-class judge = 수십 초/check").

### 3. Warm E2E latency 10건
- `test.py`의 `test_targets` dict를 쉬운 행 10개(서로 다른 카테고리)로 교체 후:
```bash
LLM_BASE_URL=http://localhost:8000/v1 LLM_API_KEY=<키> PYTHONPATH=. python3 test.py target
```
- 로그(`/tmp/joi_target_*.log`)의 `➡️ <stage>(<tok>) | ... | Total: <X>s` 줄을 파싱해
  스테이지별 latency 분포 저장 → `m4_e2e_stage_latency.json`.
- 첫 행=cold, 이후=warm으로 구분 기록. (기존 cold 1건: C09_3 총 ~5.1분 =
  pre_analysis 15.6s / service_plan 33.1s / arg_resolve 46.5s / device_match 54.1s /
  IR extract 71.3s / lowering 50.3s / diagnose+retry ~32s)
- prefix cache 효과 확인됨(동일 7k-tok prefill 35.3s → 0.4s)이므로 warm이 크게 짧아야 정상.
- 끝나면 `git checkout test.py`로 원복.

### 4. 메모리
- 3번 실행 중 vLLM 프로세스 peak RSS (`ps -o rss= -p <pid>` 주기 샘플링 또는 Activity Monitor)
- 1번 벤치의 `peak_rss_mb` (자동 기록됨) = verifier 프로세스 메모리
- 둘을 합쳐 `m4_memory.json`으로 저장.

### 5. 전력 (sudo 필요 — 사용자에게 비밀번호 입력을 요청할 것)
```bash
sudo powermetrics --samplers cpu_power,gpu_power -i 1000 -n 60  > /tmp/idle.txt       # 유휴 기준선
sudo powermetrics --samplers cpu_power,gpu_power -i 1000 -n 300 > /tmp/generating.txt # 3번 실행 중
sudo powermetrics --samplers cpu_power,gpu_power -i 1000 -n 120 > /tmp/verifier.txt   # 1번 실행 중
```
- 3구간 각각 CPU/GPU power의 mean/peak (W) 요약 → `m4_power.json`
  (원본 txt도 `paper/Final/evaluation/results/m4_power_raw/`에 보관).

### 6. 모델 로드 시간
- vLLM 서버 재시작 1회 (사용자와 조율): 시작 명령 시점 → `/v1/models` 200 응답까지 초 측정.
- `m4_memory.json`에 `model_load_s` 필드로 기록.

---

## 결과가 논문에 들어가는 자리 (참고)
- 1번 → fig:rq4(a) "verifier (ms)" 바 + §8.4 latency 분포 문장 (p50/p95/worst)
- 2번 → fig:rq4(a) "local judge (s)" 바
- 3번 → §8.4 authoring-time(1회 비용) 보고: cold vs steady-state(warm)
- 4·5·6번 → §8.4 "peak memory, power, model load time" 문장
- 주의: 논문 본문 수정은 하지 말 것 (수정 가이드는 별도 파일 `overleaf_changes.md`에서 관리 중).
  이 기기에서는 측정 + 결과 JSON 커밋까지만.
