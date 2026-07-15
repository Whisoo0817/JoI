# IR/JoI Simulators

Trace-equivalence verification for Timeline IR ↔ JoI lowering. Backs paper §6 (operational semantics) and §9 (evaluation).

## Usage

```python
from paper.simulators import (
    run_ir_simulation, run_joi_simulation,
    synthesize_scenarios, compare_traces,
)
from paper.simulators.catalog import load_catalog

catalog = load_catalog()
scenario = synthesize_scenarios(ir_dict)[0]
trace_ir  = run_ir_simulation(ir_dict, scenario, catalog)
trace_joi = run_joi_simulation(joi_block, scenario, catalog)
result = compare_traces(trace_ir, trace_joi)
print(result.equivalent, result.diff_summary)
```

Run the bundled E2E sanity suite:
```
cd /home/gnltnwjstk/joi
python -m paper.simulators.test_e2e
python -m paper.simulators.test_e2e -v   # verbose
```

## Architecture

```
ir_dict ──┐
          │  synthesize_scenarios ──> Scenario
joi_block─┘                             │
                ┌───────────────────────┴───────────────────────┐
                ▼                                               ▼
         run_ir_simulation                            run_joi_simulation
                │                                               │
                ▼                                               ▼
            Trace_IR                                        Trace_JoI
                └──────────────► compare_traces ◄───────────────┘
                                       │
                                       ▼
                                 ComparisonResult
```

## File map

| File | Purpose |
|---|---|
| `traces.py` | TraceRecord + Trace + arg normalization |
| `catalog.py` | Service catalog loader (positional arg ordering) |
| `scenario.py` | Scenario: scheduled external events |
| `world.py` | Mutable world state + virtual clock |
| `expr.py` | Expression parser+evaluator (shared by IR cond + JoI cond) |
| `event_synth.py` | IR-guided rule-based scenario generator |
| `ir_simulator.py` | Linear timeline walker (paper §6.2) |
| `joi_parser.py` | JoI script parser (statements + expressions) |
| `joi_simulator.py` | Tick-based AST interpreter (paper §6.3) |
| `comparator.py` | 5-step trace equivalence check |
| `test_e2e.py` | Hand-constructed IR/JoI pairs covering D-1..D-9 |

## Locked design decisions

See `~/.claude/projects/-home-gnltnwjstk/memory/project_simulator_design_decisions.md`.

Highlights:
- **Trace = `(timestamp_ms, service, method, args)`** — no device-id (out of scope per precision stage).
- **JoI tick = 100ms** for poll resolution; periodic JoI uses its own `period` for wake cadence.
- **Virtual clock starts at Mon 00:00**; stop conditions: 1000 distinct trace groups, 7 days, or no pending work.
- **Comparison**: normalize → group by ±100ms → dedup identical `(method, args)` within group → ordered list compare.

## Known semantic divergences (paper findings, not bugs)

- **D-4 phase lifecycle with large period**: IR's wait satisfies on the next 100ms poll; JoI's wait blocks until the next `period` tick. With `period=60s`, JoI's first emit can lag the IR emit by up to 60s. The E2E test uses `period=1000` to keep this within ±100ms tolerance; large-period D-4 cases will surface in §9 evaluation.

## Open ambiguities (decisions made; revisit if needed)

1. **`call.bind` semantics** — IR sim stores the args dict as the bound var's value (not a real return). Most patterns don't read back; revisit if D-8 (read+diff) cases need precise return modeling.
2. **`apply_effect` coverage** — covers `On`/`Off`/`Toggle`/`Set*`/`MoveTo*`. Unknown setters leave world unchanged (which is fine if downstream code doesn't read the changed attr).
3. **Synth happy-path only** — current synth produces ONE scenario taking the `then` branch and satisfying every wait. Branch-coverage extension (else paths, multiple scenarios) is future work.
4. **Cron edge cases** — 5-field cron with `*`, ranges, lists, `*/N`, and dow names supported. `@yearly`/`@daily` macros not supported (none observed in dataset).
5. **`any/all` selectors in cond** — synthesizer hard-errors on `any(#X).Y == V` (not yet supported). Phase-2 work.
