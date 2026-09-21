"""Certified integer counters observable only through literal residues.

This is a congruence quotient, not saturation. Every use is inspected; copies,
raw comparisons, queries and ACTION arguments disqualify the variable.
"""
from math import lcm
from explorer.runtime import expr as e, joi_parser as jp


def counter_moduli(stmts):
    from explorer.analysis.predicates import walk_stmts
    statements = list(walk_stmts(stmts))
    candidates = {s.name for s in statements if isinstance(s, jp.Assign)}
    answer = {}
    for name in candidates:
        mods, valid = [], True

        def visit(n):
            nonlocal valid
            if (isinstance(n, e.BinaryOp) and n.op == '%'
                    and isinstance(n.left, e.VarRef) and n.left.name == name
                    and isinstance(n.right, e.Lit) and type(n.right.value) is int
                    and n.right.value > 0):
                mods.append(n.right.value)
                return
            if isinstance(n, e.VarRef) and n.name == name: valid = False
            elif isinstance(n, (tuple, list)):
                for x in n: visit(x)
            elif hasattr(n, '__dict__'):
                for x in vars(n).values(): visit(x)

        for s in statements:
            if isinstance(s, jp.Assign) and s.name == name:
                n = s.rhs
                if isinstance(n, e.Lit) and type(n.value) is int: continue
                if (s.op == '=' and isinstance(n, e.BinaryOp) and n.op in ('+', '-')
                        and isinstance(n.left, e.VarRef) and n.left.name == name
                        and isinstance(n.right, e.Lit) and type(n.right.value) is int): continue
                valid = False
            elif isinstance(s, (jp.IfStmt, jp.WaitUntil)): visit(s.cond)
            elif isinstance(s, jp.Assign): visit(s.rhs)
            elif isinstance(s, jp.CallStmt):
                # Do not allow even residue ACTION arguments in this version.
                def raw(n):
                    nonlocal valid
                    if isinstance(n, e.VarRef) and n.name == name: valid = False
                    elif isinstance(n, (tuple, list)):
                        for x in n: raw(x)
                    elif hasattr(n, '__dict__'):
                        for x in vars(n).values(): raw(x)
                raw(s.call)
            elif not isinstance(s, (jp.Delay, jp.Break)): valid = False
        if valid and mods: answer[name] = lcm(*mods)
    return answer


def residue_expr(n, names):
    return (isinstance(n, e.BinaryOp) and n.op == '%'
            and isinstance(n.left, e.VarRef) and n.left.name in names
            and isinstance(n.right, e.Lit) and type(n.right.value) is int
            and n.right.value > 0)
