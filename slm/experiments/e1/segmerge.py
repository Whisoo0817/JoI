# -*- coding: utf-8 -*-
"""Condition-chain merging — post-processing over any clause segmentation.

Motivation (from the streaming analysis): a Korean clause ending in -고/-며/-면서/-서 has an
UNRESOLVED role at the moment it closes; it is a condition-chain link iff a later clause in
the same sentence ends in -면. Splitting such a run into separate segments over-splits a
single composite condition ("A이고 B이면" is ONE if-cond with `and`, not two ifs).

So: merge a contiguous run of chaining clauses into the -면 clause that terminates it.
This is a purely surface rule — it never looks at the gold IR.
"""
import re

COND_END = re.compile(r"면[,]?$")
COND_STOP = {"라면", "수면", "화면", "지면", "국면", "측면", "표면", "장면", "전면", "노면"}

# A chaining link counts as part of a COMPOSITE CONDITION only when its predicate is
# STATIVE (describes a state that can be tested), not an action to perform.
#   stative : 있고 / 없고 / 이고 / 되고 / 켜져있고 / 26도 이상이고 / 아니고
#   action  : 닫고 / 켜고 / 울리고 / 체크하고 / 출력하고   -> these chain ACTIONS, never merge
STATIVE_END = re.compile(r"(있고|없고|이고|되고|아니고|같고|낮고|높고|많고|적고)[,]?$")
COMPARE = re.compile(r"(이상|이하|미만|초과|넘|이고|같)")
# nouns that merely end in the same syllable
CHAIN_STOP = {"창고", "냉장고", "차고", "광고", "보고", "그리고", "최고", "중고", "신고"}


def _last(c):
    ws = c.split()
    return ws[-1] if ws else ""


def is_chain_clause(c):
    """Stative chaining link: a condition-side conjunct, safe to merge into the -면 clause."""
    w = _last(c).rstrip(",")
    if w in CHAIN_STOP:
        return False
    if STATIVE_END.search(w):
        return True
    # "26도 이상이고", "70% 이상이고" — comparison predicate ending in -고
    return w.endswith("고") and bool(COMPARE.search(w))


def is_cond_clause(c):
    w = _last(c)
    return bool(COND_END.search(w)) and w.rstrip(",") not in COND_STOP


def merge_condition_chain(clauses):
    """Merge runs of chaining clauses that terminate in a -면 clause.

    ["거실에 사람이 있고", "연기가 감지되고 있으면,", "스피커로 출력하고", "밸브를 잠궈줘."]
    -> ["거실에 사람이 있고 연기가 감지되고 있으면,", "스피커로 출력하고", "밸브를 잠궈줘."]
    """
    out, buf = [], []
    for c in clauses:
        if is_chain_clause(c):
            buf.append(c)
            continue
        if buf:
            if is_cond_clause(c):          # the run really was a condition chain
                out.append(" ".join(buf + [c]))
            else:                          # action chain — keep the pieces separate
                out.extend(buf)
                out.append(c)
            buf = []
        else:
            out.append(c)
    out.extend(buf)                        # trailing chain with no terminator
    return out


if __name__ == "__main__":
    import csv, json, sys, itertools

    # naive suffix segmentation, standalone (mirrors what seg.py will do) for testing only
    BOUND = re.compile(r"(면|고|서|거나|는데|면서|다가|자마자|때|후에|다음에)[,]?$")
    STOP = CHAIN_STOP | COND_STOP | {"때"}

    def naive_seg(cmd):
        ws, cur, out = cmd.split(), [], []
        for i, w in enumerate(ws):
            cur.append(w)
            if i == len(ws) - 1:
                break
            if w.endswith((",", ";")) or (BOUND.search(w) and w.rstrip(",;") not in STOP):
                out.append(" ".join(cur)); cur = []
        if cur:
            out.append(" ".join(cur))
        return out

    rows = list(csv.DictReader(open("/home/ikess/joi-llm/joi_new/dataset.csv")))
    seen, items = set(), []
    def nops(o):
        n = 0
        if isinstance(o, dict):
            n += 1 if "op" in o else 0
            for v in o.values(): n += nops(v)
        elif isinstance(o, list):
            for v in o: n += nops(v)
        return n
    def opseq(o, acc=None):
        acc = [] if acc is None else acc
        if isinstance(o, dict):
            if "op" in o: acc.append(o["op"])
            for v in o.values(): opseq(v, acc)
        elif isinstance(o, list):
            for v in o: opseq(v, acc)
        return acc

    n_changed = 0
    for r in rows:
        c = (r["command_kor"] or "").strip()
        if not c or c in seen: continue
        seen.add(c)
        ir = json.loads(r["ir_gt"], strict=False)
        if nops(ir) < 4: continue
        a = naive_seg(c); b = merge_condition_chain(a)
        assert " ".join(a) == " ".join(c.split()), "naive seg lost words"
        assert " ".join(b) == " ".join(c.split()), "merge lost words"
        if a != b: n_changed += 1
        items.append((c, a, b, opseq(ir)))

    print(f"eligible(>=4 ops): {len(items)} | merge changed segmentation on {n_changed} "
          f"({100*n_changed/len(items):.0f}%)")
    # how close is clause count to op count (minus start_at) after merge?
    import statistics
    def gap(seg, ops): return len(seg) - max(1, len([o for o in ops if o != "start_at"]))
    ga = [gap(a, o) for _, a, _, o in items]
    gb = [gap(b, o) for _, _, b, o in items]
    print(f"clause-count minus op-count   naive: mean {statistics.mean(ga):+.2f} "
          f"| merged: mean {statistics.mean(gb):+.2f}   (0 = aligned, + = over-split)")
    print(f"  exactly aligned  naive: {sum(1 for g in ga if g==0)}/{len(ga)}"
          f" | merged: {sum(1 for g in gb if g==0)}/{len(gb)}")
    print("\n--- examples where merging fired ---")
    shown = 0
    for c, a, b, o in items:
        if a != b and shown < 8:
            print(f"\nCMD  {c}")
            print(f" ops {o}")
            print(f" naive  : {' | '.join(a)}")
            print(f" merged : {' | '.join(b)}")
            shown += 1
