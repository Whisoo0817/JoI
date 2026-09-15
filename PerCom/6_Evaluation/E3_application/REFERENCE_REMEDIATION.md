# E3 reference remediation record

These changes apply the general rules in `files/ir_joi_semantic_contract.md`.
They are retained separately from generated-candidate outcomes.

| Scope | Change | Contract reason |
| --- | --- | --- |
| All 36 re-arming edge rows formerly using `100 MSEC` | `cycle.period` becomes `1 SEC` | Existing extractor default is 1-second polling; explicit confirmed periods are preserved |
| C01_006 | `SetChannel(current-1)` becomes `ChannelDown()` | Exact catalog relative operation avoids an invalid `-1` argument at channel 0 |
| C15_009, C15_010 | Menu query binds only `Main_MenuProvider`; inventory gains command-relevant cafeteria tags | A scalar return requires exactly one provider; the provider is made identifiable rather than selected after a verdict |
| C17_003 | Remove the unused `SetVolume` return assignment and explicitly saturate `Volume+10` at 100 | Effect and return flow are separate; numeric action args stay within the declared 0–100 domain |
| C18_006 | Wait until any motion or 23:00, and lock only when the clock ends the wait | The predicate concerns the whole 22:00–23:00 interval, not the first sample |
| C03_003 | No invented temperature bound | `TargetTemperature` has no catalog bound; it remains an explicitly named unsupported input-domain case |

The earlier candidates and outcomes remain unchanged. Fresh candidates must be
generated only after the repaired dataset and evaluator contract are frozen.
