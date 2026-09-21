"""Typed, deliberately structural relational INTEGER/text expressions.

Python equality is a program comparison, NEVER the verifier's term equality.
Use state_key.freeze_state for proof comparisons. Unhandled operations fail
closed, including text comparisons and implicit truth/number conversion.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from explorer.runtime.interp import Unsupported
from explorer.verification.symbolic_values import SymbolicValue
from explorer.runtime.integer_text import value_text

_context = ContextVar('relational_reaction', default=None)


class NeedBranch(Exception):
    def __init__(self, key):
        self.key = key


@contextmanager
def reaction(choices):
    events = []
    token = _context.set((choices, events))
    try:
        yield events
    finally:
        _context.reset(token)


def record(kind, name, value):
    context = _context.get()
    if context is not None:
        from explorer.verification.state_key import freeze_state
        context[1].append((kind, name, freeze_state(value)))


def unsupported(*args, **kwargs):
    raise Unsupported('relational value operation outside INTEGER/text fragment')


class RelValue(SymbolicValue):
    _relational = True
    __eq__ = __ne__ = __lt__ = __le__ = __gt__ = __ge__ = unsupported
    __bool__ = __int__ = __float__ = __index__ = __str__ = unsupported
    __mul__ = __rmul__ = __truediv__ = __rtruediv__ = unsupported
    __floordiv__ = __rfloordiv__ = __mod__ = __rmod__ = unsupported
    __pow__ = __rpow__ = __neg__ = __abs__ = unsupported
    __sub__ = __rsub__ = unsupported
    __hash__ = None

    def __add__(self, other):
        return add(self, other)

    def __radd__(self, other):
        return add(other, self)

    def validate(self, spec, label):
        if isinstance(self, RelText) and spec.get('type') == 'STRING' \
                and not spec.get('bound') and spec.get('members') is None:
            return
        raise Unsupported('relational ACTION domain inclusion not proved: ' + label)


def int_term(value):
    if isinstance(value, PairInt):
        return value.term
    if type(value) is int:
        return ('int', value)
    raise Unsupported('relational arithmetic requires INTEGER operands')


@dataclass(frozen=True, eq=False)
class PairInt(RelValue):
    term: tuple = ('slot', 0)

    def compare(self, op, other):
        return RelBool((op, self.term, int_term(other)))

    def __eq__(self, other): return self.compare('==', other)
    def __ne__(self, other): return self.compare('!=', other)
    def __lt__(self, other): return self.compare('<', other)
    def __le__(self, other): return self.compare('<=', other)
    def __gt__(self, other): return self.compare('>', other)
    def __ge__(self, other): return self.compare('>=', other)
    def __sub__(self, other): return PairInt(('-', self.term, int_term(other)))
    def __rsub__(self, other): return PairInt(('-', int_term(other), self.term))
    def __bool__(self): return bool(self.compare('!=', 0))


@dataclass(frozen=True, eq=False)
class RelBool(RelValue):
    term: tuple

    def __bool__(self):
        context = _context.get()
        if context is None:
            raise Unsupported('relational condition outside branch exploration')
        choices, events = context
        if self.term not in choices:
            raise NeedBranch(self.term)
        answer = choices[self.term]
        events.append(('guard', self.term, answer))
        return answer


@dataclass(frozen=True, eq=False)
class RelText(RelValue):
    parts: tuple


def text(values):
    parts = []
    for value in values:
        if isinstance(value, RelText):
            additions = value.parts
        elif isinstance(value, PairInt):
            additions = (('IntToText', value.term),)
        elif isinstance(value, SymbolicValue):
            raise Unsupported('relational text conversion requires INTEGER')
        else:
            additions = ('' if value is None else value_text(value),)
        for part in additions:
            if isinstance(part, str) and not part:
                continue
            if isinstance(part, str) and parts and isinstance(parts[-1], str):
                parts[-1] += part
            else:
                parts.append(part)
    return RelText(tuple(parts))


def add(left, right):
    if isinstance(left, (str, RelText)) or isinstance(right, (str, RelText)):
        return text((left, right))
    return PairInt(('+', int_term(left), int_term(right)))
