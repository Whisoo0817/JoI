# Instability experiment (motivation, §3) — final results 2026-06-03

Variants: 643 trace-exact equivalence variants (251 groups) from build_equiv_stress.py
(transforms: var_rename, double_neg, operand_swap, arith_commute, selector_reorder [trivial];
demorgan, branch_swap [algebraic]; prevcurr [idiom]). Dataset: data/equiv_stress_v2.json.
Judge prompt: steelman'd (general "judge by behavior, not surface form" line added).
cap-per-type 80 -> 423 pairs. flip = majority(base) != majority(variant).

## Overall flip-rate (6-cell decomposition) -> paper Table 2
| Judge config        | 9B    | GPT-5.1 | OVLA |
|---------------------|-------|---------|------|
| deterministic temp0 | 27.0% | 10.6%   | 0    |
| + sampling temp0.7  | 34.4% | 12.8%   | 0    |
| + majority vote K=5 | 31.2% | 13.5%   | 0    |

Key: no judge config drops below the deterministic floor (27/10.6); voting cancels
sampling noise but NOT systematic surface-form dependence. OVLA=0 by construction.

## Per-type flip (deterministic temp0; -> Fig 1) [9B / GPT]
selector_reorder 2%/8% · operand_swap 7%/14% · var_rename 9%/6% (pure surface, LOW)
arith_commute 28%/6% · branch_swap 40%/11% · double_neg 48%/22% · demorgan 81%/16% (logical, HIGH)
prevcurr 10%/0% (idiom)

Files: instability_{9b,gpt51}_{temp0,temp07,vote5}.json (each has overall_flip, by_type, by_depth, detail).
Plot: python3 paper/plot_instability.py
