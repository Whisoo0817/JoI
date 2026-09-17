# E2 LLM extension selection (predeclared 2026-09-18)

Draw 12 additional admissible candidates from the unchanged
`explorer/candidates/gemma4-26b-contract-v1-fresh-v4` generation pool.
Exclude every one of the original 40 IDs in `pairs/sample_388.json`, including
the two original invalid candidates. Eligibility is generation status `ok`
and a nonempty `joi_block.script`. Sort eligible remaining IDs, then shuffle
once with Python `random.Random(20260918).shuffle`. Inspect in that order and
retain the first 12 passing the static screen. Preserve the complete draw
order and every inspected acceptance/rejection with its reason.

The static screen uses the existing grammar and AST conversion, including
the existing prohibition on `any(...)` outside conditions. Check selector
members against the catalog and connected-device capabilities. Check
literal call argument types/counts/domains using the existing catalog rule.
This screen does not execute a program or inspect an Explorer/reference
result. No candidate is regenerated. No candidate is replaced based on
subsequent execution, refusal, timeout, witness, or agreement.

Build pairs with `build_388_pairs.py` field construction and start-time rule.
Build original histories using `make_388_histories.py` rules and
`make_e1_histories.build_case`, preserving 100 ms grid, 300-pulse cap,
original seed 20260914 and six-hour horizon cap. Supplement using unchanged
`make_supplement.py` rules: 200 start assignments per seed and 1500 additional
pulses per case, seed `20260914-supp`, including the exact original-history
reproduction check. Save original, supplementary, and concatenated histories.
Histories use only IR, binding, inventory, catalog and the fixed rules.

Freeze selection and all input hashes before either evaluation engine runs.
