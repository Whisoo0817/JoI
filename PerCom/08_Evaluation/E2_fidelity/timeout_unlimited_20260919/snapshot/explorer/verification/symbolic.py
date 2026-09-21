"""Universal value-flow certificates for sequential catalog-backed programs.

This is a domain-enumeration fallback, not a sampler that returns EQUIV.
The existing interpreters execute typed symbolic inputs. Only equal normal
forms certify equality; unequal forms need an ordinary concrete replay.
"""
from dataclasses import asdict
import time

from explorer.runtime import expr as e, joi_parser as jp
from explorer.verification.input_coverage import merged_coverage, unique
from explorer.runtime.interp import Unsupported
from explorer.runtime.ir_step import IrRunner
from explorer.verification.observation import actions_observation
from explorer.runtime.oneshot import OneShotRunner
from explorer.verification.product import ProductResult, Divergence, check_supported_pair, replay_divergence
from explorer.runtime.runner import TerminalRunner
from explorer.verification.symbolic_values import InputSymbol


def symbolic_input_cap_fallback(runner_a, runner_b, domains, *,
                                max_input_combinations=100_000,
                                max_transitions=2_000_000):
    """Select full-catalog symbolism only for eligible automatic input domains.

    Callers must preserve explicit finite-domain scope and explicit initial GVs.
    Selection is not certification; symbolic_product still checks terms/caps/replay.
    """
    import math
    count = math.prod(len(values) for values in domains.values())
    return (count > min(max_input_combinations, max_transitions)
            and symbolic_specs(runner_a, runner_b) is not None)


def _joi_expr(node):
    if isinstance(node, (e.Lit, e.VarRef, e.DeviceRef)):
        return True
    if isinstance(node, jp.CallExpr):
        return node.args is None or all(isinstance(a, e.Lit) for a in node.args)
    return (isinstance(node, e.BinaryOp) and node.op == '+'
            and _joi_expr(node.left) and _joi_expr(node.right))


def _ir_expr(node):
    if node[0] in ('lit', 'var', 'read'):
        return True
    if node[0] == 'expr':
        return _ir_expr(node[1])
    if node[0] == 'tmpl':
        return all(isinstance(p, str) or _ir_expr(p) for p in node[1])
    return (node[0] == 'bin' and node[1] == '+'
            and _ir_expr(node[2]) and _ir_expr(node[3]))


def symbolic_specs(runner_a, runner_b):
    """Return a certificate precondition, or None to keep the existing path."""
    from explorer.verification.timed import unwrap, reads_clock
    a, b = unwrap(runner_a), unwrap(runner_b)
    model = getattr(runner_a, 'catalog_model', None)
    if model is None or model is not getattr(runner_b, 'catalog_model', None):
        return None
    if not isinstance(a, IrRunner) or not isinstance(b, OneShotRunner):
        return None
    if reads_clock(runner_a) or reads_clock(runner_b):
        return None
    for x in a.prog.ins:
        if x.kind not in ('READ', 'CALL', 'DELAY', 'END'):
            return None
        if x.kind == 'CALL' and (not all(_ir_expr(arg) for arg in x.args)
                or (x.var and not all(arg[0] == 'lit' for arg in x.args))):
            return None
    for stmt in b.stmts:
        if isinstance(stmt, jp.Assign):
            if not _joi_expr(stmt.rhs):
                return None
        elif isinstance(stmt, jp.CallStmt):
            if not all(_joi_expr(arg) for arg in stmt.call.args or ()):
                return None
        elif not isinstance(stmt, jp.Delay):
            return None
    coverage = merged_coverage(runner_a.axes.coverage, runner_b.axes.coverage)
    if coverage.writes or any(k.startswith(('@gv:', 'clock.')) for k in coverage.predicates):
        return None
    specs = {k: model.input_spec(k) for k in coverage.predicates}
    # BOOLs retain their existing cheap concrete two-value model. A future mixed
    # symbolic/concrete BFS must explicitly branch over those control axes.
    if not specs or any(s is None or s.get('type') not in ('STRING', 'INTEGER', 'DOUBLE', 'ENUM')
                        for s in specs.values()):
        return None
    # This does not assert that None is the full domain. It only discharges the
    # existing syntactic/D7 checks; universal domains are represented by symbols.
    check_supported_pair(runner_a, runner_b, input_domains={k: [None] for k in specs})
    return specs


def witness_values(spec):
    """Small concrete candidates for finding differences, NEVER proving equality."""
    from explorer.verification.service_model import ServiceModel
    from explorer.verification.input_model import validate_domains
    if spec.get('members') is not None:
        values = list(spec['members'])
    elif spec['type'] == 'STRING':
        values = ['', 'a', 'b', '1', 'None', '메뉴', '\0']
    else:
        from fractions import Fraction
        import math
        scale = 10 if spec['type'] == 'DOUBLE' else 1
        bound = spec.get('bound')
        values = [0, 1, -1]
        if scale == 10:
            values += [0.0, -0.0, 1.0, -1.0, 0.1, -0.1]
        if bound:
            lo = math.ceil(Fraction(str(bound[0])) * scale)
            hi = math.floor(Fraction(str(bound[1])) * scale)
            values += [(n / 10 if scale == 10 else n) for n in (lo, lo + 1, hi - 1, hi)]
    valid = []
    for value in unique(values + [None]):
        try:
            ServiceModel.validate_value(value, spec, 'symbolic witness')
            validate_domains({'witness': [value]})
            valid.append(value)
        except (Unsupported, ValueError):
            pass
    return valid


def _witness(runner_a, runner_b, history, specs, result, max_attempts, max_transitions, t0_ms):
    symbols = sorted({v for world, _ in history for v in world.values()},
                     key=lambda s: (s.epoch, s.key))
    candidates = {s: witness_values(specs[s.key]) for s in symbols}
    base = {s: values[0] for s, values in candidates.items()}

    def valuations():
        yield base
        for symbol in symbols:
            for value in candidates[symbol][1:]:
                yield {**base, symbol: value}
        yield {s: None if None in candidates[s] else base[s] for s in symbols}

    for attempt, valuation in enumerate(valuations()):
        if attempt >= max_attempts or result.n_steps // 2 + len(history) > max_transitions:
            result.notes.append('symbolic counterexample search cap reached')
            break
        concrete = [({k: valuation[v] for k, v in world.items()}, dwell)
                    for world, dwell in history]
        av, ag, bv, bg, now = {}, {}, {}, {}, t0_ms
        a, b = TerminalRunner(runner_a), TerminalRunner(runner_b)
        try:
            for index, (world, dwell) in enumerate(concrete):
                now += dwell
                ra = a.step(av, ag, world, now, first_tick=index == 0)
                rb = b.step(bv, bg, world, now, first_tick=index == 0)
                result.n_steps += 2
                oa, ob = actions_observation(ra.actions), actions_observation(rb.actions)
                if oa != ob:
                    divergence = Divergence(index, world, dwell, oa, ob,
                                            concrete[:index], {}, t0_ms, result.input_step_ms)
                    if replay_divergence(runner_a, runner_b, divergence).confirmed:
                        result.divergences.append(divergence)
                        result.verdict = 'DIVERGE'
                        return
                av, ag, bv, bg = ra.vars, ra.gv, rb.vars, rb.gv
        except (Unsupported, TypeError, ArithmeticError):
            # An invalid ACTION is not an executable counterexample.
            continue
    result.verdict, result.closed = 'UNKNOWN', False
    result.notes.append('unequal symbolic terms; no concrete counterexample certified')


def symbolic_product(runner_a, runner_b, *, horizon_ms, input_step_ms, t0_ms,
                     max_states, max_transitions, max_input_combinations):
    """None means not applicable; returned EQUIV always has a universal certificate."""
    from explorer.verification.timed import next_time
    specs = symbolic_specs(runner_a, runner_b)
    if specs is None:
        return None
    started = time.perf_counter()
    result = ProductResult('EQUIV', bounded_horizon_ms=horizon_ms,
                           input_step_ms=input_step_ms)
    result.symbolic_certificate = {
        'schema': 'symbolic-value-flow-v1',
        'basis': 'universal catalog inputs, not sampled representatives',
        'input_specs': specs, 'events': [], 't0_ms': t0_ms,
        'proof_scope': 'sequential one-shot copies/text/fixed delays; D7 enforced',
    }
    result.notes.append('symbolic-value-flow-v1: structural term equality under every input valuation')
    a, b = TerminalRunner(runner_a), TerminalRunner(runner_b)
    av, ag, bv, bg, now, dwell, history = {}, {}, {}, {}, t0_ms, 0, []
    while True:
        if len(history) >= max_states or result.n_steps // 2 >= max_transitions:
            result.verdict, result.closed = 'UNKNOWN', False
            result.notes.append('symbolic state/transition cap reached')
            break
        epoch = (now - t0_ms) // input_step_ms
        world = {k: InputSymbol(k, epoch, s['type'], s.get('nullable', True)) for k, s in specs.items()}
        ra = a.step(av, ag, world, now, first_tick=not history)
        rb = b.step(bv, bg, world, now, first_tick=not history)
        result.n_steps += 2
        history.append((world, dwell))
        result.n_states = len(history)
        oa, ob = actions_observation(ra.actions), actions_observation(rb.actions)
        result.symbolic_certificate['events'].append({
            'offset_ms': now - t0_ms, 'ir': oa, 'code': ob, 'equal': oa == ob})
        if oa != ob:
            _witness(runner_a, runner_b, history, specs, result,
                     max_input_combinations, max_transitions, t0_ms)
            break
        if ra.terminated and rb.terminated:
            result.symbolic_certificate['both_terminated'] = True
            break
        av, ag, bv, bg = ra.vars, ra.gv, rb.vars, rb.gv
        nxt = next_time(a, b, av, bv, now, t0_ms, input_step_ms)
        if nxt is None or (horizon_ms is not None and nxt > t0_ms + horizon_ms):
            result.symbolic_certificate['both_terminated'] = False
            break
        dwell, now = nxt - now, nxt
    result.seconds = time.perf_counter() - started
    # Make the certificate a plain JSON-compatible record, not live terms.
    result.symbolic_certificate = asdict(result)['symbolic_certificate']
    return result
