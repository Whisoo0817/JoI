"""IR/JoI simulators for trace-equivalence verification.

Backs paper §6 (operational semantics) and §9 (evaluation).

Public entry points:
- run_ir_simulation(ir, scenario, catalog) -> Trace
- run_joi_simulation(joi_block, scenario, catalog) -> Trace
- synthesize_scenarios(ir) -> list[Scenario]
- compare_traces(trace_ir, trace_joi) -> ComparisonResult

Design decisions are locked in `project_simulator_design_decisions.md`.
"""

from .traces import TraceRecord, Trace, normalize_args
from .scenario import Scenario, ScenarioEvent
from .comparator import compare_traces, ComparisonResult
from .ir_simulator import run_ir_simulation
from .joi_simulator import run_joi_simulation
from .event_synth import synthesize_scenarios

__all__ = [
    "TraceRecord", "Trace", "normalize_args",
    "Scenario", "ScenarioEvent",
    "compare_traces", "ComparisonResult",
    "run_ir_simulation", "run_joi_simulation",
    "synthesize_scenarios",
]
