# -*- coding: utf-8 -*-
"""사용자가 정한 3원칙으로 절 경계 라벨 확정.

  1. "A이고 B이면" 복합조건 → 한 절로 병합
  2. "3분 뒤에" 시간표현 → 독립 절 유지
  3. 쉼표/마침표의 동사 없는 조각 → 앞 절에 붙임
     (단 "아니면/그렇지 (않으면)/그리고"로 시작하는 조각은 절로 유지)

출력: labels.json — 명령마다 단어 리스트 + 단어별 0/1 라벨(1 = 새 절 시작)
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "e1"))
from segmerge import merge_condition_chain  # noqa: E402

KEEP_START = ("아니면", "그렇지", "그리고")


def merge_fragments(segs):
    """규칙 3: 쉼표/마침표 경계 중 조각-성 경계를 병합."""
    out = [segs[0]]
    for k in range(1, len(segs)):
        prev_last = out[-1].split()[-1]
        first = segs[k].split()[0]
        is_punct_boundary = prev_last.endswith((",", ".")) and not re.search(
            r"(면|고|서|거나|는데|다가|마다)[,.]?$", prev_last)
        if is_punct_boundary and not first.startswith(KEEP_START):
            out[-1] = out[-1] + " " + segs[k]
        else:
            out.append(segs[k])
    return out


def main():
    draft = json.load(open(os.path.join(HERE, "draft.json")))
    n_rule1 = n_rule3 = 0
    final = []
    for item in draft:
        segs = item["segs"]
        m1 = merge_condition_chain(segs)
        if m1 != segs:
            n_rule1 += 1
        m3 = merge_fragments(m1)
        if m3 != m1:
            n_rule3 += 1
        words = item["cmd"].split()
        assert " ".join(m3) == " ".join(words), item["cmd"]
        labels, pos = [], 0
        starts = set()
        for s in m3:
            starts.add(pos)
            pos += len(s.split())
        for i in range(len(words)):
            labels.append(1 if (i in starts and i > 0) else 0)
        final.append({"cmd": item["cmd"], "cat": item["cat"], "words": words,
                      "labels": labels, "segs": m3, "ops": item["ops"]})
    json.dump(final, open(os.path.join(HERE, "labels.json"), "w"),
              ensure_ascii=False, indent=1)

    n_bound = sum(sum(f["labels"]) for f in final)
    n_words = sum(len(f["labels"]) for f in final)
    multi = [f for f in final if len(f["segs"]) >= 2]
    print("명령 %d개 | 단어 %d개 | 경계 라벨 %d개 (단어의 %.1f%%)"
          % (len(final), n_words, n_bound, 100 * n_bound / n_words))
    print("규칙1(복합조건 병합) 적용: %d개 명령 | 규칙3(조각 병합) 적용: %d개 명령"
          % (n_rule1, n_rule3))
    print("절 2개 이상인 명령: %d개" % len(multi))
    print("\n== 확정 라벨 예시 ==")
    for f in final[:2] + [f for f in final if "색조" in f["cmd"]][:1] \
            + [f for f in final if "아니면" in f["cmd"]][:1]:
        print("  " + " | ".join(f["segs"]))


if __name__ == "__main__":
    main()
