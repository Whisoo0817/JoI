# -*- coding: utf-8 -*-
"""gold IR → 구조 뼈대(canonical skeleton). 값(cond 문자열, args, duration 숫자)은 버리고
op 이름·중첩·edge·슬롯 존재 여부만 남긴다. 조립 단계는 뼈대만 책임지므로(값은 매핑/슬롯 복사) 비교 대상 = 뼈대.

정규화:
  start_at            → SA(cron?)               anchor now/cron 유무만
  call                → CALL                     (var 반환값은 무시)
  read                → READ                     단, 바로 뒤 if의 cond가 $var를 쓰면 read는 if에 흡수(READ 절 없이 조건 절만으로 gold가 read를 넣는 경우)
  wait                → WAIT(edge, for?)
  if                  → IF[then...][else...]
  cycle               → CYC(period?, until?, count?)[body...]
  delay               → DELAY
  break               → BREAK
표기: 괄호 문자열 한 줄 (비교·집계 편의).
"""
import re

def _uses_var(cond, var):
    return isinstance(cond, str) and re.search(r"\$?\b" + re.escape(var) + r"\b", cond) is not None

def canon(nodes, fold_read=True):
    out = []
    i = 0
    while i < len(nodes):
        n = nodes[i]; op = n["op"]
        if op == "start_at":
            out.append("SA:cron" if n.get("cron") else "SA")
        elif op == "call":
            out.append("CALL")
        elif op == "read":
            # read 연속 뒤에 오는 if의 cond가 그 변수들을 쓰면 read는 조건 절의 값 읽기 → if에 흡수
            j = i
            while j < len(nodes) and nodes[j]["op"] == "read":
                j += 1
            nxt = nodes[j] if j < len(nodes) else None
            if fold_read and nxt and nxt["op"] == "if" and all(_uses_var(nxt.get("cond"), nodes[k]["var"]) for k in range(i, j)):
                i = j; continue
            out.append("READ")
        elif op == "wait":
            s = "WAIT:" + n.get("edge", "none") + (":for" if n.get("for") else "")
            out.append(s)
        elif op == "if":
            out.append("IF[" + " ".join(canon(n.get("then") or [], fold_read)) + "]" +
                       ("{" + " ".join(canon(n.get("else") or [], fold_read)) + "}" if n.get("else") else ""))
        elif op == "cycle":
            fl = []
            if n.get("period"): fl.append("p")
            if n.get("until"): fl.append("u")
            if n.get("count"): fl.append("c")
            out.append("CYC:" + "".join(fl) + "[" + " ".join(canon(n.get("body") or [], fold_read)) + "]")
        elif op == "delay":
            out.append("DELAY")
        elif op == "break":
            out.append("BREAK")
        else:
            out.append("?" + op)
        i += 1
    return out

def skeleton(ir, fold_read=True):
    if not ir:
        return None
    return " ".join(canon(ir["timeline"], fold_read))
