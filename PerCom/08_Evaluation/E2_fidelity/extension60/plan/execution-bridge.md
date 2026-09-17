# Execution Bridge

Standalone, not orchestrated. C1 binds B1/G1 and B2/G2. Runner accepts --pairs, --histories, --supplement, --out, --workers8 and --freeze-manifest; --freeze-only creates data/runtime digest record before evaluation. Use /home/gnltnwjstk/temp/bin/python. Capture basegitHEAD, Pythonenvironment and currentload. Freeze each batch before launch; datachangesrequire a new explicit lineage record preserving prior attempt. Every selectedpair must appear exactlyonce in final canonicalbatch output; errors remain. Hashcontinuity doesnotprove independent isolation. See selection protocol files under e1/ and llm/ for exactsource decisions.

### B1

C1/G1: ../e1/pairs.json with ../../histories/e1_histories.json and ../../histories/supplement_histories.json.gz. Output ../runs/e1_new48.jsonl. Freeze before engine launch; no data or runtime mutation while running.

### B2

C1/G2: ../llm/pairs.json with ../llm/histories.json and ../llm/supplement_histories.json. Output ../runs/llm_new12.jsonl. Freeze before engine launch; retain all screened and excluded IDs.
