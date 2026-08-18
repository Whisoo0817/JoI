# -*- coding: utf-8 -*-
"""패러프레이즈 held-out 세트 생성 — 매핑 327 명령에서 카테고리 층화 80개를 뽑아 9B(vLLM)로 같은 뜻·다른 표현(어순·동의어·조사/어미·구어체) 2개씩 생성.
검증: 숫자 집합 보존 + 길이 비 0.5~2 + 원문과 다름. 사람이 다시 훑어볼 수 있게 para.json에 저장 (사용자 검토 전제).
주의: 이 세트는 규칙 튜닝에 쓰지 않는다(held-out)."""
import json, os, re, sys, random, urllib.request, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assembly"))
os.environ.setdefault("MAPPED_ONLY", "1")
import build_ir as B
HERE = os.path.dirname(os.path.abspath(__file__))
random.seed(0)
N = int(os.environ.get("N", "80"))
pool = [o for o in B.T if o["ir_gt"] and (o["cmd"], 0) in B.MAP]
bycat = collections.defaultdict(list)
for o in pool: bycat[o["cat"]].append(o)
picked = []
cats = sorted(bycat)
while len(picked) < N:
    for c in cats:
        if bycat[c] and len(picked) < N: picked.append(bycat[c].pop(random.randrange(len(bycat[c]))))
def chat(msg):
    req = json.dumps({"model": "cyankiwi/Qwen3.5-9B-AWQ-4bit", "messages": [{"role": "user", "content": msg}], "max_tokens": 400, "temperature": 0.8, "chat_template_kwargs": {"enable_thinking": False}}).encode()
    r = urllib.request.Request("http://localhost:8002/v1/chat/completions", data=req, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=180).read())["choices"][0]["message"]["content"]
PROMPT = """다음 스마트홈 음성 명령을 뜻은 완전히 같게 유지하면서 표현만 다르게 2가지로 바꿔 쓰세요.
규칙: 숫자·단위·기기 이름·시간·조건의 의미는 그대로. 어순 바꾸기, 동의어(예: 켜줘→틀어줘, 꺼줘→꺼주세요, 감지되면→감지될 경우), 조사·어미 바꾸기, 구어체/존댓말 섞기, 절 순서 바꾸기(의미 유지 시)를 활용. 설명 없이 한 줄에 하나씩 두 줄만 출력.
명령: {cmd}"""
def nums(t): return sorted(re.findall(r"\d+(?:\.\d+)?", t))
out = []
for o in picked:
    try: txt = chat(PROMPT.format(cmd=o["cmd"]))
    except Exception as e: print("ERR", e); continue
    lines = [re.sub(r"^\s*(\d+[.)]|[-•*])\s*", "", l).strip().strip('"') for l in txt.strip().splitlines() if l.strip()]
    ok = [l for l in lines if l and l != o["cmd"] and nums(l) == nums(o["cmd"]) and 0.5 <= len(l) / len(o["cmd"]) <= 2.0][:2]
    out.append({"i": o["i"], "cat": o["cat"], "cmd": o["cmd"], "para": ok, "raw": lines})
    print(o["cmd"]); [print("   →", l) for l in ok]
json.dump(out, open(os.path.join(HERE, "para.json"), "w"), ensure_ascii=False, indent=1)
print("명령", len(out), "패러프레이즈", sum(len(x["para"]) for x in out))
