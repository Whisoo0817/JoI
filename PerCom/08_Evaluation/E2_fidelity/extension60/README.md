# E2 extension: 200 IR–JoI pairs

Latest report: [RESULT_KO.md](RESULT_KO.md). Machine counts: [summary.json](summary.json). Per-pair canonical results: [results200.jsonl](results200.jsonl). Audit: [audit/results-audit.md](audit/results-audit.md).

The 200 pairs contain 150 hand-built pairs from the same 20 E1 requests and 50 generated candidates. The original 140 were retained; 48 new fault variants and 12 generated candidates were added. All 140 original Explorer verdicts were replayed with the current frozen runtime and remained unchanged. Original reference evidence is reused after runtime source comparison to the R14 version; all current divergent witnesses are replayed. The separate reference implementation is not an external independent audit.

Final verdicts: 64 EQUIV, 119 DIVERGE, 9 REFUSED, 8 TIMEOUT. All183 issued decisions agree with the specified reference checks. This is finite benchmark evidence, not universal correctness or population accuracy.

## Artifacts and provenance

- `plan/`: pre-execution extension allocation, decision rule, outcomes and tracker. Extension was planned after old results were known; no retroactive preregistration.
- `e1/`: declared48mutation edits, generatedpairs, staticchecks, frozenhashes and separate-agent review. Existing requests were not selected by operator coverage.
- `llm/`: seed20260918 sampling without original40, all13 inspected candidates, one static capability rejection, input histories and hashes.
- `llm/retry_c15/`: samecandidate C15_002 technicalretry; weeklycron anchor was null and corrected toSaturday00:00. Pair IR/code unchanged; all generated histories unchanged. Initialfailed attempt preserved.
- `runtime_freeze.json`:211source/asset hashes; output `.meta.json` files lock each batch's inputs and settings.
- `RUNNER_NOTES.md`: memoization, sufficient-counterexample stopping, B5 handling, preflight controls and actualhistory accounting.
- `runs/`: preserved initial12, correctedC15retry, new48 and currentbaseline140 results. Never edit these raw outputs.

## Regenerate summaries

From `E2_fidelity`:

```bash
python extension60/summarize.py
python extension60/audit/write_audit.py
```

The summary requires all200identities and preserves theinitialtechnicalerror. The audit is rootself-review with separate-agent staticinspection; its structural validation alone doesnotestablish scientificcorrectness.

## Execute unchanged frozen batches

Use commands in `plan/run-blocks.json` from each declared workingdirectory, or `RUNNER_NOTES.md` with `--reference-short-circuit`. Outputs are resumable and completederrorrows are not silentlyrerun. C15retry has its own immutableinputs and `runs/llm_c15_retry.jsonl`. Runtime or inputchanges require a separatelyrecorded retry, not overwritingfreeze/results.

Preparedhistories total55,071; new60 examined8,128 assignment-history runs plus1,465diagnostic replays (Explorerwitness replay counted separately). Preparedhistories are not all claimedexecuted. For eachassignment, one concrete difference establishes divergence; allassigned histories mustmatch for agreement. The inherited conditional supplementary/B5fold remains and mayuse different existentialassignments across original/supplement sets.
