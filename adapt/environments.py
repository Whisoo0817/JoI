"""Synthetic environment inventories (eval stage ⑤).

A deterministic family of homes for the portability sweep. The first six are
hand-anchored single-axis adversaries — each one isolates one fault class the
naive baseline should trip over:

    env00  the base office (control: identity binding)
    env01  Fan instead of AirConditioner        → (a) effect/capability
    env02  Dehumidifier instead of Humidifier   → (d) polarity
    env03  MotionSensor instead of Presence     → (b) temporal class
    env04  3 temperature sensors                → (c) quantifier
    env05  no ToastPublisher                    → (f) essential loss

The rest are seeded random mixes of the same axes (device presence, counts,
alternative types, spaces, missing notifiers), so defect rates come from a
family, not six cherry-picked homes. Same seed → same family, always.
"""

from __future__ import annotations

import random
from typing import List

from adapt.inventory import DeviceInstance, Inventory


def _mk(env_id: str, spaces, spec) -> Inventory:
    devs: List[DeviceInstance] = []
    n = {}

    def add(type_, space=None, tags=()):
        n[type_] = n.get(type_, 0) + 1
        devs.append(DeviceInstance(f"{type_.lower()[:2]}{n[type_]}", type_,
                                   [space] if space else [],
                                   list(tags)))

    s0 = spaces[0]
    for _ in range(spec.get("n_aq", 1)):
        add("AirQualitySensor", s0)
    for _ in range(spec.get("n_ts", 1)):
        add("TemperatureSensor", s0)
    for _ in range(spec.get("n_hs", 1)):
        add("HumiditySensor", s0)
    if spec.get("cooling") == "ac":
        add("AirConditioner", s0)
    elif spec.get("cooling") == "fan":
        add("Fan", s0)
    if spec.get("humid") == "humidifier":
        add("Humidifier", s0)
    elif spec.get("humid") == "dehumidifier":
        add("Dehumidifier", s0)
    if spec.get("purifier", True):
        add("AirPurifier", s0)
    if spec.get("lights", True):
        add("Light", s0, ["CO2_Indicator"])
        add("Light", s0, ["Section1"])
    if spec.get("presence") == "level":
        add("PresenceSensor", s0, ["Section1"])
    elif spec.get("presence") == "pulse":
        add("MotionSensor", s0, ["Section1"])
    if spec.get("toast", True):
        add("ToastPublisher")
    if spec.get("camera", True):
        add("Camera", s0)
    if spec.get("email", True):
        add("EmailProvider")
    if spec.get("speaker", True):
        add("Speaker", s0)
    add("Clock")
    return Inventory(name=env_id, spaces=list(spaces), devices=devs)


_BASE = {"cooling": "ac", "humid": "humidifier", "presence": "level",
         "n_aq": 1, "n_ts": 1, "n_hs": 1}

_ANCHORS = [
    ("env00", dict(_BASE)),
    ("env01", dict(_BASE, cooling="fan")),
    ("env02", dict(_BASE, humid="dehumidifier")),
    ("env03", dict(_BASE, presence="pulse")),
    ("env04", dict(_BASE, n_ts=3)),
    ("env05", dict(_BASE, toast=False)),
]


def synthetic_envs(n: int = 24, seed: int = 7) -> List[Inventory]:
    rng = random.Random(seed)
    out = [_mk(eid, ["Office"], spec) for eid, spec in _ANCHORS]
    while len(out) < n:
        spec = {
            "cooling": rng.choice(["ac", "fan", "none"]),
            "humid": rng.choice(["humidifier", "dehumidifier", "none"]),
            "presence": rng.choice(["level", "pulse", "none"]),
            "n_aq": rng.randint(0, 2),
            "n_ts": rng.randint(0, 3),
            "n_hs": rng.randint(0, 2),
            "purifier": rng.random() < 0.7,
            "lights": rng.random() < 0.8,
            "toast": rng.random() < 0.8,
            "camera": rng.random() < 0.6,
            "email": rng.random() < 0.6,
            "speaker": rng.random() < 0.6,
        }
        spaces = ["Office"] if rng.random() < 0.6 else ["Office", "Meeting"]
        out.append(_mk(f"env{len(out):02d}", spaces, spec))
    return out
