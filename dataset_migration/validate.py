"""Validate migrated GT scripts against service_list_ver2.0.4.json.

Checks every (skill, function|value) reference in each row's gt_new script
against the 2.0.4 catalog. Reports rows that reference non-existent services,
malformed syntax, or selector/connected_devices inconsistencies.

Usage:
    python3 validate.py [chunk_glob]
    python3 validate.py                                 # validates all chunk_*_migrated.json + dryrun
    python3 validate.py chunk_05_migrated.json          # single file
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG_PATH = "/home/gnltnwjstk/joi/files/service_list_ver2.0.4.json"

# ── Build catalog index ──────────────────────────────────────────────────────

def load_catalog():
    """Return {skill_lower: {functions: set, values: set, skill_id: str}}."""
    with open(CATALOG_PATH) as f:
        data = json.load(f)
    idx = {}
    for s in data['skills']:
        sid = s['id']
        idx[sid[0].lower() + sid[1:]] = {
            'skill_id': sid,
            'functions': {f['id'] for f in s.get('functions', [])},
            'function_lower': {f['id'][0].lower() + f['id'][1:] for f in s.get('functions', [])},
            'values': {v['id'] for v in s.get('values', [])},
            'value_lower': {v['id'][0].lower() + v['id'][1:] for v in s.get('values', [])},
        }
    return idx


# ── Extract (skill, member) refs from script ─────────────────────────────────

# Matches `(#sel...).<skill>_<member>` optionally followed by `(...)` or alone.
# Captures the dotted method/value name. We then split on the first underscore.
_REF_RE = re.compile(r'\)\s*\.\s*([a-z][A-Za-z0-9]*_[A-Za-z0-9_]+)')

# Matches selector tags inside (#A #B ...), all(#...), any(#...).
_SEL_RE = re.compile(r'\b(?:all|any)?\s*\(\s*((?:#[A-Za-z0-9_]+\s*)+)\)')


def extract_refs(script: str):
    """Return list of (skill_lower, member) tuples found in script."""
    refs = []
    for m in _REF_RE.finditer(script):
        compound = m.group(1)
        # Split on first underscore
        if '_' not in compound:
            continue
        skill, member = compound.split('_', 1)
        refs.append((skill, member))
    return refs


def extract_selectors(script: str):
    """Return list of tag tuples e.g. [('LivingRoom','Light'), ('Door',)]."""
    sels = []
    for m in _SEL_RE.finditer(script):
        tags = tuple(t.lstrip('#') for t in m.group(1).split())
        sels.append(tags)
    return sels


# ── Validate a single row ────────────────────────────────────────────────────

def validate_row(row, catalog):
    errors = []
    try:
        gt = json.loads(row['gt_new'])
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return [f"gt_new not valid JSON: {e}"]

    script = gt.get('script', '')
    if not script:
        return ["empty script"]

    # 1. Service refs
    for skill, member in extract_refs(script):
        if skill not in catalog:
            errors.append(f"unknown skill '{skill}' in '{skill}_{member}'")
            continue
        ent = catalog[skill]
        if member not in ent['function_lower'] and member not in ent['value_lower']:
            errors.append(
                f"{skill}_{member}: '{member}' not in skill {ent['skill_id']} "
                f"(funcs={sorted(ent['function_lower'])}, vals={sorted(ent['value_lower'])})"
            )

    # 2. Selector ↔ connected_devices consistency
    cd = row.get('connected_devices', {})
    if not isinstance(cd, dict) or not cd:
        errors.append("connected_devices missing or empty")
    else:
        # Schema check
        for dev_id, info in cd.items():
            if not isinstance(info, dict):
                errors.append(f"device '{dev_id}' info not a dict")
                continue
            if not isinstance(info.get('category'), list):
                errors.append(f"device '{dev_id}' category must be list")
            if not isinstance(info.get('tags'), list):
                errors.append(f"device '{dev_id}' tags must be list")

        # Each selector must match at least one device
        for tags in extract_selectors(script):
            matches = [
                dev_id for dev_id, info in cd.items()
                if isinstance(info.get('tags'), list)
                and all(t in info['tags'] for t in tags)
            ]
            if not matches:
                errors.append(f"selector ({' '.join('#'+t for t in tags)}) has no matching device in connected_devices")

    return errors


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    catalog = load_catalog()
    pattern = sys.argv[1] if len(sys.argv) > 1 else "chunk_*_migrated.json"
    if not pattern.startswith('/'):
        pattern = os.path.join(HERE, pattern)
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"No files matching {pattern}")
        sys.exit(1)

    total = 0
    bad = 0
    summary = defaultdict(list)
    for f in files:
        with open(f) as fh:
            rows = json.load(fh)
        for row in rows:
            total += 1
            errs = validate_row(row, catalog)
            if errs:
                bad += 1
                key = f"cat{row['category']}/idx{row['index']}"
                for e in errs:
                    summary[key].append(e)
                    print(f"[{os.path.basename(f)}] {key}: {e}")

    print()
    print(f"=== Summary: {total} rows, {bad} with issues, {total-bad} clean ===")
    if bad:
        # Failing row list for re-processing
        failing = sorted(summary.keys())
        out = os.path.join(HERE, "failing_rows.json")
        with open(out, 'w') as fh:
            json.dump({k: v for k, v in summary.items()}, fh, indent=2)
        print(f"Wrote {out} ({len(failing)} rows)")


if __name__ == '__main__':
    main()
