# E2 verdict distribution

`e2_verdicts.tex` draws the manuscript figure in native TikZ. The matching Overleaf source is `figures/e2_verdicts.tex`; `main.tex` loads TikZ and the evaluation section inputs the figure.

Counts come from `../E2_fidelity/extension60/summary.json`: equivalent 64, divergent 119, timeout 8, unsupported 9; total 200. Each arc spans `360 * count / 200` degrees. The two gray slices are undecided outcomes. These are verdict proportions, not accuracy estimates.

Build `e2_verdicts_standalone.tex` with a LaTeX engine supporting TikZ to export the same figure as a standalone vector PDF. `e2_verdicts.png` is a preview of that PDF used by both Markdown drafts.
