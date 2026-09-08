"""Exact use-site eligibility for the relational path, separate from legacy D7.

No feature flag is disabled globally. This validator owns every instruction
and expression in the admitted pair. External values occur only in direct
literal guards; hence existing joint predicate partitions remain sufficient.
"""
from dataclasses import dataclass
from explorer.runtime import expr as e, joi_parser as jp
from explorer.runtime.interp import Unsupported
from explorer.runtime.ir_step import IrRunner
from explorer.runtime.pause import PauseRunner
from explorer.verification.timed import unwrap, reads_clock

CMP = {'==', '!=', '<', '<=', '>', '>='}


@dataclass
class Mapping:
    ir_name: str
    code_name: str
    code_locals: tuple


def analyze(a, b):
    ir, code = unwrap(a), unwrap(b)
    if type(ir) is not IrRunner or type(code) is not PauseRunner:
        raise Unsupported('relational path needs IrRunner and periodic PauseRunner')
    if not code.repeat or not code.period_ms or reads_clock(a) or reads_clock(b):
        raise Unsupported('relational path needs positive period and no clock reads')
    entries = [x for x in ir.prog.ins if x.kind == 'ENTER_CYCLE']
    if len(entries) != 1 or ir.prog.ins[0].kind != 'ENTER_CYCLE':
        raise Unsupported('relational v1 needs one top-level named cycle')
    name = entries[0].cname
    top = ir.prog.ins[1]
    if not name or top.cname != name or top.count or top.mod or top.period <= 0:
        raise Unsupported('relational v1 needs a preserved unbounded named counter')
    if top.cond is not None or round(top.period * 1000) != code.period_ms:
        raise Unsupported('relational v1 cycle period/until is unsupported')
    if ir.prog.ins[-2].kind != 'END_ITER' or ir.prog.ins[-2].cname != name:
        raise Unsupported('relational v1 cycle must be the entire program')
    initializers = [s for s in code.stmts if isinstance(s, jp.Assign) and s.op == ':=']
    if len(initializers) != 1 or code.stmts[0] is not initializers[0]:
        raise Unsupported('relational v1 needs one leading persistent initializer')
    init = initializers[0]
    if not isinstance(init.rhs, e.Lit) or type(init.rhs.value) is not int:
        raise Unsupported('relational initializer must be INTEGER literal')
    locals_ = set()

    def ie(n):
        tag = n[0]
        if tag == 'lit': return ('lit', n[1])
        if tag == 'var': return ('var', n[1])
        if tag == 'read': return ('read', n[1])
        if tag == 'expr': return ie(n[1])
        if tag == 'tmpl': return ('text', tuple(ie(v) if isinstance(v, tuple) else ('lit', v) for v in n[1]))
        if tag == 'bin': return ('bin', n[1], ie(n[2]), ie(n[3]))
        if tag == 'not': return ('not', ie(n[1]))
        raise Unsupported('relational IR expression: ' + tag)

    def je(n):
        if isinstance(n, e.Lit): return ('lit', n.value)
        if isinstance(n, e.VarRef): return ('var', n.name)
        if isinstance(n, e.DeviceRef): return ('read', n.key)
        if isinstance(n, jp.CallExpr) and n.args is None:
            from explorer.runtime.interp import call_world_key
            return ('read', call_world_key(n))
        if isinstance(n, e.BinaryOp): return ('bin', n.op, je(n.left), je(n.right))
        if isinstance(n, e.UnaryOp) and n.op == 'not': return ('not', je(n.operand))
        raise Unsupported('relational JoI expression: ' + type(n).__name__)

    def value(n, allowed, *, integer=False):
        if n[0] == 'lit':
            if integer and type(n[1]) is not int:
                raise Unsupported('relational local assignment must be INTEGER')
            if not integer and type(n[1]) not in (str, int, bool):
                raise Unsupported('relational literal type outside v1')
            return
        if n[0] == 'var' and n[1] in allowed: return
        if n[0] == 'text' and not integer:
            for child in n[1]: value(child, allowed)
            return
        if n[0] == 'bin' and n[1] in ('+', '-'):
            value(n[2], allowed, integer=integer or n[1] == '-')
            value(n[3], allowed, integer=integer or n[1] == '-')
            return
        raise Unsupported('relational value use outside local INTEGER/text fragment')

    def guard(n, allowed):
        if n[0] == 'not': return guard(n[1], allowed)
        if n[0] == 'bin' and n[1] in ('and', 'or'):
            guard(n[2], allowed); guard(n[3], allowed); return
        if n[0] == 'read': return
        if n[0] == 'lit' and type(n[1]) is bool: return
        if n[0] == 'bin' and n[1] in CMP:
            l, r = n[2:]
            if (l[0], r[0]) in (('read', 'lit'), ('lit', 'read')):
                return
            value(l, allowed, integer=True); value(r, allowed, integer=True)
            return
        raise Unsupported('relational guard must be direct input/literal or INTEGER comparison')

    from explorer.analysis.predicates import walk_stmts
    for s in walk_stmts(code.stmts):
        if isinstance(s, jp.Assign): locals_.add(s.name)
    for x in ir.prog.ins:
        if x.kind in ('ENTER_CYCLE', 'TOP', 'END_ITER', 'END', 'GOTO', 'DELAY'):
            continue
        if x.kind in ('IF', 'WAIT'):
            guard(ie(x.cond), {name})
            # Sustain clocks and edge flags are retained exactly. They may
            # prevent closure, but are never silently saturated/deleted.
        elif x.kind == 'CALL' and not x.var:
            for arg in x.args: value(ie(arg), {name})
        else:
            raise Unsupported('relational IR instruction: ' + x.kind)
    for s in walk_stmts(code.stmts):
        if isinstance(s, jp.Assign):
            if s.op == ':=' and s is not init:
                raise Unsupported('relational nested initializer')
            value(je(s.rhs), locals_, integer=True)
        elif isinstance(s, (jp.IfStmt, jp.WaitUntil)):
            guard(je(s.cond), locals_)
        elif isinstance(s, jp.CallStmt):
            if s.call.service.lower() in ('gv', 'globalvariable') or s.call.args is None:
                raise Unsupported('relational query/GV ACTION unsupported')
            for arg in s.call.args: value(je(arg), locals_)
        elif not isinstance(s, (jp.Delay, jp.Break)):
            raise Unsupported('relational JoI statement: ' + type(s).__name__)
    return Mapping(name, init.name, tuple(sorted(locals_)))


def entry_live(stmts):
    """May-read-before-overwrite at the NEXT iteration; := is skipped there.

    Used only at a completed period boundary, never at a blocked continuation.
    Branch union is conservative; persistent initialization is not a kill.
    """
    def names(node):
        if isinstance(node, e.VarRef): return {node.name}
        if isinstance(node, (list, tuple)):
            return set().union(*(names(x) for x in node)) if node else set()
        if hasattr(node, '__dict__'): return names(list(vars(node).values()))
        return set()
    def block(body, live):
        live = set(live)
        for s in reversed(body):
            if isinstance(s, jp.Assign):
                if s.op != ':=':
                    live.discard(s.name)
                    live.update(names(s.rhs))
            elif isinstance(s, jp.IfStmt):
                live = block(s.then_body, live) | block(s.else_body, live) | names(s.cond)
            else:
                live.update(names(s))
        return live
    # Across repeated rounds a definition that survives one round can become
    # live later. Iterate the finite name set to a liveness fixed point.
    live = set()
    while True:
        updated = block(stmts, live)
        if updated == live: return live
        live |= updated
