"""Integer difference-bound zones and exact affine interpreter values.

The zero coordinate is fixed. Bounds are inclusive mathematical integers.
Widening only enlarges sets; success requires rechecking the enlarged set.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from fractions import Fraction
import math

from explorer.runtime.interp import Unsupported
from explorer.verification.symbolic_values import SymbolicValue

INF = math.inf
_context = ContextVar('timer_zone', default=None)


class Split(Exception):
    def __init__(self, zones):
        self.zones = zones


class Zone:
    def __init__(self, names=(), bounds=None):
        self.names = ('',) + tuple(names)
        n = len(self.names)
        self.d = ([[(0 if i == j else INF) for j in range(n)] for i in range(n)]
                  if bounds is None else [list(row) for row in bounds])

    def close(self):
        d, n = self.d, len(self.names)
        for k in range(n):
            for i in range(n):
                if d[i][k] == INF: continue
                for j in range(n):
                    d[i][j] = min(d[i][j], d[i][k] + d[k][j])
        return self if all(d[i][i] >= 0 for i in range(n)) else None

    def constrain(self, term, strict=False):
        # term <= 0 (or < 0), with one positive and one negative coefficient.
        terms = dict(term.terms)
        scale = next(iter(terms.values()), Fraction(1))
        scale = abs(scale)
        if any(abs(v) != scale for v in terms.values()):
            raise Unsupported('timer guard is not a difference constraint')
        positive = [k for k, v in terms.items() if v > 0]
        negative = [k for k, v in terms.items() if v < 0]
        if len(positive) > 1 or len(negative) > 1:
            raise Unsupported('timer guard has multiple clocks on one side')
        bound = -term.constant / scale
        bound = math.ceil(bound) - 1 if strict else math.floor(bound)
        i = self.names.index(positive[0] if positive else '')
        j = self.names.index(negative[0] if negative else '')
        out = Zone(self.names[1:], self.d)
        out.d[i][j] = min(out.d[i][j], bound)
        return out.close()

    def image(self, expressions):
        """Exact parallel assignment/projection for x' = y + integer."""
        names = tuple(sorted(expressions))
        refs = [('', 0)] + [expressions[k].reference() for k in names]
        indices = [(self.names.index(k), c) for k, c in refs]
        return Zone(names, [[self.d[i][j] + ci - cj for j, cj in indices]
                            for i, ci in indices])

    def covers(self, other):
        return self.names == other.names and all(
            a >= b for ra, rb in zip(self.d, other.d) for a, b in zip(ra, rb))

    def widen(self, other, thresholds):
        if self.names != other.names: raise Unsupported('timer zone shape changed')
        rows = []
        for ra, rb in zip(self.d, other.d):
            rows.append([a if b <= a else next((t for t in thresholds if t >= b), INF)
                         for a, b in zip(ra, rb)])
        # Do not close widening: closure can reintroduce unstable bounds.
        return Zone(self.names[1:], rows)

    def canonical(self):
        return Zone(self.names[1:], self.d).close()


class Number(SymbolicValue):
    _timer = True

    def __init__(self, terms=(), constant=0):
        self.terms = tuple(sorted((k, Fraction(v)) for k, v in dict(terms).items() if v))
        self.constant = Fraction(constant)

    @staticmethod
    def of(value):
        if isinstance(value, Number): return value
        if type(value) not in (int, Fraction):
            raise Unsupported('timer arithmetic requires exact integers/rationals')
        return Number(constant=value)

    def reference(self):
        if self.constant.denominator != 1 or (self.terms and (
                len(self.terms) != 1 or self.terms[0][1] != 1)):
            raise Unsupported('timer update is not a clock copy plus integer')
        return (self.terms[0][0] if self.terms else '', int(self.constant))

    def __add__(self, other):
        other = Number.of(other)
        terms = dict(self.terms)
        for k, v in other.terms: terms[k] = terms.get(k, 0) + v
        return Number(terms, self.constant + other.constant)

    __radd__ = __add__
    def __neg__(self): return self * -1
    def __sub__(self, other): return self + -Number.of(other)
    def __rsub__(self, other): return Number.of(other) - self

    def __mul__(self, other):
        other = Number.of(other)
        if other.terms: raise Unsupported('nonlinear timer expression')
        return Number({k: v * other.constant for k, v in self.terms}, self.constant * other.constant)

    __rmul__ = __mul__
    def __truediv__(self, other):
        other = Number.of(other)
        if other.terms or not other.constant: raise Unsupported('nonconstant timer divisor')
        return self * (1 / other.constant)

    def __round__(self, ndigits=None):
        if ndigits is not None or any(v.denominator != 1 for _, v in self.terms) or self.constant.denominator != 1:
            raise Unsupported('timer rounding is not proved integral')
        return self

    def __bool__(self): return bool(self != 0)
    def __eq__(self, other): return False if other is None else Predicate(self - other, '==')
    def __ne__(self, other): return True if other is None else Predicate(self - other, '!=')
    def __lt__(self, other): return Predicate(self - other, '<')
    def __le__(self, other): return Predicate(self - other, '<=')
    def __gt__(self, other): return Predicate(-self + other, '<')
    def __ge__(self, other): return Predicate(-self + other, '<=')


class Predicate(SymbolicValue):
    def __init__(self, term, op): self.term, self.op = term, op

    def __bool__(self):
        ctx = _context.get()
        if ctx is None: raise Unsupported('timer comparison outside zone execution')
        zone, term, op = ctx[0], self.term, self.op
        if op in ('==', '!='):
            eq = zone.constrain(term)
            eq = eq.constrain(-term) if eq is not None else None
            unequal = [zone.constrain(term, True), zone.constrain(-term, True)]
            yes, no = ([eq], unequal) if op == '==' else (unequal, [eq])
        else:
            yes = [zone.constrain(term, op == '<')]
            no = [zone.constrain(-term, op != '<')]
        yes, no = [z for z in yes if z is not None], [z for z in no if z is not None]
        if yes and no: raise Split(yes + no)
        feasible = yes or no
        if len(feasible) > 1: raise Split(feasible)
        if not feasible: raise Unsupported('empty timer reaction zone')
        ctx[0] = feasible[0]
        return bool(yes)


@contextmanager
def reaction(zone):
    ctx = [zone]
    token = _context.set(ctx)
    try: yield ctx
    finally: _context.reset(token)
