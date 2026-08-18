# -*- coding: utf-8 -*-
"""패러프레이즈 필터 — 비한글(한자 등) 제거, 9B 판정(같은 자동화 규칙인가: 순서·조건·수치·기기 동일) 3회 중 3회 '예'만 채택 → para_ok.json"""
import json, os, re, urllib.request, collections
HERE = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(HERE, "para.json")))
def chat(msg, temp=0.0):
    req = json.dumps({"model": "cyankiwi/Qwen3.5-9B-AWQ-4bit", "messages": [{"role": "user", "content": msg}], "max_tokens": 5, "temperature": temp, "chat_template_kwargs": {"enable_thinking": False}}).encode()
    r = urllib.request.Request("http://localhost:8002/v1/chat/completions", data=req, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=120).read())["choices"][0]["message"]["content"].strip()
JUDGE = """두 스마트홈 명령이 정확히 같은 자동화(같은 조건, 같은 동작 순서, 같은 수치·시간·기기·대상, 같은 반복/횟수)를 뜻하면 "예", 조금이라도 다르면(조건과 동작이 뒤바뀜, 순서가 다름, 수치·대상이 다름, 뜻이 모호함) "아니오"라고만 답하라.
A: {a}
B: {b}
답:"""
out = []; kept = 0; tot = 0
for x in P:
    ok = []
    for p in x["para"]:
        tot += 1
        if re.search(r"[一-鿿぀-ヿ]", p): continue
        votes = [chat(JUDGE.format(a=x["cmd"], b=p), temp=t) for t in (0.0, 0.5, 0.7)]
        if all(v.startswith("예") for v in votes): ok.append(p); kept += 1
        else: print("✗", p, "|", votes)
    out.append({**x, "para": ok})
json.dump(out, open(os.path.join(HERE, "para_ok.json"), "w"), ensure_ascii=False, indent=1)
print(f"채택 {kept}/{tot}, 명령 {sum(1 for x in out if x['para'])}/{len(out)}")
