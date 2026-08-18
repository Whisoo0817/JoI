# -*- coding: utf-8 -*-
"""명사형 종결 합성 증강 — gold 절(type_labels.json)을 규칙으로 명사화해 새 명령을 만든다.

변환(절 타입별, 규칙이 걸리는 절만; 안 걸리면 원문 유지):
  TRIG  "…가 감지되면" → "… 감지 시" / "…이 눌리면" → "… 누름 시" / "열리면"→"열림 시" / "이상이 되면"→"이상 시" / "때마다"→"때마다"(유지)
  COND  "…이상이면" → "… 이상 시" | "… 이상인 경우" / "켜져 있으면"→"켜짐 상태 시" / "없으면"→"부재 시" / "N분 이상 X이면"→"X N분 이상 지속되는 동안"
  ACT   "켜줘"→"점등|켜기|On" / "꺼줘"→"소등|끄기|Off" / "V해줘"→"V" / "V어줘·아줘"→"V기" (사전) / "…로 설정해줘"→"… 설정"
  DELAY "N 뒤에"→"N 후" | 유지     TIME/READ/STOP/ELSE 유지
경계는 절 단위로 그대로 계승(단어 수만 달라짐), 타입도 계승. 쉼표 있는 판/없는 판 둘 다 생성.
출력: aug_nominal.json (labels.json과 같은 스키마 + type/segments + src)
"""
import json, os, re, random
HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, "type_labels.json")))
random.seed(0)

def strip_end(s):
    return s.strip().rstrip(".,")

TRIG_RULES = [
    (r"(.+?)(이|가) 감지되면$", r"\1 감지 시"),
    (r"(.+?)(이|가) 감지될 때마다$", r"\1 감지 시마다"),
    (r"(.+?)(이|가) 눌리면$", r"\1 누름 시"),
    (r"(.+?)(이|가) 눌릴 때마다$", r"\1 누름 시마다"),
    (r"(.+?)(이|가) 열리면$", r"\1 열림 시"),
    (r"(.+?)(이|가) 닫히면$", r"\1 닫힘 시"),
    (r"(.+?) 이상이 되면$", r"\1 이상 도달 시"),
    (r"(.+?) 이하가 되면$", r"\1 이하 도달 시"),
    (r"(.+?)보다 (높아지면|커지면)$", r"\1 초과 시"),
    (r"(.+?)보다 (낮아지면|작아지면)$", r"\1 미만 시"),
    (r"(.+?)(을|를) 넘으면$", r"\1 초과 시"),
    (r"(.+?)(이|가) 오면$", r"\1 시작 시"),
    (r"(.+?)(이|가) 되면$", r"\1 시"),
]
COND_RULES = [
    (r"(.+?)(이|가) (\S+) 이상 (감지되면|감지되지 않으면|없으면|있으면|열려 ?있으면|닫혀 ?있으면|유지되면|머무르면)$",
     lambda m: f"{m.group(1)} {m.group(3)} 이상 " + {"감지되면": "감지 지속 시", "감지되지 않으면": "미감지 지속 시", "없으면": "부재 지속 시", "있으면": "재실 지속 시", "열려있으면": "열림 지속 시", "열려 있으면": "열림 지속 시", "닫혀있으면": "닫힘 지속 시", "닫혀 있으면": "닫힘 지속 시", "유지되면": "유지 시", "머무르면": "체류 시"}[m.group(4)]),
    (r"(.+?) 이상이면$", r"\1 이상 시"),
    (r"(.+?) 이하이면$", r"\1 이하 시"),
    (r"(.+?) 이하면$", r"\1 이하 시"),
    (r"(.+?) 미만이면$", r"\1 미만 시"),
    (r"(.+?)보다 크면$", r"\1 초과 시"),
    (r"(.+?)(이|가) 켜져 ?있으면$", r"\1 켜짐 상태 시"),
    (r"(.+?)(이|가) 꺼져 ?있으면$", r"\1 꺼짐 상태 시"),
    (r"(.+?)(이|가) 열려 ?있으면$", r"\1 열림 상태 시"),
    (r"(.+?)(이|가) 닫혀 ?있으면$", r"\1 닫힘 상태 시"),
    (r"(.+?)(이|가) 잠겨 ?있으면$", r"\1 잠김 상태 시"),
    (r"(.+?) 없으면$", r"\1 부재 시"),
    (r"(.+?) 있으면$", r"\1 있는 경우"),
    (r"(.+?) 모드이면$", r"\1 모드인 경우"),
    (r"(.+?)(이|가) 감지되고 ?있으면$", r"\1 감지 상태 시"),
    (r"(.+?)상태면$", r"\1상태인 경우"),
    (r"(.+?)이면$", r"\1인 경우"),
]
ACT_VERB = {  # 어간+어미 → 명사형 후보들
    "켜줘": ["점등", "켜기", "On"], "켜고": ["점등 후", "켜고"], "켜 줘": ["켜기"],
    "꺼줘": ["소등", "끄기", "Off"], "꺼주고": ["소등 후"], "끄고": ["소등 후", "끄고"],
    "닫아줘": ["닫기"], "닫고": ["닫고", "닫은 뒤"], "열어줘": ["열기", "개방"], "열고": ["열고", "연 뒤"],
    "잠궈줘": ["잠금"], "잠가줘": ["잠금"], "잠그고": ["잠금 후"], "울려줘": ["울리기", "작동"], "울리고": ["울린 뒤"],
    "찍어줘": ["촬영"], "찍고": ["촬영 후"], "올려줘": ["올리기"], "내려줘": ["내리기"], "낮춰줘": ["낮추기"], "높여줘": ["높이기"],
    "멈춰줘": ["정지"], "멈추고": ["정지 후"], "바꿔줘": ["변경"], "바꾸고": ["변경 후"], "맞춰줘": ["설정"],
    "말해줘": ["안내"], "알려줘": ["안내"], "출력해줘": ["출력"], "보내줘": ["전송"], "재생해줘": ["재생"], "틀어줘": ["재생"],
    "설정해줘": ["설정"], "설정하고": ["설정 후"], "작동시켜줘": ["작동"], "작동해줘": ["작동"], "시작해줘": ["시작"],
    "변경해줘": ["변경"], "조절해줘": ["조절"], "저장해줘": ["저장"], "생성하고": ["생성 후"], "차단해줘": ["차단"],
}
def nominalize_act(s):
    core = strip_end(s)
    core = re.sub(r"(\S+?)(을|를) (\S+)$", r"\1 \3", core)     # 목적격 조사 탈락 ("창문을 닫아줘"→"창문 닫기")
    for k in sorted(ACT_VERB, key=len, reverse=True):
        if core.endswith(k):
            return core[: -len(k)].rstrip() + " " + random.choice(ACT_VERB[k])
    m = re.match(r"^(.*?)(\S+?)해줘$", core)
    if m:
        return (m.group(1) + m.group(2)).strip()
    return None

def apply(rules, s):
    core = strip_end(s)
    for pat, rep in rules:
        m = re.match(pat, core)
        if m:
            return rep(m) if callable(rep) else re.sub(pat, rep, core)
    return None

def nominalize(seg):
    t, s = seg["type"], seg["text"]
    if t == "TRIG": return apply(TRIG_RULES, s)
    if t == "COND": return apply(COND_RULES, s)
    if t == "ACT": return nominalize_act(s)
    if t == "DELAY":
        m = re.match(r"^(.+?) ?(뒤에|후에)$", strip_end(s))
        return m.group(1) + " 후" if m and random.random() < 0.5 else None
    return None

out = []
for o in T:
    segs = o["segments"]
    new, changed = [], 0
    for sg in segs:
        n = nominalize(sg)
        if n and n.strip() and n.strip() != strip_end(sg["text"]):
            new.append((n.strip(), sg["type"], sg["mods"])); changed += 1
        else:
            new.append((strip_end(sg["text"]), sg["type"], sg["mods"]))
    if changed == 0:
        continue
    for punct in (True, False):
        # 쉼표판: 절 사이 ", " / 무쉼표판: " " ; 문미 마침표는 쉼표판만
        joiner = ", " if punct else " "
        text = joiner.join(x[0] for x in new) + ("." if punct else "")
        words, labels, cur_segs, types = [], [], [], []
        for k, (txt, ty, mods) in enumerate(new):
            ws = (txt + ("," if punct and k < len(new) - 1 else ("." if punct and k == len(new) - 1 else ""))).split()
            words += ws; labels += [1 if (k > 0 and i == 0) else 0 for i in range(len(ws))]
            cur_segs.append(" ".join(ws)); types.append(ty)
        labels[0] = 0
        out.append({"cmd": " ".join(words), "cat": o["cat"], "words": words, "labels": labels,
                    "segs": cur_segs, "types": types, "src": o["i"], "punct": punct})
json.dump(out, open(os.path.join(HERE, "aug_nominal.json"), "w"), ensure_ascii=False, indent=1)
print("합성 명령", len(out), "원본 명령", len({x["src"] for x in out}))
for x in random.sample(out, 12):
    print("  " + " ‖ ".join(f"[{t}] {s}" for s, t in zip(x["segs"], x["types"])))
