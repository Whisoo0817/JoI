# -*- coding: utf-8 -*-
"""절 경계 라벨 초안 만들기 + 애매한 유형 집계.

라벨 = 단어마다 "여기서 새 절이 시작되나" (1/0).
초안은 어미 규칙 분할기(seg.py)에서 얻고, 정답 IR의 동작 개수와 대조해서
절 개수가 안 맞는 명령을 골라낸다. 애매한 경계는 유형별로 모아 사용자에게 물어본다.
"""
import json, re, sys, os
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
E1 = os.path.join(os.path.dirname(HERE), "e1")
sys.path.insert(0, E1)
from seg import segment_kor, parse_ir, count_ops, op_sequence  # noqa: E402
from segmerge import merge_condition_chain                     # noqa: E402

import csv
rows = list(csv.DictReader(open("/home/ikess/joi-llm/joi_new/dataset.csv")))
seen, cmds = set(), []
for r in rows:
    c = (r["command_kor"] or "").strip()
    if c and c not in seen:
        seen.add(c)
        cmds.append({"cmd": c, "ir": parse_ir(r["ir_gt"]), "cat": r["category_v2"]})
print("명령 수:", len(cmds))

# ---- 경계 유형 분류 ---------------------------------------------------------
def cue_of(prev_word, first_word_of_new):
    w = prev_word.rstrip(",.;!?")
    if re.search(r"(하|해|외출|귀가)?(면|되면|이면|오면|나면|지면|리면|가면|녁이면)$", w) and w.endswith("면"):
        return "면"
    if w.endswith("고"):
        return "고"
    if re.search(r"(해서|아서|어서|와서|워서|여서)$", w):
        return "서"
    if re.search(r"(뒤에?|후에?)$", w) or re.search(r"(뒤에?|후에?)$", first_word_of_new):
        return "시간(뒤에/후에)"
    if re.search(r"때(마다)?$", w):
        return "때(마다)"
    if re.search(r"(마다)$", w):
        return "마다"
    if prev_word.endswith(","):
        return "쉼표"
    if prev_word.endswith("."):
        return "마침표(문장분리)"
    if w.endswith(("거나", "는데")):
        return "거나/는데"
    return "기타"

stats = Counter()
mismatch = []          # 절 수 != 동작 수
frag_examples = defaultdict(list)
for item in cmds:
    segs = segment_kor(item["cmd"])
    item["segs"] = segs
    ops = [o for o in op_sequence(item["ir"]) if o != "start_at"]
    item["ops"] = ops
    for k in range(1, len(segs)):
        prev_last = segs[k - 1].split()[-1]
        first_new = segs[k].split()[0]
        cue = cue_of(prev_last, first_new)
        stats[cue] += 1
        if len(frag_examples[cue]) < 4:
            frag_examples[cue].append(
                "%s ▸| %s" % (segs[k - 1].split()[-1], " ".join(segs[k].split()[:3])))
    if len(segs) >= 2 and len(segs) != len(ops):
        mismatch.append(item)

print("\n== 경계 유형별 개수 (총 %d개) ==" % sum(stats.values()))
for cue, n in stats.most_common():
    print("  %-14s %4d   예: %s" % (cue, n, " / ".join(frag_examples[cue][:3])))

print("\n== 절 수와 정답 동작 수가 다른 명령: %d개 ==" % len(mismatch))
over = [m for m in mismatch if len(m["segs"]) > len(m["ops"])]
under = [m for m in mismatch if len(m["segs"]) < len(m["ops"])]
print("  절이 더 많음(너무 잘게 쪼갬 후보): %d | 절이 더 적음(덜 쪼갬 후보): %d"
      % (len(over), len(under)))

# 복합 조건(A이고 B이면)이 관여한 over-split이 몇 개인지
merged_fix = 0
for m in over:
    if merge_condition_chain(m["segs"]) != m["segs"]:
        merged_fix += 1
print("  그중 'A이고 B이면' 복합조건 병합으로 해소되는 것: %d" % merged_fix)

print("\n== 너무 잘게 쪼갠 예 5개 ==")
for m in over[:5]:
    print("  ops=%s" % m["ops"])
    print("  절 : %s" % " | ".join(m["segs"]))
print("\n== 덜 쪼갠 예 5개 ==")
for m in under[:5]:
    print("  ops=%s" % m["ops"])
    print("  절 : %s" % " | ".join(m["segs"]))

json.dump([{"cmd": c["cmd"], "segs": c["segs"], "ops": c["ops"], "cat": c["cat"]}
           for c in cmds], open(os.path.join(HERE, "draft.json"), "w"),
          ensure_ascii=False, indent=1)
print("\ndraft.json 저장")
