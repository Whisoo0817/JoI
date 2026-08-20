# -*- coding: utf-8 -*-
"""IR 두 개 대보기 — 뜻이 같은데 적는 방식만 다른 것은 같은 것으로 친다.

정답(dataset.csv 의 ir_gt)은 사람이 손으로 적은 것이라, 뜻과 상관없는 자리에서 표기가 갈린다:
  · 센서값을 read 로 빼낼 때 붙이는 변수 이름이 행마다 제각각이다 (t1 v temp lux Temperature …)
  · 그 변수를 쓸 때 $ 를 붙이기도 하고 안 붙이기도 한다
  · 조건식에 괄호를 넣기도 하고 안 넣기도 한다
  · 스피커로 말할 문구는 한국어 명령을 영어 문장으로 옮겨 적어 두었다 (규칙으로는 만들 수 없는 자리)
이런 자리를 맞히는 건 실력이 아니므로, 채점은 두 가지로 나눠서 본다:
  똑같다(strict)  — 글자까지 완전히 같다
  뜻이 같다(same) — 위 표기 차이를 지우고 같다   ← 파이프라인 실력은 이쪽으로 본다
말 문구는 따로 세어 "문구까지 같은 행"으로 보고한다.
"""
import copy, json, re

TEXT_ARGS = {"Text", "Prompt", "Command", "Title", "Body", "Message"}   # 사람이 문장으로 적어 넣는 자리


def _walk(ir, fn):
    ir = copy.deepcopy(ir)
    def go(o):
        if isinstance(o, dict):
            fn(o)
            for v in list(o.values()): go(v)
        elif isinstance(o, list):
            for v in o: go(v)
    go(ir)
    return ir


def _drop_var(ir):
    """호출에 붙은 결과 이름표(var)는 이름이 제각각이라 지운다 (read 의 var 는 _inline_read 가 처리)."""
    return _walk(ir, lambda o: o.pop("var", None) if o.get("op") in ("call", "cycle") else None)


def _mask_text(ir):
    """말할 문구·프롬프트는 자리만 남기고 지운다."""
    def f(o):
        a = o.get("args")
        if isinstance(a, dict):
            for k in list(a):
                if k in TEXT_ARGS and isinstance(a[k], str): a[k] = "<문구>"
    return _walk(ir, f)


def _inline_read(ir):
    """read 로 빼 둔 센서값을 조건식에 도로 끼워 넣는다 — 변수 이름과 $ 표기를 없앤다."""
    ir = copy.deepcopy(ir)
    src = {}
    _walk(ir, lambda o: src.update({o["var"]: o["src"]}) if o.get("op") == "read" and o.get("var") and o.get("src") else None)
    def strip(node):
        if isinstance(node, list):
            return [strip(x) for x in node if not (isinstance(x, dict) and x.get("op") == "read" and x.get("var") in src)]
        if isinstance(node, dict): return {k: strip(v) for k, v in node.items()}
        return node
    ir = strip(ir)
    if src:
        s = json.dumps(ir, ensure_ascii=False)
        for v, t in sorted(src.items(), key=lambda x: -len(x[0])):
            s = re.sub(r"\$?\b" + re.escape(v) + r"\b(?!\.)", t, s)
        ir = json.loads(s)
    return ir


def _tidy_cond(ir):
    """조건식 표기 정리 — 괄호·군더더기 공백, 같은 항이 여러 번 나오면 하나로.
    (정답은 "문이 하나라도 열려 있으면" 을 기기 수만큼 'X or X' 로 늘려 적기도 한다 — 뜻은 X 하나와 같다.)"""
    def f(m):
        e = m.group(1).replace("(", "").replace(")", "")
        e = re.sub(r"\s+", " ", e).strip()
        for op in (" or ", " and "):
            if op in e and " or " not in e.replace(op, "") and " and " not in e.replace(op, ""):
                seen = []
                for t in e.split(op):
                    if t not in seen: seen.append(t)
                e = op.join(seen)
        return '"cond": "' + e + '"'
    return json.loads(re.sub(r'"cond": "((?:[^"\\]|\\.)*)"', f, json.dumps(ir, ensure_ascii=False)))


def normalize(ir):
    """표기 차이를 지운 모습."""
    for f in (_inline_read, _mask_text, _drop_var, _tidy_cond): ir = f(ir)
    return ir


def _J(x): return json.dumps(x, ensure_ascii=False, sort_keys=True)


def services(ir):
    return sorted(set(re.findall(r"\b([A-Z][A-Za-z]+\.[A-Za-z0-9]+)", json.dumps(ir, ensure_ascii=False))))


def verdict(ir, ir_gt):
    """→ {"strict": 글자까지 같다, "same": 뜻이 같다, "text": 말 문구까지 같다, "svc": 서비스가 같다}"""
    if ir_gt is None: return {}
    strict = _J(ir) == _J(ir_gt)
    svc = services(ir or {}) == services(ir_gt)
    same = svc and _J(normalize(ir or {})) == _J(normalize(ir_gt))     # 문구를 가려도 쓰는 서비스는 같아야 한다
    text = same and _J(_tidy_cond(_drop_var(_inline_read(ir or {})))) == _J(_tidy_cond(_drop_var(_inline_read(ir_gt))))
    return {"strict": strict, "same": same, "text": text, "svc": svc}
