# HANDOFF — JoI-LLM paper (current as of 2026-05-28)

> **Primary continuity = auto-memory** (`MEMORY.md` CURRENT STATE + linked project/reference files), loaded every session. This file = snapshot + file map + next steps + **the enforcement checklist of locked decisions**.

## 0. One-line state
Contribution LOCKED = **IR-as-spec**: a user-confirmed Timeline IR is both a confirmable spec and a machine-checkable oracle; the same mechanism verifies generated JoI at runtime and grades the benchmark offline. Paper = **flow-draft** (`paper.md`/`paper_kor.md`, EN+KOR synced) through codex Round 9. Flag commit `d886015`; latest committed `bafd971` (mutation+sim+first 382 results).

### CURRENT STATE (2026-05-29) — experiment phase, first batch DONE
- **DONE (382, committed bafd971, in `experiments/`)**: E2E OFF 80.6%→ON 84.0% (FN all upstream-IR, verifier_miss=0); Stage-B OFF 90.8%→ON **93.5%** (R=1.0 FN=0 hurt=0); **Mutation 1461/1475=99.05%** (11 ops, +break_drop 100%; 14 survivors = same sub-tolerance comparator class); **Coverage 441/480=91.9%**. See [[project-experiment-inventory-2026-05-27]].
- **Code added (bafd971)**: `break_drop` op + `joi_simulator` MAX_TICKS/MAX_RAW runaway caps. `wait_drop` excluded (equiv-on-data).
- **Paper edit**: §5 NEW **dual-payoff bullet** (IR = generation scaffold AND verification spec; "verification-driven design is also the better gen target"; measured by Stage-B + minus-IR; headline stays verification). EN+KOR synced. Resolves the "is the hero verify or accuracy?" confusion → hero=verification; generation-scaffold=Role 0, owned not headlined.
- **IN PROGRESS — LLM-as-judge vs verifier (RQ3 baseline, `paper/run_judge_compare.py`, task #64)**: on the mutation ground-truth (correct=verifier-clean Stage-B JoI / wrong=injected non-equiv mutant), swap the judge: our verifier vs 9B-as-judge vs GPT-judge. Same question = **IR↔JoI equivalence** (NOT NL↔JoI — that's RQ7 user study). 9B smoke (60 wrong/20 correct): ours R=1.0 P=1.0; **9B-judge R=1.0 but P=0.75, FP=20/20 (over-rejects ALL correct) → useless as a gate**. Bigger 9B run + GPT arm pending (GPT needs `paper/openai.txt` re-added — DELETED per user). Gotchas fixed: `_verify` needs the catalog object (not category str); harvest early-stops at `cap` wrong (full-382 harvest = ~76min); 9B judge call MUST use `enable_thinking=False` (else empty content).
- **Baseline strategy (codex-reviewed + agent web-search)**: monolithic 9B/GPT + **minus-IR ablation (codex P0 = mandatory, isolates IR causality)** + code-as-IR/PoT (P1). GPIoT released but different task → cite, don't run (no SOTA claim). **RecipeGen++** (ICPC'22, code released) = only reproducible NL→TAP named baseline but simple-TAP only → use on expressible subset, expressivity gap = our contribution. **No published system does NL→reactive-DSL** (justifies constructed baselines). codex also elevated **user study (RQ7) to P0** (hero "user-confirmable" claim is asserted, not yet evidenced). See [[project-baseline-strategy-2026-05-29]].
- **NEXT**: confirm 9B-judge over-reject (balanced run) + GPT arm; decide minus-IR / PoT / RecipeGen++ builds; then user study design. Baseline generator code was DELETED this session (clean slate).
- **DELETED this session**: `paper/baselines/` (generator code), `paper/openai.txt` (API key) + its .gitignore line.

## 1. Where things live
| Artifact | File | Status |
|---|---|---|
| **Paper draft** | `paper/paper.md` + `paper/paper_kor.md` | LIVING source of truth (flow bullets; prose not started). EN+KOR MUST stay synced. `paper_summary.md/_kor` = **DELETED** (superseded; in git history if needed). |
| Related work | `paper/related_works.md` (+ `related_works/` PDFs/txt sources) | 2-axis: primitives P1–P14 + verification tiers T1–T7. |
| Pipeline | `paper/run_local_ir.py :: generate_joi_code_ir` | module view: Intent Analysis / Service Mapping / Device Mapping / IR Assembly / Lowering / Verifier (impl = 7 sLLM calls). |
| Verifier | `paper/verifier/` (l1_static, l2_runtime, diagnose, llm_diagnose, retry_harness) | L1 static + L2 trace-equivalence; `JOI_VERIFY=1`. |
| Simulators | `paper/simulators/` (ir/joi sim, coverage.py, event_synth.py, catalog.py, expr.py) | tick=100ms; tolerance max(500ms,10%). |
| Experiment scripts | `paper/run_mutation_test.py`, `run_coverage_report.py`, `run_gt_ir_audit.py`, `run_lower_gt_batch.py`, `run_joi_eval_batch.py` | mutation/coverage = DONE on old data, **need re-run on `dataset.csv`**. |
| **Dataset** | **`dataset.csv`** (repo root) | **382 rows, 24 categories.** C04 (if-else) MERGED into C03 → C03=34 (reindexed C03_32..35); NEW `has_else` column. Backup `dataset_migration/local_dataset2.csv.bak_premerge` (untracked). |
| Test runner | `python3 test.py target` | vLLM `http://localhost:8002/v1`, `cyankiwi/Qwen3.5-9B-AWQ-4bit` (≤9B, **4-bit AWQ**). Catalog `files/service_list_ver2.0.4.json`. |
| **Experiment record system** | `experiments/INDEX.md` (ledger) + `experiments/init_run.py` | EVERY run: `python3 experiments/init_run.py <exp> --dataset dataset.csv --model <id> --cmd "..."` → timestamped dir pinning git commit + dataset sha256 + model/decode + command. run.json+results/+notes committed; raw/+intermediate/ disk-optional. **Append to INDEX, never delete runs.** |
| Codex session | id `019e5e7b-21ed-72a2-b7cd-54fbb2deaa15` | resume for paper-writing continuity (via codex-reviewer agent). |

## 2. ★ ENFORCEMENT CHECKLIST — locked decisions that MUST hold (experiments + eval writing)
1. **Correctness claim = Rung-1.** Correct = (A) JoI≡IR [verifier, BOUNDED by mutation/coverage/confusion, NOT proven] + (B) IR≡intent [user-confirm / audited gt_ir + user study]. **NEVER write "verified / model-checked / sound acceptance / bounded completeness".** KEEP "rejection soundness" (=T2, proven) and "event-triggered" (reactive nature, not a sensor-delivery claim).
2. **Correctness weight = Stage-B (confirmed IR→JoI) + verifier.** NOT E2E. E2E (verifier-OFF) serves only: baseline apples-to-apples axis + usability proxy (pre-confirm IR acc = user correction burden) + IR-bottleneck diagnosis. **Do NOT headline the small E2E ON-vs-OFF lift (+0.5%) as verifier evidence.** Verifier evidence = mutation 99.3% + coverage 91.9% + recovery + confusion (FP/FN).
3. **Non-circularity ORDER**: establish verifier quality INDEPENDENTLY (mutation = injected-bug ground truth / confusion vs human / tolerance sweep) BEFORE reusing the verifier as the offline grader. Verifier never self-judges.
4. **Baselines**: BOTH (a) native E2E (NL→DSL) and (b) **lowering-only (inject our IR → IR→JoI)** for general-LLM baselines (isolates lowering + matches verifier regime; GPIoT = native E2E). **Prompt parity** (schema/few-shot/decode), **release all prompts**, **temp=0**, + a prompt/temperature sensitivity mini-ablation. Contribution = ARCHITECTURE not prompts; verifier gains orthogonal to prompt quality; hero (mutation/coverage) prompt-independent.
5. **Upstream (intent/service/device/arg/IR-extract) = NOT the hero** (§7 compact ~0.5p, platform-agnostic). Present as "multi-stage decomposition + structured-output validation/retry"; attribute accuracy via RQ2 ablation; per-stage acc / device-mapping P/R only as an error-breakdown table where gold exists (supports IR-bottleneck), prompt rules → appendix.
6. **Edge co-design**: method is model-agnostic in principle, but edge MAKES verification necessary + CONSTRAINS it LLM-free/on-device; generalization = §11 strength. SenSys entry ticket = RQ6 edge-cost + RQ8 deploy; verification = novelty ticket.
7. **C6 (verifier-curated structural exemplar routing) = unbuilt [PLANNED], SEPARATE.** Hero doesn't depend on it. Today's coarse-routing run = its control arm. Frame as "IR's THIRD payoff" folded into C4, NOT a 6th contribution; "exemplar accumulation improves retrieval" (NOT "self-improving"/learning); routing acts in generator prompt-construction only, verdict stays LLM-free.
8. **IR-as-spec is the single hero.** self-correction / feasibility-gate (IR-SIM reject) / C6 routing = applications, not heroes.
9. **EN+KOR paper sync** on every edit. **Sensor model = 100ms polling (non-decision; no paper claim).**
10. **Every experiment via `init_run.py`** (provenance pinning) + INDEX.md ledger.

## 3. Next steps — full TODO = memory `project-backlog-2026-05-26` (P0/P1/P1.5/P1.6/P1.7)
- **First experiments**: 382 re-run on `dataset.csv` (E2E / Stage-B / recovery / confusion) + mutation/coverage re-run; then E1 baselines (incl. lowering-only condition), E2 FT-SLM, RQ6 edge-cost, RQ7 user study, RQ8 deploy, artifact.
- **Builds (P1.6/P1.7)**: IR-SIM feasibility-gate reject (assertion-based) + C6 routing (then its ablation/efficiency/replay experiments).
- **Writing (P1)**: flow→prose §1 (resume codex 019e5e7b) + reflect arithmetic Contribution-2 (§6/§8.6/§11).

## 4. Memory pointers (read for detail)
**Read-first this session**: `project-contribution-framing-2026-05-28` (venue-fit/edge-codesign/local-sLLM/prompt-fairness), `project-formal-verify-differentiation-2026-05-28` (verifier vs FV/TA wedge), `project-experiment-inventory-2026-05-27` (RQ map + non-circularity + EVAL DESIGN CLARIFICATIONS), `project-backlog-2026-05-26` (P1.5/1.6/1.7 TODO), `project-joi-dataset-categories` (C03/C04 merge, 24 cats).
**Foundation**: `project-correctness-claim-2026-05-25`, `project-mutation-testing-2026-05-25`, `project-arithmetic-boundary-2026-05-26` (re-run recipe), `project-gt-ir-audit-2026-05-25`, `reference-iot-dsl-verification-landscape`, `project-paper-framework`/`project-paper-narrative-2026-05-21`.

## 5. Re-run recipe (mutation + coverage) — update dataset to `dataset.csv`
Seeds = `/tmp/joi_stageB_full_llm_v2/on` (Stage-B dumps; regenerate if stale). From `paper/`:
```bash
for grp in "A:C01,C02,C03" "B:C05,C06,C07" "C:C08" \
           "D:C09,C10,C11,C12,C13,C14,C15" "E:C16,C17,C18,C19,C20,C21,C22,C23,C24,C25"; do
  n=${grp%%:*}; c=${grp#*:}
  BATCH_CATEGORIES="$c" MUT_OUT=/tmp/mut_$n PYTHONPATH=/home/gnltnwjstk/joi \
    python3 run_mutation_test.py > /tmp/mut_$n.log 2>&1 &
done; wait
# aggregate per_operator{genuine,caught} across /tmp/mut_*/_mutation.json
PYTHONPATH=/home/gnltnwjstk/joi python3 run_coverage_report.py
```
(C04 dropped from groups — merged into C03. C23/24/25 added to group E.)
