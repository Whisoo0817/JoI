# OVLA 실험 총괄 인덱스 (2026-06-06 기준, 논문 = ovla_final.tex)

논문에 들어가는 모든 수치의 (1) 실험 방법, (2) 실행 커맨드, (3) raw data 위치, (4) 최종 수치를 한곳에 정리.
경로는 레포 루트(`~/joi`) 기준. `results/` = `paper/Final/evaluation/results/`.

공통 전제:
- 데이터셋: `dataset.csv` (루트, 382행, 24 categories, sha256 앞 16 = `23337e472c4d11cc`)
- 시뮬레이터/검증기 코드: `paper/simulators/` (fall variant 포함 커밋 `d7fe27f`)
- comparator 의미론: ±100ms 그룹 + 그룹 내 dedup (`paper/simulators/comparator.py`)
- 모델 서빙: 9B=Qwen3.5-9B-AWQ(vLLM, A6000), 8B=`~/temp/bin/vllm serve Qwen/Qwen3-8B-AWQ --port 8003`, E4B=Gemma-4-E4B-AWQ. `LLM_BASE_URL` env로 지정.

---

## RQ1 — Rendering faithfulness (§8.1)

**방법**: 결정론 renderer(`paper/ir_renderer.py`)가 IR의 유한 슬롯에 주입된 fault를 평문에 surface하는지.
Part A = 실제 NL→IR 오류 55쌍(382 run에서 추출; catalog arg gate가 상류 기각한 행은 모수 제외),
Part B = 8개 fault class 합성 주입 1,504쌍.

**커맨드**: `python3 -m paper.run_faithfulness_surfacing`

**Raw**: `results/faithfulness_surfacing.json` (키: `claim`, `part_A_real_errors`, `part_B_synthetic_by_class`)
보조: `results/nl2ir_error_distribution.json` (`paper/extract_nl2ir_errors.py`; 382행 중 idiom-동치 323 / 진짜 오류 59 분포),
`results/rendering_worked_examples.json` + `paper/plot_worked_examples.py`, `paper/plot_rq1_substitute.py`

**최종 수치**: Part A **55/55 = 100%**, Part B **1,504/1,504 = 100%** (blind 0)

---

## RQ2 — Detection power: mutation + coverage (§8.2)

### Mutation (12 operators)

**방법**: stageB on-arm JoI dump를 시드로 mutation operator 적용 → IR-sim vs mutant-JoI trace 비교로 catch 여부. equivalent mutant는 결정론 필터로 제외.

**커맨드** (5-shard; `MUT_SEED_DIR` env로 시드 지정):
```
MUT_SEED_DIR=experiments/mutation_382_fall/seed_dump_on \
  python3 -m paper.run_mutation_test --shard A   # A..E
```

**Raw**:
- 시드 dump (357 JoI): `experiments/mutation_382_fall/seed_dump_on/` (원본 `/tmp/joi_stageB_full_llm_v2/on`에서 보존)
- 샤드별 결과+로그: `results/mutation_fall/mutation_{A..E}.{json,log}` (= `experiments/mutation_382_fall/`에도 사본)
- 구버전(fall 이전, superseded): `results/mutation_v3.json`, `results/mutation_refix/`

**최종 수치**: 유효 시드 **328**, 생성 **1,651** / equivalent **99** / genuine **1,552** / caught **1,541** = **99.3%**.
Survivor 11 = comparator 8 (sub-tolerance), call_drop 2, cmp_direction 1.

### Coverage (spec-side + impl-side)

**방법**: IR-FSM transition-boundary obligation 열거(`paper/simulators/coverage.py`) vs 합성 스위트가 실제 행사한 것. impl-side = 같은 스위트가 생성 JoI의 분기를 도는 비율.

**커맨드**:
```
JOI_DUMP_DIR=experiments/stageB_382/20260528_170116__d886015/intermediate/on \
  python3 -m paper.run_coverage_report
```

**Raw**: `results/coverage_fall.txt` (2026-06-06 정식 dump로 재생성, 수치 재현 확인). 구버전: `results/coverage_v3.txt`

**최종 수치**: spec **350/359 = 97.5%** (미커버 9 = counter-modulo guard else쪽, var-cmp/arith 비합성 guard),
impl **676/692 = 97.7%** (236 JoI programs).

---

## RQ3 — Safety: gate 분포 + 양방향 독립 재심 (§8.3)

### Gate 분포 (3 모델, paired 설계: off-arm 시드 주입 후 on-arm)

**방법**: `paper/run_lower_gt_paired.py`. off-arm(verifier OFF) 산출물을 시드로 on-arm 재실행 → divergent/repaired/rejected/deployed 분류.

**Raw** (run.json에 provenance):
- 9B: `experiments/stageB_382/20260604_220553__paired/results/paired_summary.json` (pre-fall)
  + fall delta: `experiments/stageB_382/20260606__paired_fall/` (C11_7, C11_8 재실행 — repair 2회 실패 → fail-closed reject; `paired_summary_fall.json`)
- 8B: `experiments/stageB_382_8B/20260604_221020__paired/` + `experiments/stageB_382_8B/20260606__paired_fall/`
- E4B: `experiments/stageB_382_gemma4/20260604_220114__paired/` (fall 영향 없음)

**최종 수치 (post-fall, 논문 표 기준)**:
| model | divergent w/o gate | repaired | rejected | deployed |
|---|---|---|---|---|
| 9B  | 35 (9.2%)  | 11 | 24 | **358 (93.7%)** |
| 8B  | 63 (16.5%) | 11 | 52 | 330 (86.4%) |
| E4B | 55 (14.4%) | 16 | 39 | 343 (89.8%) |

silent-wrong은 세 모델 모두 **0**.

### 기각 방향 재심 (전수 audit)

기각 33건 수동 audit: 33 genuine + 2 subset, 오기각 0. (세션 기록; semantic reject 재현은 dense replay fail-side 참조)

### 배포 방향 재심 (dense replay)

**방법**: pre-registered protocol = `paper/eval/dense_replay_protocol.md` (제외사유 4건 + 판정 3분류 사전 등록).
배포된 (gt_ir, JoI) 쌍 전체를 무작위 dense 시나리오 K=100으로 재생 (≈36,000 replays), fail-side는 K=50.

**커맨드**:
```
python3 -m paper.run_dense_replay \
  --from-paired experiments/stageB_382/20260604_220553__paired --k 100 --k-fail 50 --seed 7
```

**Raw**: `results/dense_replay.json` (+ pilot `results/dense_replay_pilot.json`)

**최종 수치**: pass 358 중 **356 완전일치**, 2건(C12_6, C12_8) = 위상 아티팩트(tolerance 설계 허용).
fail 재현 19/20 (C20_4는 경계정밀 버그라 무작위로 불가).
**발견→보강 서사**: 초기 replay가 C11_8 절대값 버그(genuine miss) 발견 → synthesizer에 fall variant 추가
(`paper/simulators/event_synth.py` reg 시딩 lo/hi/fall, `coverage.py` reg_fall obligation, 커밋 `d7fe27f`)
→ C11_7도 결정론 검출 → RQ2/RQ3 전 수치 재실행이 위 표.

---

## RQ4 — On-device cost + 실배포 (§8.4)

### M4 측정 (Mac Mini M4 16GB, vllm-mlx, Qwen3-8B-4bit)

**방법**: `paper/bench_verifier_m4.py` (verifier latency 378행×10 reps), powermetrics 전력.

**Raw**: `results/m4_verifier_latency.json` (p50 **0.97ms** / p95 697ms / worst 8.4s),
`results/m4_power.json` + `results/m4_power_raw/{idle,verifier,generating}.txt` (verifier **5.5W**, no GPU),
`results/m4_memory.json`, `results/m4_e2e_stage_latency.json`

### 실배포 (Mysmax/JoI 상용 플랫폼, Pi 허브 + 실기기)

**방법**: 라이브 작성 6명령, gated 파이프라인 → 실기기 deploy 관찰.

**Raw**: `results/deployment/live_raw/LIVE_*__gated.json` (hero retry 포함),
`results/deployment/observations.json`, `results/deployment/registration_package*.json`
그림: `figs/deployment.pdf` (생성 스크립트 plot_rq4.py는 cleanup 시 삭제; git 히스토리에 보존)

**최종**: hero(TV플러그) 30s vs 5:00 timeline trace, 자연 발생 버그 4/4 gate 검출, 세션 5/6 기각 사례. Layer A 에피소드 2건.

---

## §3 Motivation (LLM-judge 비일관성)

**방법**: `paper/run_instability.py` — 동일 (IR, code) 쌍을 LLM judge에 반복 질의, verdict 분산 측정. 6-cell (9B/GPT-5.1 × temp0/temp0.7/vote5).

**Raw**: `results/instability/` (6 json + README), `results/instability_*.json`, `results/injected_*.json`, `results/multigt_*.json`
그림: `paper/plot_instability.py`

**최종**: 9B flip 27.0%, GPT-5.1 10.6% floor (vote5에도 잔존); multi-GT 30/30에서 verifier invariant.

---

## 정리 이력 (2026-06-09 paper 폴더 cleanup)

논문 작업 종료 후 구버전·중간 산출물·작업노트를 삭제. 전부 git 히스토리에 남아 복구 가능.

- **삭제된 superseded 결과**: `results/mutation_v3.json`·`results/mutation_refix/`(→`mutation_fall/`이 대체), `results/coverage_v3.txt`(→`coverage_fall.txt`), `results/rq3_pipeline_effect.json`·`results/ovla_results.xlsx`(중간 산출물).
- **삭제된 dead 실험 스크립트**: `aggregate_motivation.py` `plot_motivation.py` `build_equiv_stress.py` `build_mutant_stress.py` `build_results_xlsx.py` `rq3_pipeline_effect.py` `run_gt_ir_audit.py` `run_ir_only_batch.py` `run_repeat_control.py` `make_arch_fig.py` (canonical 실험의 의존성 아님).
- **삭제된 작업노트/구버전 tex**: `HANDOFF.md` `sensys.md` `re_translate.md` `why_not_fsm.md` `timeline_ir_extractor.md` `energy.md`; `ovla.tex` `ovla_final.tex`.
- **여전히 repo 루트에 보존(paper 수치의 raw)**: `experiments/mutation_382_fall/`, `experiments/stageB_382*/...__paired*/`. 구세대 `experiments/{e2e_382,mutation_382*,coverage_382*,judge_compare}`는 paper 수치 아님(필요시 별도 정리).

**canonical 실험 스크립트는 `paper/` 루트에 그대로 두고, 이 문서가 RQ별 (코드 경로 / 방법 / 명령 / raw / 최종수치)의 단일 인덱스다.**
