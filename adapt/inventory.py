"""Environment inventory + tag taxonomy (M-C ①).

A home is a set of device *instances*. Each instance carries JoI-style tags,
which the corpus uses on one flat plane; binding needs them classified:

    type tags      #AirConditioner, #TemperatureSensor  (device type = catalog id)
    space tags     #Office, #Home, #LivingRoom          (where the device is)
    instance tags  #CO2_Indicator, #Section1            (naming one device/group)
    marker tags    #NoneNecessary                       (policy markers)

Classification rules, in order:
1. a tag equal to a catalog service id  -> type
2. a tag the inventory declares a space -> space
3. everything else                      -> instance (safe default: instance tags
   restrict candidacy, so mis-classifying a space tag as instance can only make
   binding *more* conservative, never wrong)

The inventory also answers the two candidate queries stage ④ needs:
    instances_of(type)                and     instances_in(space)
plus availability (a dead device stays listed, marked offline — Problem 2's
trigger is exactly a transition of that flag).
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Iterable, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from sim.catalog import load_catalog  # noqa: E402

SPATIAL_MODES = ("same_space", "anywhere", "follows_user")


@dataclass
class DeviceInstance:
    id: str
    type: str                          # catalog service id (e.g. "AirConditioner")
    spaces: list[str]                  # space tags (e.g. ["Office"])
    instance_tags: list[str] = field(default_factory=list)
    online: bool = True

    @property
    def tags(self) -> list[str]:
        """The JoI selector tags this instance answers to."""
        return [self.type] + self.spaces + self.instance_tags


@dataclass
class Inventory:
    name: str
    spaces: list[str]
    devices: list[DeviceInstance]

    # -- taxonomy --------------------------------------------------------------

    def classify_tag(self, tag: str) -> str:
        cat = load_catalog()
        if tag in cat or tag.lower() in {k.lower() for k in cat} or tag == "GlobalVariable":
            return "type"
        if tag in self.spaces:
            return "space"
        return "instance"

    # -- candidate queries -----------------------------------------------------

    def instances_of(self, type_: str, *, online_only: bool = True) -> list[DeviceInstance]:
        return [d for d in self.devices
                if d.type == type_ and (d.online or not online_only)]

    def instances_in(self, space: str, *, online_only: bool = True) -> list[DeviceInstance]:
        return [d for d in self.devices
                if space in d.spaces and (d.online or not online_only)]

    def candidates(self, type_: str, *, space: Optional[str] = None,
                   spatial: str = "same_space",
                   instance_tags: Iterable[str] = (),
                   online_only: bool = True) -> list[DeviceInstance]:
        """Instances of `type_` that satisfy the spatial constraint and carry
        every required instance tag."""
        need = set(instance_tags)
        out = []
        for d in self.instances_of(type_, online_only=online_only):
            if spatial == "same_space" and space is not None and space not in d.spaces:
                continue
            if not need.issubset(set(d.instance_tags)):
                continue
            out.append(d)
        return out

    def set_online(self, device_id: str, online: bool) -> None:
        for d in self.devices:
            if d.id == device_id:
                d.online = online
                return
        raise KeyError(device_id)

    def types_present(self, *, online_only: bool = True) -> set[str]:
        return {d.type for d in self.devices if d.online or not online_only}


def from_dict(d: dict) -> Inventory:
    return Inventory(
        name=d.get("name", "home"),
        spaces=list(d.get("spaces", [])),
        devices=[DeviceInstance(id=x["id"], type=x["type"], spaces=list(x.get("spaces", [])),
                                instance_tags=list(x.get("instance_tags", [])),
                                online=x.get("online", True))
                 for x in d.get("devices", [])],
    )


def load_inventory(path: str) -> Inventory:
    with open(path, encoding="utf-8") as f:
        return from_dict(json.load(f))


# ── the base environment (the office the corpus was written for) ─────────────

def base_office() -> Inventory:
    """Inventory matching the hand-written corpus's own environment, inferred
    from the tags the scenarios use. One instance per (type, space) suffices for
    binding decisions; counts only matter for quantifier checks, which read the
    code's all()/any() and not the inventory."""
    mk = DeviceInstance
    devs = [
        mk("aq1", "AirQualitySensor", ["Office"]),
        mk("ts1", "TemperatureSensor", ["Office"]),
        mk("hs1", "HumiditySensor", ["Office"]),
        mk("ac1", "AirConditioner", ["Office"]),
        mk("hf1", "Humidifier", ["Office"]),
        mk("ap1", "AirPurifier", ["Office"]),
        mk("li1", "Light", ["Office"], ["CO2_Indicator"]),
        mk("li2", "Light", ["Office"], ["Section1"]),
        mk("ps1", "PresenceSensor", ["Office"], ["Section1"]),
        mk("tp1", "ToastPublisher", []),
        mk("cam1", "Camera", ["Office"]),
        mk("em1", "EmailProvider", []),
        mk("sp1", "Speaker", ["Office"]),
        mk("ck1", "Clock", []),
    ]
    return Inventory(name="base_office", spaces=["Office"], devices=devs)
