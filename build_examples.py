# -*- coding: utf-8 -*-
"""코퍼스 예문 다시 만들기 — 5k 학습 몫으로 assets/examples.json 을 채운다.

매핑은 서비스마다 두 가지로 점수를 낸다.
  ① 문서 유사도 — 서비스 설명·한국어 표현(effects.json)과 절이 얼마나 닮았나
  ② 예문 유사도 — 그 서비스를 실제로 부른 절(examples.json)과 얼마나 닮았나
②가 훨씬 세다. 사람이 쓰는 말과 서비스 설명은 생김새가 다르기 때문이다.

옛 예문 766개는 옛 377행에서 나왔다. 여기서는 **5k 학습 몫**(split_5k.json)의
정답 IR 과 절 라벨(labels_5k.json)로 다시 만든다. 시험 몫은 절대 넣지 않는다 —
넣으면 시험이 무의미해진다.

    ~/temp/bin/python build_examples.py --dry     # 몇 건이 재료가 되는지만
    ~/temp/bin/python build_examples.py
"""
import argparse
import collections
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

ENGINE_URL = "http://localhost:49998"
LABELS = os.path.join(HERE, "bench", "labels_5k.json")
SPLIT = os.path.join(HERE, "bench", "split_5k.json")
DATA = os.path.join(HERE, "bench", "dataset_5k.csv")


def use_engine_server(url=None):
    import urllib.request
    url = url or os.environ.get("JOI_ENGINE_URL") or ENGINE_URL
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/health", timeout=1.5) as r:
            if r.status != 200:
                return False
    except Exception:                                  # noqa: BLE001
        return False
    os.environ["JOI_ENGINE_URL"] = url
    return True


def material():
    """정답 IR 이 있는 행 (--train-only 면 학습 몫만) → build_examples 가 받는 모양."""
    split = json.load(open(SPLIT, encoding="utf-8"))
    train = set(split["학습"]) if "--train-only" in sys.argv else None
    ir = {r["id"]: r["ir_gt"] for r in csv.DictReader(open(DATA, encoding="utf-8"))}
    out, gold = [], {}
    for i, o in enumerate(json.load(open(LABELS, encoding="utf-8"))):
        if (train is not None and o["id"] not in train) or not ir.get(o["id"]):
            continue
        out.append({"i": i, "cmd": o["cmd"],
                    "segments": [{"text": c["글"], "type": c["종류"], "mods": c["mods"]}
                                 for c in o["절"]]})
        gold[i] = json.loads(ir[o["id"]])
    return out, gold


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    labels, gold = material()
    print(f"{'학습 몫' if '--train-only' in sys.argv else '전부'} 중 정답 IR 이 있는 행: {len(labels)}")
    print("  절 종류:", dict(collections.Counter(
        s["type"] for o in labels for s in o["segments"]).most_common()))
    if args.dry:
        return 0

    if not use_engine_server():
        print("엔진 서버가 없다 — engine_server.py 를 먼저 띄워라")
        return 1
    from joi_slm.encoder import make_embedder
    from joi_slm.mapping import build_examples

    ex = build_examples(labels, lambda o: gold.get(o["i"]), make_embedder())
    print(f"\nexamples.json — 예문 {len(ex)}개 / 서비스 {len({e['svc'] for e in ex})}종")
    print("  많이 나온 서비스:", collections.Counter(e["svc"] for e in ex).most_common(6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
