# Motivation pilot: silent behavioral divergence in LLM-generated JoI

2026-09-11. **Pilot / development evidence.** Not a frozen protocol and not a paper result.
Discussion origin: Codex's funnel design plus three amendments (three generation conditions,
complexity levels, independent gold histories). The Explorer is not used as the oracle.

## Question

Among JoI programs that pass the checks existing systems already perform (output format, JoI
grammar, catalog/API/selector validity, execution without error, a nominal test), how many still
produce a different timed ACTION trace from the confirmed behavior on boundary input histories?
Does that persist when the behavior is stated explicitly, and when the confirmed Timeline IR is given?

## Design

| Item | Decision |
| --- | --- |
| Tasks | 12, `tasks.py`. 4 mechanism families (sustain, edge, snapshot, repetition) x 3 levels (L1 single mechanism, L2 plus re-arming or one more operator, L3 composition with repetition). New wording and devices, not copied from `dataset.csv`. |
| Hidden gold | Timeline IR, binding plan, input histories and hand-derived expected traces. The gold IR must reproduce every hand-derived trace (`controls.py`). |
| Histories | 34 total. `nominal` = the obvious single test. `boundary` = interruption, re-arming, threshold, value change, extra event. `nl_determined=False` marks the 2 histories whose expected trace only the explicit contract fixes. |
| Binding | Given to every condition as `[Precision Selectors]` (one selector per `Service.Method`), so grounding errors do not mask temporal errors. |
| Conditions | `NL`: command + JoI language reference (`prompts/joi_reference.md`, no behavior idiom templates). `SPEC`: NL + explicit behavior contract. `IR`: command + confirmed Timeline IR + the unchanged production lowering prompt (`joi_common.md` + `joi_<bucket>.md`). |
| Post-processing | Same selector/service-prefix normalization as production for all conditions. The production IR-derived `period` override is NOT applied (it would repair model output using the reference). One level of JSON nested inside `script` is unwrapped. |
| Models | `qwen9b`: cyankiwi/Qwen3.5-9B-AWQ-4bit, thinking off, T=0.7/top_p=0.8/top_k=20, 2000 tokens. `qwen9b_think`: same, thinking on, T=0.6/top_p=0.95/top_k=20, 23000 tokens (first 12000-token attempt truncated; truncated outputs regenerated). `gpt54mini`: gpt-5.4-mini-2026-03-17, reasoning_effort=medium. 3 samples per task x condition. |
| Oracle | Concrete replay on the model runtime (`explorer.runtime` runners via `prepare_pair`) on a grid that hits every input change, deadline and period tick. No Explorer search. |
| Match | Same ACTION signatures (service, method, typed args, target) in the same order, each time within 1 s. Exact-time match is recorded separately. 1 s absorbs the one-tick offset of 1 s polling counters, including the production D-10 template. |
| Funnel | format -> syntax (ANTLR `JOILang.g4`) -> modeled_fragment -> api_binding -> runtime -> nominal -> boundary. `silent divergence` = passes everything through nominal, fails a boundary history. |

## Controls (`python controls.py`)

All pass (`runs/controls.json`): gold IR reproduces all 34 hand-derived traces; 12 hand-written
correct JoI programs pass every history; 5 known bug patterns fail at the expected stage
(delay-then-recheck sustain and top-level `:=` snapshot fail only on boundary histories).

## Production prompt fix found by this pilot (2026-09-11)

The first IR-condition run failed on every T11/T12 candidate for both models. Cause in
`files/joi_cycle.md`: idiom row 1 (`cycle.until` -> D-9) won over row 3 (body `wait` -> D-3/D-10), and
Step 1.5 appended `n = n + 1` at the end of the script, which counts 1 s polling ticks instead of
iterations when the body waits. Fix: row 1 applies only without a `wait`; with a `wait`, the counter is
advanced right after Y inside the fired block (template added). IR T10-T12 were regenerated for
`gpt54mini` and `qwen9b`; pre-fix outputs and results are in `runs/archive_before_count_fix/`.
T10 was included as a regression check because its prompt text changed too.

## Known limitations of this pilot

- 12 tasks, 3 samples: descriptive only. Task wording, history choice and prompts were fixed before
  seeing model output, except the two prompt changes recorded here.
- Prompt change after the first run: the first NL/SPEC run (`runs/v0_before_format_example/`) failed
  mostly on nested-JSON output. A non-temporal format example was added to `joi_reference.md` and
  NL/SPEC were regenerated. The IR prompt changed once, by the production fix above.
- The runtime contract (e.g. `:=` only in the first run, period counted after body completion) is the
  adopted target contract, not measured JoI server behavior.
- Boundary histories are a test suite chosen by the authors; silent-divergence counts are lower bounds.
- Gold T02/T12 use `wait(for)` + `wait(re-arm)` inside `cycle`, because `rising` + `for` in one wait is
  outside the current IR/Explorer semantics.

## Run

```bash
python tasks.py && python controls.py
python generate.py --model qwen9b
python generate.py --model qwen9b_think
python generate.py --model gpt54mini   # key: OPENAI_API_KEY, joi/openai.txt or ~/openai.txt
python classify.py && python explorer_check.py --model gpt54mini
python evaluate.py
python judge.py --judge gpt54mini --repeats 3
python judge.py --judge gemma26b                  # vLLM on :8002
python judge.py --report
python explorer_judge_set.py                      # runs/judge/explorer_step1000.jsonl
```

## Checker comparison on the 116-program set (2026-09-11)

`judge.py` collected every distinct program produced by the three generation conditions
(181 samples -> 116 distinct `task + period + script`, `runs/judge/programs.json`), and three
checkers were run over the same set.

Labels. `wrong` (33) = fails a hand-written history; `visible` 23 fail the nominal one,
`silent` 10 fail only a boundary one. `hidden` (26) = passes all hand histories, but a judge
returned a counterexample that, replayed against the gold IR (`cex_valid`), really diverges.
`correct` (57) = the remainder; 45 of those are proved equivalent by the Explorer.

**Hand histories miss 26 of the 59 wrong programs (44%).**

LLM judge (command + behavior contract + initial-state sentence + selectors + JoI execution
rules + program; JSON verdict with a counterexample). `runs/judge/verdicts_<judge>.jsonl`.

| verdicts | gpt54mini (3 repeats) | gemma26b (1 repeat) |
| --- | --- | --- |
| wrong accepted | 2 / 99 (both silent) | 1 / 32 |
| hidden accepted | 7 / 78, 4 distinct programs | 1 / 23 |
| correct rejected | 5 / 171 | 3 / 46 |
| programs with mixed verdicts | 10 / 116 | n/a |
| unparsed | 0 | 15 / 116 |

Explorer (`gate_pair`, horizon None, `input_step_ms=1000`, explicit pilot domains, exact time).
`runs/judge/explorer_step1000.jsonl`; `DIVERGE_timing` = `tolerant_recheck` says the reported
difference is within 1 s.

| label | EQUIV | DIVERGE real | DIVERGE timing | REFUSED |
| --- | --- | --- | --- | --- |
| correct 57 | 45 | 0 | 9 | 3 (state cap) |
| wrong_visible 23 | 0 | 23 | 0 | 0 |
| wrong_silent 10 | 0 | 10 | 0 | 0 |
| hidden 26 | 0 | 22 | 4 | 0 |

No wrong program is accepted, and no correct program gets a real divergence. 100 / 116 decided
(69 before the input-copy fix). Search time: median 0.005 s, p95 0.311 s; the 3 cap refusals are
1 s-polling T02/T03 programs that burn 400000 states in 100-142 s.

Two open gaps, both listed as future work rather than fixed here:
the Explorer compares exact times and stops at the first difference, so 13 programs
(9 correct, 4 hidden-wrong whose real bug sits behind a 1 s offset) stay undecided; and 3 programs
hit the state cap.

Bias warning: the 26 hidden-wrong programs were found *by* the judges, so this set cannot be used
to claim coverage for the judges, and errors that neither checker found may still sit inside the
57 correct ones (45 of which are Explorer-proved).

## Status

**2026-09-12: on hold.** Design, data and the numbers above are complete and reproducible from
the committed aggregates. Undecided by the author: whether the Explorer gets a tolerance, whether
this judge comparison appears in the paper at all (motivation vs. E3), and the abstract sentence
about manual/LLM inspection. Raw per-call model outputs stay on disk only (see `.gitignore`).
