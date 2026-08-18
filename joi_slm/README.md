# joi_slm — 한국어 IoT 명령어 → Timeline IR (sLM head + 규칙 조립)

2B 모델의 은닉 상태 위 **선형 head**(절 경계·타입·mods, 그래프 역할·범위·앵커)와 **결정론적 규칙**(상자 조립·슬롯·재정렬)로
명령어를 Timeline IR JSON으로 만든다. LLM 텍스트 생성 없음. 저확신 판정 자리에서만 9B 1토큰 객관식(선택). 연구 노트·실험 기록은 `slm/README.md`(§1–29), 실험 스크립트·데이터는 `slm/experiments/`.

```
텍스트 ─▶ WordEncoder(2B, prefill 1회: 층 2·6 단어 상태)
       ─▶ Segmenter: 경계 head(L2) → 절 / 타입·mods head(L6)   [저확신만 MCQ 게이트: 경계 2지선다·타입 8지선다]
       ─▶ graph.normalize: 역할·범위 부모·앵커 head(L6) → 필러 탈락·참조 이동·후치 절 앞으로
       ─▶ Retriever: Qwen3-Embedding 절 검색(카탈로그 문서 + 코퍼스 예문) + 역할·연결 기기 조인 → 절별 top-5, 조건 부분 값 서비스
       ─▶ builder.build: box(구조) + slots(cron/period/until/count/duration/for) + rerank(top-1 규칙) + 인자·조건식 규칙 → IR
```

## 파일

| 파일 | 역할 |
|---|---|
| `pipeline.py` | `CommandToIR(gates=True)` — 한 번 적재, `pipe(text, connected_devices)` → `{"ir", "segments", "mapping", "graph"}` |
| `encoder.py` | `WordEncoder`(Qwen3.5-2B-AWQ, 층 2·6 단어 마지막 토큰), `Embedder`(Qwen3-Embedding-0.6B) |
| `heads.py` | `SegHeads`(경계·타입·mods 로지스틱, PCA256) + `train_seg_heads` |
| `segment.py` | `Segmenter`(경계→절→타입·mods, 수사·단위 제약, MCQ 게이트), `MCQ`(vLLM completions 1토큰) |
| `graph.py` | `normalize`(역할·부모·앵커·방향 head → 절 재배열/필터) + `train_graph_heads` |
| `mapping.py` | `Retriever`(문서+예문 임베딩 검색, 조인, 조건 부분 재질의) → `Mapping`; `build_examples` |
| `builder.py` | `build(segments, Mapping)` → IR. 절 전처리(`slot_mods`, `seg_fix`, 두 번 읽기 관용구), 조건식·함수·인자 규칙, 후처리(상보 조건 ELSE, 주말) |
| `box.py` `slots.py` `rerank.py` `skeleton.py` | 규칙: 상자 조립기 / 시간·수량 슬롯·enum 어휘 / top-1 재정렬·값 관례 / IR 뼈대(평가) |
| `catalog.py` | 서비스 카탈로그(`loader.SERVICE_DATA`, `assets/effects.json`, 별칭), *Control 제외 |
| `evaluate.py` | `grade(ir, gold, cmd)` 계층 채점 S→T→C→V→A, 관례 동치, `gold_fix`(사용자 검토 결정) |
| `train.py` | 자산 생성 `python -m joi_slm.train [seg|graph|examples|all]` (`slm/experiments/` 상태 파일 필요) |
| `eval_gg.py` / `eval_para.py` | 380 G/G 평가(gold 절 + experiments 매핑) / 텍스트만 넣는 종단 평가(원문 80 + 패러프레이즈 160) |
| `assets/` | `seg_heads.pkl` `graph_heads.pkl` `examples.json` |

## 사용

```python
from joi_slm import CommandToIR                      # 리포 루트에서
pipe = CommandToIR()                                 # 2B + 임베더 적재, 게이트는 localhost:8002 vLLM 9B (없으면 gates=False)
r = pipe("거실 온도가 28도 이상이면 에어컨을 켜줘.", connected_devices)
r["ir"]         # {"timeline": [{"op": "start_at", ...}, {"op": "if", "cond": "TemperatureSensor.Temperature >= 28", "then": [...], "else": []}]}
r["segments"]   # [{"j", "text", "type", "mods", "p"}], r["mapping"] 절별 후보, r["graph"] 정규화 진단
```
서빙 파이프라인(`joi/generate.py`)의 Stage 1이 이 `CommandToIR`다(프로세스당 한 번 적재, `JOI_SLM_GATES=0`이면 게이트 없이 head만).
IR 안의 서비스 → 연결 기기 셀렉터는 `joi/devices.py`가 카테고리 조인으로 만든다.

평가(리포 루트에서, `slm/experiments/` 상태 파일 필요): `python -m joi_slm.eval_gg` / `python -m joi_slm.eval_para [--no-gates]`

## 수치 (2026-08-19)

| 조건 | 완전 IR |
|---|---|
| G/G — gold 절·타입·mods, 매핑은 5-fold 예문 확장 (380) | **0.989** (376/380; 잔여 4 = 녹음→저장 합성, IsAvailable 조회, 25→50→75 순환, gold cycle 표기) |
| 텍스트만 — 원문 80 (예문에서 자기 명령 제외) | 0.963 |
| 텍스트만 — 직접 작성 패러프레이즈 160 (held-out) | **0.738** (S 27 · C 12 · V 3) |

## 남은 일 (TODO)
- 패러 잔여: 경계·타입 head가 확신하고 틀리는 표현("연기가 감지된 뒤로는 …", "복도 조명이 켜지고 5분 뒤에"를 ACT로, 25→50→75 순환) → 표현 합성 증강 또는 게이트 문턱 확대; "재생 중이면 멈춰"의 Stop/Pause; 패러프레이즈가 뜻을 바꾼 C("넘게" > vs 원문 ≥).
- 합성 호출(녹음→저장 한 호출), IsAvailable 조회 관례, 25→50→75 순환 구조.
- 문자열 인자(Speak Text 등)는 영어 자유문 gold라 규칙 대상 아님(생성 과제로 별도).
- 매핑 예문(`examples.json`)은 380 gold에서 만든 것 — 새 카탈로그/데이터에 맞춰 `train.py examples` 재생성.
