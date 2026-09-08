"""Conservative integer interval comparisons over either expression AST.

No AST mutation, sampling, nullable-value assumptions, or branch deletion.
The resolver supplies a proved non-null integer range for an actual read.
Unknown expressions (including arithmetic, aliases and function calls) remain
unknown. Both endpoints suffice for inequalities; equality uses disjointness
or equal singleton intervals, never endpoint agreement alone.
"""
from explorer.runtime import expr as e
from explorer.runtime import joi_parser as jp


def interval_comparison(op, left, right):
    if left is None or right is None:
        return None
    lo, hi = left
    rlo, rhi = right
    if op == '<':
        return True if hi < rlo else False if lo >= rhi else None
    if op == '<=':
        return True if hi <= rlo else False if lo > rhi else None
    if op == '>':
        return interval_comparison('<', right, left)
    if op == '>=':
        return interval_comparison('<=', right, left)
    if op in ('==', '!='):
        equal = False if hi < rlo or rhi < lo else True if lo == hi == rlo == rhi else None
        return equal if op == '==' or equal is None else not equal
    return None


def constant_integer_comparison(node, resolve_range):
    def interval(value):
        if type(value) is e.Lit:
            return (value.value, value.value) if type(value.value) is int else None
        if type(value) is tuple and len(value) == 2 and value[0] == 'lit':
            return (value[1], value[1]) if type(value[1]) is int else None
        if type(value) is tuple and len(value) >= 2 and value[0] == 'read':
            return resolve_range(value[1])
        if type(value) is e.ClockRef:
            # Other ClockRef fields have different/unsupported evaluator paths.
            return resolve_range('clock.time') if value.field == 'time' else None
        if type(value) in (e.DeviceRef, e.QuantRef):
            key = value.key
            if type(value) is e.QuantRef:
                from explorer.runtime.interp import world_key
                key = world_key(value.tags, value.tags[-1] if value.tags else '', value.member)
            # A JoI Clock.Time property is not the numeric IR built-in.
            if key == 'clock.time':
                return None
            return resolve_range(key)
        if type(value) is jp.CallExpr and value.args is None:
            from explorer.runtime.interp import call_world_key
            key = call_world_key(value)
            return None if key == 'clock.time' else resolve_range(key)
        return None

    if type(node) is e.BinaryOp:
        op, left, right = node.op, node.left, node.right
    elif type(node) is tuple and len(node) == 4 and node[0] == 'bin':
        _, op, left, right = node
    else:
        return None
    return interval_comparison(op, interval(left), interval(right))
