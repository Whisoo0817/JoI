"""Execution-position evidence for silent time elision.

Only the concrete, known runner implementations are recognized. A fixed sleep
cannot inspect inputs before its deadline. A plain wait is silent under a held
input, but NOT under arbitrary changing inputs. Keep those two facts separate.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Suspension:
    kind: str
    deadline: int | None = None

    @property
    def input_blind(self):
        return self.kind in ('terminated', 'delay', 'period')


def suspension(runner, values, now):
    from explorer.runtime.ir_step import IrRunner
    from explorer.runtime.oneshot import OneShotRunner
    from explorer.runtime.pause import PauseRunner
    from explorer.runtime.runner import TerminalRunner, DoneLatch
    from explorer.verification.service_model import CatalogRunner
    from explorer.runtime import joi_parser as jp
    while hasattr(runner, 'inner'):
        # A user wrapper can execute extra code even when its inner sleeps.
        # Recognize only the three wrappers whose step semantics we inspected.
        if type(runner) not in (TerminalRunner, DoneLatch, CatalogRunner):
            return None
        if type(runner) is TerminalRunner and values.get(runner.key):
            return Suspension('terminated')
        if type(runner) is DoneLatch and values.get('__fin'):
            return Suspension('terminated')
        runner = runner.inner
    if type(runner) is IrRunner:
        if values.get('done'): return Suspension('terminated')
        pc = int(values.get('pc', 0))
        ins = runner.prog.ins[pc]
        if ins.kind == 'DELAY' and values.get(f'd{pc}') is not None:
            due = round(values[f'd{pc}'] * 1000) + round(ins.for_sec * 1000)
            return Suspension('delay', due) if due > now else None
        if ins.kind == 'TOP' and values.get(f'c{ins.idx}') is not None:
            due = round(values[f'c{ins.idx}'] * 1000) + round(ins.period * 1000)
            return Suspension('period', due) if due > now else None
        if ins.kind == 'WAIT':
            # Under an unchanged, clock-free input a completed WAIT reaction
            # leaves its edge memory/start registers stationary until one of
            # these deadlines. Under changing inputs it remains fully reactive.
            deadlines = [round(values[reg] * 1000) + round(duration * 1000)
                         for reg, duration in ((f's{pc}', ins.for_sec), (f't{pc}', ins.to_sec))
                         if duration and values.get(reg) is not None]
            if any(d <= now for d in deadlines): return None
            return Suspension('wait', min(deadlines) if deadlines else None)
    elif type(runner) is OneShotRunner:
        if values.get('__done'): return Suspension('terminated')
        seg = int(values.get('__seg', 0))
        if seg < len(runner.segs):
            kind, payload = runner.segs[seg]
            if kind == 'delay' and values.get('__dstart') is not None:
                due = round(values['__dstart'] * 1000) + payload
                return Suspension('delay', due) if due > now else None
            if kind == 'wait': return Suspension('wait')
    elif type(runner) is PauseRunner:
        if values.get('__done'): return Suspension('terminated')
        if values.get('__next_run') is not None:
            due = round(values['__next_run'] * 1000)
            return Suspension('period', due) if due > now else None
        path, statements = values.get('__path') or (), runner.stmts
        statement = None
        for index, branch in path:
            statement = statements[index]
            if branch >= 0:
                statements = statement.then_body if branch == 0 else statement.else_body
        if isinstance(statement, jp.Delay) and values.get('__dstart') is not None:
            due = round(values['__dstart'] * 1000) + statement.ms
            return Suspension('delay', due) if due > now else None
        if isinstance(statement, jp.WaitUntil): return Suspension('wait')
    return None


def silent_deadline(a, b, av, bv, now, *, held_waits=False):
    """Earliest mandatory event, or None if silence has not been established.

    held_waits is only for a concrete witness whose world is held constant. Its
    caller must exclude clock reads and use a state after a reaction to that world.
It must never prune the universal BFS's input branches.
"""
    states = [suspension(r, v, now) for r, v in ((a, av), (b, bv))]
    if any(s is None or not (s.input_blind or held_waits and s.kind == 'wait') for s in states):
        return None
    deadlines = [s.deadline for s in states if s.deadline is not None]
    return min(deadlines) if deadlines else None


def crossed_input_grid(before, after, t0, step):
    return (after - t0) // step > (before - t0) // step


def grid_history(history, t0, step):
    """Place an endpoint's latest input on the last crossed grid, if off-grid.

Search elides only unobservable earlier inputs. This builds a legal concrete
representative; replay still executes intervening mandatory events itself.
"""
    result, now = [], t0
    for world, dwell in history:
        end = now + dwell
        grid = t0 + ((end - t0) // step) * step
        if now < grid < end:
            result.append((world, grid - now))
            result.append((world, end - grid))
        else:
            result.append((world, dwell))
        now = end
    return result
