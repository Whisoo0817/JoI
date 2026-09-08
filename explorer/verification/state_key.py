"""Concrete store identity, deliberately stricter than ACTION equivalence.

Numeric ACTION arguments may equate 1 and 1.0, but stored values must retain
their types: string conversion and parameterized query keys distinguish them.
"""
from dataclasses import fields, is_dataclass
from fractions import Fraction


def freeze_state(value):
    if value is None:
        return ("none",)
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, int):
        return ("int", value)
    if isinstance(value, float):
        # hex also preserves negative zero, observable through str(value).
        return ("float", value.hex())
    if isinstance(value, Fraction):
        return ("rational", value.numerator, value.denominator)
    if isinstance(value, str):
        return ("str", value)
    if isinstance(value, dict):
        return ("dict", tuple(sorted(
            ((freeze_state(k), freeze_state(v)) for k, v in value.items()), key=repr)))
    if isinstance(value, (list, tuple)):
        return (type(value).__name__, tuple(map(freeze_state, value)))
    if isinstance(value, (set, frozenset)):
        return (type(value).__name__, tuple(sorted(map(freeze_state, value), key=repr)))
    if is_dataclass(value) and not isinstance(value, type):
        return ("dataclass", type(value).__module__, type(value).__qualname__,
                tuple((f.name, freeze_state(getattr(value, f.name))) for f in fields(value)))
    # Unknown objects must not silently become an unsound repr/equality key.
    from explorer.runtime.interp import Unsupported
    raise Unsupported(f"unsupported concrete state type: {type(value).__name__}")
