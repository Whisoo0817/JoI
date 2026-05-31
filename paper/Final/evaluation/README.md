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

Run the judges (per (base,variant) pair, flip = verdict differs; cap 25/type):
```
PYTHONPATH=/home/gnltnwjstk/joi python3 paper/run_instability.py \
    --backend qwen   --equiv paper/Final/evaluation/data/equiv_stress.json --cap-per-type 25 --out /tmp/instab_qwen
PYTHONPATH=/home/gnltnwjstk/joi python3 paper/run_instability.py \
    --backend openai --model gpt-5.1 --equiv paper/Final/evaluation/data/equiv_stress.json --cap-per-type 25 --out /tmp/instab_gpt51
```

**Results** (temp=0, 150 pairs each):

| judge | overall flip | structural | shallow | most dramatic |
|---|---|---|---|---|
| Qwen3.5-9B | **33%** (50/150) | 55% | 12% | deMorgan 92%, branch-swap 60% |
| GPT-5.1    | **14%** (21/150) | 15% | 13% | deMorgan 28%, operand-swap 20% |
| ours (deterministic trace check) | **0%** | 0 | 0 | accepts all 391 variants |

Figure: `figs/instability.png`. Per-run detail: `results/instability_{9B,gpt51}.json`.
Honesty note: not all structural rewrites flip equally (prev/curr is low); deMorgan
and branch-swap are the dramatic ones. GPT-5.1 flips even on the trivial boolean
reorder `A and B`↔`B and A` (20%).

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

## Reproduction determinism notes
- 9B: temp=0, `enable_thinking=False` ⇒ deterministic.
- GPT-5.1: temp=0, seed=42 (gpt-5* DO accept temperature=0). temp=1 gave 12% vs
  temp=0's 14% on instability ⇒ flips are idiom-sensitivity, not sampling noise.
- Equivalence/bug labels come from the trace simulator; for the EVAL section that
  compares our verifier, disclose that the verifier shares the simulator (soundness
  is by construction; mutation/coverage measure scenario adequacy, not ground-truth
  correctness — an independent human-oracle study is still TODO).
