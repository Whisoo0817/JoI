# Motivation evaluation — LLM-as-judge is not a stable verification oracle

This folder makes the motivation experiments fully reproducible (scripts, data,
results, figures). All scripts live in `paper/` and are run with
`PYTHONPATH=/home/gnltnwjstk/joi`. The local 9B judge uses the vLLM server at
`localhost:8002` (`enable_thinking=False`, temp=0); the cloud judge uses
`paper/openai.txt` (gpt-5.1, temp=0, seed=42). **`paper/openai.txt` is gitignored —
never commit it.**

## What this evaluation argues (and what it deliberately does NOT)

**Motivation claim (ours-free — VIOLA/IR/verifier never appear in motivation):**
an LLM used as the verification oracle is **not a stable acceptance boundary**.
Even with a fully steelmanned prompt and deterministic decoding (temp=0), its
accept/reject verdict changes when a program is rewritten into a
behaviorally-IDENTICAL form. Its verdict tracks surface form, not behavior.

**We do NOT claim** "LLMs cannot catch reactive bugs." On clean injected bugs a
steelmanned GPT-5.1 is a competent catcher; our own inspection showed its apparent
misses are dominated by (a) over-strict labels on don't-care arguments and (b)
genuine one-shot-vs-continuous intent ambiguity — not incompetence. Cost is also
NOT argued here (it belongs in the evaluation/RQ4 cost comparison, where it can be
fairly compared given the confirmed IR).

## Experiments

### 1. Instability (HEADLINE, label-free, ours-free)
Behaviorally-identical rewrites of verifier-clean programs; measure how often the
judge flips its verdict. Pure idiom-sensitivity (temp=0 ⇒ not sampling noise).

Build the trace-exact equivalence dataset (keeps a rewrite only if its action-trace
signature is identical to the seed ⇒ our system treats it as equivalent; this
auto-rejects non-equivalences like `switch_on`↔`moveToBrightness(100)`):

```
PYTHONPATH=/home/gnltnwjstk/joi python3 paper/build_equiv_stress.py \
    --out paper/Final/evaluation/data/equiv_stress.json
```
(→ 235 groups / 391 verified trace-exact variants; 6 rewrites = structural
{prevcurr, branch_swap, demorgan} + shallow {operand_swap, arith_commute,
selector_reorder}.)

Run the judges, BOTH methods (direct judge AND back-translation round-trip);
per (base,variant) pair, flip = verdict differs; cap 25/type:
```
# direct judge
PYTHONPATH=/home/gnltnwjstk/joi python3 paper/run_instability.py \
    --backend qwen   --method direct    --equiv paper/Final/evaluation/data/equiv_stress.json --cap-per-type 25 --out /tmp/instab_qwen
PYTHONPATH=/home/gnltnwjstk/joi python3 paper/run_instability.py \
    --backend openai --model gpt-5.1 --method direct --equiv paper/Final/evaluation/data/equiv_stress.json --cap-per-type 25 --out /tmp/instab_gpt51
# back-translation round-trip (joi -> NL via re_translate.md, then NL-vs-command match)
PYTHONPATH=/home/gnltnwjstk/joi python3 paper/run_instability.py \
    --backend qwen   --method roundtrip --equiv paper/Final/evaluation/data/equiv_stress.json --cap-per-type 25 --out /tmp/instab_qwen_rt
PYTHONPATH=/home/gnltnwjstk/joi python3 paper/run_instability.py \
    --backend openai --model gpt-5.1 --method roundtrip --equiv paper/Final/evaluation/data/equiv_stress.json --cap-per-type 25 --out /tmp/instab_gpt51_rt
```

**Results** (temp=0, 150 pairs each). Overall verdict flip-rate on
behaviorally-identical programs, by model x method:

| judge | direct | back-translation |
|---|---|---|
| Qwen3.5-9B | **33%** (struct 55% / shallow 12%; deMorgan 92%, branch-swap 60%) | **29%** (struct 43%; deMorgan 68%) |
| GPT-5.1    | **14%** (struct 15% / shallow 13%; deMorgan 28%, operand-swap 20%) | **18%** (struct 27% / shallow 9%; prev/curr 32%) |
| ours (deterministic trace check) | **0%** | **0%** |

Figures: `figs/instability_4cell.png` (model x method overall + struct/shallow),
`figs/instability.png` (direct, per rewrite type). Detail:
`results/instability_{9B,gpt51}{,_retrans}.json`.

Takeaway: verdict flips 14-33% across BOTH models AND BOTH verification methods
(direct judge or NL round-trip); ours = 0 in every condition. So LLM-based
verification is unstable regardless of approach. Honesty notes: not all structural
rewrites flip equally (prev/curr is low for some); deMorgan/branch-swap dominate;
GPT-5.1 flips even on the trivial boolean reorder `A and B`↔`B and A`.

### 2. Injected-bug judge audit (supporting; shows LLM is competent → why we DON'T claim incompetence)
Genuine trace-divergent mutants of clean seeds (277 wrong + 69 correct), tagged
fault_family × construct. Judge sees NL command + code (NO IR).

```
PYTHONPATH=/home/gnltnwjstk/joi python3 paper/build_mutant_stress.py \
    --out paper/Final/evaluation/data/mutant_stress.json
PYTHONPATH=/home/gnltnwjstk/joi python3 paper/run_motivation_judge.py \
    --backend qwen   --method direct    --stress-file paper/Final/evaluation/data/mutant_stress.json --out /tmp/mut_qwen_direct
PYTHONPATH=/home/gnltnwjstk/joi python3 paper/run_motivation_judge.py \
    --backend qwen   --method roundtrip --stress-file paper/Final/evaluation/data/mutant_stress.json --out /tmp/mut_qwen_roundtrip
PYTHONPATH=/home/gnltnwjstk/joi python3 paper/run_motivation_judge.py \
    --backend openai --model gpt-5.1 --method direct --stress-file paper/Final/evaluation/data/mutant_stress.json --out /tmp/mut_gpt51_direct
PYTHONPATH=/home/gnltnwjstk/joi python3 paper/aggregate_motivation.py \
    9B_direct=results/injected_9B_direct.json 9B_retrans=results/injected_9B_retrans.json GPT51=results/injected_gpt51_direct.json
```

**Results** (FN = silent-accept of a wrong program; FP = reject of a correct one):

| judge | FN-rate | FP-rate |
|---|---|---|
| 9B direct | 13% (36/277) | 25% (17/69) |
| 9B back-translation | 24% (67/277) | 20% |
| GPT-5.1 direct | 5.8% (16/277) | 20% |

**Caveat (load-bearing):** opening up GPT-5.1's failures, the FN are mostly
don't-care-arg label noise (e.g. a transition-rate parameter the command never
mentions, or brightness 100→117 which still means "on"); comparator `>=`→`>` was
only 11% missed. The FP are mostly one-shot-vs-continuous intent ambiguity. So this
table is evidence that **a strong LLM judge is competent**, which is exactly why the
motivation rests on INSTABILITY, not on a miss-rate. Figures `figs/heatmap_GPT51.png`
(per fault×construct miss-rate) and `figs/bars_fn_fp.png`.

### 3. Multi-GT prev/curr (idiom-invariance; mostly a prompt-clarity lesson)
30 `prev/curr` edge-idiom variants of correct seeds (our verifier accepts all 30).
GPT-5.1 first rejected 30/30 (misreading `:=` persistence) but this DISSOLVED to
1/30 once the `:=` semantics were stated explicitly in the prompt — so this is NOT
a robust over-rejection result; kept only as the lesson that prompt
under-specification, not multiplicity, drove it. `results/multigt_gpt51_explicit.json`.

### 4. NL→IR error distribution + faithfulness-surfacing (RQ1 substitute, human-free)
The RQ1 user study is deferred this round (no IRB). These two human-free analyses
establish the IR rendering as a *confirmable, faithful surface* (necessary
condition for confirmation; they do NOT claim humans detect faults well).

```
PYTHONPATH=/home/gnltnwjstk/joi python3 paper/extract_nl2ir_errors.py
PYTHONPATH=/home/gnltnwjstk/joi python3 paper/run_faithfulness_surfacing.py
```

(a) **Real NL→IR error distribution** (`extract_nl2ir_errors.py`): for each row,
behaviorally compare the generated IR vs `ir_gt` (synthesize scenarios from gt,
run both IR sims, compare action traces). Behaviorally-equivalent = idiom variant
(NOT a fault); divergent = real error, classified into fault classes. Result:
of 382 rows, **323 (85%) behaviorally equivalent** (multiplicity / label-noise
evidence) and **59 (15.4%) real errors** (arg-value 19 / device 12 / condition 12
/ timing 9 / single-vs-cycle 8 / …). Reactive-mode confusions (oneshot↔waituntil,
AND↔sequential) are genuinely rare in this pipeline (not filtered out — all the
ones that occur are behaviorally divergent). → `results/nl2ir_error_distribution.json`.

(b) **Faithfulness-surfacing** (`run_faithfulness_surfacing.py`): does the
DETERMINISTIC renderer surface faults in plain text? Blind spot = two
behaviorally-different IRs that render to identical text. **Part B** (synthetic
injection over 8 fault classes incl. reactive-mode oneshot↔waituntil /
single↔cycle / and-drop): **1504/1504 = 100% surfaced, 0 blind spots**. **Part A**
(57 real errors): **56/57 = 98.2%**; the single blind spot (C16_5) is a
device-scope *selector* difference (`all(#Floor2)` vs default) that the behavioral
rendering abstracts away — device mapping is a separate precision/selector
confirmation channel (reported as an honest limitation; renderer not modified).
→ `results/faithfulness_surfacing.json` + `results/rendering_worked_examples.json`
(command, render(correct), render(faulty) triples for worked-example figures).

## Files
- `data/equiv_stress.json` — 235 groups / 391 trace-exact equivalence variants (instability input).
- `data/mutant_stress.json` — 277 tagged genuine bugs + 69 correct controls (judge-audit input).
- `results/*.json` — per-run confusion / flip detail.
- `figs/*.png` — instability bars, fault×construct miss heatmap, FN/FP bars.

## Scripts (in `paper/`)
- `build_equiv_stress.py` — trace-exact equivalence-variant generator (instability data).
- `run_instability.py` — flip-rate over equivalence groups.
- `build_mutant_stress.py` — tagged genuine-bug + control generator.
- `run_motivation_judge.py` — judge harness (direct / back-translation; qwen / gpt-5.1; `--stress-file`).
  Contains the steelmanned judge reference + few-shot. `re_translate.md` is the
  back-translation describe prompt (extended with sustain/counter idioms).
- `aggregate_motivation.py`, `plot_motivation.py` — tables + figures.
- `run_repeat_control.py` — same-input repeat control (NOT needed once temp=0 confirmed; kept for record).
- `extract_nl2ir_errors.py` — real NL→IR error distribution (trace-based; idiom-variant vs real-fault).
- `run_faithfulness_surfacing.py` — blind-spot / fault-surfacing measurement over the deterministic renderer (RQ1 human-free substitute).

## Reproduction determinism notes
- 9B: temp=0, `enable_thinking=False` ⇒ deterministic.
- GPT-5.1: temp=0, seed=42 (gpt-5* DO accept temperature=0). temp=1 gave 12% vs
  temp=0's 14% on instability ⇒ flips are idiom-sensitivity, not sampling noise.
- Equivalence/bug labels come from the trace simulator; for the EVAL section that
  compares our verifier, disclose that the verifier shares the simulator (soundness
  is by construction; mutation/coverage measure scenario adequacy, not ground-truth
  correctness — an independent human-oracle study is still TODO).
