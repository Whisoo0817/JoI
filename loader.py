import os
import re
import json

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Service List (1회 로딩) ───────────────────────────────
_SERVICE_LIST_PATH = os.path.join(_BASE_DIR, "files/service_list_ver2.0.7.json")
try:
    with open(_SERVICE_LIST_PATH, 'r', encoding='utf-8') as f:
        _raw = json.load(f)
    # skills 배열 → { id: { descriptor, values, functions, enums_map } } dict
    SERVICE_DATA = {}
    for item in _raw.get("skills", []):
        dev_id = item["id"]
        enums_map = {
            e["id"]: [f"{m['value']} - {m['description']}" for m in e.get("members", [])]
            for e in item.get("enums", [])
        }
        SERVICE_DATA[dev_id] = {
            "descriptor": item.get("descriptor", ""),
            "values": item.get("values", []),
            "functions": item.get("functions", []),
            "enums_map": enums_map,
        }
except FileNotFoundError:
    print(f"Warning: {_SERVICE_LIST_PATH} not found.")
    SERVICE_DATA = {}

# ── Prompts (1회 로딩) ────────────────────────────────────
def _load_all_prompts(base_dir):
    prompts = {}
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f.endswith(".md"):
                prompts[f[:-3]] = open(os.path.join(root, f), "r", encoding='utf-8').read()
    return prompts

PROMPTS = _load_all_prompts(os.path.join(_BASE_DIR, "files"))


# ── Catalog sub-skill capability tags (single source of truth) ────────────
# Skills that are not standalone devices but capability mixins always attached
# to a parent device (e.g. Light has Switch + LevelControl + ColorControl).
# Pipeline stages that need to special-case these tags MUST import this set
# rather than re-defining it locally:
#   - joi/generate.py precision builder (filters sub-skill tags from
#     selectors unless the service prefix matches)
#   - pipeline_helpers.py _build_service_category_map (lets sub-skill categories
#     overwrite primary mappings for shared service names)
#   - files/mapping_device_match.md Rule 1 (rendered via {{SUB_SKILLS}})
SUB_SKILL_TAGS = {"Switch", "LevelControl", "ColorControl", "RotaryControl"}


def _render_sub_skills_inline(fmt: str) -> str:
    """Render SUB_SKILL_TAGS as a comma-separated inline list.

    fmt examples: '`{name}`' → ``Switch``, ``LevelControl``, ``ColorControl``, ``RotaryControl``
                  '`#{name}`' → ``#Switch``, ``#LevelControl``, ...
    Deterministic alphabetical order so prompt rendering is stable across runs.
    """
    return ", ".join(fmt.format(name=t) for t in sorted(SUB_SKILL_TAGS))


# Substitute placeholders in loaded prompts so the SUB_SKILL_TAGS set above is
# the single source of truth. Add new placeholders here if other catalog
# constants need the same treatment.
_PLACEHOLDERS = {
    "{{SUB_SKILLS}}":      _render_sub_skills_inline("`{name}`"),
    "{{SUB_SKILLS_HASH}}": _render_sub_skills_inline("`#{name}`"),
}
for _k in list(PROMPTS.keys()):
    _txt = PROMPTS[_k]
    for _ph, _val in _PLACEHOLDERS.items():
        if _ph in _txt:
            _txt = _txt.replace(_ph, _val)
    PROMPTS[_k] = _txt


# ── device_rules section split ───────────────────────────────
# Each device_rules_<cat>.md may contain optional stage-scoped hint sections
# introduced by a `# @<SectionName>` heading. Everything before the first such
# heading is the default ("service_plan") section. Other named sections are
# pulled by downstream stages on demand (e.g. arg_resolve grabs `arg_resolve`).
_SECTION_RE = re.compile(r'^# @(\w+)\s*$', re.MULTILINE)


def _norm_key(s: str) -> str:
    """Normalize a section key: lowercase, strip non-alphanumeric. So
    `ArgResolve`, `arg_resolve`, `arg-resolve`, and `argresolve` all map to
    `argresolve` and lookups are tolerant of casing/separator differences."""
    return re.sub(r'[^a-z0-9]', '', s.lower())


def _split_device_rules_sections(content: str) -> dict:
    sections = {_norm_key("service_plan"): ""}
    if not content:
        return sections
    matches = list(_SECTION_RE.finditer(content))
    if not matches:
        sections[_norm_key("service_plan")] = content.strip()
        return sections
    sections[_norm_key("service_plan")] = content[:matches[0].start()].strip()
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[m.end():end].strip()
        sections[_norm_key(m.group(1))] = body
    return sections


def get_device_rules_section(category: str, section: str = "service_plan") -> str:
    """Return a named section of `device_rules_<category>.md`.
    Default section "service_plan" is everything before any `# @Name` heading.
    Other named sections (e.g. "arg_resolve", "enum_resolve") are extracted by
    `# @<Name>` markers and returned as plain text (empty if absent).
    Lookup is case- and separator-insensitive: `# @ArgResolve` and
    `get_device_rules_section(..., "arg_resolve")` both resolve to the same
    section.
    """
    raw = PROMPTS.get(f"device_rules_{category.lower()}", "")
    return _split_device_rules_sections(raw).get(_norm_key(section), "")
