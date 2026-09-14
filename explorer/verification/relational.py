"""Inductive relational graph closure for one periodic INTEGER counter pair.

Each node denotes ALL integer valuations of its shared slot. Every reaction
checks ordered ACTIONs and the post-relation before generalizing. Guard choices
are shared structurally within a reaction; forgetting them between reactions
is an overapproximation. No finite horizon is a success criterion.
"""
from collections import deque
from dataclasses import asdict
from pathlib import Path
import hashlib
import itertools
import math
import time

from explorer.runtime.interp import Unsupported
from explorer.verification.input_model import validate_domains
from explorer.verification.observation import actions_observation
from explorer.verification.product import ProductResult, Divergence, merge_axes
from explorer.runtime.runner import TerminalRunner
from explorer.verification.service_model import runner_input_domains
from explorer.verification.state_key import freeze_state as freeze
from explorer.verification.timed import internal_timers, next_time, unwrap
from explorer.verification.time_events import crossed_input_grid
from explorer.verification.relational_analysis import analyze, entry_live
from explorer.verification.relational_values import PairInt, RelValue, NeedBranch, reaction


def relational_product(runner_a, runner_b, **kwargs):
    from explorer.verification.observation import observation_scope
    with observation_scope(runner_a, runner_b):
        return _relational_product(runner_a, runner_b, **kwargs)


def _relational_product(runner_a, runner_b, *, input_domains=None, horizon_ms=None,
                       initial_gv_domains=None, input_step_ms=100, t0_ms=2_419_200_000,
                       max_states=400_000, max_transitions=2_000_000,
                       max_input_combinations=100_000, **unused):
    if horizon_ms is not None:
        raise Unsupported('relational mode requires explicit horizon_ms=None; bounded requests are not upgraded')
    if initial_gv_domains:
        raise Unsupported('relational v1 does not support initial/external GVs')
    if type(input_step_ms) is not int or input_step_ms <= 0 or type(t0_ms) is not int:
        raise ValueError('invalid relational input clock')
    if any(type(cap) is not int or cap <= 0 for cap in (max_states, max_transitions, max_input_combinations)):
        raise ValueError('relational caps must be positive integers')
    mapping = analyze(runner_a, runner_b)
    axes = merge_axes(runner_a.axes, runner_b.axes)
    if axes.coverage.errors or axes.param_reads or axes.coverage.writes:
        raise Unsupported('relational input coverage/query/GV obligations not met')
    if axes.observable_reads or axes.exact_reads:
        raise Unsupported('relational v1 admits external inputs only in direct guards')
    domains = runner_input_domains(runner_a, runner_b, input_domains)
    domains = axes.cells if domains is None else domains
    validate_domains(domains, required=axes.cells)
    if any(k.startswith('@gv:') for k in domains):
        raise Unsupported('relational external GV input unsupported')
    result = ProductResult('UNKNOWN', closed=False, input_step_ms=input_step_ms)
    started = time.perf_counter()
    cert = result.symbolic_certificate = {
        'schema': 'relational-state-v1', 'closure_kind': 'inductive-relational-graph',
        'complete': False, 'mapping': asdict(mapping), 'integer_domain': 'mathematical INTEGER',
        'initial_relation': [], 'events': [], 'states': [], 'input_domains': domains,
        'input_basis': 'explicit declared finite domain' if input_domains is not None else 'joint certified guard representatives',
        'time_model': {'input_step_ms': input_step_ms, 't0_ms': t0_ms, 'timer_unit_ms': 1,
                       'normalization': 'exact interpreter-owned timer ages and input phase'},
        'caps': dict(max_states=max_states, max_transitions=max_transitions,
                     max_input_combinations=max_input_combinations),
        'sources': {str(p.relative_to(Path(__file__).parents[1])): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(Path(__file__).parents[1].rglob('*.py'))},
        'fallback': 'none; failed structural obligations are inconclusive, not ACTION counterexamples',
    }
    model = getattr(runner_a, 'catalog_model', None)
    if model: cert['service_model'] = model.evidence()

    def finish(reason, success=False):
        result.notes.append(reason)
        result.seconds = time.perf_counter() - started
        if success:
            result.verdict, result.closed, cert['complete'] = 'EQUIV', True, True
        return result

    keys = sorted(domains)
    if math.prod(len(domains[k]) for k in keys) > max_input_combinations:
        return finish('input combination cap reached')
    combos = [dict(zip(keys, values)) for values in itertools.product(*(domains[k] for k in keys))]
    a, b = TerminalRunner(runner_a), TerminalRunner(runner_b)
    timers_a, timers_b = internal_timers(a), internal_timers(b)
    live_entry = entry_live(unwrap(b).stmts)
    queue, seen, nodes = deque(), {}, []
    attempts = 0

    def same(x, y): return freeze(x) == freeze(y)

    def normalize(ra, rb):
        av, bv = dict(ra.vars), dict(rb.vars)
        if mapping.ir_name not in av or mapping.code_name not in bv:
            raise Unsupported('relational initializer has not established both counters')
        va, vb = av[mapping.ir_name], bv[mapping.code_name]
        if not (type(va) is int or isinstance(va, PairInt)) or not same(va, vb):
            raise Unsupported('post-relation INTEGER equality not proved')
        # Exactly at the next-iteration boundary, values killed before every
        # future use are dead. At a paused PC every stored snapshot is retained.
        removed = []
        if bv.get('__next_run') is not None:
            for name in mapping.code_locals:
                if name != mapping.code_name and name not in live_entry and name in bv:
                    del bv[name]
                    removed.append(name)
        for values, selected in ((av, mapping.ir_name), (bv, mapping.code_name)):
            for name, value in list(values.items()):
                if name == selected: continue
                if isinstance(value, RelValue):
                    if isinstance(value, PairInt) and same(value, va):
                        values[name] = PairInt()
                    else:
                        # Reusing slot0 for current while leaving an old slot0
                        # snapshot would assert a false equality. Never do it.
                        raise Unsupported('live old snapshot/correlation outside relational v1')
            values[selected] = PairInt()
        return av, bv, removed

    def store(values, timers, now):
        return freeze({k: ('age-ms', now - round(v * 1000)) if k in timers and v is not None else v
                       for k, v in values.items()})

    def expand(av, bv, now, inputs, parent):
        nonlocal attempts
        branches = [{}]
        while branches:
            if attempts >= max_transitions:
                return finish('transition/branch execution cap reached')
            choices = branches.pop()
            attempts += 1
            cert['execution_attempts'] = attempts
            try:
                with reaction(choices) as ea:
                    ra = a.step(av, {}, inputs, now, first_tick=parent is None)
                with reaction(choices) as eb:
                    rb = b.step(bv, {}, inputs, now, first_tick=parent is None)
            except NeedBranch as branch:
                branches.extend([{**choices, branch.key: False}, {**choices, branch.key: True}])
                continue
            result.n_steps += 2
            oa, ob = freeze(actions_observation(ra.actions)), freeze(actions_observation(rb.actions))
            if oa != ob:
                # Only a first concrete reaction is itself a concrete witness.
                # Abstract paths are never reported as ACTION divergences.
                if parent is None:
                    result.verdict = 'DIVERGE'
                    result.divergences.append(Divergence(0, inputs, 0,
                        actions_observation(ra.actions), actions_observation(rb.actions), [], {}, t0_ms))
                return finish('ACTION equality obligation failed')
            if ra.gv or rb.gv:
                raise Unsupported('relational execution wrote a GV')
            def proof_observations(events, counter):
                from types import SimpleNamespace
                out, actions = [], []
                def flush():
                    if actions:
                        out.append(('actions', actions_observation(actions)))
                        actions.clear()
                for kind, name, value in events:
                    if kind == 'action':
                        service, method, target, fanout = name
                        actions.append(SimpleNamespace(service=service, method=method,
                            target=target, fanout=fanout, args=value))
                    elif kind in ('initialize', 'increment', 'assign') and name == counter:
                        flush()
                        out.append(('update', value))
                flush()
                return out
            updates_a = proof_observations(ea, mapping.ir_name)
            updates_b = proof_observations(eb, mapping.code_name)
            if updates_a != updates_b:
                return finish('ordered counter initialization/update obligations failed')
            if parent is None:
                cert['initial_relation'].append({'input': inputs,
                    'initialization_and_update_equal': True,
                    'post_ir': freeze(ra.vars.get(mapping.ir_name)),
                    'post_code': freeze(rb.vars.get(mapping.code_name))})
            nv_a, nv_b, removed = normalize(ra, rb)
            event = {'from': parent, 'input': inputs, 'choices': list(choices.items()),
                     'action_equal': True, 'actions': oa, 'post_equal': True,
                     'ordered_updates_equal': True,
                     'post_term': freeze(ra.vars[mapping.ir_name]),
                     'ir_observations': ea, 'code_observations': eb,
                     'dead_locals': removed,
                     'elapsed_ms': 0 if parent is None else now - nodes[parent][2]}
            cert['events'].append(event)
            key = (store(nv_a, timers_a, now), store(nv_b, timers_b, now),
                   (now - t0_ms) % input_step_ms, freeze(inputs))
            if key not in seen:
                if len(seen) >= max_states: return finish('state cap reached')
                seen[key] = len(nodes)
                nodes.append((nv_a, nv_b, now, dict(inputs)))
                cert['states'].append(key)
                queue.append(len(nodes)-1)
                result.n_states = len(nodes)
            event['to'] = seen[key]
        return None

    try:
        for inputs in combos:
            stop = expand({}, {}, t0_ms, inputs, None)
            if stop is not None: return stop
        while queue:
            parent = queue.popleft()
            av, bv, now, held = nodes[parent]
            following = next_time(a, b, av, bv, now, t0_ms, input_step_ms)
            if following is None: continue
            choices = combos if crossed_input_grid(now, following, t0_ms, input_step_ms) else [held]
            for inputs in choices:
                stop = expand(av, bv, following, inputs, parent)
                if stop is not None: return stop
    except Unsupported as error:
        return finish(str(error))
    return finish('initial relation, universal reaction obligations and finite graph closure verified', success=True)
