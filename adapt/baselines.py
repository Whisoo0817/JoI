"""Baseline B1 — naive interface-level slot substitution (eval stage ⑤).

The SO-middleware / IoTGPT move, faithfully reproduced: when the target home
lacks a device type, pick the present type with the most similar *interface*
(member names), rewrite the selector tags and rename the members — and change
NOTHING else. No effect-direction contracts, no temporal classes, no slicing,
no verification. B1 embodies exactly the interface-substitutability assumption
the six fault classes refute; the sweep measures where that assumption breaks.

Matching rules (deliberately name-level):
    exact member suffix shared (switch_on, temperature)         score 2
    both sides have a `set*Mode` member                         score 1
    both sides have some other setter / some value member       score 1
Ties break alphabetically. No candidate with score > 0 → the type stays
unmapped (dangling reference: an honest B1 deployment failure).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sim import expr as E

from adapt.effects import catalog_members
from adapt.patch import apply_edits
from adapt.structure import Structure, parse_errors


@dataclass
class B1Result:
    output: str
    type_map: Dict[str, str]            # old type -> new type ('' = unmapped)
    member_map: Dict[str, str]          # old raw member -> new raw member
    deployable: bool = False
    issues: List[str] = field(default_factory=list)


def _suffixes(type_: str) -> set:
    return {m.split(".", 1)[1] for m in catalog_members(type_)}


def _raw_member(type_: str, suffix: str, catalog: dict) -> str:
    """Rebuild the corpus-style raw member name (`fan_setFanMode`) for a
    canonical suffix, from the catalog's own casing."""
    svc = catalog.get(type_, {})
    prefix = type_[0].lower() + type_[1:]
    for kind in ("functions", "values"):
        for item in svc.get(kind, []):
            name = item if isinstance(item, str) else (item.get("name") or "")
            if name.lower() == suffix:
                return f"{prefix}_{name[0].lower()}{name[1:]}"
    return f"{prefix}_{suffix}"


def _value_types(type_: str, catalog: dict) -> Dict[str, str]:
    vals = (catalog.get(type_) or {}).get("values") or {}
    if isinstance(vals, dict):
        return {k.lower(): v for k, v in vals.items()}
    return {}


def _match_member(suffix: str, cand_sufs: set, want_type: Optional[str] = None,
                  cand_vtypes: Optional[Dict[str, str]] = None) -> Optional[str]:
    if suffix in cand_sufs:
        return suffix
    if suffix.startswith("set") and suffix.endswith("mode"):
        modes = sorted(s for s in cand_sufs if s.startswith("set") and s.endswith("mode"))
        if modes:
            return modes[0]
    if suffix.startswith("set"):
        setters = sorted(s for s in cand_sufs
                         if s.startswith("set") and not s.endswith("mode"))
        if setters:
            return setters[0]
    if not suffix.startswith("set"):
        # value read → a value member of the SAME declared type (BOOL reads
        # bind to BOOL providers — catalog-schema matching, no semantics)
        vals = sorted(s for s in cand_sufs if not s.startswith("set")
                      and s not in ("on", "off", "toggle", "switch"))
        if want_type and cand_vtypes is not None:
            typed = [s for s in vals if cand_vtypes.get(s) == want_type]
            return typed[0] if typed else None
        if vals:
            return vals[0]
    return None


def _score(used: set, cand_sufs: set, kind_match: bool,
           used_vtypes: Optional[Dict[str, str]] = None,
           cand_vtypes: Optional[Dict[str, str]] = None) -> int:
    sc = 0
    for s in used:
        m = _match_member(s, cand_sufs, (used_vtypes or {}).get(s), cand_vtypes)
        if m == s:
            sc += 2
        elif m is not None:
            sc += 1
    # interface-level kind similarity (a type with no functions is read-only,
    # i.e. sensor-shaped): read-only usage prefers read-only providers. Still
    # name/shape matching — no effect semantics involved.
    if sc and kind_match:
        sc += 1
    return sc


def b5_patch(src: str, st: Structure, env, catalog: dict) -> B1Result:
    """Baseline B5 — contract-less AST patcher: the SAME naive candidate
    selection as B1, applied through our typed-edit machinery (ReplaceSelector
    / ReplaceMember + splice verification). Structurally impeccable by
    construction — and exactly as contract-blind as B1. Its column is the
    thesis line as data: structure is preserved; correctness is not."""
    from adapt.patch import apply_and_check, replace_member, replace_tag

    type_map, member_map, issues = _plan_substitution(st, env, catalog)
    edits = []
    for old, new in type_map.items():
        if new and new != old:
            edits.extend(replace_tag(st, old, new))
    for sp in ("Office", "Meeting", "LivingRoom", "Home"):
        if sp not in env.spaces:
            edits.extend(replace_tag(st, sp, env.spaces[0]))
    inv_member = dict(member_map)
    for d in st.devices:
        if d.member in inv_member:
            edits.append(replace_member(d, inv_member[d.member]))

    res = B1Result("", type_map, member_map, issues=list(issues))
    unmapped = [t for t, n in type_map.items() if not n]
    for t in unmapped:
        res.issues.append(f"dangling type {t}")
    if unmapped:
        res.deployable = False
        return res
    pr = apply_and_check(st, edits)
    res.output = pr.output or ""
    if not pr.ok:
        res.issues.append(f"patch gate: {pr.summary[:80]}")
    res.deployable = pr.ok
    return res


_B3_SYSTEM = """You adapt a smart-home automation scenario to a different home.
You get the scenario source (a small reactive DSL — keep its syntax exactly as
you see it) and the target home's device inventory. Rewrite the WHOLE scenario
so it only references devices that exist in the target home, substituting the
closest available device where a referenced one is missing, and keeping all
behavior you are not forced to change. Output ONLY the rewritten source code,
no commentary, no code fences."""


_CODE_LINE = re.compile(
    r"(:=|\(#|^\s*(if|for|wait|delay|break|else)\b|^\s*[}{]\s*$|^\s*//)")


def _extract_code(text: str) -> str:
    """Cut leaked prose around the emitted program: keep the span from the
    first to the last code-looking line (the model sometimes narrates without
    a closing think tag; judging prose as a parse failure would be unfair
    to B3)."""
    lines = text.split("\n")
    idx = [i for i, ln in enumerate(lines)
           if _CODE_LINE.search(ln) and not ln.strip().startswith("```")]
    if not idx:
        return text
    return "\n".join(lines[idx[0]:idx[-1] + 1])


def b3_regen(src: str, env, catalog: dict, thinking: bool = False) -> "B1Result":
    """Baseline B3 — full LLM re-emission (the Cursor move): hand the model
    the source + target inventory and let it rewrite everything. Judged with
    the same machine checks as B1, plus what B1 cannot lose by construction:
    byte preservation of the code the adaptation had no reason to touch."""
    from adapt.llm import chat
    inv_lines = [f"  {d.id}: {d.type}"
                 f"{' @' + '/'.join(d.spaces) if d.spaces else ''}"
                 f"{' tags=' + ','.join(d.instance_tags) if d.instance_tags else ''}"
                 for d in env.devices]
    out = chat(f"target home devices:\n" + "\n".join(inv_lines)
               + f"\n\nscenario source:\n{src}", system=_B3_SYSTEM,
               max_tokens=8192, thinking=thinking)
    out = _extract_code(out)
    res = B1Result(out, {}, {})
    errs = parse_errors(out)
    if errs:
        res.issues.append(f"parse: {errs[0]}")
    present = env.types_present(online_only=False) | {"GlobalVariable", "Clock"}
    import re as _re
    dangling = sorted({t for t in _re.findall(r"#([A-Za-z_][A-Za-z0-9_]*)", out)
                       if t in catalog and t not in present})
    for t in dangling:
        res.issues.append(f"dangling type {t}")
    res.deployable = not errs and not dangling
    # byte-preservation: fraction of original lines that survive verbatim
    orig = [ln for ln in src.split("\n") if ln.strip()]
    got = set(ln.strip() for ln in out.split("\n"))
    res.type_map = {}
    res.member_map = {"_lines_preserved":
                      f"{sum(1 for ln in orig if ln.strip() in got)}/{len(orig)}"}
    return res


def _plan_substitution(st: Structure, env, catalog: dict):
    """The shared naive-candidate selection (interface/name matching only) —
    B1 applies it by raw text rewrite, B5 by typed AST edits."""
    present = sorted(env.types_present(online_only=False))
    used_types: Dict[str, set] = {}
    for d in st.devices:
        for tag in d.tags:
            if tag in catalog:
                svc_c, mem_c = E.canonical_key(tag, d.member)
                used_types.setdefault(tag, set()).add(mem_c)

    type_map: Dict[str, str] = {}
    member_map: Dict[str, str] = {}
    issues: List[str] = []
    for type_, used in sorted(used_types.items()):
        if type_ in present or type_ in ("GlobalVariable", "Clock"):
            type_map[type_] = type_
            continue
        reads_only = all(not s.startswith("set") and s not in ("on", "off", "toggle")
                         for s in used)
        used_vtypes = _value_types(type_, catalog)
        best, best_sc = "", 0
        for cand in present:
            if cand in ("Clock",):
                continue
            cand_readonly = not (catalog.get(cand) or {}).get("functions")
            sc = _score(used, _suffixes(cand),
                        kind_match=(reads_only == cand_readonly),
                        used_vtypes=used_vtypes,
                        cand_vtypes=_value_types(cand, catalog))
            if sc > best_sc:
                best, best_sc = cand, sc
        type_map[type_] = best
        if not best:
            issues.append(f"{type_}: no interface-similar type in {env.name}")
            continue
        cand_sufs = _suffixes(best)
        cand_vtypes = _value_types(best, catalog)
        for s in sorted(used):
            m = _match_member(s, cand_sufs, used_vtypes.get(s), cand_vtypes)
            if m is not None and m != s:
                member_map[_raw_member(type_, s, catalog)] = \
                    _raw_member(best, m, catalog)
    return type_map, member_map, issues


def b1_adapt(src: str, st: Structure, env, catalog: dict) -> B1Result:
    type_map, member_map, issues = _plan_substitution(st, env, catalog)

    # textual rewrite: tags, members, then foreign space tags
    out = src
    for old, new in type_map.items():
        if new and new != old:
            out = out.replace(f"#{old}", f"#{new}")
    for old, new in member_map.items():
        out = re.sub(rf"\b{re.escape(old)}\b", new, out)
    for sp in ("Office", "Meeting", "LivingRoom", "Home"):
        if sp not in env.spaces:
            out = out.replace(f"#{sp}", f"#{env.spaces[0]}")

    res = B1Result(out, type_map, member_map, issues=issues)

    errs = parse_errors(out)
    if errs:
        res.issues.append(f"parse: {errs[0]}")
    unmapped = [t for t, n in type_map.items() if not n]
    for t in unmapped:
        res.issues.append(f"dangling type {t}")
    res.deployable = not errs and not unmapped
    return res
