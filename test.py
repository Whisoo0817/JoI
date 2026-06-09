"""Interactive CLI for testing generate_joi_code without web frontend or joi-agent.

Usage:
    python3 test.py                                  # interactive REPL
    python3 test.py "오후 3시마다 조명을 켜줘"        # one-shot
"""

import json
import sys
from datetime import datetime

import requests

APP_URL = "http://192.168.0.250:49999/generate_joi_code"

DEVICES = {
    "tc0_af37207d-f2f2-447f-8006-f1e030755e65": {
        "category": ["MultiButton"],
        "tags": ["PhilipsHue", "DimmerSwitch", "MultiButton"],
    },
    "tc0_5452b6c5-0dee-4cca-ba6f-15582b358305": {
        "category": ["Switch", "Light"],
        "tags": ["PhilipsHue", "Light", "Switch"],
    },
    "tc0_9fe5d8b9-9ebc-4203-9963-497546c9740d": {
        "category": ["Switch", "Light"],
        "tags": ["PhilipsHue", "Light", "Switch"],
    },
    "tc0_7def1d9d-721c-4e35-b217-51fb8b46ba59": {
        "category": ["Switch", "Light"],
        "tags": ["PhilipsHue", "Light", "Switch"],
    },
    "tc0_a2e7594e-aced-4e03-a25e-841aa7315614": {
        "category": ["Switch", "Light"],
        "tags": ["PhilipsHue", "Light", "Switch"],
    },
    "tc0_ebf02f5cfcd67e4ce4bexu": {
        "category": ["Switch", "AirConditioner", "TemperatureSensor"],
        "tags": ["Hejhome", "AirConditioner", "Switch", "TemperatureSensor"],
    },
    "tc0_eba69f1846b797f9a72gis": {
        "category": ["Switch"],
        "tags": ["Hejhome", "Siren", "Switch"],
    },
    "tc0_ebd382239e6a6e4a29lccz": {
        "category": ["Switch"],
        "tags": ["Hejhome", "Switch"],
    },
    "tc0_plug_001": {
        "category": ["Switch", "Plug"],
        "tags": ["Hejhome", "Plug", "Switch"],
    },
    "tc0_plug_002": {
        "category": ["Switch", "Plug"],
        "tags": ["Hejhome", "Plug", "Switch"],
    },
}


def call(sentence: str) -> None:
    payload = {
        "sentence": sentence,
        "model": "joi",
        "current_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "connected_devices": DEVICES,
    }
    try:
        resp = requests.post(APP_URL, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[request error] {e}")
        return

    if not data.get("success"):
        print(f"[error {data.get('error_code')}] {data.get('error_message')}")
        return

    print(f"\ntranslated : {data['log'].get('translated_sentence', '')}")
    print(f"time       : {data['log'].get('response_time', '')}")
    print()
    for item in data.get("code", []):
        print(f"name  : {item.get('name', '')}")
        print(f"cron  : {item.get('cron', '') or '-'}")
        print(f"period: {item.get('period', '')}")
        print(f"code  : {item.get('code', '')}")
        print()


def repl() -> None:
    print("joi code gen CLI — type a command, /quit to exit.")
    while True:
        try:
            sentence = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not sentence:
            continue
        if sentence in ("/quit", "/exit"):
            return
        call(sentence)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        call(" ".join(sys.argv[1:]))
    else:
        repl()
