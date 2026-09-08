"""External finite input declarations; the frozen Timeline IR is unchanged."""
from decimal import Decimal
import math


def decimal_domain(minimum, maximum, *, include_missing=False):
    """Inclusive 0.1-spaced range. Bounds must be supplied by the model owner."""
    lo, hi = Decimal(str(minimum)) * 10, Decimal(str(maximum)) * 10
    if not lo.is_finite() or not hi.is_finite() or lo != lo.to_integral_value() or hi != hi.to_integral_value() or lo > hi:
        raise ValueError("domain bounds must be finite, ordered multiples of 0.1")
    if hi - lo > 1_000_000:
        raise ValueError("domain range exceeds materialization cap")
    values = [float(Decimal(n) / 10) for n in range(int(lo), int(hi) + 1)]
    return ([None] if include_missing else []) + values


def validate_domains(domains, *, required=()):
    missing = set(required) - set(domains)
    if missing:
        raise ValueError("input domains missing keys: " + ", ".join(sorted(missing)))
    for key, values in domains.items():
        if not isinstance(key, str) or not isinstance(values, (list, tuple)) or not values:
            raise ValueError(f"nonempty input domain required: {key!r}")
        if key.startswith("clock.") and key != "clock.isholiday":
            raise ValueError(f"derived clock cannot be an external input: {key}")
        for value in values:
            if key == 'clock.isholiday' and type(value) is not bool:
                raise ValueError('clock.isholiday requires true/false inputs')
            if isinstance(value, float):
                scaled = Decimal(str(value)) * 10
                if not math.isfinite(value) or scaled != scaled.to_integral_value():
                    raise ValueError(f"{key}: float input must be a finite multiple of 0.1: {value}")
            elif value is not None and not isinstance(value, (bool, int, str)):
                raise ValueError(f"{key}: unsupported input value {value!r}")
