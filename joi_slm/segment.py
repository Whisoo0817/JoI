# -*- coding: utf-8 -*-
"""절 분할기 — 단어 상태 → 경계 → 절 타입·mods (+ 저확신 자리만 9B 객관식 게이트).
출력 절: {j, text, type, mods, p, h6}  (h6 = 층 6 절 끝 벡터, 그래프 정규화기 입력)"""
import json, re, urllib.request
import numpy as np
from .heads import SegHeads, MODS

NUMERAL = re.compile(r"(한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|스무|서른|반)"); UNIT = re.compile(r"(시간|시|분|초|번|회|개|장|컷|도|층)")
TYPE_OPTS = [("ACT", "행동 — 기기를 켜라/꺼라/설정하라 등 실행 명령"), ("COND", "조건 — 어떤 상태가 …이면/일 때(상태 검사)"), ("TRIG", "사건 — 무엇이 감지되면/눌리면/될 때마다(사건 발생 시)"),
             ("TIME", "시각·기간 — 언제 할지만 말함(오후 6시에, 매일 아침, 밤 10시부터 자정까지)"), ("DELAY", "지연 — N초/분/시간 뒤에"), ("READ", "값 확인 — 온도·습도 등을 읽거나 확인하라"),
             ("STOP", "중지 — 반복을 끝내라/그만"), ("ELSE", "아니면 — 앞 조건이 아닐 때")]

class MCQ:
    """OpenAI 호환 completions(vLLM)로 1토큰 객관식. 실패하면 None."""
    def __init__(self, url="http://localhost:8002/v1/completions", model="cyankiwi/Qwen3.5-9B-AWQ-4bit"): self.url, self.model = url, model
    def _logits(self, prompt, letters):
        req = json.dumps({"model": self.model, "prompt": prompt, "max_tokens": 1, "temperature": 0, "logprobs": 20}).encode()
        try:
            r = urllib.request.Request(self.url, data=req, headers={"Content-Type": "application/json"})
            top = json.loads(urllib.request.urlopen(r, timeout=120).read())["choices"][0]["logprobs"]["top_logprobs"][0]
        except Exception: return None
        return [max([v for t, v in top.items() if t.strip() == L] or [-30.0]) for L in letters]
    def seg_type(self, cmd, seg):
        letters = "ABCDEFGH"; body = "\n".join(f"{letters[i]}. {d}" for i, (_, d) in enumerate(TYPE_OPTS))
        sc = self._logits(f"사용자 명령: \"{cmd}\"\n이 명령을 절 단위로 나눴을 때 다음 절의 역할을 고르시오.\n절: \"{seg}\"\n\n{body}\n\n답:", letters)
        return TYPE_OPTS[int(np.argmax(sc))][0] if sc else None
    def boundary(self, cmd, words, t):
        p = (f"사용자 명령: \"{cmd}\"\n이 명령을 의미 단위(조건/행동/시각/지연 절)로 나눌 때, 아래 두 부분 사이에서 나누는 것이 맞는가?\n"
             f"앞: \"{' '.join(words[:t])}\"\n뒤: \"{' '.join(words[t:])}\"\n\nA. 나눈다 (뒤 부분이 새 절의 시작)\nB. 나누지 않는다 (같은 절이 이어짐)\n\n답:")
        sc = self._logits(p, "AB"); return None if sc is None else int(sc[0] > sc[1])

class Segmenter:
    def __init__(self, encoder, heads=None, mcq=None, tau_type=0.8, tau_boundary=0.3):
        """encoder: WordEncoder. mcq: MCQ 또는 None(게이트 끔). tau_type: 타입 확률 < tau면 객관식. tau_boundary: |p-0.5| < tau면 객관식."""
        self.enc, self.heads, self.mcq, self.tau_t, self.tau_b = encoder, heads or SegHeads.load(), mcq, tau_type, tau_boundary
        self.log = []
    def __call__(self, text):
        words, F = self.enc(text)
        pb = self.heads.boundary_proba(F[:, 0]); lab = (pb >= 0.5).astype(int); lab[0] = 1
        for t in range(1, len(words)):
            if NUMERAL.fullmatch(words[t - 1]) and UNIT.match(words[t]): lab[t] = 0; pb[t] = 0.0     # "한 ‖ 시간"은 경계 아님
            elif self.mcq and abs(pb[t] - 0.5) < self.tau_b:
                g = self.mcq.boundary(text, words, t); self.log.append(("boundary", words[t], float(pb[t]), g))
                if g is not None: lab[t] = g
        starts = [t for t in range(len(words)) if lab[t] == 1]; ends = starts[1:] + [len(words)]
        segs = [" ".join(words[a:b]) for a, b in zip(starts, ends)]
        ty, pr, md = self.heads.types(F[[e - 1 for e in ends], 1])
        for r in range(len(segs)):
            if self.mcq and pr[r] < self.tau_t:
                t2 = self.mcq.seg_type(text, segs[r]); self.log.append(("type", segs[r], ty[r], float(pr[r]), t2))
                if t2: ty[r] = t2
        return [{"j": r, "text": s, "type": ty[r], "mods": md[r], "p": float(pr[r]), "h6": F[ends[r] - 1, 1].astype(np.float32).tolist()} for r, s in enumerate(segs)]
