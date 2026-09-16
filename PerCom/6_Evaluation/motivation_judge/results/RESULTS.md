# Fig2 / Table1 — judge verdict consistency on behavior-preserving rewrites

Seeds: E3 EQUIV-FIXPOINT programs (confirmed IR + binding). Every rewrite was re-checked by the frozen E3 evaluator and is EQUIV-FIXPOINT against the confirmed IR (rewrites/verified_pairs.json). Judge input: the natural-language command and the program; base and rewrite in separate calls. Identity: the base program judged again with the same prompt (rep 0 vs rep 1). Flip = J(base) != J(rewrite) over valid pairs (both parsed). 95% CI: percentile bootstrap over seed programs (2000 resamples).

## Primary view: rewrites of programs the judge itself accepted

Each judge is conditioned on its own first-pass verdict. Of the pairs whose original this judge accepted, the table reports how often it rejected the behavior-preserving rewrite. The control re-asks the identical accepted program.

| judge | accepted pairs | rewrite rejected | rate | 95% CI | control seeds | control rejected | control rate |
|---|---:|---:|---:|---|---:|---:|---:|
| `Hyper-AI/Qwen3.5-9B-fp8` | 249 | 52 | 20.9% | [16.1, 26.3] | 108 | 0 | 0.0% |
| `gpt-5.4-mini-2026-03-17` | 236 | 31 | 13.1% | [8.4, 18.1] | 90 | 16 | 17.8% |
| `claude-sonnet-5` | 222 | 22 | 9.9% | [5.2, 15.3] | 83 | 9 | 10.8% |

**Hyper-AI/Qwen3.5-9B-fp8**, by rewrite type:

| | rewrite | accepted pairs | rejected | rate | 95% CI |
|---|---|---:|---:|---:|---|
| VAR | rename a variable | 34 | 0 | 0.0% | [0.0, 0.0] |
| CMP | mirror a comparison (x >= 26 -> 26 <= x) | 79 | 19 | 24.1% | [14.6, 33.3] |
| UNIT | change the time unit (3 MIN -> 180 SEC) | 16 | 1 | 6.2% | [0.0, 20.0] |
| GRP | respell a condition over a group of devices | 13 | 5 | 38.5% | [11.1, 66.7] |
| BR | negate the guard and swap the branches | 27 | 1 | 3.7% | [0.0, 12.9] |
| ELS | drop the else by guarding it with the negated condition | 20 | 0 | 0.0% | [0.0, 0.0] |
| DLY | split one delay into two | 13 | 0 | 0.0% | [0.0, 0.0] |
| UNR | unroll a counted periodic loop | 13 | 10 | 76.9% | [53.3, 100.0] |
| PHS | integer phase -> boolean flag with shared tail | 7 | 2 | 28.6% | [0.0, 66.7] |
| WPC | check the condition before blocking on it | 27 | 14 | 51.9% | [32.3, 70.0] |

**gpt-5.4-mini-2026-03-17**, by rewrite type:

| | rewrite | accepted pairs | rejected | rate | 95% CI |
|---|---|---:|---:|---:|---|
| VAR | rename a variable | 37 | 5 | 13.5% | [2.9, 25.0] |
| CMP | mirror a comparison (x >= 26 -> 26 <= x) | 67 | 9 | 13.4% | [6.1, 22.6] |
| UNIT | change the time unit (3 MIN -> 180 SEC) | 12 | 2 | 16.7% | [0.0, 41.7] |
| GRP | respell a condition over a group of devices | 11 | 1 | 9.1% | [0.0, 28.6] |
| BR | negate the guard and swap the branches | 28 | 6 | 21.4% | [7.4, 37.9] |
| ELS | drop the else by guarding it with the negated condition | 20 | 2 | 10.0% | [0.0, 26.1] |
| DLY | split one delay into two | 11 | 0 | 0.0% | [0.0, 0.0] |
| UNR | unroll a counted periodic loop | 13 | 0 | 0.0% | [0.0, 0.0] |
| PHS | integer phase -> boolean flag with shared tail | 8 | 0 | 0.0% | [0.0, 0.0] |
| WPC | check the condition before blocking on it | 29 | 6 | 20.7% | [6.7, 37.1] |

**claude-sonnet-5**, by rewrite type:

| | rewrite | accepted pairs | rejected | rate | 95% CI |
|---|---|---:|---:|---:|---|
| VAR | rename a variable | 40 | 3 | 7.5% | [0.0, 16.7] |
| CMP | mirror a comparison (x >= 26 -> 26 <= x) | 63 | 5 | 7.9% | [1.8, 15.0] |
| UNIT | change the time unit (3 MIN -> 180 SEC) | 14 | 0 | 0.0% | [0.0, 0.0] |
| GRP | respell a condition over a group of devices | 12 | 3 | 25.0% | [0.0, 50.0] |
| BR | negate the guard and swap the branches | 27 | 3 | 11.1% | [0.0, 24.1] |
| ELS | drop the else by guarding it with the negated condition | 20 | 4 | 20.0% | [4.8, 39.1] |
| DLY | split one delay into two | 10 | 0 | 0.0% | [0.0, 0.0] |
| UNR | unroll a counted periodic loop | 14 | 0 | 0.0% | [0.0, 0.0] |
| PHS | integer phase -> boolean flag with shared tail | 7 | 0 | 0.0% | [0.0, 0.0] |
| WPC | check the condition before blocking on it | 15 | 4 | 26.7% | [6.2, 52.9] |

## Secondary view: all pairs, flips in either direction

## qwen: `Hyper-AI/Qwen3.5-9B-fp8`, temperature 0.0, thinking off, seed 0, budget 1500+300

| | pairs | valid | flip | deploy→reject | reject→deploy | flip rate | 95% CI | identity flip (n) | identity rate | identity CI |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| **all rewrites** | 446 | 446 | 102 | 52 | 50 | 22.9% | [18.6, 27.4] | 0/216 | 0.0% | [0.0, 0.0] |
| **Spelling** | 268 | 268 | 57 | 25 | 32 | 21.3% | [16.5, 26.6] | 0/197 | 0.0% | [0.0, 0.0] |
| **Logic** | 65 | 65 | 11 | 1 | 10 | 16.9% | [6.2, 30.0] | 0/38 | 0.0% | [0.0, 0.0] |
| **Temporal structure** | 113 | 113 | 34 | 26 | 8 | 30.1% | [21.6, 39.3] | 0/93 | 0.0% | [0.0, 0.0] |
| VAR — rename a variable | 50 | 50 | 4 | 0 | 4 | 8.0% | [2.0, 16.0] | 0/50 | 0.0% | [0.0, 0.0] |
| CMP — mirror a comparison (x >= 26 -> 26 <= x) | 152 | 152 | 41 | 19 | 22 | 27.0% | [19.7, 33.6] | 0/152 | 0.0% | [0.0, 0.0] |
| UNIT — change the time unit (3 MIN -> 180 SEC) | 27 | 27 | 1 | 1 | 0 | 3.7% | [0.0, 11.1] | 0/27 | 0.0% | [0.0, 0.0] |
| GRP — respell a condition over a group of devices | 39 | 39 | 11 | 5 | 6 | 28.2% | [15.4, 41.0] | 0/39 | 0.0% | [0.0, 0.0] |
| BR — negate the guard and swap the branches | 38 | 38 | 7 | 1 | 6 | 18.4% | [7.9, 31.6] | 0/38 | 0.0% | [0.0, 0.0] |
| ELS — drop the else by guarding it with the negated condition | 27 | 27 | 4 | 0 | 4 | 14.8% | [3.7, 29.6] | 0/27 | 0.0% | [0.0, 0.0] |
| DLY — split one delay into two | 25 | 25 | 3 | 0 | 3 | 12.0% | [0.0, 24.0] | 0/25 | 0.0% | [0.0, 0.0] |
| UNR — unroll a counted periodic loop | 15 | 15 | 10 | 10 | 0 | 66.7% | [40.0, 86.7] | 0/15 | 0.0% | [0.0, 0.0] |
| PHS — integer phase -> boolean flag with shared tail | 11 | 11 | 2 | 2 | 0 | 18.2% | [0.0, 45.5] | 0/11 | 0.0% | [0.0, 0.0] |
| WPC — check the condition before blocking on it | 62 | 62 | 19 | 14 | 5 | 30.6% | [19.4, 41.9] | 0/62 | 0.0% | [0.0, 0.0] |

Base programs judged deployable: 55.8% of valid pairs. Invalid (unparsed/error) pairs: 0. Seeds whose three identity repeats disagree at all: 0/216.

## gpt: `gpt-5.4-mini-2026-03-17`, reasoning_effort low, seed 42

| | pairs | valid | flip | deploy→reject | reject→deploy | flip rate | 95% CI | identity flip (n) | identity rate | identity CI |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| **all rewrites** | 446 | 446 | 59 | 31 | 28 | 13.2% | [9.6, 17.2] | 26/216 | 12.0% | [8.8, 15.2] |
| **Spelling** | 268 | 268 | 36 | 17 | 19 | 13.4% | [9.1, 18.1] | 25/197 | 12.7% | [9.2, 16.3] |
| **Logic** | 65 | 65 | 11 | 8 | 3 | 16.9% | [7.7, 28.4] | 8/38 | 21.1% | [11.5, 30.4] |
| **Temporal structure** | 113 | 113 | 12 | 6 | 6 | 10.6% | [5.2, 17.0] | 11/93 | 11.8% | [6.6, 16.4] |
| VAR — rename a variable | 50 | 50 | 9 | 5 | 4 | 18.0% | [8.0, 28.0] | 9/50 | 18.0% | [9.4, 25.8] |
| CMP — mirror a comparison (x >= 26 -> 26 <= x) | 152 | 152 | 19 | 9 | 10 | 12.5% | [7.2, 17.8] | 19/152 | 12.5% | [8.2, 16.5] |
| UNIT — change the time unit (3 MIN -> 180 SEC) | 27 | 27 | 5 | 2 | 3 | 18.5% | [3.7, 33.3] | 4/27 | 14.8% | [5.6, 23.5] |
| GRP — respell a condition over a group of devices | 39 | 39 | 3 | 1 | 2 | 7.7% | [0.0, 17.9] | 6/39 | 15.4% | [7.4, 24.0] |
| BR — negate the guard and swap the branches | 38 | 38 | 8 | 6 | 2 | 21.1% | [10.5, 34.2] | 8/38 | 21.1% | [11.5, 30.4] |
| ELS — drop the else by guarding it with the negated condition | 27 | 27 | 3 | 2 | 1 | 11.1% | [0.0, 25.9] | 5/27 | 18.5% | [6.2, 28.6] |
| DLY — split one delay into two | 25 | 25 | 1 | 0 | 1 | 4.0% | [0.0, 12.0] | 3/25 | 12.0% | [0.0, 21.4] |
| UNR — unroll a counted periodic loop | 15 | 15 | 1 | 0 | 1 | 6.7% | [0.0, 20.0] | 2/15 | 13.3% | [0.0, 25.0] |
| PHS — integer phase -> boolean flag with shared tail | 11 | 11 | 0 | 0 | 0 | 0.0% | [0.0, 0.0] | 3/11 | 27.3% | [0.0, 50.0] |
| WPC — check the condition before blocking on it | 62 | 62 | 10 | 6 | 4 | 16.1% | [8.1, 25.8] | 8/62 | 12.9% | [7.1, 18.9] |

Base programs judged deployable: 52.9% of valid pairs. Invalid (unparsed/error) pairs: 0. Seeds whose three identity repeats disagree at all: 36/216.

## claude: `claude-sonnet-5`, adaptive thinking, effort low

| | pairs | valid | flip | deploy→reject | reject→deploy | flip rate | 95% CI | identity flip (n) | identity rate | identity CI |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| **all rewrites** | 446 | 446 | 56 | 22 | 34 | 12.6% | [8.4, 17.1] | 16/216 | 7.4% | [4.7, 10.1] |
| **Spelling** | 268 | 268 | 24 | 11 | 13 | 9.0% | [5.1, 13.3] | 16/197 | 8.1% | [5.3, 10.9] |
| **Logic** | 65 | 65 | 10 | 7 | 3 | 15.4% | [7.4, 25.5] | 5/38 | 13.2% | [4.3, 20.8] |
| **Temporal structure** | 113 | 113 | 22 | 4 | 18 | 19.5% | [12.0, 27.6] | 7/93 | 7.5% | [3.4, 11.5] |
| VAR — rename a variable | 50 | 50 | 5 | 3 | 2 | 10.0% | [2.0, 20.0] | 7/50 | 14.0% | [6.2, 21.2] |
| CMP — mirror a comparison (x >= 26 -> 26 <= x) | 152 | 152 | 9 | 5 | 4 | 5.9% | [2.6, 9.9] | 12/152 | 7.9% | [4.3, 11.0] |
| UNIT — change the time unit (3 MIN -> 180 SEC) | 27 | 27 | 2 | 0 | 2 | 7.4% | [0.0, 18.5] | 2/27 | 7.4% | [0.0, 13.3] |
| GRP — respell a condition over a group of devices | 39 | 39 | 8 | 3 | 5 | 20.5% | [10.3, 33.3] | 2/39 | 5.1% | [0.0, 9.1] |
| BR — negate the guard and swap the branches | 38 | 38 | 5 | 3 | 2 | 13.2% | [2.6, 23.7] | 5/38 | 13.2% | [4.3, 20.8] |
| ELS — drop the else by guarding it with the negated condition | 27 | 27 | 5 | 4 | 1 | 18.5% | [3.7, 33.3] | 3/27 | 11.1% | [0.0, 18.8] |
| DLY — split one delay into two | 25 | 25 | 2 | 0 | 2 | 8.0% | [0.0, 20.0] | 0/25 | 0.0% | [0.0, 0.0] |
| UNR — unroll a counted periodic loop | 15 | 15 | 0 | 0 | 0 | 0.0% | [0.0, 0.0] | 3/15 | 20.0% | [0.0, 33.3] |
| PHS — integer phase -> boolean flag with shared tail | 11 | 11 | 1 | 0 | 1 | 9.1% | [0.0, 27.3] | 2/11 | 18.2% | [0.0, 33.3] |
| WPC — check the condition before blocking on it | 62 | 62 | 19 | 4 | 15 | 30.6% | [19.4, 41.9] | 4/62 | 6.5% | [2.4, 10.5] |

Base programs judged deployable: 49.8% of valid pairs. Invalid (unparsed/error) pairs: 0. Seeds whose three identity repeats disagree at all: 21/216.
