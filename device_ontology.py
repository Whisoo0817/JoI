"""Deterministic device-targeting helpers for the device-first pipeline.

Pure functions shared by the targeting stages (no LLM, no I/O):
  - parse_targets      : <targets> block text → structured target groups
  - minimal_tags_for   : matched devices → the tightest selector tag(s)
  - quantifier_for     : (scope, role, count) → all/any/'' prefix
  - _CHANNEL_CATEGORY  : notify channel → realizing category
"""

import re
from itertools import combinations


# Notification channels → the category that realizes each.
_CHANNEL_CATEGORY = {"speaker": "Speaker", "toast": "ToastPublisher"}


def minimal_tags_for(matched, cd):
    """Given a set of matched device keys and the device dict {key:{category,tags}},
    return (tags, exact): the SMALLEST list of (clean, real) tags whose intersection
    selects those devices, and whether it selects EXACTLY them.

    The candidate tags are the devices' COMMON tags (a tag missing from any matched
    device can't be used — it would drop that device), minus noise: per-device real
    ids and infra tags all start with `tc0_`, and `NoneNecessary` is filler. We then
    pick the fewest tags (smallest first) whose intersection over ALL devices equals
    the matched set — so "거실에 조명뿐" yields `[LivingRoom]`, while a mixed room
    yields `[LivingRoom, Light]`, and `hue 조명` yields `[PhilipsHue, Light]`.

    Returns ([], False) when no semantic-tag combo isolates the set (e.g. one of two
    devices that differ only by id) — the caller then selects by the device id alias.
    """
    M = set(matched)
    if not M:
        return ([], False)

    def tags_of(k):
        d = cd.get(k, {})
        return set(d.get("category", [])) | set(d.get("tags", []))

    common = set.intersection(*(tags_of(k) for k in M))
    cands = [t for t in common
             if not str(t).startswith("tc0_")     # drops real ids + infra tags
             and t != "NoneNecessary"]
    # de-prioritize generic power tags so a meaningful tag is chosen at equal size
    cands.sort(key=lambda t: (t in ("Switch", "Matter"), str(t)))

    def select(T):
        T = set(T)
        return {k for k in cd if T <= tags_of(k)}

    for size in range(1, len(cands) + 1):
        for combo in combinations(cands, size):
            if select(combo) == M:
                return (list(combo), True)
    # No tag combo isolates the set exactly. For ONE device the caller selects by
    # its id alias (returning the candidate tags would over-select its siblings).
    # For a GROUP, fall back to the tightest common tags (a valid intersection,
    # possibly a superset) — never an id-join of distinct ids, which selects none.
    if len(M) == 1:
        return ([], False)
    return (cands, False)


def _norm(s):
    return re.sub(r'\s+', '', str(s)).lower()


def resolve_criterion(expr, cd):
    """Parse a grounding criterion into OR-groups of matched device keys.

    Grammar (emitted by the ground_targets LLM): tokens joined by `+` (intersection,
    AND) within a group, groups joined by `;` (union, separate clusters). A token is
    a label matched against a device's category ∪ tags, or `nickname:<name>`.
      "Tuya"                  → [[all Tuya devices]]
      "LivingRoom + Light"    → [[devices with BOTH LivingRoom and Light]]
      "Light ; LightSwitch"   → [[Light devices], [LightSwitch devices]]  (2 clusters)
      "nickname:삼성 …"        → [[that one device]]
    Returns a list of OR-groups (each a sorted list of device keys); empty groups
    are dropped, so an all-miss criterion returns [].
    """
    def labels_of(k):
        d = cd.get(k, {})
        return set(d.get("category", [])) | set(d.get("tags", []))

    out = []
    for orpart in str(expr).split(';'):
        toks = [t.strip() for t in orpart.split('+') if t.strip()]
        if not toks:
            continue
        ids = None
        for tok in toks:
            if tok.lower().startswith('nickname:'):
                want = _norm(tok.split(':', 1)[1])
                match = {k for k in cd if want and (
                    want == _norm(cd[k].get("nickname", "")) or
                    want in _norm(cd[k].get("nickname", "")) or
                    _norm(cd[k].get("nickname", "")) in want)}
            else:
                want = _norm(tok)
                match = {k for k in cd if any(_norm(x) == want for x in labels_of(k))}
            ids = match if ids is None else (ids & match)
        if ids:
            out.append(sorted(ids))
    return out


def parse_targets(block: str) -> list:
    """Parse a <targets> block body into [{role, by_kind, by_val, scope}].
    Tolerant of spacing; ignores non-matching lines."""
    out = []
    for ln in (block or "").splitlines():
        ln = ln.strip().lstrip("-").strip()
        if not ln or "by=" not in ln:
            continue
        role_m = re.search(r'role\s*=\s*(\w+)', ln)
        scope_m = re.search(r'scope\s*=\s*(\w+)', ln)
        # by= must stop at the next " | " so it doesn't swallow "| scope=..."
        by_m = re.search(r'by\s*=\s*([a-zA-Z]+)\s*:\s*([^|]+)', ln)
        if not by_m:
            continue
        out.append({
            "role": (role_m.group(1).strip().lower() if role_m else "action"),
            "by_kind": by_m.group(1).strip().lower(),     # label | channel
            "by_val": by_m.group(2).strip(),
            "scope": (scope_m.group(1).strip().lower() if scope_m else "auto"),  # all|any|one|auto
        })
    return out


def quantifier_for(scope: str, role: str, n: int) -> str:
    """Deterministic quantifier prefix: '', 'all', or 'any'.

    Rule: an EXPLICIT user quantity word wins verbatim; only `auto` (no quantity
    word in the command) falls back to (count, role).
      explicit `all`  (모두/전부/다/모든/전체) → 'all'  (condition → all-satisfy `==`)
      explicit `any`  (하나라도/적어도 하나)    → 'any'  (condition → any-satisfy `==|`)
      explicit `one`  (하나만/하나/한 개)       → ''     (no prefix → runtime picks 1)
      auto: n<=1 → '' (one); role==condition → 'any'; else → 'all'
    """
    if scope == "all":
        return "all"
    if scope == "any":
        return "any"
    if scope == "one":
        return ""
    # auto / unspecified — decide from match count + role
    if n <= 1:
        return ""
    if role == "condition":
        return "any"
    return "all"
