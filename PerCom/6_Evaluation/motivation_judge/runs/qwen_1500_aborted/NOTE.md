# Aborted Qwen arm — max_tokens 1500 (2026-09-16)

313 of 948 calls. Stopped because 46 of the first 311 (15%) hit the 1500-token cap
(`finish=length`) and never emitted the JSON verdict, so they counted as unparsed. The cap,
not the judge, was the binding constraint. Re-run with max_tokens 3000; these responses are
not used, because every call in one Table 1 row must share one decoding configuration.
