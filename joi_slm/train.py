# -*- coding: utf-8 -*-
"""자산 학습/생성 — 절 분할 head(seg_heads.pkl), 그래프 head(graph_heads.pkl), 코퍼스 예문(examples.json).
    python -m joi_slm.train [seg|graph|examples|all]   (리포 루트에서 실행; slm/experiments/ 의 상태 파일 필요)"""
import os, sys, json
import pandas as pd
EXP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "slm", "experiments")
def labels():
    T = json.load(open(os.path.join(EXP, "type", "type_labels.json"))) + json.load(open(os.path.join(EXP, "type", "type_labels_extra.json")))
    P = pd.read_csv(os.path.join(EXP, "map", "dataset_paper.csv")); G = {r.command_kor: json.loads(r.ir_gt) for r in P.itertuples() if isinstance(r.ir_gt, str)}
    return T, G
if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("seg", "all"):
        from .heads import train_seg_heads
        _, n = train_seg_heads(EXP); print("seg_heads.pkl: 경계 행", n[0], "절", n[1])
    if what in ("graph", "all"):
        from .graph import train_graph_heads
        train_graph_heads(os.path.join(EXP, "graph", "pairs.json"), os.path.join(EXP, "graph", "pairs_words.npz")); print("graph_heads.pkl")
    if what in ("examples", "all"):
        from .mapping import build_examples
        from .encoder import make_embedder
        from .evaluate import gold_fix
        T, G = labels()
        ex = build_examples([o for o in T if o["cmd"] in G], lambda o: gold_fix(o["cmd"], G[o["cmd"]]), make_embedder()); print("examples.json:", len(ex))
