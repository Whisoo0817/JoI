# Execution bridge

## E3-B1

- Claim: `E3-C1`; gate: `E3-G1`; evidence class: exploratory.
- Inputs: complete current `dataset.csv`, fixed `gemma4-26b-heldout-v3` candidate directory, and its historical hash manifest.
- Protocol first: run `explorer.eval.frozen_contract protocol --unbounded --candidate-provenance ...`.
- Preparation second: freeze current pair payloads, candidate hashes, automatic method choice, input/GV domains, and preparation failures.
- Execution third: run the frozen manifest once. Keep all 388 rows and all failure states.
- Audit checks: source/candidate continuity; unique exact ID coverage; positive closure with no bounded horizon; confirmed replay for each divergence; separate completion and outcome rates.
- Restart: outputs are exclusive-create/append-only. A failed run is preserved and any retry receives a new run ID.
- Blocker for stronger evidence: `localhost:8002` and the configured SSH tunnel are unavailable, so no fresh candidate sample can currently be generated.
