# -*- coding: utf-8 -*-
"""후보 구조 열거 + 원문 절 timeline 배치 렌더러 (객관식 판정용).

후보 = 줄 목록 [(seg_i, depth, marker)] — 원문 절을 실행 순서대로, 들여쓰기(상자 소속) + 마커로 배치.
  마커: 시각 / 반복 / 조건 / 아니면 / 대기 / 지연 / 읽기 / 참조 / 무시 / 종료 / ''(행동)
상자 기계 결과(Box 트리)를 줄 목록으로 바꾸고, 결정점별 국소 교란으로 대안을 만든다:
  shift   잎의 들여쓰기 ±1 (어느 상자에 담기나: DELAY 안/밖, 조건 우산 범위)
  elseif  [아니면]↔[조건] (else-if vs 형제 조건)
  ref     행동 절을 [참조](새 실행 아님)로 / 그 역
  drop    절을 [무시]로 / 그 역
  post    말미 조건을 앞 행동들 위로 올려 감싸기 (조건 후치)
  hoist   상자 머리(반복/조건)를 한 절 뒤로 밀기 (범위 시작점)
"""
import json, os, sys, random, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from box import Box, Leaf, assemble_tree, gold_flags

LEAF_MARK = {"CALL": "", "READ": "읽기", "DELAY": "지연", "WAIT:none": "대기", "WAIT:rising": "대기", "WAIT:none:for": "대기", "BREAK": "종료"}
HEAD_MARK = {"CYC": "반복", "IF": "조건"}

def tree_to_lines(root, segs):
    """Box 트리 → 줄 목록. 잎이 없는 절(TIME/ELSE/STOP/흡수된 READ)은 이웃 절의 깊이로 끼워 넣는다."""
    lines = []          # (seg, depth, marker)
    def first_seg_of(items):
        for y in items:
            return y.seg if isinstance(y, Box) else None
        return None
    def emit_else(x, d):
        items = x.else_items
        if len(items) == 1 and isinstance(items[0], Box) and items[0].kind == "IF":     # else-if → "[아니면] 조건절"
            y = items[0]; lines.append((y.seg, d, "아니면")); walk(y, d + 1)
            if y.else_items is not None: emit_else(y, d)
            return
        fs = None
        for y in items:
            fs = y.seg if isinstance(y, Box) else x.owner.get(id(y)); break
        e = next((k for k in range(x.seg + 1, fs if fs is not None else len(segs)) if segs[k][0] == "ELSE"), None) if x.seg is not None else None
        lines.append((e, d, "아니면"))
        for y in items:
            if isinstance(y, Box):
                lines.append((y.seg, d + 1, HEAD_MARK[y.kind])); walk(y, d + 2)
                if y.else_items is not None: emit_else(y, d + 1)
            else:
                lines.append((x.owner[id(y)], d + 1, LEAF_MARK.get(str(y), "")))
    def walk(b, d):
        for x in b.items:
            if isinstance(x, Box):
                lines.append((x.seg, d, HEAD_MARK[x.kind])); walk(x, d + 1)
                if x.else_items is not None: emit_else(x, d)
            else:
                lines.append((b.owner[id(x)], d, LEAF_MARK.get(str(x), "")))
    walk(root, 0)
    # 같은 절의 잎 여러 개(pulse 등) → 한 줄
    dedup = []
    for ln in lines:
        if ln[0] is not None and any(p[0] == ln[0] for p in dedup): continue
        dedup.append(ln)
    lines = dedup
    placed = {ln[0] for ln in lines if ln[0] is not None}
    # 미배치 절 끼워 넣기 (원문 순서 유지)
    out = []; n = len(segs)
    def depth_near(i):
        after = next((ln[1] for ln in lines if ln[0] is not None and ln[0] > i), None)
        before = next((ln[1] for ln in reversed(lines) if ln[0] is not None and ln[0] < i), None)
        return after if after is not None else (before if before is not None else 0)
    li = 0
    for i in range(n):
        while li < len(lines) and (lines[li][0] is None or lines[li][0] < i):
            out.append(lines[li]); li += 1
        if i in placed:
            out.append(lines[li]); li += 1
        else:
            t, m, _ = segs[i]
            mk = "시각" if t == "TIME" or ("time" in m and t != "STOP" and i == 0) else ("읽기" if t == "READ" else ("종료" if t == "STOP" else ("아니면" if t == "ELSE" else "")))
            if t == "TIME" and any(ln[0] == i for ln in lines): continue
            out.append((i, depth_near(i), mk))
    out += lines[li:]
    # 첫 절이 시각(cron)만 있는 TIME이면 [시각], 절 자체가 이미 반복 머리면 그대로
    return out

def render(lines, segs, letter=None):
    rows = []
    for seg, d, mk in lines:
        txt = segs[seg][2] if seg is not None else ""
        tag = f"[{mk}] " if mk else ""
        rows.append(("  " * d + tag + txt).rstrip())
    body = "\n".join(rows)
    return (f"{letter})\n" if letter else "") + body

def key(lines): return tuple(lines)

def perturb(lines, segs):
    """단일 교란 후보 전부 (종류 태그 포함)."""
    L = list(lines); out = []
    n = len(L)
    for i, (seg, d, mk) in enumerate(L):
        if seg is None: continue
        prev_d = L[i - 1][1] if i > 0 else 0
        is_head = mk in ("반복", "조건", "아니면", "시각")
        # shift ±1 (잎·머리 모두; 머리를 옮기면 그 자식들도 함께)
        for dd in (-1, +1):
            nd = d + dd
            if nd < 0 or nd > prev_d + 1: continue
            if i > 0 and dd == +1 and L[i - 1][2] not in ("반복", "조건", "아니면") and nd > L[i - 1][1]: continue  # 상자 머리 없이 더 깊이 못 들어감
            M = list(L)
            j = i; M[j] = (seg, nd, mk); j += 1
            while is_head and j < n and L[j][1] > d:      # 자식 동반
                M[j] = (L[j][0], L[j][1] + dd, L[j][2]); j += 1
            if all(m[1] >= 0 for m in M): out.append(("shift", M))
        if mk == "아니면":
            M = list(L); M[i] = (seg, d, "조건"); out.append(("elseif", M))
        if mk == "조건" and i > 0 and any(L[k][2] == "조건" and L[k][1] == d for k in range(i)):
            M = list(L); M[i] = (seg, d, "아니면"); out.append(("elseif", M))
        if mk == "" and segs[seg][0] == "ACT":
            M = list(L); M[i] = (seg, d, "참조"); out.append(("ref", M))
            M = list(L); M[i] = (seg, d, "무시"); out.append(("drop", M))
        if mk in ("참조", "무시"):
            M = list(L); M[i] = (seg, d, ""); out.append(("ref" if mk == "참조" else "drop", M))
        if mk == "지연":
            M = list(L); M[i] = (seg, d, ""); out.append(("mark", M))
    # post: 말미(또는 뒤쪽) 조건 머리를 앞 행동 k개 위로 올려 감싸기
    for i, (seg, d, mk) in enumerate(L):
        if mk != "조건" or seg is None: continue
        follow = [k for k in range(i + 1, n) if L[k][1] > d]
        if follow: continue                          # 이미 자식이 있음
        for k in (1, 2, 3):
            if i - k < 0: break
            block = L[i - k:i]
            if any(b[1] != d for b in block): break
            M = L[:i - k] + [(seg, d, "조건")] + [(b[0], d + 1, b[2]) for b in block] + L[i + 1:]
            out.append(("post", M))
    # hoist: 상자 머리를 한 줄 뒤로 (첫 자식이 상자 밖으로)
    for i, (seg, d, mk) in enumerate(L):
        if mk not in ("반복", "조건") or i + 1 >= n or L[i + 1][1] <= d or L[i + 1][2] in ("반복", "조건", "아니면"): continue
        M = list(L); M[i], M[i + 1] = (L[i + 1][0], d, L[i + 1][2]), (seg, d, mk)
        out.append(("hoist", M))
    return out

def make_candidates(lines, segs, k=5, seed=0, double=True):
    rnd = random.Random(seed)
    seen = {key(lines)}; pool = []
    for tag, M in perturb(lines, segs):
        if key(M) not in seen and _valid(M):
            seen.add(key(M)); pool.append((tag, M))
    if double:
        for tag, M in list(pool):
            for tag2, M2 in perturb(M, segs):
                if key(M2) not in seen and _valid(M2):
                    seen.add(key(M2)); pool.append((tag + "+" + tag2, M2))
    # 종류 다양하게 뽑기: 단일 교란 우선(핵심 결정점 대안 보장), 그다음 이중 교란
    singles = [p for p in pool if "+" not in p[0]]; doubles = [p for p in pool if "+" in p[0]]
    rnd.shuffle(singles); rnd.shuffle(doubles)
    by = {}
    for tag, M in singles + doubles: by.setdefault(tag.split("+")[0], []).append((tag, M))
    picked = []
    while len(picked) < k - 1 and any(by.values()):
        for t in sorted(by):
            if by[t] and len(picked) < k - 1: picked.append(by[t].pop(0))
    return picked

def _valid(M):
    d0 = 0
    for i, (seg, d, mk) in enumerate(M):
        if d > d0 + 1: return False
        if d > d0 and (i == 0 or M[i - 1][2] not in ("반복", "조건", "아니면", "시각")): return False
        d0 = d
    if any(mk == "아니면" and (i == 0 or not any(M[j][2] in ("조건", "아니면") and M[j][1] == d for j in range(i))) for i, (seg, d, mk) in enumerate(M)): return False
    return True

if __name__ == "__main__":
    HERE = os.path.dirname(os.path.abspath(__file__))
    T = json.load(open(os.path.join(HERE, "..", "type", "type_labels.json")))
    for idx in [int(a) for a in sys.argv[1:]] or [220, 98, 306, 96, 244]:
        o = T[idx]; segs = [(s["type"], s["mods"], s["text"]) for s in o["segments"]]
        root = assemble_tree(segs, *gold_flags(o["ir_gt"]))
        L = tree_to_lines(root, segs)
        print("=" * 60); print(o["cmd"]); print(render(L, segs, "정답")); 
        for tag, M in make_candidates(L, segs, k=5):
            print(f"-- {tag}"); print(render(M, segs))
