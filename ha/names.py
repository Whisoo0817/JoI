"""기기/속성 ↔ HA entity 이름 규칙 (profile 공용).

lower_ref(생성)와 ha_step(해석)가 같은 표를 쓰도록 한 곳에 모았다 —
이름 규칙은 의미론이 아니라 표기이므로 공유해도 맞검사가 깨지지 않는다.
규칙은 ha/README.md "명명 규칙" 절 참조.
"""

from __future__ import annotations

import json
import os
import re

_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(_DIR, "skill_map.json"), encoding="utf-8") as f:
    SKILLS: dict = json.load(f)["skills"]

# 속성 값 타입 (BOOL/DOUBLE/INTEGER/ENUM/STRING…) — 템플릿 렌더링에 사용
with open(os.path.join(_DIR, "..", "files", "service_list_ver2.0.7.json"),
          encoding="utf-8") as f:
    _cat = json.load(f)
ATTR_TYPE: dict[tuple[str, str], str] = {}
for _s in _cat["skills"]:
    for _v in _s.get("values", []):
        ATTR_TYPE[(_s["id"], _v["id"])] = _v.get("type", "")

# 능력 스킬(부모 기기에 붙는 부속) — entity domain은 주 스킬 것을 쓴다
SUB_SKILLS = {"Switch", "LevelControl", "ColorControl", "RotaryControl"}


def snake(s: str) -> str:
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", s)
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", s)
    return s.lower().replace("-", "_")


def primary_skill(categories: list[str]) -> str:
    for c in categories:
        if c not in SUB_SKILLS and c in SKILLS:
            return c
    return categories[0] if categories else ""


def device_entity(dev_id: str, categories: list[str]) -> str:
    p = primary_skill(categories)
    dom = SKILLS.get(p, {}).get("domain", snake(p or "device"))
    return f"{dom}.{snake(dev_id)}"


def numeric_attr(skill: str, attr: str) -> bool:
    return ATTR_TYPE.get((skill, attr)) in ("DOUBLE", "INTEGER")


class Tables:
    """행별 인벤토리로 만든 정/역 대응표.

    ent2dev:  기기 entity → (기기 id, 카테고리 목록)
    ent2attr: 속성 entity → (기기 id, 스킬, 속성)
    svc_of:   (기기 id, HA 서비스 이름) → (스킬, 메서드)
    """

    def __init__(self, devices: dict) -> None:
        self.devices = devices
        self.ent2dev: dict[str, tuple[str, list[str]]] = {}
        self.ent2attr: dict[str, tuple[str, str, str]] = {}
        self.svc_of: dict[tuple[str, str], tuple[str, str]] = {}
        self._attr_ent: dict[tuple[str, str, str], str] = {}
        for did, d in devices.items():
            cats = list(d.get("category") or [])
            self.ent2dev[device_entity(did, cats)] = (did, cats)
            for sk in cats:
                info = SKILLS.get(sk)
                if not info:
                    continue
                for m, ha_name in info["services"].items():
                    key = (did, ha_name)
                    if key in self.svc_of and self.svc_of[key] != (sk, m):
                        raise ValueError(f"서비스 이름 겹침: {key} "
                                         f"{self.svc_of[key]} vs {(sk, m)}")
                    self.svc_of[key] = (sk, m)
                for attr, dom in info["attrs"].items():
                    ent = f"{dom}.{snake(did)}_{snake(attr)}"
                    if ent in self.ent2attr and \
                            self.ent2attr[ent][1:] != (sk, attr):
                        ent = f"{dom}.{snake(did)}_{snake(sk)}_{snake(attr)}"
                    self.ent2attr[ent] = (did, sk, attr)
                    self._attr_ent[(did, sk, attr)] = ent

    def attr_entity(self, dev_id: str, skill: str, attr: str) -> str:
        return self._attr_ent[(dev_id, skill, attr)]

    def dev_entity(self, dev_id: str) -> str:
        cats = list(self.devices[dev_id].get("category") or [])
        return device_entity(dev_id, cats)

    def service(self, dev_id: str, skill: str, method: str) -> str:
        """호출 문자열 "domain.service" — domain은 기기의 주 스킬 것."""
        cats = list(self.devices[dev_id].get("category") or [])
        p = primary_skill(cats)
        dom = SKILLS.get(p, {}).get("domain", snake(p or "device"))
        name = SKILLS.get(skill, {}).get("services", {}).get(method,
                                                             snake(method))
        return f"{dom}.{name}"
