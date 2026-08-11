# -*- coding: utf-8 -*-
"""Render a compact [Services] block for exactly the device categories a command owns.

Identical for every arm of E1 — it removes the artificial floor where the model has to
guess service names it was never shown. Only the categories in connected_devices are
included, so the block stays small (2-5 categories).
"""
import json, os

CATALOG = "/home/ikess/joi-llm/joi_new/files/service_list_ver2.0.7.json"
_CACHE = {}


def _skills(path=CATALOG):
    if path not in _CACHE:
        _CACHE[path] = {s["id"]: s for s in json.load(open(path))["skills"]}
    return _CACHE[path]


def categories_of(devices_str):
    """Ordered unique category list from a connected_devices JSON string."""
    try:
        dev = json.loads(devices_str, strict=False)
    except Exception:
        return []
    cats, seen = [], set()
    for _, meta in (dev.items() if isinstance(dev, dict) else []):
        for c in (meta or {}).get("category", []) or []:
            if c not in seen:
                seen.add(c); cats.append(c)
    return cats


def _fmt_type(v):
    t = v.get("type", "")
    if t == "ENUM" and v.get("format"):
        return f"ENUM:{v['format']}"
    return t


def render_category(cat, skills=None):
    skills = skills or _skills()
    s = skills.get(cat)
    if s is None:
        return f"{cat}: (unknown category)"
    lines = [f"{cat}:"]
    vals = s.get("values") or []
    if vals:
        lines.append("  attrs: " + ", ".join(f"{v['id']}({_fmt_type(v)})" for v in vals))
    fns = s.get("functions") or []
    if fns:
        parts = []
        for f in fns:
            args = ", ".join(f"{a['id']}:{_fmt_type(a)}" for a in (f.get("arguments") or []))
            parts.append(f"{f['id']}({args})")
        lines.append("  funcs: " + ", ".join(parts))
    for e in (s.get("enums") or []):
        name = e.get("id") or "enum"
        vs = [m.get("value") for m in (e.get("members") or []) if m.get("value") is not None]
        if vs:
            lines.append(f"  enum {name}: " + ", ".join(map(str, vs)))
    return "\n".join(lines)


def services_block(devices_str, extra=("Clock",)):
    """Compact [Services] text for the categories present, plus always-available ones."""
    skills = _skills()
    cats = categories_of(devices_str)
    for c in extra:
        if c in skills and c not in cats:
            cats.append(c)
    return "\n".join(render_category(c, skills) for c in cats)


def devices_and_services(devices_str):
    """The full environment block handed identically to every arm."""
    return f"[Devices]\n{devices_str.strip()}\n[Services]\n{services_block(devices_str)}"


if __name__ == "__main__":
    import csv
    rows = list(csv.DictReader(open("/home/ikess/joi-llm/joi_new/dataset.csv")))
    sizes = []
    for r in rows[:200]:
        d = r["connected_devices"]
        if not d.strip():
            continue
        blk = devices_and_services(d)
        sizes.append(len(blk))
    sizes.sort()
    print(f"env block chars: n={len(sizes)} min={sizes[0]} p50={sizes[len(sizes)//2]} "
          f"p90={sizes[int(len(sizes)*0.9)]} max={sizes[-1]}")
    print("\n--- example ---")
    print(devices_and_services(rows[3]["connected_devices"])[:2000])
