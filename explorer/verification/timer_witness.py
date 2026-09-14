"""Boundary-directed witness search. Only original-runner replay grants DIVERGE.

Held-input self loops use exact affine translations and their branch DBM to
visit the last two feasible iterations without enumerating the waiting ticks.
This search is incomplete and is never used to certify EQUIV.
"""
from collections import deque
import math
import time

from explorer.runtime.interp import Unsupported
from explorer.verification.timer_domain import Zone, Number, Split, reaction, INF
from explorer.verification.state_key import freeze_state as freeze
from explorer.verification.observation import actions_observation
from explorer.verification.product import Divergence, replay_divergence

LAST_STATS = {}


def calendar_witness(originals, history, combos, step, t0):
    """Schedule an abstract Hour skeleton on an actual forward calendar."""
    from explorer.runtime.interp import clock_state
    for idle in combos[:2]:
        idle = {k:v for k,v in idle.items() if not k.startswith('clock.')}
        trace, now = [(idle, 0)], t0
        for world in history:
            hour = world.get('clock.hour', clock_state(now)['clock.hour'])
            end = now + step
            if clock_state(end)['clock.hour'] != hour:
                end = (end // 86400000) * 86400000 + hour * 3600000
                if end <= now: end += 86400000
                end = t0 + ((end-t0+step-1)//step)*step
            trace.append(({k:v for k,v in world.items() if not k.startswith('clock.')}, end-now))
            now = end
        if now-t0 > 86400000: continue
        world, dwell = trace.pop()
        dv = Divergence(len(trace), world, dwell, (), (), trace, {}, t0, step)
        if replay_divergence(*originals, dv).confirmed: return dv
    return None


def snapshot_witness(originals, combos, plan, step, t0, max_nodes=500):
    """Budgeted event candidates for elapsed snapshots; full replay is mandatory.

    Skipping intermediate reactions here is only a candidate-generation heuristic.
    A candidate may be spurious and must never be used as a proof state.
    """
    from explorer.runtime.runner import TerminalRunner
    a,b = map(TerminalRunner, originals)
    queue = deque([({}, {}, t0, [])])
    seen = set()
    constants = sorted({abs(v) for v in plan.thresholds if v > 1})
    started = time.perf_counter()
    while queue and len(seen) < max_nodes and time.perf_counter()-started < 10:
        av,bv,now,history = queue.popleft()
        deltas = {step} if history else {0}
        if history:
            for side, values in enumerate((av,bv)):
                for name in plan.snapshots[side]:
                    saved = values.get(name)
                    if saved is None: continue
                    for c in constants:
                        boundary = int((saved+c)*1000)
                        for shift in (-step,0,step):
                            end = t0+((boundary+shift-t0+step-1)//step)*step
                            if now < end <= now+86400000: deltas.add(end-now)
        for dwell in sorted(deltas):
            for world in combos:
                ra=a.step(av,{},world,now+dwell,first_tick=not history)
                rb=b.step(bv,{},world,now+dwell,first_tick=not history)
                oa,ob=actions_observation(ra.actions),actions_observation(rb.actions)
                if oa != ob:
                    dv=Divergence(len(history),world,dwell,oa,ob,history,{},t0,step)
                    if replay_divergence(*originals,dv).confirmed: return dv
                    continue
                values=[]
                for side, store in enumerate((ra.vars,rb.vars)):
                    out=dict(store)
                    for name in plan.snapshots[side]:
                        if out.get(name) is not None:
                            age=(now+dwell)//1000-out[name]
                            out[name]=tuple((age<c,age==c) for c in constants)
                    for name in plan.aliases: out.pop(name,None)
                    from explorer.verification.timed import internal_timers
                    for name in internal_timers(originals[side]):
                        if out.get(name) is not None: out[name]=(now+dwell)-out[name]*1000
                    values.append(out)
                key=freeze(values)
                if key not in seen:
                    seen.add(key)
                    queue.append((ra.vars,rb.vars,now+dwell,history+[(world,dwell)]))
    return None


def boundary_witness(a, b, originals, combos, plan, stores, materialize,
                     step, t0, max_nodes=2000, budget=15):
    if plan.hours or any(plan.snapshots): return None
    started = time.perf_counter()
    LAST_STATS.clear()
    LAST_STATS.update(expanded=0, jumps=0, candidates=0)
    queue = deque([({}, {}, Zone(), [])])
    seen = set()

    def append(history, world, dwell):
        history = list(history)
        if len(history) > 1 and history[-1][0] == world and history[-2][0] == world:
            history[-1] = (world, history[-1][1] + dwell)
        else: history.append((world, dwell))
        return history

    def point_values(z):
        if any(z.d[i][0] != -z.d[0][i] for i in range(len(z.names))):
            raise Unsupported('witness state is not a point')
        return [z.d[i][0] for i in range(len(z.names))]

    def enqueue(av, bv, point, history):
        # Only a search heuristic: keep concrete boundary states; no proof merge.
        key = freeze((av, bv, point.names, point.d))
        if key not in seen and len(seen) < max_nodes:
            seen.add(key)
            queue.append((av, bv, point, history))

    while queue and time.perf_counter() - started < budget:
        av, bv, point, history = queue.popleft()
        LAST_STATS['expanded'] += 1
        now = step if history else 0
        for world in combos:
            region = Zone(point.names[1:])
            while True:
                try:
                    with reaction(region) as ctx:
                        ra = a.step(materialize(av, 0), {}, world, now, first_tick=not history)
                        rb = b.step(materialize(bv, 1), {}, world, now, first_tick=not history)
                        oa, ob = actions_observation(ra.actions), actions_observation(rb.actions)
                        (nav, nbv), after = stores(ra.vars, rb.vars, point, now)
                    region = ctx[0]
                    break
                except Split as split:
                    region = next((z for z in split.zones if z.covers(point)), None)
                    if region is None: raise Unsupported('witness branch lost concrete point')
            if oa != ob:
                LAST_STATS['candidates'] += 1
                dv = Divergence(len(history), world, step if history else 0,
                                oa, ob, history, {}, t0, step)
                if replay_divergence(*originals, dv).confirmed: return dv
                continue
            if ra.terminated and rb.terminated: continue
            enqueue(nav, nbv, after, append(history, world, step if history else 0))
            if not history or freeze((av, bv)) != freeze((nav, nbv)) or point.names != after.names:
                continue
            p, q = point_values(point), point_values(after)
            delta = [y-x for x, y in zip(p, q)]
            if not any(delta): continue
            for i, k in enumerate(point.names):
                if i and delta[i] == 0:
                    term = Number({k: 1}, -p[i])
                    region = region.constrain(term).constrain(-term)
            # Check that the symbolic image is a translation, not merely that
            # two concrete points happened to have this difference.
            (_, _), image = stores(ra.vars, rb.vars, region, now)
            translated = region.image({k: Number({k: 1}, delta[i])
                                       for i, k in enumerate(point.names) if i})
            if image.canonical().d != translated.canonical().d: continue
            last = INF
            for i, row in enumerate(region.d):
                for j, bound in enumerate(row):
                    slope = delta[i] - delta[j]
                    if slope > 0 and bound != INF:
                        last = min(last, (bound - p[i] + p[j]) // slope + 1)
            if last == INF or last < 2: continue
            for count in {int(last)-1, int(last)}:
                if count < 2: continue
                LAST_STATS['jumps'] += 1
                advanced = Zone().image({k: Number(constant=p[i]+count*delta[i])
                                         for i, k in enumerate(point.names) if i})
                # The new world takes effect on the FIRST tick of the run.
                extended = append(history, world, step)
                extended = append(extended, world, (count-1)*step)
                enqueue(nav, nbv, advanced, extended)
    return None
