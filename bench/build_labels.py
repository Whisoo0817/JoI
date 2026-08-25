#!/usr/bin/env python3
"""절 라벨 뽑개 — 5k 한국어 문장에 "어디서 절이 갈리고 무슨 절인가" 를 붙인다.

왜 프로그램으로 뽑나
  옛 라벨 411개는 사람이 문장마다 손으로 나눈 것이다. 5k 는 우리가 틀에서 조립했으니
  어느 조각이 어디에 들어갔는지 이미 안다. 그래서 **틀 하나에 한 번만** 적으면
  그 틀을 쓴 문장 전부에 붙는다 — 5,578번이 아니라 스무 번 남짓이다.

절 종류 (옛 라벨 관례를 따른다)
  TRIG  센서·사건        "버튼이 눌리면"
  TIME  시각·주기        "10분마다", "저녁 7시에"
  COND  값 조건          "온도가 30도를 넘으면"
  ACT   시키는 일        "거실 조명 켜"
  DELAY 뒤에             "5분 뒤에"
  READ  확인해서
  STOP  멈춰

우리가 옛 관례에서 바꾼 것 하나 (whisoo 2026-08-24)
  "1시간마다" 는 **따로 뗀다.** 옛 라벨은 동작절 안에 넣고 mods 로만 표시했는데
  ("1시간마다 문을 열었다 닫았다 반복해줘." 한 덩어리), "10분마다 확인해서" 는
  이미 따로 떼고 있어서 앞뒤가 안 맞았다. 주기 표현은 늘 제 절로 선다.

    python bench/build_labels.py           # → labels_5k.json
    python bench/build_labels.py --show 5  # 몇 개 찍어 보기
"""
import argparse
import collections
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ir as IR         # noqa: E402
import korean as K       # noqa: E402
import templates as T    # noqa: E402

# 시간절 중 "이미 그런 상태이면" 을 뜻하는 틀 — 정답 IR 이 edge 를 none 으로 둔 것들.
# ("창문이 열린 채로 있으면", "아무도 없는 동안" …) 나머지는 그 일이 벌어지는 순간(rising)이다.
# 손으로 적지 않고 정답 IR 에서 그대로 읽어 온다.
STATE_TRIG = {k for k, v in IR.TRIG_IR.items() if "'edge': 'none'" in str(v)}

OUT = os.path.join(HERE, "labels_5k.json")

PLACE = {"{a}", "{a_c}", "{cond}", "{cond_while}", "{cond_until}", "{cond_q}",
         "{cond_when}", "{cond_only}"}
SPLIT = re.compile(
    r"(\{(?:a_c|a|cond_while|cond_until|cond_q|cond_only|cond_when|cond)\})")

# ── 로직 틀의 글자 조각 → (절 종류, mods) ──────────────────────────────
# 20종뿐이다. 새 조각이 생기면 검산이 잡는다.
CHUNK = {
    "{n}분마다":                      ("TIME",  ["every"]),
    "{n}분마다 확인해서":              ("TIME",  ["every", "read"]),
    "그때부터 {n}분마다":              ("TIME",  ["every"]),
    "앞으로 {m}시간 동안 {n}분마다":    ("TIME",  ["every", "sustain"]),
    "기다렸다가 {m}시간 동안 {n}분마다": ("TIME",  ["every", "sustain"]),
    "{m}시간 뒤에는 멈춰":             ("STOP",  ["sustain"]),
    "{n}분 기다렸다가":                ("DELAY", ["delay"]),
    "{n}분 뒤에 다시 꺼":              ("ACT",   ["delay", "repeat"]),
    "{n}분 쉬는 걸 {m}번 반복해":      ("ACT",   ["repeat", "count"]),
    "최대 {n}분 기다려 보고, 그래도 아니면": ("TIME",  ["sustain"]),
    "계속":                           ("READ",  ["read"]),
    "그러다 바뀌면 멈춰":              ("STOP",  []),
    "그 횟수를 세다가 {m}번을 넘으면":   ("COND", ["count"]),
    "그게 한 시간 전보다 높으면":      ("COND",  ["read"]),
    "그게 어제 같은 시각보다 올랐으면": ("COND",  ["read"]),
}

# 시간절이 시각인가 사건인가 — 시나리오의 방아쇠 종류로 가른다
# 해·일몰·일출은 시계가 아니라 **바깥 상태**다 — 정답 IR 도 cron 앵커가 아니라
# SunProvider 를 기다리는 wait 마디다(bench/ir.py SUN_DOWN/SUN_UP). TIME 으로 두면
# 조립기가 시계 길로 보내고, 시각 문구가 없어 절이 통째로 사라진다.
TIME_TRIGS = {"time", "timer"}


def chunk_label(text):
    """글자 조각 → (종류, mods). 숫자가 박힌 뒤라도 틀 모양으로 되찾는다."""
    key = re.sub(r"\d+", "{n}", text.strip(" ,"))
    if key in CHUNK:
        return CHUNK[key]
    for k in CHUNK:                      # {m} 자리도 숫자로 바뀌었을 수 있다
        if re.sub(r"\{[nm]\}", "{n}", k) == key:
            return CHUNK[k]
    return None


def read_needed(part, row):
    """이 행의 ACT 절이 "센서값을 읽어서 알려주는" 절인가.

    "욕실 온도 보내 줘" 는 두 수다 — 온도를 읽고, 그 값을 말한다. 그런데 말에는
    "확인해서" 같은 표시가 없어서 옛 라벨은 read 를 안 붙였고, 조립기는 알 방법이
    없어 호출 한 번으로 냈다. 손으로 적지 않고 **정답 IR 에 read 마디가 있는지**로 안다.
    로직 틀이 있는 행(세다가·오늘 몇 번…)은 건드리지 않는다 — 거기 read 는 틀이
    스스로 넣는 것이라 ACT 절의 몫이 아니다.
    """
    return not part["frame"] and '"op": "read"' in (row.get("ir_gt") or "")


def pulse_needed(part, row):
    """이 행의 ACT 절이 "잠깐 켰다가 끄는" 절인가.

    "선풍기 3분 동안 돌려" 는 세 수다 — 켜고, 3분 기다리고, 끈다. 말에는 "동안"
    밖에 없어서 옛 라벨은 아무 표시도 안 붙였고, 조립기는 호출 한 번으로 냈다.
    손으로 낱말표를 적지 않고 **정답 IR 이 call → delay → call 로 되어 있는지**로
    안다. "동안"이 있어도 세 수가 아닌 행이 30개나 되므로 말만 보면 안 된다.
    ACT 절이 둘인 행("…켜 주고, 5분 뒤에 다시 꺼")은 뺀다 — 거기 지연은 뒤 절의
    몫이고 이미 delay 표시가 붙어 있다. 로직 틀이 있는 행도 뺀다.
    """
    if part["frame"] or sum(1 for _, k, _ in part["ko_parts"] if k in ("{a}", "{a_c}")) != 1:
        return False
    try:
        ops = [x.get("op") for x in json.loads(row.get("ir_gt") or "{}").get("timeline", [])]
    except Exception:                                   # noqa: BLE001
        return False
    return any(ops[k:k + 3] == ["call", "delay", "call"] for k in range(len(ops) - 2))


def segs_of(part, row):
    """행 하나 → 절 목록. 조각(ko_parts)이 문장을 이룬 순서 그대로다.
    → [{"글", "종류", "mods", "단어수"}] 또는 ("모르는 조각", 글) 또는 None"""
    out = []
    for nw, kind, text in part["ko_parts"]:
        if kind == "{trig}":
            t, mods = ("TIME" if row["trig"] in TIME_TRIGS else "TRIG"), []
            if part["trig"] in STATE_TRIG:
                mods = ["state"]      # 벌어지는 순간이 아니라 이미 그런 상태
        elif kind in ("{a}", "{a_c}"):
            t, mods = "ACT", []
            if read_needed(part, row): mods.append("read")
            if pulse_needed(part, row): mods.append("pulse")
        elif kind in PLACE:
            t, mods = "COND", []
        else:
            lab = chunk_label(text)
            if lab is None:
                return ("모르는 조각", text)
            t, mods = lab[0], list(lab[1])
        out.append({"글": text, "종류": t, "mods": mods, "단어수": nw})
    return out or None


def boundaries(segs, n_words):
    """절 목록 → 단어마다 0/1. 1 이 새 절이 시작하는 단어다.
    말투가 뒤에 붙인 단어("주세요.")는 마지막 절 몫이다."""
    lab, i = [0] * n_words, 0
    for k, s in enumerate(segs):
        if i >= n_words:
            return None                      # 조각이 문장보다 길다 — 이 행은 버린다
        if k:
            lab[i] = 1
        i += s["단어수"]
    if i > n_words:
        return None
    return lab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=0)
    args = ap.parse_args()

    parts = {p["id"]: p for p in json.load(open(os.path.join(HERE, "parts_5k.json"),
                                               encoding="utf-8"))}
    rows = list(csv.DictReader(open(os.path.join(HERE, "dataset_5k.csv"), encoding="utf-8")))

    out, skip, unknown = [], collections.Counter(), collections.Counter()
    for r in rows:
        p = parts.get(r["id"])
        if p is None:
            skip["U행(틀이 없다)"] += 1
            continue
        s = segs_of(p, r)
        if s is None:
            skip["한국어 틀 없음"] += 1
            continue
        if isinstance(s, tuple):
            unknown[s[1]] += 1
            continue
        words = r["command_ko"].split()
        lab = boundaries(s, len(words))
        if lab is None:
            skip["조각이 문장과 안 맞음"] += 1
            continue
        # 절 글은 **실제 문장에서 잘라** 담는다. 조립할 때 뽑은 글은 말투가 붙기 전
        # 모습이라("…멈춰" → "…멈춰 주세요.") 문장과 글자가 다르다. 자르는 자리는
        # 같으니 자리로 잘라 오면 문장과 정확히 맞는다.
        cut = [0] + [k for k, x in enumerate(lab) if x] + [len(words)]
        txt = [" ".join(words[cut[k]:cut[k + 1]]) for k in range(len(cut) - 1)]
        out.append({"id": r["id"], "cmd": r["command_ko"], "words": words,
                    "gold_labels": lab,
                    "절": [{"글": t, "종류": x["종류"], "mods": x["mods"]}
                          for t, x in zip(txt, s)]})
        skip["됨"] += 1

    print(f"라벨 만든 행 {len(out)} / {len(rows)}")
    print(" 건너뛴 까닭:", dict(skip.most_common()))
    if unknown:
        print(" ★ 모르는 조각:", dict(unknown))
    print(" 절 종류:", dict(collections.Counter(c["종류"] for o in out for c in o["절"]).most_common()))
    print(" 절 개수 분포:", dict(sorted(collections.Counter(len(o["절"]) for o in out).items())))

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    for o in out[:args.show]:
        print("\n ", o["cmd"])
        print("    경계", o["gold_labels"])
        print("   ", " | ".join(f"{c['종류']}{c['mods'] or ''}" for c in o["절"]))
    return 1 if unknown else 0


if __name__ == "__main__":
    sys.exit(main())
