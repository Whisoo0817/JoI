"""Small, intentionally incomplete algebra of catalog input copies and text.

Equality is structural equality of terms, a sufficient universal certificate.
Inequality of terms is NOT a certificate of semantic inequality.
"""
from dataclasses import dataclass

from explorer.runtime.interp import Unsupported
from explorer.runtime.integer_text import value_text


class SymbolicValue:
    def __str__(self):
        raise Unsupported('symbolic value needs an explicit certified conversion')

    def __bool__(self):
        raise Unsupported('symbolic input-dependent control is outside value-flow v1')


def resolve_input(value):
    """Force an SMT input's representation only when the program reads it."""
    return value.force() if getattr(value, '_smt_input', False) else value


@dataclass(frozen=True)
class InputSymbol(SymbolicValue):
    key: str
    epoch: int
    type: str
    nullable: bool


@dataclass(frozen=True)
class TextTerm(SymbolicValue):
    # Each InputSymbol means str(value), with None mapped to empty text.
    parts: tuple


def text_join(values):
    """Normalize only associative string concatenation and adjacent literals."""
    values = list(values)
    if any(getattr(v, '_smt', False) for v in values):
        from explorer.verification.smt_values import text
        return text(values)
    if any(getattr(v, '_relational', False) for v in values):
        from explorer.verification.relational_values import text
        return text(values)
    parts = []
    for value in values:
        if isinstance(value, TextTerm):
            additions = value.parts
        elif isinstance(value, InputSymbol):
            additions = (value,)
        elif isinstance(value, SymbolicValue):
            raise Unsupported('unrecognized symbolic text operand')
        else:
            additions = ('' if value is None else value_text(value),)
        for part in additions:
            if isinstance(part, str):
                if not part:
                    continue
                if parts and isinstance(parts[-1], str):
                    parts[-1] += part
                else:
                    parts.append(part)
            else:
                parts.append(part)
    if all(isinstance(p, str) for p in parts):
        return ''.join(parts)
    return TextTerm(tuple(parts))


def symbolic_add(left, right):
    if getattr(left, '_relational', False) or getattr(right, '_relational', False):
        from explorer.verification.relational_values import add
        return add(left, right)
    if getattr(left, '_smt', False) or getattr(right, '_smt', False):
        from explorer.verification.smt_values import add
        return add(left, right)
    # A nullable STRING alone is not guaranteed to trigger string addition:
    # None + None is numeric 0 under the concrete evaluator. Do not flatten it.
    if not any(isinstance(v, (str, TextTerm)) for v in (left, right)):
        raise Unsupported('symbolic + requires a guaranteed string operand')
    return text_join((left, right))


def validate_symbolic(value, spec, label):
    if getattr(value, '_relational', False):
        return value.validate(spec, label)
    if getattr(value, '_smt', False):
        return value.validate(spec, label)
    # Converted text is always STRING, even for missing / numeric inputs.
    if isinstance(value, TextTerm):
        if spec.get('type') == 'STRING' and not spec.get('bound') and spec.get('members') is None:
            return
    if isinstance(value, InputSymbol) and value.type == 'STRING' and not value.nullable:
        if spec.get('type') == 'STRING' and not spec.get('bound') and spec.get('members') is None:
            return
    # Raw nullable inputs cannot meet a non-null ACTION signature universally.
    if isinstance(value, InputSymbol) and value.nullable:
        raise Unsupported('symbolic ACTION may receive missing/None: ' + label)
    raise Unsupported('symbolic ACTION domain inclusion is not certified: ' + label)


def substitute(value, valuation):
    """Concrete denotation, used only for tests and witness materialization."""
    if isinstance(value, InputSymbol):
        return valuation[value]
    if isinstance(value, TextTerm):
        return ''.join('' if (v := substitute(p, valuation)) is None else str(v)
                       for p in value.parts)
    return value
