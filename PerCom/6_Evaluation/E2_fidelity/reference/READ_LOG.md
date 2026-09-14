# READ_LOG — files opened while writing the E2 independent reference

Every file opened (read, loaded, parsed or imported) by the author agent, with its purpose. Paths relative to `~/joi`.
Directory listings (`ls`) that only showed file names are listed at the end. No file under a forbidden path
(`explorer/runtime`, `explorer/verification`, `explorer/analysis`, `explorer/eval/*.py`, `explorer/tests/*.py` other than
`e1_runtime_probe.py`, `timeline_ir/*.py`, `timeline_ir/mapping/`, `lowering/*.py`, `lowering/parser/validator.py`,
`run_e1.py`, `run_depth.py`, `run_depth_v2.py`, `sensys/`) was opened.

## Specifications and protocol

| Path | Purpose |
|---|---|
| PerCom/6_Evaluation/E2_fidelity/PROTOCOL_DRAFT.md | experiment protocol; S1–S11, L1, `for` exclusion |
| explorer/docs/model/RUNTIME_CONTRACT.md | R1–R13 execution rules, `:=` boundary |
| explorer/docs/model/VERIFICATION_CONTRACT.md | inputs/services, time/reaction table, ACTION observation normal form |
| explorer/docs/model/SERVICE_MODEL.md | name normalisation, 7 read-role functions, argument checks |
| explorer/docs/model/SUPPORTED_FRAGMENT.md | only to know what the Explorer fragment describes |
| explorer/docs/proof/FRONTEND_CORRECTNESS.md | §1 query vs ACTION, §2 precedence, §3 fixed binding / quantifiers / slots (§4–§7 also visible in the same read) |
| docs/VETS_verification_contract_decisions_2026-09-07.md | D1–D9 |
| docs/JOI_SPEC.md | JoI language description |
| files/joi_common.md | JoI cheat-sheet, IR→JoI lowering rules (template/expression args, min/max meaning) |
| files/joi_cycle.md | cycle idioms (examples of intended meaning) |
| files/joi_noncycle.md | non-cycle idioms |
| lowering/parser/JOILang.g4 | JoI grammar |
| files/timeline_ir/extractor.md | Timeline IR step/expression grammar, D-rules (not modified) |
| PerCom/3_Timeline_IR/HANDOFF.md | "E1 에서 확정된 실행 의미" |

## Catalogs

| Path | Purpose |
|---|---|
| files/service_list_ver2.0.7.json | service catalog (loaded with `json`, structure surveyed) |
| PerCom/6_Evaluation/E1_adequacy/breadth/depth/runs/fixture_catalog.json | E1 fixture catalog v1 (json, type survey) |
| PerCom/6_Evaluation/E1_adequacy/breadth/depth/runs/fixture_catalog_v2.json | E1 fixture catalog v2 (json, used by depth v2 conformance) |

## E1 case data (IR-free expected traces and IR encodings as data)

| Path | Purpose |
|---|---|
| PerCom/6_Evaluation/E1_adequacy/README.md | Stage A procedure, tolerance, notes |
| PerCom/6_Evaluation/E1_adequacy/cases.py | Stage A interpretations and expected traces (no imports; imported as data by the conformance test) |
| PerCom/6_Evaluation/E1_adequacy/irs.py | Stage A IRs (no imports; imported as data) |
| PerCom/6_Evaluation/E1_adequacy/breadth/depth/depth_cases.py | depth v1 records, transcription rules T1–T7 (no imports; imported as data) |
| PerCom/6_Evaluation/E1_adequacy/breadth/depth/depth_cases_v2.py | depth v2 records (imports only `copy`, `depth_cases`; imported as data) |
| PerCom/6_Evaluation/E1_adequacy/breadth/depth/depth_attempts.py | v1 encodings and JoI blocks (no imports; imported as data) |
| PerCom/6_Evaluation/E1_adequacy/breadth/depth/depth_attempts_v2.py | v2 encodings (imports only `depth_attempts`; imported as data) |
| PerCom/6_Evaluation/E1_adequacy/breadth/depth/fixture.py | stub definitions (read only, not imported) |
| PerCom/6_Evaluation/E1_adequacy/breadth/depth/fixture_v2.py | stub definitions v2 (read only, not imported) |
| PerCom/6_Evaluation/E1_adequacy/breadth/depth/README.md | depth procedure |
| PerCom/6_Evaluation/E1_adequacy/breadth/depth/RESULTS.md | depth v2 recorded results (for comparison of counts only) |
| PerCom/6_Evaluation/E1_adequacy/breadth/frozen_cases/E1-028.md, E1-034.md, E1-062.md, E1-072.md, E1-086.md, E1-092.md, E1-095.md, E1-099.md, README.md | frozen records |
| explorer/tests/e1_runtime_probe.py | READ ONLY to copy the 15 hand-computed script/expected-trace pairs and 3 mutation controls; never imported |

## Dataset and candidates

| Path | Purpose |
|---|---|
| dataset.csv | 388 rows: `ir_gt`, `binding_gt`, `connected_devices` (csv, surveyed and used by smoke test) |
| explorer/candidates/gemma4-26b-contract-v1-fresh-v4/*.json (388 files) | `joi_block` scripts (json, surveyed and used by smoke test) |

## Code imported

| Path | Purpose |
|---|---|
| lowering/parser/generated/JOILangLexer.py, JOILangParser.py | ANTLR-generated parser (imported from its directory; first 5 lines of JOILangParser.py viewed, `grep antlr4`, class introspection) |
| ~/temp/lib/python3.12/site-packages/antlr4 | ANTLR runtime (imported) |

## Update 2026-09-14 (author decisions on SPEC_GAPS)

| Path | Purpose |
|---|---|
| lowering/parser/JOILang.g4 | copied (unchanged source) to reference/grammar/JOILang.g4, `%` added there |
| lowering/parser/antlr-4.13.2-complete.jar | run with `java -jar` to regenerate the Python3 parser into reference/grammar/ (not imported) |
| reference/grammar/JOILangLexer.py, JOILangParser.py, JOILangListener.py | generated; now the parser imported by joi_ref.py (lowering/parser/generated is no longer imported) |

Not opened: `../pairs/`, `../histories/`.

## Update 2026-09-14 (ordered comparison with None)

No new file opened. Change made from the author decision relayed by the coordinator. Not opened: `../pairs/`,
`../histories/`, `../runs/`, `../run_e2.py`.

## 2026-09-14 binding decision update

| Path | Purpose |
|---|---|
| PerCom/6_Evaluation/E2_fidelity/BINDING_DECISION_2026-09-14.md | author decision B0–B4 (implemented as B1/B2) |
| PerCom/6_Evaluation/E2_fidelity/reference/common.py, ir_ref.py, joi_ref.py, run.py, SPEC_GAPS.md, CONFORMANCE.md, READ_LOG.md, test_independence.py, test_e1_conformance.py, smoke_388.py | the reference's own files, re-read before editing |
| explorer/docs/model/VERIFICATION_CONTRACT.md | "ACTION 관찰" section re-read (grep of that heading and the following lines) for the B2 unit rule |
| files/service_list_ver2.0.7.json, PerCom/6_Evaluation/E1_adequacy/breadth/depth/runs/fixture_catalog_v2.json | loaded through `Catalog` to confirm Switch.On, Speaker.Speak, TemperatureSensor.Temperature, Valve.Open/Close exist for the self-test |
| PerCom/6_Evaluation/E2_fidelity/pairs/sample_388_pairs.json, pairs/e1_pairs.json | read (json) to see the pair shape and to run the 8 pairs named by the coordinator with the new API (not modified) |
| PerCom/6_Evaluation/E2_fidelity/histories/sample_388_histories.json, histories/e1_histories.json | read (json) for the frozen histories of those pairs (not modified) |

Not opened: `../runs/`, `../handoff_timer/`, `../run_e2.py`, `pairs/*.py`, `histories/*.py`, and every forbidden path.
The E1 conformance run imports the E1 data modules listed above as before. Directory listing only: `pairs/`,
`histories/` (file names).

### 2026-09-14 binding decision update — corrections (B1.3, B1.4, B2)

| Path | Purpose |
|---|---|
| PerCom/6_Evaluation/E2_fidelity/BINDING_DECISION_2026-09-14.md | re-read after the author revised B1.3/B1.4 (B2 correction taken from the coordinator's message) |
| PerCom/6_Evaluation/E2_fidelity/pairs/sample_388_pairs.json, pairs/e1_pairs.json, histories/sample_388_histories.json, histories/e1_histories.json | read again (json) to redo the 8-pair check (not modified) |

No other new file opened; no forbidden path opened.

### 2026-09-14 binding decision update — B5 (selector assignments)

| Path | Purpose |
|---|---|
| PerCom/6_Evaluation/E2_fidelity/BINDING_DECISION_2026-09-14.md | §B5 read (grep of "B5" and the following 40 lines, which also showed §B3/§B4 again) |

No other new file opened (the B5 tests are hand-written; no pair, history or run file used); no forbidden path opened.

### 2026-09-14 author decision — `any(...)` in ACTION position is a syntax error (SPEC_GAPS G35)

| Path | Purpose |
|---|---|
| (coordinator message) | author decision whisoo 2026-09-14: `any(...)` on a call statement is invalid input |
| PerCom/6_Evaluation/E2_fidelity/handoff_timer/e2_population.json | decision record: C03_008/llm excluded as `invalid_syntax` (json, read only) |
| PerCom/6_Evaluation/E2_fidelity/BINDING_DECISION_2026-09-14.md | grep of `any(` to find text about `any` selectors |
| PerCom/6_Evaluation/E2_fidelity/pairs/e1_pairs.json, pairs/sample_388_pairs.json | JoI scripts scanned with the reference parser for ACTION-position `any` (not modified) |

No other new file opened; no forbidden path opened. Not opened: `../runs/`, `../histories/`, other `handoff_timer/` files.

### 2026-09-14 author decision — `any(...)` only inside a condition (SPEC_GAPS G35 revised)

| Path | Purpose |
|---|---|
| (coordinator message) | author decision whisoo 2026-09-14: `any(...)` allowed only in a condition (if / else if / wait until); replaces the G35 [choice] on query assignments |
| PerCom/6_Evaluation/E2_fidelity/reference/grammar/JOILang.g4 | reference copy of the grammar: which rules take a `condition_list` (if, wait until, loop) and where `range_type` appears |
| PerCom/6_Evaluation/E2_fidelity/pairs/e1_pairs.json, pairs/sample_388_pairs.json | JoI scripts scanned with the reference parser for `any` outside a condition (not modified) |

No other new file opened; no forbidden path opened. Not opened: `../runs/`, `../histories/`, `handoff_timer/`.

## Directory listings only (names, no content)

`PerCom/6_Evaluation/E2_fidelity/`, `PerCom/6_Evaluation/E1_adequacy/` (+ `breadth/`, `breadth/depth/`, `breadth/depth/runs/`,
`breadth/frozen_cases/`), `lowering/parser/generated/`, `explorer/candidates/gemma4-26b-contract-v1-fresh-v4/` (count).
The E1 listing showed the names `run_e1.py`, `run_depth.py`, `run_depth_v2.py`, `probes.py`, `probe_attempts.py`,
`make_results.py` etc.; none of them was opened.
