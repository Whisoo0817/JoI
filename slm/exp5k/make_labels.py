# -*- coding: utf-8 -*-
"""5k 절 라벨 → 옛 학습 코드가 읽는 모양으로 옮긴다.

joi_slm/heads.py 의 train_seg_heads(exp_dir) 는
  <exp_dir>/type/type_labels.json  (i, cmd, words, gold_labels, segments[{type, mods}])
  <exp_dir>/head/states.npz        (2B 단어 상태)
두 개를 읽는다. 여기서는 앞엣것을 만든다. 뒤엣것은 extract_states.py 가 만든다.

기본은 **전부** 담는다 — 서비스로 쓸 것이라 데이터를 아낄 까닭이 없다 (whisoo 2026-08-25).
논문용으로 일반화를 재려면 --train-only 로 학습 몫만 담는다 (bench/split_5k.json).
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

labels = json.load(open(os.path.join(ROOT, "bench", "labels_5k.json"), encoding="utf-8"))
only_train = "--train-only" in sys.argv
train = set(json.load(open(os.path.join(ROOT, "bench", "split_5k.json"), encoding="utf-8"))["학습"])

out = []
for o in labels:
    if only_train and o["id"] not in train:
        continue
    out.append({"i": len(out), "id": o["id"], "cmd": o["cmd"], "words": o["words"],
                "labels": o["gold_labels"], "gold_labels": o["gold_labels"],
                "segments": [{"text": c["글"], "type": c["종류"], "mods": c["mods"]}
                             for c in o["절"]]})

json.dump(out, open(os.path.join(HERE, "type", "type_labels.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
json.dump(out, open(os.path.join(HERE, "head", "labels.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print(f"{'학습 몫' if only_train else '전부'} 절 라벨 {len(out)}행 → slm/exp5k/{{type,head}}/")
import collections
print("  절 종류:", dict(collections.Counter(s["type"] for o in out for s in o["segments"]).most_common()))
print("  mods:", dict(collections.Counter(m for o in out for s in o["segments"] for m in s["mods"]).most_common()))
