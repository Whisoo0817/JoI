"""Bounded, tick-by-tick reference search for IR/code behavior pairs.

This module is intentionally separate from :mod:`explorer.product`.  It does
not use predicate cells derived from source code, normalized states, time
jumps, stutter witnesses, or input-combination deduplication.  The caller
supplies a finite input model explicitly and the oracle executes every input
sequence through the declared tick horizon.

The oracle reuses the two concrete one-step runners.  Consequently, agreement
with this module validates the Explorer's search reductions, not the semantic
correctness of those runners.  Interpreter conformance remains a separate E1
obligation.
"""

from __future__ import annotations

import itertools
import math
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

from .interp import Unsupported


# Monday 00:00, aligned with the Explorer but duplicated here so this search
# implementation does not depend on explorer.explore/product internals.
T0_DEFAULT = 28 * 24 * 60 * 60 * 1000


class _InputSpaceTooLarge(ValueError):
    pass


@dataclass(frozen=True)
class ExactDivergence:
    """First difference under canonical input enumeration."""

    tick: int
    input_: dict
    actions_a: tuple
    actions_b: tuple
    terminated_a: bool
    terminated_b: bool
    path: tuple


@dataclass
class ExactTickResult:
    """Outcome of complete bounded history-tree exploration."""

    verdict: str  # EQUIV_BOUNDED | DIVERGE | INCOMPLETE
    horizon_ticks: int
    n_input_combinations: int
    n_states: int = 0
    n_transitions: int = 0
    max_frontier: int = 0
    completed_ticks: int = 0
    seconds: float = 0.0
    divergence: ExactDivergence | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class _Node:
    av: dict
    ag: dict
    bv: dict
    bg: dict
    path: tuple


def _freeze(value: Any) -> Any:
    """Lossless hashable form for concrete stores and action arguments."""

    if isinstance(value, dict):
        return tuple(sorted((str(k), _freeze(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, set):
        return tuple(sorted((_freeze(v) for v in value), key=repr))
    if isinstance(value, float) and value.is_integer():
        return int(value)
    try:
        hash(value)
    except TypeError:
        return repr(value)
    return value


def _actions(actions: Iterable) -> tuple:
    """Observable action sequence: order, duplicates, arguments, and target."""

    out = []
    for action in actions:
        try:
            out.append((
                str(action.service),
                str(action.method),
                _freeze(tuple(action.args)),
                _freeze(tuple(action.target)),
            ))
        except Exception as exc:
            raise Unsupported(
                f"exact oracle cannot canonicalize action {action!r}: {exc}")
    return tuple(out)


def _input_combinations(domains: dict[str, list], maximum: int) -> list[dict]:
    keys = sorted(domains)
    for key in keys:
        if not domains[key]:
            raise ValueError(f"empty input domain: {key}")
    count = math.prod(len(domains[key]) for key in keys)
    if count > maximum:
        raise _InputSpaceTooLarge(
            f"input combinations {count} exceed cap {maximum}")
    if not keys:
        return [{}]
    return [dict(zip(keys, values))
            for values in itertools.product(*(domains[k] for k in keys))]


def _initial_gv_stores(domains: dict[str, list] | None) -> list[dict]:
    """Enumerate initial persistent-variable stores; ``None`` means absent."""

    if not domains:
        return [{}]
    keys = sorted(domains)
    for key in keys:
        if not domains[key]:
            raise ValueError(f"empty initial GV domain: {key}")
    stores = []
    for values in itertools.product(*(domains[k] for k in keys)):
        stores.append({k: v for k, v in zip(keys, values) if v is not None})
    return stores


def exact_tick_product(
    runner_a,
    runner_b,
    *,
    period_ms: int,
    input_domains: dict[str, list],
    horizon_ticks: int,
    initial_gv_domains: dict[str, list] | None = None,
    t0_ms: int = T0_DEFAULT,
    max_states: int = 1_000_000,
    max_transitions: int = 5_000_000,
    max_input_combinations: int = 100_000,
) -> ExactTickResult:
    """Execute every modeled input sequence for exactly ``horizon_ticks``.

    Input names prefixed by ``@gv:`` are external persistent-variable inputs;
    all other names are sensor/environment inputs.  Equal concrete product
    states at the same depth are merged losslessly.  No cross-depth or
    abstract-state merging is performed.
    """

    if period_ms <= 0:
        raise ValueError("period_ms must be positive")
    if horizon_ticks <= 0:
        raise ValueError("horizon_ticks must be positive")
    if max_states <= 0 or max_transitions <= 0:
        raise ValueError("resource caps must be positive")

    started = time.perf_counter()
    try:
        combos = _input_combinations(input_domains, max_input_combinations)
    except _InputSpaceTooLarge as exc:
        return ExactTickResult(
            verdict="INCOMPLETE",
            horizon_ticks=horizon_ticks,
            n_input_combinations=0,
            seconds=time.perf_counter() - started,
            notes=[str(exc)],
        )
    gv_stores = _initial_gv_stores(initial_gv_domains)
    external_gv = {k[4:] for k in input_domains if k.startswith("@gv:")}
    result = ExactTickResult(
        verdict="EQUIV_BOUNDED",
        horizon_ticks=horizon_ticks,
        n_input_combinations=len(combos),
    )

    def split(inputs: dict) -> tuple[dict, dict]:
        return (
            {k: v for k, v in inputs.items() if not k.startswith("@gv:")},
            {k[4:]: v for k, v in inputs.items() if k.startswith("@gv:")},
        )

    def owned(gv: dict) -> dict:
        return {k: v for k, v in gv.items() if k not in external_gv}

    def node_key(node: _Node) -> tuple:
        return (_freeze(node.av), _freeze(node.ag),
                _freeze(node.bv), _freeze(node.bg))

    def stop_incomplete(note: str, completed_ticks: int) -> ExactTickResult:
        result.verdict = "INCOMPLETE"
        result.completed_ticks = completed_ticks
        result.notes.append(note)
        result.seconds = time.perf_counter() - started
        return result

    frontier: dict[tuple, _Node] = {}
    now = t0_ms
    for inputs in combos:
        world, external = split(inputs)
        for gv0 in gv_stores:
            if result.n_transitions >= max_transitions:
                return stop_incomplete("transition cap reached", 0)
            ra = runner_a.step({}, {**gv0, **external}, world, now,
                               first_tick=True)
            rb = runner_b.step({}, {**gv0, **external}, world, now,
                               first_tick=True)
            result.n_transitions += 1
            oa, ob = _actions(ra.actions), _actions(rb.actions)
            if oa != ob or ra.terminated != rb.terminated:
                result.verdict = "DIVERGE"
                result.divergence = ExactDivergence(
                    0, dict(inputs), oa, ob, ra.terminated, rb.terminated,
                    (dict(inputs),),
                )
                result.completed_ticks = 1
                result.seconds = time.perf_counter() - started
                return result
            if not ra.terminated:
                node = _Node(ra.vars, owned(ra.gv), rb.vars, owned(rb.gv),
                             (dict(inputs),))
                frontier.setdefault(node_key(node), node)

    result.n_states = len(frontier)
    result.max_frontier = len(frontier)
    if result.n_states > max_states:
        return stop_incomplete("state cap reached", 1)
    result.completed_ticks = 1

    for tick in range(1, horizon_ticks):
        now = t0_ms + tick * period_ms
        next_frontier: dict[tuple, _Node] = {}
        for node in frontier.values():
            for inputs in combos:
                if result.n_transitions >= max_transitions:
                    return stop_incomplete("transition cap reached", tick)
                world, external = split(inputs)
                ra = runner_a.step(node.av, {**node.ag, **external}, world, now)
                rb = runner_b.step(node.bv, {**node.bg, **external}, world, now)
                result.n_transitions += 1
                oa, ob = _actions(ra.actions), _actions(rb.actions)
                path = node.path + (dict(inputs),)
                if oa != ob or ra.terminated != rb.terminated:
                    result.verdict = "DIVERGE"
                    result.divergence = ExactDivergence(
                        tick, dict(inputs), oa, ob,
                        ra.terminated, rb.terminated, path,
                    )
                    result.completed_ticks = tick + 1
                    result.seconds = time.perf_counter() - started
                    return result
                if not ra.terminated:
                    nxt = _Node(ra.vars, owned(ra.gv), rb.vars, owned(rb.gv),
                                path)
                    next_frontier.setdefault(node_key(nxt), nxt)
        frontier = next_frontier
        result.n_states += len(frontier)
        result.max_frontier = max(result.max_frontier, len(frontier))
        result.completed_ticks = tick + 1
        if result.n_states > max_states:
            return stop_incomplete("state cap reached", tick + 1)
        if not frontier:
            # Every execution terminated identically, so later ticks cannot
            # add behavior and the declared horizon is complete.
            result.completed_ticks = horizon_ticks
            break

    result.seconds = time.perf_counter() - started
    return result
