# HANDOFF — JoI-LLM paper (current as of 2026-05-26)

> Single consolidated handoff. Supersedes the prior `paper/HANDOFF.md` (5/21) and `paper/HANDOFF_2026_05_24.md` (deleted).
> **Primary continuity is the auto-memory** (`MEMORY.md` CURRENT STATE + linked project/reference files), loaded every session. This file = a snapshot + file map + next steps. (Prior stale handoffs — root `../HANDOFF.md` 5/22, `paper/eval/HANDOFF.md` 5/20, `paper/HANDOFF_2026_05_24.md` — consolidated here and deleted; their detail lives in memory.)

## 0. One-line state
Contribution LOCKED = **IR-as-spec**: a user-confirmed Timeline IR is both a confirmable spec and a machine-checkable oracle; the same mechanism verifies generated JoI at runtime and grades the benchmark offline. Paper is in **flow-draft** (`paper.md`/`paper_kor.md`), narrative-restructured + competitor-differentiated + codex-validated (session `019e5e7b`). Experiments for the writing are assumed-good (baselines/FT/deploy/user-study NOT yet run).

## 1. Where things live
| Artifact | File | Status |
|---|---|---|
| **Paper draft (flow→prose)** | `paper/paper.md` + `paper/paper_kor.md` | LIVING source of truth for narrative/structure. Flow bullets; prose not yet started. |
| Detailed design rationale | `paper/paper_summary.md` + `_kor.md` | Reference for schema/§6 obligations/RQ tables/appendices. **Narrative partially SUPERSEDED by paper.md** (oracle-prerequisite, module §7, T6 conjunction live only in paper.md). Mine for detail, then fold in; don't trust its narrative over paper.md. |
| Related work catalog | `paper/related_works.md` | Consolidated (replaces per-folder `related_works/*_ko_overleaf/`; PDFs/txt kept there as sources). 2-axis: primitives (P1–P14) + verification tiers (T1–T7). |
| Pipeline | `paper/run_local_ir.py :: generate_joi_code_ir` | 7 stages (module view: Intent Analysis / Service Mapping / Device Mapping / IR Assembly / Lowering / Verifier). |
| Verifier | `paper/verifier/` (l1_static, l2_runtime, ir_fsm, diagnose, retry_harness) | L1 static + L2 trace-equivalence; `JOI_VERIFY=1`. |
| Simulators | `paper/simulators/` (ir/joi sim, coverage.py, event_synth.py) | tick=100ms; tolerance max(500ms,10%). |
| Experiments | `paper/run_mutation_test.py`, `run_gt_ir_audit.py`, `run_coverage_report.py`, `run_lower_gt_batch.py` | **mutation 1287/1296 = 99.31%** (incl. arithmetic ops cmp_direction/arith_op 100%); **coverage 441/480 = 91.9%**; C1 audit done. See §5 re-run. |
| Dataset | `dataset_migration/local_dataset2.csv` | **382 rows** (post C1 audit: 7 value-errors + 8 suspicious fixed, 3 C04 dup deleted), C01–C25, 0 dup keys. |
| Test runner | `python3 test.py target` | LLM = vLLM `http://localhost:8002/v1`, `cyankiwi/Qwen3.5-9B-AWQ-4bit`. Catalog `files/service_list_ver2.0.4.json`. |
| Codex session | id `019e5e7b-21ed-72a2-b7cd-54fbb2deaa15` | resume for paper-writing continuity (`codex exec resume <id>` via codex-reviewer agent). |

## 2. Locked paper narrative (this session, 2026-05-25/26 — all in paper.md, both langs)
- **Lead = deployment/trust; spec-gap = the DIAGNOSIS** (not the opening hook). §1 = 6-beat arc; opening sentence locked.
- **Oracle-prerequisite framing**: NL→code verification works where an oracle exists (text-to-SQL exec-accuracy, codegen unit tests); reactive automation lacks the prerequisites (no independent executable reference, output = future device side-effects, no temporal I/O examples) → we **derive a deploy-time reference oracle from a user-confirmed IR**; trace-equivalence = reactive analogue of execution accuracy. "Execution ≠ verification."
- **Three spec properties**: Confirmable / Executable / Obligation-derivable (C1–C5 demoted to design-requirements; C2 idiom-invariance = the principle; C5 = deployment constraint). IR-SIM + IR-FSM = **two projections** (not "two faces").
- **Competitor wedge (T6)**: page-1 table (GPIoT/TaskSense/LLMind/consumer-DSLs/Ours). T6 = 5-element conjunction (NL→generated code + user-confirmed spec + executable trace oracle + auto-synthesized scenarios/coverage + trace-equivalence on idiomatic code) — empty across the field, to our knowledge. Closest neighbors AutoTap/TAPFixer/TAP-debug differentiated by "complete expected behavior vs property constraints"; openHAB RSpec conceded as supporting precedent (T4, not T6); AWS IoT Events = structural diagnostics over hand-authored FSM (≈ our L1 in kind).
- **§7 module-level**: Intent Analysis → {Service Mapping module (service_plan+enum+arg), Device Mapping resolver (device_match)} → IR Assembly (confirm) → Lowering → Verifier. NOT "agents" (deterministic glue, LLM-free verdict). Honesty: impl = 7 calls; RQ2 ablation stays fine-grained.
- **Claim ladder (§8.3)**: prove T1 (IR-FSM determinism) + T2 (rejection soundness; "real divergence" defined vs simulators/observation-model/tolerance/fragment F); target Rung-1 bounded transition-boundary coverage. Framed as a contract (guaranteed/covered/exposed/measured), never "sound acceptance."
- **Verifier doubles as grader (§9.1b)**: same IR-as-spec → runtime verification (user-confirmed IR) + offline auto-grading (audited gt_ir); circularity safeguard = gt_ir audited (C1) + E2E/human-spot-check independent + Stage-B = lowering/self-correction isolation.

## 3. Next steps — **full prioritized TODO = memory `project-backlog-2026-05-26`** (read that first)
- **P0 experiments (assumed-good in draft; MUST run before submission)**: E1 baselines (9B-direct/CoT, GPT-4o ±schema ±self-repair, RAG), E2 **fine-tuned-SLM baseline** (GPIoT-style, RQ1), E3 real-hub deploy (RQ8), E4 user study (RQ7), artifact release (last blocker). E5 OOD, E6 edge-cost.
- **P1 writing**: flow→prose starting §1 (resume codex 019e5e7b each section) + reflect arithmetic Contribution-2 into §6/§8.6/§11.
- **P2 hygiene**: build .bib; fix "IoT-forensics" → FSAIoT ARES'17 (not IEEE IoT-J'19). (mutation/coverage on 382 = DONE, §4b.)
- **P3**: C11 directional-vs-abs + C14 inverted-clamp = verifier-caught real bugs → §9.10 case studies.

## 4b. Arithmetic boundary fault-class (2026-05-26 PM — DONE, Contribution-2)
**Why:** JoI has no `abs`/`min`/`max`; lowering UNROLLS them into if-else (`min(x+10,100)`→`tmp=x+10;if(tmp>100){tmp=100}`). We check trace-equiv only, so wrong unrollings (inverted clamp) are caught only if the input is driven to the operator's internal boundary. Found a latent sim bug: `$Service.Attr` evaluated to **None** (VarRef miss) → clamps were never exercised; and mutation/coverage excluded the arithmetic class (reviewer-attackable "easy boundaries only"). codex: do the strong path.
**Fixes:** `expr.evaluate` VarRef dotted-Capitalized `$Service.Attr`→`ctx.world.get(canonical_key)` device read (symmetric w/ JoI selectors); `catalog.value_domains()` (per-sensor type/bound/enum); `event_synth` sensor-value boundary seeding (`expr:lo/hi` at 5%/95% of bound; regs via stepped events) with `_written_keys` guard (excludes self-ref accumulators `Volume=Volume+10` → no false-positive); `coverage.py` expr obligations + initial_world distinguishing; `run_mutation_test.py` new ops `cmp_direction`/`arith_op` + per-mutant try/except (sim-crash=fail-closed).
**Results:** mutation **1287/1296=99.31%** (cmp_direction 65/65, arith_op 26/26; 9 survivors all known sub-tolerance/edge; 0 new, 0 FP), coverage **441/480=91.9%**. Surfaced REAL bugs: C14_002 inverted max-clamp, C11_2/3/4/6 IR-directional-vs-JoI-abs (correctly flagged). Detail + full re-run commands: memory `project-arithmetic-boundary-2026-05-26`.

## 5. Re-run recipe (mutation + coverage)
Seeds = `/tmp/joi_stageB_full_llm_v2/on` (357 Stage-B dumps). From `paper/`:
```bash
# mutation — 5 parallel groups (full single job times out >590s):
for grp in "A:C01,C02,C03,C04" "B:C05,C06,C07" "C:C08" \
           "D:C09,C10,C11,C12,C13,C14,C15" "E:C16,C17,C18,C19,C20,C21,C22"; do
  n=${grp%%:*}; c=${grp#*:}
  BATCH_CATEGORIES="$c" MUT_OUT=/tmp/mut_$n PYTHONPATH=/home/gnltnwjstk/joi \
    python3 run_mutation_test.py > /tmp/mut_$n.log 2>&1 &
done; wait
# aggregate per_operator{genuine,caught} across /tmp/mut_*/_mutation.json
# coverage (spec+impl two-sided over dataset gt_ir):
PYTHONPATH=/home/gnltnwjstk/joi python3 run_coverage_report.py
```

## 4. Memory pointers (read these for detail)
`project-correctness-claim-2026-05-25` (claim ladder), `project-mutation-testing-2026-05-25`, `project-arithmetic-boundary-2026-05-26` (arithmetic fault-class: why/results/re-run), `project-gt-ir-audit-2026-05-25` (dataset 382), `reference-iot-dsl-verification-landscape` (related-work survey + oracle reframe), `project-paper-framework` / `project-paper-narrative-2026-05-21` (architecture).
