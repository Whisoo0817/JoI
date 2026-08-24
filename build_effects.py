# -*- coding: utf-8 -*-
"""effects.json 채우기 — 카탈로그에 있는데 검색 색인에 없는 서비스를 메운다.

왜 필요한가
  매핑(joi_slm/mapping.py)은 assets/effects.json 에 적힌 서비스만 후보로 본다.
  카탈로그를 3.1.0 으로 올리니 472개 중 **220개가 색인에 없어** 아예 못 골랐다.
  Stage 1 이 "독서 모드" 를 로봇청소기 모드로 잡던 까닭이 여기 있다.

무엇을 채우나
  kind·role·returns·effects 는 카탈로그에서 그대로 뽑는다.
  한국어 표현(ko_triggers)만 2B 에게 짓게 한다 — 사람이 그 서비스를 부를 때 쓸 말.

    ~/temp/bin/python build_effects.py --dry      # 몇 개 빠졌는지만
    ~/temp/bin/python build_effects.py -n 20      # 앞 20개만 지어 보기
    ~/temp/bin/python build_effects.py            # 전부
"""
import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "bench"))     # korean.NOUN_KO (기기 한국어 이름)

ASSET = os.path.join(HERE, "joi_slm", "assets", "effects.json")
ENGINE_URL = "http://localhost:49998"

SYS = """스마트홈에서 사람이 실제로 말하는 한국어 표현을 짓는다.

규칙
- 기기의 한국어 이름을 쓴다. 영어 이름(Mower, RunHours)을 문장에 넣지 마라.
- 다섯 줄. 서로 다른 말이어야 한다. 같은 문장 반복 금지.
- 짧게. 조회면 "~뭐야"·"~알려줘", 실행이면 "~해줘", 조건이면 "~면" 으로 끝난다.
- 설명하지 말고 표현 다섯 줄만 쓴다."""

# 있는 항목에서 뽑은 본보기 — 2B 는 예를 봐야 말투를 잡는다
SHOTS = [
    ("에어컨", "AirConditionerMode", "지금 에어컨 모드를 알려준다", "조회",
     ["에어컨 모드 뭐야", "에어컨 지금 무슨 모드야", "에어컨 냉방이야 난방이야",
      "에어컨 모드 확인해줘", "에어컨이 냉방 모드면"]),
    ("로봇청소기", "StartCleaning", "청소를 시작한다", "실행",
     ["청소 시작해줘", "로봇청소기 돌려줘", "지금 청소 시켜", "바닥 좀 밀어줘", "청소기 켜줘"]),
]


def shots():
    out = []
    for ko_cat, name, what, kind, lines in SHOTS:
        out.append({"role": "user",
                    "content": f"기기: {ko_cat}\n하는 일: {what}\n종류: {kind}"})
        out.append({"role": "assistant", "content": "\n".join(lines)})
    return out


def use_engine_server(url=None):
    import urllib.request
    url = url or os.environ.get("JOI_ENGINE_URL") or ENGINE_URL
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/health", timeout=1.5) as r:
            if r.status != 200:
                return False
    except Exception:                                 # noqa: BLE001
        return False
    os.environ["JOI_ENGINE_URL"] = url
    return True


def catalog_entries():
    """카탈로그 → {svc: {kind, role, returns, effects}} (한국어 표현은 아직 없다)."""
    from loader import SERVICE_DATA
    out = {}
    for cat, d in SERVICE_DATA.items():
        for v in d.get("values", []):
            out[f"{cat}.{v['id']}"] = {
                "kind": "value", "role": "read",
                "returns": v.get("type") or "",
                "effects": [v.get("descriptor") or f"report {cat} {v['id']}"],
            }
        for f in d.get("functions", []):
            out[f"{cat}.{f['id']}"] = {
                "kind": "function", "role": "action",
                "returns": f.get("returns") or "VOID",
                "effects": [f.get("descriptor") or f"{f['id']} on {cat}"],
            }
    return out


def ko_name(cat):
    """카테고리의 한국어 이름. bench/korean.py 가 이미 92종을 들고 있다."""
    import korean as KO
    return KO.NOUN_KO.get(cat) or cat


def ask_ko(svc, info, infer):
    """2B 에게 한국어 표현 5개를 짓게 한다. 한국어 기기 이름과 본보기를 같이 준다."""
    cat, _ = svc.split(".", 1)
    what = "; ".join(info["effects"])
    kind = "조회" if info["role"] == "read" else "실행"
    user = f"기기: {ko_name(cat)}\n하는 일: {what}\n종류: {kind}"
    txt = infer(user)
    lines = [re.sub(r"^[-*\d.)\s]+", "", x).strip() for x in txt.splitlines()]
    out = []
    for x in lines:
        if not x or len(x) > 40 or x.startswith("("):
            continue
        if re.search(r"[A-Za-z]{3,}", x):      # 영어 이름을 그대로 옮긴 줄은 버린다
            continue
        out.append(x)
    return list(dict.fromkeys(out))[:5]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="몇 개 빠졌는지만 본다")
    ap.add_argument("-n", type=int, default=0, help="앞 N개만 (0=전부)")
    args = ap.parse_args()

    have = {s["svc"]: s for s in json.load(open(ASSET, encoding="utf-8"))["services"]}
    want = catalog_entries()
    miss = [s for s in want if s not in have]
    print(f"카탈로그 {len(want)} · 색인에 있는 것 {len(have)} · 빠진 것 {len(miss)}")
    if args.dry:
        return 0
    if args.n:
        miss = miss[:args.n]

    if not use_engine_server():
        print("엔진 서버가 없다 — engine_server.py 를 먼저 띄워라")
        return 1
    from pipeline_helpers import run_llm_inference

    def infer(user):
        content, _ = run_llm_inference("ko_triggers",
            [{"role": "system", "content": SYS}] + shots()
            + [{"role": "user", "content": user}], max_tokens=200)
        return content

    t0, made = time.perf_counter(), []
    for i, svc in enumerate(miss, 1):
        info = want[svc]
        try:
            ko = ask_ko(svc, info, infer)
        except Exception as e:                        # noqa: BLE001
            print(f"  ✗ {svc}: {type(e).__name__}")
            ko = []
        made.append({"svc": svc, **info, "ko_triggers": ko})
        if i % 25 == 0 or i == len(miss):
            print(f"  {i}/{len(miss)}  ({time.perf_counter()-t0:.0f}초)  마지막: {svc} → {ko[:2]}")

    doc = json.load(open(ASSET, encoding="utf-8"))
    doc["services"] = doc["services"] + made
    doc.setdefault("_comment", "")
    with open(ASSET, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    empty = sum(1 for m in made if not m["ko_triggers"])
    print(f"\n{ASSET} — {len(doc['services'])}개 (새로 {len(made)}, 한국어 못 지은 것 {empty})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
