"""D1 observation: ordered calls, unordered independent targets within a call.

The fanout boundary is execution metadata, not a device/service identifier.
Never infer parallelism merely from two actions sharing a timestamp.

Binding decision (whisoo 2026-09-14, E2 BINDING_DECISION B2): when the prepared
pair carries the IR binding's multi-device sets, consecutive calls with the
same (service, method, concrete args) whose targets all lie in one such set are
one observation unit whose target is the device set. A call the binding splits
over devices is then equal whether the JoI wrote one fan-out or several lines.
Calls on different sets, single-device sets or non-consecutive calls keep their
order and multiplicity. Without binding sets the observation is unchanged.
"""
import contextlib
import contextvars

from explorer.runtime.interp import Unsupported

_MERGE_SETS = contextvars.ContextVar("vets_observation_merge_sets", default=())


def merge_sets_of(*runners):
    """Multi-device binding sets attached by prepare_pair, or None."""
    for runner in runners:
        sets = getattr(runner, "observation_sets", None)
        if sets:
            return tuple(sets)
    return None


@contextlib.contextmanager
def observation_scope(*runners):
    """Apply the runners' binding sets to every observation inside the block."""
    sets = merge_sets_of(*runners)
    if sets is None:
        yield
        return
    token = _MERGE_SETS.set(sets)
    try:
        yield
    finally:
        _MERGE_SETS.reset(token)


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


def _concrete(value):
    """True when equality of the value is a plain Python fact (no SMT/relational term)."""
    if getattr(value, '_smt', False) or getattr(value, '_relational', False):
        return False
    if isinstance(value, dict):
        return all(_concrete(k) and _concrete(v) for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return all(_concrete(v) for v in value)
    return True


def actions_observation(actions, merge_sets=None):
    out, group, flags, group_ok = [], [], [], True
    expected = 0
    for action in actions:
        signature = (action.service, action.method, freeze(action.args),
                     tuple(action.target))
        ok = _concrete(action.args)
        mark = action.fanout
        if mark is None:
            if group:
                raise Unsupported("interrupted ACTION fanout")
            out.append((signature,))
            flags.append(ok)
            continue
        index, size = mark
        if size < 2 or index != len(group) or (group and expected != size):
            raise Unsupported("invalid ACTION fanout boundary")
        expected = size
        group.append(signature)
        group_ok = group_ok and ok
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
            flags.append(group_ok)
            group, group_ok = [], True
    if group:
        raise Unsupported("incomplete ACTION fanout")
    sets = _MERGE_SETS.get() if merge_sets is None else tuple(merge_sets)
    if not sets:
        return tuple(out)
    return _merge_binding_units(out, flags, sets)


def _plain(value):
    """True when a frozen value holds only plain Python data (no symbolic term)."""
    if isinstance(value, tuple):
        return all(_plain(v) for v in value)
    return value is None or isinstance(value, (str, int, float, bool))


def _merge_binding_units(groups, flags, sets):
    """B2: merge consecutive same-call groups whose devices lie in one binding set.

    One fan-out group comes from one call, so its devices share one argument value
    even when that value is symbolic. Separate groups join a run only when their
    arguments are plain and equal; symbolic arguments of separate calls never join.
    The unit's target is that binding set when exactly one set fits (so a selector
    naming only part of the bound devices is not a difference), otherwise the devices
    actually called. The unit repeats k times, k = the largest number of calls on one
    device in the run, so a duplicated call stays observable.
    """
    result, run = [], None

    def flush():
        nonlocal run
        if run is not None:
            service, method, args = run["out"]
            if len(run["sets"]) == 1:
                target = tuple(sorted(sets[next(iter(run["sets"]))], key=repr))
            else:
                target = tuple(sorted(run["counts"], key=repr))
            result.append(((service, method, args, target),) * max(run["counts"].values()))
            run = None

    for group in groups:
        info = None
        if group and all(len(sig[3]) == 1 for sig in group) and len({sig[:2] for sig in group}) == 1:
            plain = all(_plain(sig[2]) for sig in group)
            if not plain or len({sig[2] for sig in group}) == 1:
                devices = [sig[3][0] for sig in group]
                candidates = {i for i, s in enumerate(sets) if len(s) >= 2 and set(devices) <= s}
                if candidates:
                    info = (group[0][:3], plain, candidates, devices)
        if info is None:
            flush()
            result.append(group)
            continue
        out, plain, candidates, devices = info
        joins = (run is not None and plain and run["plain"] and run["out"] == out
                 and bool(run["sets"] & candidates))
        if not joins:
            flush()
            run = {"out": out, "plain": plain, "sets": set(candidates), "counts": {}}
        run["sets"] &= candidates
        for device in devices:
            run["counts"][device] = run["counts"].get(device, 0) + 1
    flush()
    return tuple(result)
