"""Quick smoke test: translation + pre_analysis only.

Usage:
    cd /home/gnltnwjstk/joi
    python3 -m paper.test_pre_analysis [C09]      # default categories
    python3 -m paper.test_pre_analysis C09 C08    # specific categories
"""

from __future__ import annotations

import re
import sys
import time
import pandas as pd

from config import get_client, get_model_id
from loader import PROMPTS
from run_local import run_llm_inference

CSV = "dataset_migration/local_dataset2.csv"

DEFAULT_TARGETS = {
    "C09": [6, 13, 14, 16, 17],
}


def run_one(model, client, command_kor: str):
    log = []

    def infer(key, user_input):
        sys_content = PROMPTS.get(key, "")
        content, log_line = run_llm_inference(model, client, key, [
            {"role": "system", "content": sys_content},
            {"role": "user", "content": user_input},
        ])
        log.append(log_line)
        return content

    sentence = command_kor
    first_word = sentence.strip().split()[0] if sentence.strip() else ""
    if re.search("[가-힣]", first_word):
        sentence = infer("translation", sentence)

    pre = infer("pre_analysis", f"[Command]\n{sentence}")

    return sentence, pre, log


def main():
    args = sys.argv[1:]
    if args:
        targets = {c: DEFAULT_TARGETS.get(c) for c in args}
    else:
        targets = DEFAULT_TARGETS

    df = pd.read_csv(CSV, encoding="utf-8-sig")
    client = get_client()
    model = get_model_id(client)

    t_total = time.perf_counter()
    for cat, indices in targets.items():
        sub = df[df["category_v2"] == cat]
        if indices is None:
            indices = sorted(sub["index"].tolist())
        for idx in indices:
            match = sub[sub["index"] == idx]
            if match.empty:
                print(f"\n--- {cat} #{idx} NOT FOUND ---")
                continue
            row = match.iloc[0]
            kor = row["command_kor"]
            print(f"\n=========== {cat} #{idx} ===========")
            print(f"KOR: {kor}")
            t0 = time.perf_counter()
            try:
                eng, pre, log = run_one(model, client, kor)
                elapsed = time.perf_counter() - t0
                print(f"ENG: {eng}")
                print(f"\n[pre_analysis]\n{pre}")
                print(f"\n[stage timings]")
                for line in log:
                    head = line.split("\n", 1)[0]
                    print(f"  {head}")
                print(f"[total: {elapsed:.2f}s]")
            except Exception as e:
                elapsed = time.perf_counter() - t0
                print(f"ERR after {elapsed:.2f}s: {e}")

    print(f"\nGRAND TOTAL: {time.perf_counter() - t_total:.2f}s")


if __name__ == "__main__":
    main()
