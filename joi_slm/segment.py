# -*- coding: utf-8 -*-
"""절 분할기 — 단어 상태 → 경계 → 절 타입·mods (+ 저확신 자리만 같은 모델 1토큰 객관식 게이트).
출력 절: {j, text, type, mods, p, h6}  (h6 = 층 6 절 끝 벡터, 그래프 정규화기 입력)"""
import re
import numpy as np
from .heads import SegHeads, MODS

NUMERAL = re.compile(r"(한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|스무|서른|반)"); UNIT = re.compile(r"(시간|시|분|초|번|회|개|장|컷|도|층)")
TYPE_OPTS = [("ACT", "행동 — 기기를 켜라/꺼라/설정하라 등 실행 명령"), ("COND", "조건 — 어떤 상태가 …이면/일 때(상태 검사)"), ("TRIG", "사건 — 무엇이 감지되면/눌리면/될 때마다(사건 발생 시)"),
             ("TIME", "시각·기간 — 언제 할지만 말함(오후 6시에, 매일 아침, 밤 10시부터 자정까지)"), ("DELAY", "지연 — N초/분/시간 뒤에"), ("READ", "값 확인 — 온도·습도 등을 읽거나 확인하라"),
             ("STOP", "중지 — 반복을 끝내라/그만"), ("ELSE", "아니면 — 앞 조건이 아닐 때")]

ELSE_HEAD = re.compile(r"^(아니면|아니라면|그렇지 않으면|그 외에는|그외에는)")
FRAG_RO = re.compile(r"(으로|로)[.,]?$")
DELAY_TAIL = re.compile(r"((\d+(?:\.\d+)?|한|두|세|네|다섯|반)\s*(밀리초|초|분|시간|일)\s*(뒤에|후에|뒤|후|있다가|지나서|지나고))[.,]?\s*$")
def stitch(segs):
    """나뉜 절 꿰매기(경계 head 실수 복구) — 매핑 전에 돌아서 서비스 후보도 온전한 절로 뽑힌다.
    ① 서술어 없이 '~로'로 끝나는 절("밥솥을 조리 모드로")은 다음 절을 꾸미는 조각 → 다음 절 앞에 붙인다.
       (단, 다음 절이 "아니면 …"이면 동사를 나눠 쓰는 if/else 관용구("냉방으로, 아니면 자동으로 설정")라 그대로 둔다)
    ② DELAY 절이 시간말 앞에 딴 말을 달고 있으면("밥솥을 조리 모드로 30분 뒤에") 그 말을 다음 행동 절로 넘긴다."""
    out = [dict(s) for s in segs]
    for i in range(len(out) - 2, -1, -1):                                    # ① 뒤에서부터: 조각이 이어져도 한 번에 붙는다
        s, nx = out[i], out[i + 1]
        if FRAG_RO.search(s["text"].strip()) and nx["type"] != "ELSE" and not ELSE_HEAD.match(nx["text"].strip()):
            out[i:i + 2] = [{**nx, "text": s["text"].rstrip(" ,.") + " " + nx["text"], "mods": sorted(set(s["mods"]) | set(nx["mods"]))}]
    for i, s in enumerate(out[:-1]):                                         # ② 시간말만 DELAY 에 남긴다
        if s["type"] == "DELAY" and out[i + 1]["type"] == "ACT":
            m = DELAY_TAIL.search(s["text"])
            pre = s["text"][:m.start()].strip(" ,.") if m else ""
            if pre and re.search(r"(을|를|으로|로)$", pre):                  # 딴 말 = 목적어·부사어 조각일 때만 (동사로 끝나면 관용구일 수 있어 안 건드림)
                s["text"] = m.group(1); out[i + 1]["text"] = pre + " " + out[i + 1]["text"]
    for r, s in enumerate(out): s["j"] = r
    return out

class MCQ:
    """단일 엔진으로 1토큰 객관식. 실패하면 None."""
    def __init__(self, engine): self.engine = engine
    def _logits(self, prompt, letters):
        try: return self.engine.choice(prompt, letters)
        except Exception: return None
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
        return stitch([{"j": r, "text": s, "type": ty[r], "mods": md[r], "p": float(pr[r]), "h6": F[ends[r] - 1, 1].astype(np.float32).tolist()} for r, s in enumerate(segs)])
