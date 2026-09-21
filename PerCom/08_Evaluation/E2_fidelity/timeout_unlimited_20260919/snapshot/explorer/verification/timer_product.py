"""Inductive, overapproximating timer-zone product on an exact input grid.

No abstract mismatch is a counterexample. Widened nodes are re-expanded;
only a closed post-fixpoint can certify unbounded ACTION equivalence.
"""
from collections import deque
from fractions import Fraction
import itertools
import math
import time

from explorer.runtime.interp import Unsupported
from explorer.runtime.runner import TerminalRunner
from explorer.verification.observation import actions_observation
from explorer.verification.product import ProductResult, Divergence, replay_divergence
from explorer.verification.state_key import freeze_state as freeze
from explorer.verification.symbolic_values import SymbolicValue
from explorer.verification.timer_analysis import analyze
from explorer.verification.timer_domain import Number, Zone, Split, reaction, INF
from explorer.analysis.predicates import walk_stmts


def timer_product(a, b, *, domains, axes, input_step_ms, t0_ms,
                  max_states, max_transitions, max_input_combinations):
    step = input_step_ms
    plan = analyze(a, b, step)
    if (plan.hours or any(plan.snapshots)) and (1000 % step or t0_ms % step):
        raise Unsupported('clock-zone events must align with the input grid')
    if axes.coverage.errors or axes.coverage.writes or axes.param_reads or axes.mirror_gv:
        raise Unsupported('timer zones do not admit queries/GVs/coverage errors')
    if any(k.startswith(('@gv:', 'clock.')) for k in domains):
        raise Unsupported('timer zones do not admit external clock/GV overrides')
    if math.prod(map(len, domains.values())) > max_input_combinations:
        raise Unsupported('timer input combination cap')
    from explorer.verification.timed import internal_timers, unwrap
    from explorer.verification.relational_analysis import entry_live
    live = entry_live(unwrap(b).stmts)
    locals_ = {s.name for s in walk_stmts(unwrap(b).stmts)
               if hasattr(s, 'name')}
    timers = (internal_timers(a), internal_timers(b))
    original_a, original_b = a, b
    a, b = TerminalRunner(a), TerminalRunner(b)
    combos = [dict(zip(domains, vals)) for vals in itertools.product(*domains.values())]
    if plan.hours:
        if len(combos) * 24 > max_input_combinations:
            raise Unsupported('calendar input combination cap')
        combos = [{**world, 'clock.hour': h} for world in combos for h in range(24)]
    started = time.perf_counter()
    result = ProductResult('UNKNOWN', closed=False, input_step_ms=step)
    result.notes.append('timer-zones-v2: integer difference bounds; widening with rechecked successors')
    result.symbolic_certificate = cert = {
        'schema': 'timer-zones-v2', 'complete': False, 'counters': plan.counters,
        'dead_clock_reads': sorted(plan.dead), 'input_step_ms': step,
        'thresholds': plan.thresholds, 'widenings': 0, 'reactions': 0,
        'calendar': 'arbitrary shared Hour at each reaction (overapproximation)' if plan.hours else None,
        'snapshots': plan.snapshots,
        'timestamp_progress': 'shared floor/ceil seconds per grid step (overapproximation)',
        'time_model': 'all deadlines on input grid; exact one-grid-step reactions',
    }
    pending, nodes = deque(), {}

    def finish(reason, success=False):
        result.seconds = time.perf_counter() - started
        result.notes.append(reason)
        if success:
            result.verdict, result.closed, cert['complete'] = 'EQUIV', True, True
            cert['states'] = [{'key': repr(key), 'names': node[2].names,
                               'bounds': [[None if v == INF else v for v in row] for row in node[2].d]}
                              for key, node in nodes.items()]
        return result

    def stores(av, bv, zone, now, stamp=0):
        concrete, expressions = [], {}
        for side, values in enumerate((av, bv)):
            values = dict(values)
            if side == 0:
                for name in plan.dead: values.pop(name, None)
            elif values.get('__next_run') is not None:
                for name in locals_ - live - set(plan.counters): values.pop(name, None)
            out = {}
            for name, value in values.items():
                selected = name in timers[side] or name in plan.snapshots[side] or side == 1 and name in plan.counters
                if selected and value is not None:
                    term = Number.of(value)
                    if name in timers[side]: term = (now - term * 1000) / step
                    elif name in plan.snapshots[side]: term = stamp - term
                    ident = f'{side}:{name}'
                    expressions[ident] = term
                    out[name] = ('timer-slot', ident)
                else:
                    if isinstance(value, SymbolicValue):
                        raise Unsupported('symbolic timer escapes selected storage')
                    out[name] = value
            concrete.append(out)
        return concrete, zone.image(expressions)

    def materialize(values, side):
        out = {}
        for name, value in values.items():
            if isinstance(value, tuple) and len(value) == 2 and value[0] == 'timer-slot':
                term = Number({value[1]: 1})
                # The previous reaction's time is rebased to zero.
                out[name] = (-term * Fraction(step, 1000) if name in timers[side]
                             else -term if name in plan.snapshots[side] else term)
            else: out[name] = value
        return out

    def admit(ra, rb, zone, now, history, stamp=0):
        if ra.gv or rb.gv: raise Unsupported('timer zone reaction wrote a GV')
        if ra.terminated and rb.terminated: return
        (av, bv), projected = stores(ra.vars, rb.vars, zone, now, stamp)
        key = freeze((av, bv))
        if key not in nodes:
            if len(nodes) >= max_states: raise Unsupported('timer zone state cap')
            nodes[key] = [av, bv, projected, history]
            pending.append(key)
            result.n_states = len(nodes)
        else:
            previous = nodes[key][2]
            if not previous.covers(projected):
                nodes[key][2] = previous.widen(projected, plan.thresholds)
                # Keep the incoming skeleton that exposed the new relation.
                # This affects witness candidates only, never the proof zone.
                nodes[key][3] = history
                cert['widenings'] += 1
                if key not in pending: pending.append(key)

    def concrete_witness(history):
        """Try boundary-length repetitions of the abstract input skeleton.

        This is only a bounded bug-finding heuristic. Every candidate executes
        original runners at EVERY grid point, and is independently replayed.
        """
        if not history: return None
        if plan.hours: return None  # Synthetic calendar paths are not concrete witnesses.
        history = [{k: v for k, v in world.items() if not k.startswith('clock.')}
                   for world in history]
        # Runs of identical worlds identify places to extend a held input.
        runs = []
        for world in history:
            if runs and runs[-1][0] == world: runs[-1][1] += 1
            else: runs.append([world, 1])
        trials = [(None, 0)] + [(i, ticks) for i in range(len(runs))
                                for ticks in plan.witness_ticks]
        for index, ticks in trials:
            av, bv, now, trace = {}, {}, t0_ms, []
            for i, (world, count) in enumerate(runs):
                for _ in range(count + (ticks if i == index else 0)):
                    if result.n_steps // 2 >= max_transitions:
                        return None
                    ra = a.step(av, {}, world, now, first_tick=not trace)
                    rb = b.step(bv, {}, world, now, first_tick=not trace)
                    result.n_steps += 2
                    oa, ob = actions_observation(ra.actions), actions_observation(rb.actions)
                    if oa != ob:
                        dv = Divergence(len(trace), world, step if trace else 0,
                                        oa, ob, trace, {}, t0_ms, step)
                        if replay_divergence(original_a, original_b, dv).confirmed:
                            return dv
                        return None
                    if len(trace) > 1 and trace[-1][0] == world and trace[-2][0] == world:
                        trace[-1] = (world, trace[-1][1] + step)
                    else:
                        trace.append((world, step if trace else 0))
                    av, bv, now = ra.vars, rb.vars, now + step
        return None

    def expand(av, bv, zone, world, now, history, stamp=0):
        if any(plan.snapshots): world = {**world, 'clock.timestamp': stamp}
        branches = [zone.canonical()]
        while branches:
            current = branches.pop()
            if current is None: continue
            if result.n_steps // 2 >= max_transitions: raise Unsupported('timer zone transition cap')
            result.n_steps += 2
            try:
                with reaction(current) as ctx:
                    ra = a.step(av, {}, world, now, first_tick=not history)
                    rb = b.step(bv, {}, world, now, first_tick=not history)
                    # An ACTION cannot contain any selected symbolic value.
                    def symbolic(v):
                        if isinstance(v, SymbolicValue): return True
                        if isinstance(v, (list, tuple)): return any(symbolic(x) for x in v)
                        return False
                    if any(symbolic(x.args) for x in ra.actions + rb.actions):
                        raise Unsupported('timer value escapes into ACTION')
                    mismatch = actions_observation(ra.actions) != actions_observation(rb.actions)
                    zone_after = ctx[0]
            except Split as split:
                branches.extend(split.zones)
                continue
            cert['reactions'] += 1
            if mismatch:
                from explorer.verification.timer_witness import boundary_witness, calendar_witness, snapshot_witness
                originals = (original_a, original_b)
                if plan.hours:
                    dv = calendar_witness(originals, history+[world], combos, step, t0_ms)
                elif any(plan.snapshots):
                    dv = snapshot_witness(originals, combos, plan, step, t0_ms,
                                          max_nodes=max_states)
                else:
                    dv = boundary_witness(a, b, originals, combos, plan,
                                          stores, materialize, step, t0_ms,
                                          max_nodes=max_states)
                if dv is not None:
                    result.verdict = 'DIVERGE'
                    result.divergences.append(dv)
                    return finish('boundary-directed timer witness replay confirmed')
                dv = concrete_witness(history + [world])
                if dv is not None:
                    result.verdict = 'DIVERGE'
                    result.divergences.append(dv)
                    return finish('timer-zone candidate concretely executed and replayed')
                return finish('abstract ACTION mismatch without confirmed concrete witness')
            admit(ra, rb, zone_after, now, history + [world], stamp)
        return None

    try:
        for world in combos:
            stopped = expand({}, {}, Zone(), world, 0, [], t0_ms // 1000)
            if stopped is not None: return stopped
        while pending:
            key = pending.popleft()
            av, bv, zone, history = nodes[key]
            for world in combos:
                advances = sorted({step // 1000, (step + 999) // 1000}) if any(plan.snapshots) else [0]
                for stamp in advances:
                    stopped = expand(materialize(av, 0), materialize(bv, 1), zone, world, step, history, stamp)
                    if stopped is not None: return stopped
    except Unsupported as exc:
        return finish(str(exc))
    return finish('all initial states and enlarged-zone successors covered; inductive fixpoint', True)
