# -*- coding: utf-8 -*-
"""명령어 → Timeline IR 파이프라인 (한 번 적재, 명령마다 호출).
  텍스트 → [2B 단어 상태] → 경계·타입·mods head → (9B 객관식 게이트, 저확신만) → 그래프 정규화(필러·참조·후치)
        → 임베딩 매핑(연결 기기 조인) → 상자 규칙 + 슬롯·재정렬 규칙 → IR JSON"""
from .encoder import WordEncoder, Embedder
from .heads import SegHeads
from .segment import Segmenter, MCQ
from .mapping import Retriever
from .builder import build

class CommandToIR:
    def __init__(self, mcq_url="http://localhost:8002/v1/completions", mcq_model="cyankiwi/Qwen3.5-9B-AWQ-4bit", gates=True):
        """gates=False면 9B 객관식 게이트 없이 head만."""
        self.seg = Segmenter(WordEncoder(), SegHeads.load(), MCQ(mcq_url, mcq_model) if gates else None)
        self.map = Retriever(Embedder())
    def __call__(self, text, connected_devices=None, exclude=()):
        """→ {"ir": {...}, "segments": [...], "mapping": {...}, "graph": {...}}. exclude: 매핑 예문에서 뺄 원본 명령 i(평가용)."""
        segs = self.seg(text.strip())
        M = self.map(segs, connected_devices, exclude)
        ir = build(segs, M)
        return {"ir": ir, "segments": [{k: v for k, v in s.items() if k != "h6"} for s in build.last["segments"]],
                "mapping": {"ranked": M.r, "parts": M.p}, "graph": build.last["graph"]}
