"""Independent search oracle: every millisecond, every declared input history.

No deadline scheduler, predicate partition, time rebasing, or input reduction
is shared with timed.py. Concrete one-step runners and ACTION observation are
shared; interpreter correctness therefore needs separate expected-trace tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import itertools
import math
import time

from explorer.verification.input_model import validate_domains
from explorer.verification.observation import actions_observation
from explorer.verification.state_key import freeze_state as freeze
from explorer.runtime.runner import TerminalRunner


@dataclass
class ExactTimedResult:
    verdict: str
    horizon_ms: int
    input_step_ms: int
    n_states: int = 0
    n_transitions: int = 0
    seconds: float = 0.0
    divergence_ms: int | None = None
    actions_a: tuple = ()
    actions_b: tuple = ()
    path: tuple = ()  # (offset_ms, inputs), only input changes
    notes: list = field(default_factory=list)


def exact_timed_product(runner_a, runner_b, *, input_domains, horizon_ms,
                        input_step_ms=100, initial_gv_domains=None,
                        t0_ms=2_419_200_000, max_states=1_000_000,
                        max_transitions=5_000_000, max_input_combinations=100_000):
    if type(t0_ms) is not int:
        raise ValueError("t0_ms must be an integer")
    if type(horizon_ms) is not int or horizon_ms < 0:
        raise ValueError("horizon_ms must be a nonnegative integer")
    if type(input_step_ms) is not int or input_step_ms <= 0:
        raise ValueError("input_step_ms must be a positive integer")
    if min(max_states, max_transitions, max_input_combinations) <= 0:
        raise ValueError("resource caps must be positive")
    from explorer.verification.product import merge_axes
    from explorer.verification.input_coverage import initial_domains
    from explorer.verification.service_model import runner_input_domains
    input_domains = runner_input_domains(runner_a, runner_b, input_domains)
    axes = merge_axes(runner_a.axes, runner_b.axes)
    validate_domains(input_domains, required=axes.cells)
    initial_gv_domains = initial_domains(axes, initial_gv_domains)
    if any(k.startswith("@gv:") and k[4:] in axes.coverage.writes for k in input_domains):
        raise ValueError("written GVs require initial domains, not external input domains")
    started = time.perf_counter()
    result = ExactTimedResult("EQUIV_BOUNDED", horizon_ms, input_step_ms)

    def stop(note):
        result.verdict = "INCOMPLETE"
        result.notes.append(note)
        result.seconds = time.perf_counter() - started
        return result

    keys, init_keys = sorted(input_domains), sorted(initial_gv_domains)
    count = math.prod(len(input_domains[k]) for k in keys)
    init_count = math.prod(len(initial_gv_domains[k]) for k in init_keys)
    if count > max_input_combinations or count * init_count > max_transitions:
        return stop("input/initial-state combination cap reached")
    combos = [dict(zip(keys, vals)) for vals in itertools.product(*(input_domains[k] for k in keys))]
    initial = [{k: v for k, v in zip(init_keys, vals) if v is not None}
               for vals in itertools.product(*(initial_gv_domains[k] for k in init_keys))]
    external_gv = {k[4:] for k in keys if k.startswith("@gv:")}
    a, b = TerminalRunner(runner_a), TerminalRunner(runner_b)
    frontier = [({}, gv, {}, gv, {}, ()) for gv in initial]
    for offset in range(horizon_ms + 1):
        successors = {}
        for av, ag, bv, bg, held, path in frontier:
            choices = combos if offset % input_step_ms == 0 else [held]
            for inputs in choices:
                if result.n_transitions >= max_transitions:
                    return stop("transition cap reached")
                world = {k: v for k, v in inputs.items() if not k.startswith("@gv:")}
                external = {k[4:]: v for k, v in inputs.items() if k.startswith("@gv:")}
                ra = a.step(av, {**ag, **external}, world, t0_ms + offset, offset == 0)
                rb = b.step(bv, {**bg, **external}, world, t0_ms + offset, offset == 0)
                result.n_transitions += 1
                next_path = path + ((offset, dict(inputs)),) if offset % input_step_ms == 0 else path
                oa, ob = actions_observation(ra.actions), actions_observation(rb.actions)
                if oa != ob:
                    result.verdict = "DIVERGE"
                    result.divergence_ms, result.path = offset, next_path
                    result.actions_a, result.actions_b = oa, ob
                    result.seconds = time.perf_counter() - started
                    return result
                if ra.terminated and rb.terminated:
                    continue
                agn = {k: v for k, v in ra.gv.items() if k not in external_gv}
                bgn = {k: v for k, v in rb.gv.items() if k not in external_gv}
                key = freeze((ra.vars, agn, rb.vars, bgn, inputs))
                successors.setdefault(key, (ra.vars, agn, rb.vars, bgn, dict(inputs), next_path))
                if len(successors) + result.n_states > max_states:
                    return stop("state cap reached")
        result.n_states += len(successors)
        frontier = list(successors.values())
        if not frontier:
            break
    result.seconds = time.perf_counter() - started
    return result
