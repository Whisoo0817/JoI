# Experiment tracker

| Run ID | Block ID | Gate ID | Purpose | Priority | Status | Dependency | Output artifact | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| e3-gemma-v3-b5-hnone-20260915 | E3-B1 | E3-G1 | Current-contract H=None recheck | must-run | decisive | E3-G0 pass | `runs/e3_gemma_v3_b5_hnone_20260915/` | E3-G1 pass; exploratory fixed outcome-visible candidates |
| e3-fresh-confirmatory | E3-B1 | E3-G2 | Fresh generation and H=None evaluation | must-run for stronger evidence | blocked | Gemma endpoint recovery and pre-generation freeze | separate future run | must not overwrite or pool current run |
