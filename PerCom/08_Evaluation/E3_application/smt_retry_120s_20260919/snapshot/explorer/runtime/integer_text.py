"""Total decimal conversion for the model's mathematical INTEGER values.

Avoid Python's process-wide decimal digit limit without changing that limit.
Each builtin str call converts at most nine digits. Resource exhaustion still
propagates; it is never a proof of equality.
"""


def value_text(value):
    if type(value) is not int:
        return str(value)
    if value == 0:
        return '0'
    negative, number = value < 0, abs(value)
    chunks = []
    while number:
        number, remainder = divmod(number, 1_000_000_000)
        chunks.append(remainder)
    return ('-' if negative else '') + str(chunks[-1]) + ''.join(
        str(chunk).zfill(9) for chunk in reversed(chunks[:-1]))
