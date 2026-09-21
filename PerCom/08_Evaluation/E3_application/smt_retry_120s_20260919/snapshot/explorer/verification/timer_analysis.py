"""Fail-closed eligibility for synchronous integer timer zones."""
from dataclasses import dataclass
from fractions import Fraction

from explorer.runtime import expr as e, joi_parser as jp
from explorer.runtime.interp import Unsupported
from explorer.runtime.ir_step import IrRunner
from explorer.runtime.pause import PauseRunner
from explorer.runtime.oneshot import OneShotRunner
from explorer.runtime.runner import TerminalRunner, DoneLatch
from explorer.verification.service_model import CatalogRunner
from explorer.analysis.predicates import walk_stmts


def known_inner(runner):
    while type(runner) in (TerminalRunner, DoneLatch, CatalogRunner): runner = runner.inner
    if type(runner) not in (IrRunner, PauseRunner, OneShotRunner):
        raise Unsupported('timer zones require known IR/periodic runners and wrappers')
    return runner


def ir_refs(value):
    if isinstance(value, tuple):
        if value and value[0] == 'var': return {value[1]}
        return set().union(*(ir_refs(x) for x in value))
    if isinstance(value, list): return set().union(*(ir_refs(x) for x in value))
    return set()


def dead_clock_reads(ir):
    """Only globally unused, plain local READs; never queries or reserved slots."""
    used = set().union(*(ir_refs(x.cond) | ir_refs(x.args) for x in ir.prog.ins))
    reserved = {'pc', 'done'} | {x.cname for x in ir.prog.ins if x.cname}
    from explorer.verification.timed import internal_timers
    reserved |= internal_timers(ir)
    reserved |= {f'p{i}' for i in range(len(ir.prog.ins))}
    return {x.var for x in ir.prog.ins if x.kind == 'READ'
            and x.key.startswith('clock.') and x.var not in used | reserved
            and not x.var.startswith('__')}


@dataclass
class Plan:
    counters: tuple
    dead: set
    thresholds: tuple
    witness_ticks: tuple
    hours: bool = False
    snapshots: tuple = ((), ())
    aliases: tuple = ()


def analyze(a, b, step):
    ir, code = known_inner(a), known_inner(b)
    if type(ir) is not IrRunner or type(code) not in (PauseRunner, OneShotRunner):
        raise Unsupported('timer zones need IR and scheduled JoI')
    if getattr(code, 'repeat', False) and code.period_ms != step:
        raise Unsupported('timer zones require JoI period equal to input grid')
    dead = dead_clock_reads(ir)
    from explorer.verification.timed import reads_clock
    from explorer.verification.timed import internal_timers
    def clock_keys(n):
        if isinstance(n, e.ClockRef): return {'clock.' + n.field.lower()}
        if isinstance(n, jp.CallExpr):
            from explorer.runtime.interp import call_world_key
            key = call_world_key(n)
            if key.startswith('clock.'): return {key}
        if isinstance(n, e.DeviceRef) and n.key.startswith('clock.'): return {n.key}
        if isinstance(n, tuple) and len(n) > 1 and n[0] == 'read':
            return {n[1]} if str(n[1]).startswith('clock.') else set()
        if isinstance(n, (list, tuple)): return set().union(*(clock_keys(x) for x in n))
        if hasattr(n, '__dict__'): return set().union(*(clock_keys(x) for x in vars(n).values()))
        return set()
    clocks = clock_keys(code.stmts)
    clocks |= set().union(*(clock_keys(x.cond) | clock_keys(x.args) for x in ir.prog.ins))
    clocks |= {x.key for x in ir.prog.ins if x.kind == 'READ' and x.key.startswith('clock.') and x.var not in dead}
    if clocks - {'clock.hour', 'clock.timestamp'}: raise Unsupported('unsupported calendar field')
    snapshots, aliases, snapshot_limits = ((), ()), (), set()
    if 'clock.timestamp' in clocks:
        from explorer.verification.timestamp_analysis import snapshot_plan
        snapshots, aliases, snapshot_limits = snapshot_plan(ir, code)
    durations = {0, 1}
    modular_ir = {x.cname for x in ir.prog.ins if x.cname and x.mod}
    for x in ir.prog.ins:
        if x.kind == 'READ' and x.key.startswith('clock.') and x.var.startswith('__'):
            raise Unsupported('reserved clock destination')
        if (ir_refs(x.cond) | ir_refs(x.args)) & internal_timers(ir):
            raise Unsupported('program reads an interpreter timer register')
        if x.cname and x.cname not in ir.axes.counter_caps and x.cname not in modular_ir:
            raise Unsupported('unbounded named IR counter outside timer zones')
        if x.kind == 'CALL' and x.var: raise Unsupported('IR queries outside timer zones v1')
        def clock(v):
            if isinstance(v, (list, tuple)):
                return (len(v) > 1 and v[0] == 'read' and str(v[1]).startswith('clock.')) or any(clock(t) for t in v)
            return False
        for duration in (x.period, x.for_sec, x.to_sec):
            ticks = Fraction(duration) * 1000 / step
            if ticks.denominator != 1: raise Unsupported('off-grid IR deadline outside timer zones v1')
            durations.add(int(ticks))
    stmts = list(walk_stmts(code.stmts))
    def increment(s):
        return (isinstance(s, jp.Assign) and s.op == '=' and isinstance(s.rhs, e.BinaryOp)
                and s.rhs.op == '+' and isinstance(s.rhs.left, e.VarRef)
                and s.rhs.left.name == s.name and isinstance(s.rhs.right, e.Lit)
                and type(s.rhs.right.value) is int and s.rhs.right.value == 1)
    counters = {s.name for s in stmts if increment(s)}
    if not counters and not clocks: raise Unsupported('no timer counter or calendar clock')
    limits = set()
    def refs(n):
        if isinstance(n, e.VarRef): return {n.name} & counters
        if isinstance(n, (list, tuple)): return set().union(*(refs(t) for t in n))
        if hasattr(n, '__dict__'): return set().union(*(refs(t) for t in vars(n).values()))
        return set()
    def guard(n):
        if not refs(n): return
        if isinstance(n, e.UnaryOp) and n.op == 'not': return guard(n.operand)
        if isinstance(n, e.BinaryOp):
            if n.op in ('and', 'or'):
                guard(n.left); guard(n.right); return
            l, r = n.left, n.right
            if isinstance(r, e.VarRef): l, r = r, l
            if (n.op in ('==', '!=', '<', '<=', '>', '>=') and isinstance(l, e.VarRef)
                    and l.name in counters and isinstance(r, e.Lit) and type(r.value) is int):
                limits.add(r.value); return
        raise Unsupported('timer counter guard is not a literal comparison')
    for s in stmts:
        if isinstance(s, jp.Assign):
            if s.name in counters:
                if not increment(s) and not (isinstance(s.rhs, e.Lit) and type(s.rhs.value) is int):
                    raise Unsupported('timer counter reset is not an integer constant')
                if isinstance(s.rhs, e.Lit): limits.add(s.rhs.value)
            elif refs(s.rhs): raise Unsupported('timer counter escapes into another variable')
        elif isinstance(s, (jp.IfStmt, jp.WaitUntil)): guard(s.cond)
        elif isinstance(s, jp.CallStmt):
            if refs(s.call): raise Unsupported('timer counter escapes into ACTION/query arguments')
        elif isinstance(s, jp.Delay):
            if s.ms % step: raise Unsupported('off-grid JoI delay')
            durations.add(s.ms // step)
        elif not isinstance(s, jp.Break):
            raise Unsupported('blocking/loop JoI outside timer zones v1')
    points = durations | limits | snapshot_limits
    thresholds = sorted({v + delta for p in points for v in (p, -p) for delta in (-1, 0, 1)})
    # Small control counters retain their concrete value (e.g. blink/round count).
    selected = {n for n in counters if code.axes.counter_caps.get(n, 100000) > 32}
    return Plan(tuple(sorted(selected)), dead, tuple(thresholds),
                tuple(sorted({p + d for p in points if p > 1 for d in (-1, 0, 1) if p + d > 0})),
                'clock.hour' in clocks, snapshots, aliases)
