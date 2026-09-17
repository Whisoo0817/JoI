# Extension execution harness

`runner.py` executes the supplied new pairs using the existing `run_e2.py`
reference, Explorer, witness replay and agreement functions. It does not alter
the original evaluator, reference, Explorer or historical result files.

Both binding switches are forced on. Explorer keeps the original 120-second
alarm, 400,000-state and 2,000,000-transition limits, unbounded horizon and
`verification_mode="auto"`. As in the existing B5 harness, 120 seconds applies
to **each selector assignment exploration**, not to a newly imposed total
across assignments. Reference histories have no new timeout or sample cap.

By default the reference runs every original history for the first/tag-rule
assignment; the existing B5 search and its subsequent-assignment divergence
short circuit are retained. The prospective opt-in
`--reference-short-circuit` execution refinement stops **each assignment**
after its first concrete reference divergence. It still tries other B5
assignments: equivalence requires one assignment to complete every history,
and divergence requires a counterexample for every assignment. Undecided
assignments retain the existing B5 unsupported/error handling. Thus the
refinement preserves the pair-level decision without claiming unchanged
history coverage. It never selects histories using Explorer outcomes.

The short-circuit option replays the first divergent history once to retain
the normal first-divergence diagnostics. `n_histories` remains the inherited
available-history count; new `n_histories_available`,
`n_histories_examined` and `n_diagnostic_replays` disambiguate coverage.
`reference_assignment_checks` records **all** attempted assignments, including
those whose result was not selected by B5. Supplementary assignment records
are in `reference_supplement.assignment_checks`. The option is off by default
and is part of the runtime freeze, so use it consistently when freezing and
running if the prospective protocol selects it.

Supplementary histories run only after an original-history
`REF-EQUIV-CHECKED` outcome, following `run_binding_v1.py`. Only a supplementary
divergence replaces the combined reference outcome. Supplementary unsupported,
error and harness-error outcomes remain explicitly recorded in
`reference_supplement`; they must not be described as fully checked equivalence
over supplementary histories. Counts and original-history outcomes are retained.
The runner does not require new faults to diverge and does not remove any
refusal, timeout, unsupported result or error from the output.

## Invocation and freeze

From `PerCom/08_Evaluation/E2_fidelity`, for example:

```bash
~/temp/bin/python extension60/runner.py \
  --pairs extension60/e1/pairs.json \
  --histories histories/e1_histories.json \
  --supplement histories/supplement_histories.json.gz \
  --freeze-manifest extension60/runtime_freeze.json --freeze-only \
  --reference-short-circuit

~/temp/bin/python extension60/runner.py \
  --pairs extension60/e1/pairs.json \
  --histories histories/e1_histories.json \
  --supplement histories/supplement_histories.json.gz \
  --freeze-manifest extension60/runtime_freeze.json \
  --out extension60/runs/e1_extension.jsonl --workers 8 \
  --reference-short-circuit
```

Repeat `--pairs`, `--histories` and `--supplement` for multiple files. They use
the existing `{"pairs": [...]}` and `{"histories": {base: [...]}}` formats;
gzip is accepted. Repeated base-case histories must be identical, otherwise
the loader refuses ambiguous overwrites. Pair IDs must be unique. Referenced
catalogs must exist: data preparation must explicitly resolve the historical
`PerCom/6_Evaluation` to `PerCom/08_Evaluation` directory rename.

The runtime manifest is created exclusively and contains SHA-256 hashes of
the harness, original evaluators, Explorer Python sources, reference Python
sources, `timeline_ir`, `lowering`, grammar, E1 lowering dependencies and
catalog assets, plus Python/dependency versions and settings. It is checked
before and after execution. It can be shared by separately prepared input
batches. Each output's `.meta.json` independently locks the input-file and
catalog hashes, selected pair IDs, stage and runtime-manifest hash. A restart
with changed inputs or runtime is refused. This is a source/hash freeze, not a
filesystem snapshot; do not edit the frozen runtime during execution.

`--only PREFIX` is recorded in the output metadata. `--preflight` marks every
row and its metadata as preflight and permits an unfrozen old-pair smoke.
Preflight subsets are not extension experiment evidence. The runner refuses
to write under the historical `E2_fidelity/runs` directory.

## Speed and recovery

Pairs are grouped by base case. Each worker memoizes the full public reference
`run_ir` call, including IR, bindings, inventory, events, horizon, catalog,
start time and keyword arguments, with an 8,192-entry LRU cache. Serialization
preserves mapping order. Cached results are defensively copied. Cache reuse
does not depend on JoI output, Explorer verdict or history name. Consequently
variants sharing exactly the same IR/history inputs avoid repeated IR
execution; distinct automations, histories and witness replays remain distinct
calls. Memoization itself removes no JoI history execution; the separate
opt-in counterexample stopping rule is described above. The cache is released between base
groups. Per-row cache hit/miss counts are recorded.

A Manager queue streams completed pairs to the parent immediately, even while
other variants of that base are still running. The parent appends, flushes and
fsyncs every JSONL row. Rerunning the same command skips every recorded pair,
including error outcomes, and recomputes only unfinished pairs. Malformed
JSONL is refused rather than silently discarded. An intact final JSON object
missing only its trailing newline is repaired. Worker failures are retained
as `HARNESS-ERROR`; no outcome-specific filtering is applied. Workers cancel
any remaining SIGALRM after each pair.

Historical timings are an approximate planning guide only: the old
`binding-final` run accumulated 50,491.63 wall-seconds across 142 pairs.
Assigning each new E1 pair the old median of its base gives 20,156 seconds for
the 48-pair batch, or 42 minutes at ideal eight-worker utilization before cache
savings. Grouping can create stragglers: the two E1-034 variants correspond to
6,804 historical seconds (113 minutes) before savings. Current hardware,
contention, mutation behavior and cache reuse can change these substantially.
No guaranteed finish time follows from these old measurements. These timing
estimates precede the opt-in counterexample stopping refinement; faults
exposed by early histories can now finish much sooner, while equivalent pairs
still check every required history.

## Preflight evidence (2026-09-18; old pairs only)

The source passed `python -m py_compile`. The following old-pair checks used
the first three original C01 histories, explicitly as preflight subsets:

| Old pair | Uncached reference | Cached reference, two passes | Explorer |
|---|---|---|---|
| `C01/correct` | `REF-EQUIV-CHECKED`, 3 equal | Exactly identical dictionaries | `EQUIV`, 6 states |
| `C01/fault1` | `REF-DIVERGE`, 3 diverge | Exactly identical dictionaries | `DIVERGE`, 4 states |

Both cache checks recorded exactly three misses on the first cached pass and
three hits on the next. Correct-pair uncached reference took 0.473 s; the two
cached passes together took 0.752 s. Full `work_group` integration on the same
correct-pair subset yielded `AGREE-EQUIV-ON-CHECKED` in 0.512 s. The mutation
control's first `single_pass` divergence retained the IR light-Off action at
140,000 ms and the faulty JoI light-Off action at 80,000 ms; Explorer reported
DIVERGE in 0.18 s. These checks establish local cache agreement and outcome
plumbing, not full-corpus regression or extension outcomes.

The additional short-circuit preflight compared the same old pairs before
and after enabling the option. `C01/correct` retained its outcome and checked
3/3 histories with no diagnostic replay. `C01/fault1` retained `REF-DIVERGE`
and the **exact same first-divergence dictionary**, checked 1/3 histories,
and performed one diagnostic replay. Its recorded divergence count changed
from three to one as intended; this is actual coverage, not a claim that all
three histories were re-executed in the optimized pass. B5 orchestration is
the unchanged `run_e2.reference_side`, and an assignment can return
`REF-EQUIV-CHECKED` only when its equal count equals the full history count.

A direct B5 safety preflight used old `C16/fault1` and its first three
histories. Both implementations returned `REF-EQUIV-CHECKED` after two
assignments, with identical selector metadata. The optimized audit recorded
assignment `[0,0]` as divergent after 1/3 histories plus one diagnostic replay,
then assignment `[0,1]` as equivalent after all 3/3 histories. This verifies
that an early counterexample on the tag-rule assignment does not prevent a
later equivalent assignment from determining the final result.

A two-pair CLI preflight in an automatically deleted temporary directory
exercised the process pool, queue, JSONL and resume metadata using those same
three-history C01 subsets. It wrote exactly two rows (`AGREE-EQUIV-ON-CHECKED`
and `AGREE-DIVERGE`), with worker durations 0.234 s and 0.204 s. The faulty
variant reused two IR calls and computed one additional witness IR call.
Repeating the identical command reported zero remaining pairs and left the
JSONL byte-for-byte unchanged. No extension candidates were executed by these
preflight checks.

The current Explorer differs from the historical mixed-source E2 results.
Preserving old 140 rows and appending current 60 rows alone does not establish
a homogeneous runtime version. The separate `baseline_regression.py` artifact
and reference-source compatibility audit must support any current-runtime
combined-table claim. This runner neither overwrites nor relabels the original
140 historical rows.
