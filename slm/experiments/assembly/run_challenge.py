import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mcq, challenge
from candidates import render
items = challenge.items()
wrong = mcq.evaluate(items, "challenge")
groups = [("조건후치", 0, 6), ("REF", 6, 12), ("필러", 12, 16), ("장문", 16, 22)]
wrong_cmds = {w[0] for w in wrong}
for g, a, b in groups:
    print(f"  {g}: {sum(1 for it in items[a:b] if it[0] not in wrong_cmds)}/{b-a}")
for w in wrong:
    print("\n✗", w[0], "| 고른 교란:", w[1]); print("  선택:\n" + "\n".join("    " + l for l in w[3].splitlines()))
