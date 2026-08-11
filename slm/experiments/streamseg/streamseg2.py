# -*- coding: utf-8 -*-
"""Streaming word-by-word clause segmentation, judged by the 2B model itself.

v2 — raw /v1/completions (NO chat template: the chat wrapper put the model in
"answer mode" and killed the digit distribution; pattern continuation works).

Per new word the model emits ONE token: 1 = new clause starts here,
0 = continues current clause, 2 = ambiguous/defer.  We read the digit
probabilities from top_logprobs (argmax over {0,1,2}), so we also get a
confidence for every judgment.  First word of a command is never judged.

Variants: base task text vs + temporal-order explanation (user's question).
"""
import json, math, os, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "http://localhost:8002/v1/completions"
MODEL = "cyankiwi/Qwen3.5-2B-AWQ-4bit"

HEAD_BASE = (
    "한국어 IoT 명령어를 단어 단위로 읽으며 절을 나눈다. 절 = 하나의 조건 또는 하나의 행동.\n"
    "각 줄: 지금까지의 절 구분 || 새 단어 => 판단 (1=새 절 시작, 0=이어짐, 2=애매)\n\n"
)
TEMPORAL = (
    "명령어는 시간 순서대로 배열된다: 언제/어떤 조건(트리거)이 먼저, 실행할 행동들이 나중.\n"
    "절이 바뀌는 곳은 새로운 조건이나 새로운 행동이 시작되는 지점이다.\n\n"
)

TRACE = """아침 7시에 || 거실 => 1
아침 7시에 | 거실 || 창문이 => 0
아침 7시에 | 거실 창문이 || 열리면 => 0
아침 7시에 | 거실 창문이 열리면 || 조명을 => 1
아침 7시에 | 거실 창문이 열리면 | 조명을 || 켜고 => 0
아침 7시에 | 거실 창문이 열리면 | 조명을 켜고 || 스피커를 => 1
아침 7시에 | 거실 창문이 열리면 | 조명을 켜고 | 스피커를 || 꺼줘. => 0
비가 || 오면 => 0
비가 오면 || 창문을 => 1
비가 오면 | 창문을 || 닫고 => 0
비가 오면 | 창문을 닫고 || 30분 => 2
비가 오면 | 창문을 닫고 30분 || 뒤에 => 0
비가 오면 | 창문을 닫고 30분 뒤에 || 다시 => 1
비가 오면 | 창문을 닫고 30분 뒤에 | 다시 || 열어줘. => 0
주방 온도가 40도 || 이상이고 => 0
주방 온도가 40도 이상이고 || 밸브가 => 1
주방 온도가 40도 이상이고 | 밸브가 열려 있으면 || 밸브를 => 1
주방 온도가 40도 이상이고 | 밸브가 열려 있으면 | 밸브를 || 잠그고 => 0
"""


def judge(head, seg_text, new_word, retries=2):
    prompt = head + TRACE + "%s || %s => " % (seg_text, new_word)
    body = {"model": MODEL, "prompt": prompt, "temperature": 0, "max_tokens": 1,
            "seed": 0, "logprobs": 10}
    for a in range(retries + 1):
        try:
            r = urllib.request.urlopen(urllib.request.Request(
                URL, json.dumps(body).encode(), {"Content-Type": "application/json"}),
                timeout=60)
            d = json.loads(r.read())["choices"][0]
            lp = d["logprobs"]["top_logprobs"][0]
            pr = {k: math.exp(v) for k, v in lp.items()}
            p = {c: pr.get(c, 0.0) for c in ("0", "1", "2")}
            lab = max(p, key=p.get) if max(p.values()) > 0 else "0"
            return lab, p
        except Exception:
            if a == retries:
                return "E", {"0": 0, "1": 0, "2": 0}
            time.sleep(1.0)


def run_command(head, cmd):
    ws = cmd.split()
    segs, labels, confs = [[ws[0]]], ["S"], [None]
    for w in ws[1:]:
        seg_text = " | ".join(" ".join(s) for s in segs)
        lab, p = judge(head, seg_text, w)
        labels.append(lab)
        confs.append(round(p.get("1", 0.0), 3))
        if lab == "1":
            segs.append([w])
        else:
            segs[-1].append(("?" + w) if lab == "2" else w)
    seg = " | ".join(" ".join(s) for s in segs)
    return {"labels": labels, "p1": confs, "seg": seg}


def main():
    items = json.load(open(os.path.join(HERE, "items_final.json")))
    sample = items[::2][:30]
    out = []
    t0 = time.time()
    for k, it in enumerate(sample):
        row = {"idx": it["index"], "cmd": it["cmd"]}
        row["base"] = run_command(HEAD_BASE, it["cmd"])
        row["temporal"] = run_command(TEMPORAL + HEAD_BASE, it["cmd"])
        out.append(row)
        json.dump(out, open(os.path.join(HERE, "streamseg2_results.json"), "w"),
                  ensure_ascii=False, indent=1)
        print("[%2d/30] %5.1fs  %s" % (k + 1, time.time() - t0, it["cmd"][:44]), flush=True)
    print("done %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
