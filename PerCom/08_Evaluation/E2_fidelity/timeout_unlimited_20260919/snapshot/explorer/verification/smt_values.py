"""Typed terms executed by the ordinary interpreters in the SMT product.

Integers are mathematical integers; floats are IEEE binary64 with RNE. We do
not replace float arithmetic by real arithmetic. Float-to-text is a shared
uninterpreted function: UNSAT is sound under this overapproximation, whereas
SAT always needs concrete replay. No numeric/string normalization is added.
"""
import math

import z3

from explorer.runtime.interp import Unsupported
from explorer.verification.symbolic_values import SymbolicValue

FP = z3.Float64()
RNE = z3.RNE()


class SmtValue(SymbolicValue):
    """Never let Python identity equality or a swallowed TypeError define DSL semantics."""
    _smt = True

    def unsupported(self, *args):
        raise Unsupported('SMT operation is outside the typed numeric/text-output fragment')

    __eq__ = __ne__ = __lt__ = __le__ = __gt__ = __ge__ = unsupported
    __add__ = __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = unsupported
    __truediv__ = __rtruediv__ = __mod__ = __rmod__ = unsupported
    __neg__ = __abs__ = unsupported


class SmtBool(SmtValue):

    def __init__(self, ctx, term):
        self.ctx, self.term = ctx, z3.simplify(term)

    def __bool__(self):
        return self.ctx.choose(self.term)

    def __eq__(self, other):
        if isinstance(other, SmtBool):
            return SmtBool(self.ctx, self.term == other.term)
        if type(other) is bool:
            return SmtBool(self.ctx, self.term == other)
        raise Unsupported('SMT Boolean/numeric coercion is not supported')

    def __ne__(self, other):
        return SmtBool(self.ctx, z3.Not(self.__eq__(other).term))

    def validate(self, spec, label):
        if spec.get('type') not in ('BOOL', 'BOOLEAN') or spec.get('bound') or spec.get('members') is not None:
            raise Unsupported('SMT Boolean ACTION type mismatch: ' + label)


class SmtNumber(SmtValue):

    def __init__(self, ctx, term, kind, magnitude, dependent=True, origin=None):
        self.ctx, self.term, self.kind = ctx, z3.simplify(term), kind
        self.magnitude, self.dependent, self.origin = magnitude, dependent, origin
        # Conservative totality restriction, not an assumption on valuations.
        if not math.isfinite(magnitude) or magnitude > 1e100:
            raise Unsupported('SMT arithmetic magnitude/overflow is outside v1')

    def fp(self):
        return self.term if self.kind == 'float' else z3.fpRealToFP(RNE, z3.ToReal(self.term), FP)

    def real(self):
        return z3.fpToReal(self.term) if self.kind == 'float' else z3.ToReal(self.term)

    def __bool__(self):
        return bool(self.__ne__(0))

    def compare(self, other, op):
        if other is None:
            return SmtBool(self.ctx, z3.BoolVal(op == '!='))
        other = number(self.ctx, other)
        # Python mixed int/float comparisons compare exact numeric values.
        a, b = (self.term, other.term) if self.kind == other.kind == 'int' else (self.real(), other.real())
        return SmtBool(self.ctx, {'==': lambda: a == b, '!=': lambda: a != b,
            '<': lambda: a < b, '<=': lambda: a <= b,
            '>': lambda: a > b, '>=': lambda: a >= b}[op]())

    def __eq__(self, other): return self.compare(other, '==')
    def __ne__(self, other): return self.compare(other, '!=')
    def __lt__(self, other): return self.compare(other, '<')
    def __le__(self, other): return self.compare(other, '<=')
    def __gt__(self, other): return self.compare(other, '>')
    def __ge__(self, other): return self.compare(other, '>=')

    def arithmetic(self, other, op):
        other = number(self.ctx, other)
        if op == '*' and self.dependent and other.dependent:
            raise Unsupported('SMT v1 refuses multiplication of two input-dependent terms')
        if op == '/' and other.dependent:
            raise Unsupported('SMT v1 requires a constant divisor')
        dep = self.dependent or other.dependent
        if op == '/':
            divisor = concrete_number(other)
            if divisor == 0:
                return 0  # Existing JoI/IR division-by-zero rule.
            if self.kind == other.kind == 'int':
                term = z3.fpRealToFP(RNE, self.real() / other.real(), FP)
                if divisor < 0:
                    term = z3.If(self.term == 0, z3.FPVal(-0.0, FP), term)
            else:
                term = z3.fpDiv(RNE, self.fp(), other.fp())
            bound = self.magnitude / abs(divisor)
            kind = 'float'
        else:
            kind = 'float' if 'float' in (self.kind, other.kind) else 'int'
            if kind == 'float':
                term = {'+': z3.fpAdd, '-': z3.fpSub, '*': z3.fpMul}[op](RNE, self.fp(), other.fp())
            else:
                term = {'+': lambda a, b: a + b, '-': lambda a, b: a - b,
                        '*': lambda a, b: a * b}[op](self.term, other.term)
            bound = self.magnitude * other.magnitude if op == '*' else self.magnitude + other.magnitude
        # Outward rounding bounds every supported operation, including underflow.
        bound = math.nextafter(bound, math.inf)
        return SmtNumber(self.ctx, term, kind, bound, dep)

    def __add__(self, other): return add(self, other)
    def __radd__(self, other): return add(other, self)
    def __sub__(self, other): return self.arithmetic(other, '-')
    def __rsub__(self, other): return number(self.ctx, other).arithmetic(self, '-')
    def __mul__(self, other): return self.arithmetic(other, '*')
    def __rmul__(self, other): return self.__mul__(other)
    def __truediv__(self, other): return self.arithmetic(other, '/')
    def __rtruediv__(self, other): return number(self.ctx, other).arithmetic(self, '/')

    def __neg__(self):
        term = z3.fpNeg(self.term) if self.kind == 'float' else -self.term
        return SmtNumber(self.ctx, term, self.kind, self.magnitude, self.dependent)

    def __abs__(self):
        term = z3.fpAbs(self.term) if self.kind == 'float' else z3.If(self.term < 0, -self.term, self.term)
        return SmtNumber(self.ctx, term, self.kind, self.magnitude, self.dependent)

    def validate(self, spec, label):
        typ = spec.get('type')
        if typ not in ('INTEGER', 'DOUBLE') or (typ == 'INTEGER' and self.kind != 'int'):
            raise Unsupported('SMT numeric ACTION type mismatch: ' + label)
        conditions = []
        if spec.get('bound'):
            lo, hi = spec['bound']
            conditions += [self.compare(lo, '>=').term, self.compare(hi, '<=').term]
        if spec.get('members') is not None:
            conditions.append(z3.Or(*[self.compare(v, '==').term for v in spec['members']]))
        self.ctx.require(z3.And(*conditions), 'SMT ACTION domain is not universally valid: ' + label)


def number(ctx, value):
    if isinstance(value, SmtNumber):
        return value
    if value is None:
        value = 0
    if type(value) not in (int, float) or not math.isfinite(value):
        raise Unsupported('SMT arithmetic requires finite numeric operands')
    term = z3.IntVal(value) if type(value) is int else z3.FPVal(value, FP)
    return SmtNumber(ctx, term, 'int' if type(value) is int else 'float',
                     math.nextafter(float(abs(value)), math.inf), False)


def concrete_number(value):
    if value.dependent:
        raise Unsupported('SMT expected constant')
    if value.kind == 'int' and z3.is_int_value(value.term):
        return value.term.as_long()
    if value.kind == 'float' and isinstance(value.term, z3.FPNumRef):
        import struct
        bits = z3.simplify(z3.fpToIEEEBV(value.term)).as_long()
        return struct.unpack('>d', bits.to_bytes(8, 'big'))[0]
    raise Unsupported('SMT constant expression did not normalize')


class SmtText(SmtValue):

    def __init__(self, ctx, parts):
        self.ctx, self.parts = ctx, tuple(parts)

    def validate(self, spec, label):
        if spec.get('type') != 'STRING' or spec.get('bound') or spec.get('members') is not None:
            raise Unsupported('SMT text ACTION needs unrestricted STRING: ' + label)

    def expression(self):
        def render(part):
            if isinstance(part, str):
                return z3.StringVal(part)
            if part.kind == 'int':
                n = part.term
                return z3.If(n < 0, z3.Concat(z3.StringVal('-'), z3.IntToStr(-n)), z3.IntToStr(n))
            return self.ctx.float_text(z3.fpToIEEEBV(part.term))
        return z3.Concat(z3.StringVal(''), *[render(p) for p in self.parts])


def text(values):
    parts, ctx = [], None
    for value in values:
        if isinstance(value, SmtText):
            ctx = value.ctx
            additions = value.parts
        elif isinstance(value, SmtNumber):
            ctx = value.ctx
            additions = (value,)
        elif isinstance(value, SymbolicValue):
            raise Unsupported('SMT text conversion supports numbers only')
        else:
            additions = ('' if value is None else str(value),)
        for part in additions:
            if isinstance(part, str) and parts and isinstance(parts[-1], str):
                parts[-1] += part
            elif not isinstance(part, str) or part:
                parts.append(part)
    return SmtText(ctx, parts) if ctx else ''.join(parts)


def add(left, right):
    if isinstance(left, (str, SmtText)) or isinstance(right, (str, SmtText)):
        return text((left, right))
    ctx = left.ctx if isinstance(left, SmtNumber) else right.ctx
    return number(ctx, left).arithmetic(right, '+')


def equal(left, right, ctx):
    """Equality of D1 observations; numeric ACTIONs retain numeric equality."""
    if isinstance(left, SmtText) or isinstance(right, SmtText):
        if not isinstance(left, (str, SmtText)) or not isinstance(right, (str, SmtText)):
            return z3.BoolVal(False)
        a = left.expression() if isinstance(left, SmtText) else z3.StringVal(left)
        b = right.expression() if isinstance(right, SmtText) else z3.StringVal(right)
        return a == b
    if isinstance(left, SmtNumber) or isinstance(right, SmtNumber):
        return number(ctx, left).compare(right, '==').term
    if isinstance(left, SmtBool) or isinstance(right, SmtBool):
        a = left.term if isinstance(left, SmtBool) else z3.BoolVal(left)
        b = right.term if isinstance(right, SmtBool) else z3.BoolVal(right)
        return a == b
    if isinstance(left, tuple) and isinstance(right, tuple):
        if len(left) != len(right):
            return z3.BoolVal(False)
        return z3.And(*[equal(a, b, ctx) for a, b in zip(left, right)])
    return z3.BoolVal(type(left) is type(right) and left == right)
