"""v3 회귀 케이스 — 어휘로 못 푸는 것들이 LLM 판단으로 풀리는지, 그리고
실현 불가 상황이 조용히 넘어가지 않고 에러로 떨어지는지.

/home/ikess/joi-llm/venv/bin/python test_v3_cases.py
"""
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import run as R  # noqa: E402
from resolver_v3 import resolve_v3  # noqa: E402

BASE = R.CONNECTED_DEVICES


def run(title, command, devices, expect):
    res = resolve_v3(command, devices)
    picked = sorted({devices[i]["nickname"]
                     for g in res["groups"] for cl in g["clusters"]
                     for i in cl["ids"]})
    svcs = sorted({cl["svc"] for g in res["groups"] for cl in g["clusters"]})
    ok = expect(picked, svcs, res["errors"])
    print(f"{'✅' if ok else '❌'} {title}")
    print(f"    명령: {command}")
    print(f"    선택: {picked}")
    print(f"    서비스: {svcs}")
    for e in res["errors"]:
        print(f"    🚫 {e}")
    return ok


results = []

# ── 1. 대조적 의도: KT가 있으니 '삼성'은 배제 의도 ──
results.append(run(
    "삼성 지정 → KT 제외", "삼성 공기청정기를 모두 꺼줘", BASE,
    lambda p, s, e: p == ["삼성 공기청정기 　큰거".replace("　", ""), "삼성 공기청정기 작은거"][::1]
    or (len(p) == 2 and all("삼성" in x for x in p))))

# ── 2. 한정어 없음 → 전부 (KT 포함) ──
results.append(run(
    "한정어 없음 → 전체", "공기청정기 다 꺼줘", BASE,
    lambda p, s, e: len(p) == 3 and any("KT" in x for x in p)))

# ── 3. 표기 불일치: 태그는 영문 samsung, 닉네임도 영문, 발화는 한글 ──
dev_en = copy.deepcopy(BASE)
for did, d in dev_en.items():
    if d["nickname"] == "삼성 공기청정기 큰거":
        d["nickname"] = "SAMSUNG Air Purifier L"
        d["tags"] = d["tags"] + ["samsung"]
results.append(run(
    "영문 표기 기기를 한글 '삼성'으로 지칭", "삼성 공기청정기 다 꺼줘", dev_en,
    lambda p, s, e: any("SAMSUNG" in x for x in p) and not any("KT" in x for x in p)))

# ── 4. 알릴 수단 부재 → 에러 (조용히 성공하면 안 됨) ──
dev_nochan = {k: v for k, v in BASE.items()
              if not ({"Speaker", "ToastPublisher"} & set(v["category"]))}
results.append(run(
    "스피커·토스트 모두 없음 → 에러", "사람이 감지되면 알려줘", dev_nochan,
    lambda p, s, e: bool(e) and not any("Speak" in x or "Publish" in x for x in s)))

# ── 5. 능력 없음 → 귀속 에러 (다른 기기로 대체 금지) ──
results.append(run(
    "삼성 에어컨으로 습도 측정 → 에러", "삼성 에어컨으로 습도를 측정해줘", BASE,
    lambda p, s, e: bool(e)))

# ── 6. 회귀: 외재적 affordance (불 → Light ∪ LightSwitch) ──
results.append(run(
    "불 켜줘 → Light+LightSwitch", "불 켜줘", BASE,
    lambda p, s, e: len(p) == 16 and s == ["Switch.On"]))

# ── 7. 회귀: 체이닝 (챗봇 답 → 스피커, 자체 태그) ──
results.append(run(
    "챗봇 → Speaker 체이닝", "챗봇에게 수도가 어디인지 물어봐줘", BASE,
    lambda p, s, e: "ChatProvider.Chat" in s and "Speaker.Speak" in s))

print(f"\n═══ {sum(results)}/{len(results)} 통과")
