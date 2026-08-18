# -*- coding: utf-8 -*-
"""명령어 → Timeline IR 파이프라인 (한 번 적재, 명령마다 호출).
  텍스트 → [2B 단어 상태(엔진 hook)] → 경계·타입·mods head → (같은 2B 1토큰 객관식 게이트, 저확신만) → 그래프 정규화(필러·참조·후치)
        → 임베딩 매핑(연결 기기 조인) → 상자 규칙 + 슬롯·재정렬 규칙 → IR JSON"""
from .encoder import WordEncoder, Embedder
from .heads import SegHeads
from .segment import Segmenter, MCQ
from .mapping import Retriever
from .builder import build

class CommandToIR:
    def __init__(self, engine=None, gates=True):
        """engine: engine.Engine(없으면 get_engine()) — 은닉 상태·객관식 게이트 모두 이 하나의 모델. gates=False면 head만."""
        if engine is None:
            import os, sys
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            if root not in sys.path: sys.path.insert(0, root)
            from engine import get_engine
            engine = get_engine()
        self.engine = engine
        self.seg = Segmenter(WordEncoder(engine), SegHeads.load(), MCQ(engine) if gates else None)
        self.map = Retriever(Embedder())
    def __call__(self, text, connected_devices=None, exclude=()):
        """→ {"ir": {...}, "segments": [...], "mapping": {...}, "graph": {...}}. exclude: 매핑 예문에서 뺄 원본 명령 i(평가용)."""
        segs = self.seg(text.strip())
        M = self.map(segs, connected_devices, exclude)
        ir = build(segs, M)
        return {"ir": ir, "segments": [{k: v for k, v in s.items() if k != "h6"} for s in build.last["segments"]],
                "mapping": {"ranked": M.r, "parts": M.p}, "graph": build.last["graph"]}
