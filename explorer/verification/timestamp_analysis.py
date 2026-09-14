"""Use-site checks for timestamp snapshots used only as elapsed ages."""
from explorer.runtime import expr as e, joi_parser as jp
from explorer.runtime.interp import Unsupported, call_world_key
from explorer.analysis.predicates import walk_stmts
from explorer.verification.relational_analysis import entry_live


def snapshot_plan(ir, code):
    def clock(n):
        return (isinstance(n, jp.CallExpr) and n.args is None and call_world_key(n) == 'clock.timestamp'
                or isinstance(n, e.ClockRef) and n.field == 'timestamp'
                or isinstance(n, e.DeviceRef) and n.key == 'clock.timestamp')
    stmts = list(walk_stmts(code.stmts))
    if not getattr(code, 'repeat', False) or any(isinstance(s, (jp.WaitUntil, jp.Delay, jp.Loop)) for s in stmts):
        raise Unsupported('timestamp aliases require nonblocking repeating JoI')
    aliases = {s.name for s in stmts if isinstance(s, jp.Assign) and s.op == '=' and clock(s.rhs)}
    if aliases & entry_live(code.stmts): raise Unsupported('timestamp alias carried across iterations')
    slots = {s.name for s in stmts if isinstance(s, jp.Assign) and
             (clock(s.rhs) or isinstance(s.rhs, e.VarRef) and s.rhs.name in aliases)} - aliases
    ir_slots = {x.var for x in ir.prog.ins if x.kind == 'READ' and x.key == 'clock.timestamp'}
    if not slots and not ir_slots: raise Unsupported('no elapsed timestamp snapshot')

    def now(n): return clock(n) or isinstance(n, e.VarRef) and n.name in aliases
    def saved(n): return isinstance(n, e.VarRef) and n.name in slots
    def refs(n):
        if clock(n) or isinstance(n, e.VarRef) and n.name in slots | aliases: return True
        if isinstance(n, (list, tuple)): return any(refs(x) for x in n)
        if hasattr(n, '__dict__'): return any(refs(x) for x in vars(n).values())
        return False
    limits = set()
    def guard(n):
        if not refs(n): return
        if isinstance(n, e.UnaryOp) and n.op == 'not': return guard(n.operand)
        if isinstance(n, e.BinaryOp) and n.op in ('and','or'):
            guard(n.left); guard(n.right); return
        if isinstance(n, e.BinaryOp) and n.op in ('==','!=','<','<=','>','>='):
            for a,b in ((n.left,n.right),(n.right,n.left)):
                if isinstance(b,e.Lit):
                    if saved(a) and b.value is None and n.op in ('==','!='): return
                    if (isinstance(a,e.BinaryOp) and a.op=='-' and now(a.left)
                            and saved(a.right) and type(b.value) is int):
                        limits.add(b.value); return
        raise Unsupported('timestamp use is not an elapsed-age literal guard')
    for s in stmts:
        if isinstance(s,jp.Assign):
            if s.name in aliases:
                if s.op != '=' or not clock(s.rhs): raise Unsupported('timestamp alias reassigned')
            elif s.name in slots:
                if not now(s.rhs) and not (s.op == ':=' and isinstance(s.rhs,e.Lit) and type(s.rhs.value) is int):
                    raise Unsupported('timestamp snapshot must copy current timestamp')
            elif refs(s.rhs): raise Unsupported('timestamp escapes into variable')
        elif isinstance(s,(jp.IfStmt,jp.WaitUntil)): guard(s.cond)
        elif isinstance(s,jp.CallStmt) and refs(s.call): raise Unsupported('timestamp escapes into ACTION/query')
    def ir_guard(n):
        if not isinstance(n,tuple): return
        if n[0]=='bin' and n[1] in ('and','or'):
            ir_guard(n[2]); ir_guard(n[3]); return
        def refs_ir(v):
            return isinstance(v,tuple) and (v[:2] == ('read','clock.timestamp') or
                v[0]=='var' and v[1] in ir_slots or any(refs_ir(x) for x in v))
        if not refs_ir(n): return
        if n[0]=='not': return ir_guard(n[1])
        if n[0]=='bin' and n[1] in ('==','!=','<','<=','>','>='):
            for a,b in ((n[2],n[3]),(n[3],n[2])):
                if b[0]=='lit':
                    if a[0]=='var' and a[1] in ir_slots and b[1] is None and n[1] in ('==','!='): return
                    if (a[0:2]==('bin','-') and a[2][:2]==('read','clock.timestamp')
                            and a[3][0]=='var' and a[3][1] in ir_slots and type(b[1]) is int):
                        limits.add(b[1]); return
        raise Unsupported('IR timestamp use outside elapsed-age guard')
    from explorer.verification.timer_analysis import ir_refs
    for x in ir.prog.ins:
        if x.var in ir_slots and (x.kind != 'READ' or x.key != 'clock.timestamp'):
            raise Unsupported('IR timestamp snapshot overwritten with a non-clock value')
        ir_guard(x.cond)
        if ir_refs(x.args) & ir_slots: raise Unsupported('IR timestamp escapes into ACTION/query')
        def direct(v):
            return isinstance(v,tuple) and (v[:2] == ('read','clock.timestamp') or any(direct(t) for t in v))
        if any(direct(arg) for arg in x.args): raise Unsupported('IR timestamp escapes directly into ACTION/query')
    return (tuple(sorted(ir_slots)),tuple(sorted(slots))), tuple(sorted(aliases)), limits
