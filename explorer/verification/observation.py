"""D1 observation: ordered calls, unordered independent targets within a call.

The fanout boundary is execution metadata, not a device/service identifier.
Never infer parallelism merely from two actions sharing a timestamp.
"""
from explorer.runtime.interp import Unsupported


def freeze(value):
    if getattr(value, '_relational', False):
        from explorer.verification.state_key import freeze_state
        return ('relational', freeze_state(value))
    if getattr(value, '_smt', False):
        from explorer.verification.smt_values import SmtNumber, SmtText
        return ('number' if isinstance(value, SmtNumber) else
                'string' if isinstance(value, SmtText) else 'bool', value)
    if isinstance(value, dict):
        return ("dict", tuple(sorted((freeze(k), freeze(v)) for k, v in value.items())))
    if isinstance(value, list):
        return ("list", tuple(freeze(v) for v in value))
    if isinstance(value, tuple):
        return ("tuple", tuple(freeze(v) for v in value))
    if isinstance(value, set):
        return ("set", tuple(sorted(map(freeze, value), key=repr)))
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float)):
        return ("number", int(value) if isinstance(value, float) and value.is_integer() else value)
    if isinstance(value, str):
        return ("string", value)
    if value is None:
        return ("null",)
    return value


def actions_observation(actions):
    out, group = [], []
    expected = 0
    for action in actions:
        signature = (action.service, action.method, freeze(action.args),
                     tuple(action.target))
        mark = action.fanout
        if mark is None:
            if group:
                raise Unsupported("interrupted ACTION fanout")
            out.append((signature,))
            continue
        index, size = mark
        if size < 2 or index != len(group) or (group and expected != size):
            raise Unsupported("invalid ACTION fanout boundary")
        expected = size
        group.append(signature)
        if len(group) == size:
            # Keep order on a shared concrete device, including overlapping
            # selectors; commute only the independent device chains.
            chains = {}
            for item in group:
                if len(item[3]) != 1:
                    raise Unsupported("fanout needs concrete device IDs")
                chains.setdefault(item[3], []).append(item)
            out.append(tuple(item for target in sorted(chains, key=repr)
                             for item in chains[target]))
            group = []
    if group:
        raise Unsupported("incomplete ACTION fanout")
    return tuple(out)
