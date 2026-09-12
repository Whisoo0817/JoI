"""Manual classification of every executable candidate that failed a history.

Labels were assigned by reading the generated script and its trace diff
(`runs/results_<model>.jsonl`). They are the pilot author's judgment, not an
independent annotation.

mechanism
  sustain_as_delay_recheck  continuous-duration condition implemented as wait/delay then one re-check
  repeat_policy             fires again (or not) after an episode, differing from the confirmed once/re-arm policy
  counter_per_tick          iteration/announcement counter advanced every polling tick instead of per event
  tick_conversion           duration converted to the wrong number of polling ticks for the chosen period
  snapshot_lifetime         stored value kept from an earlier episode (`:=`) instead of re-read per episode
  spurious_operation        extra computation not in the behavior (e.g. abs on a signed difference)
  broken_state_logic        counter/flag/prev-value bookkeeping that never or wrongly reaches the action
  inverted_condition        sensor polarity or branch inverted
  no_temporal_logic         checks once and ends; no waiting/repetition at all
  control_misuse            break/termination placed so the automation ends early

layer
  implementation   the given input (command, contract or IR) determines the behavior that was violated
  interpretation   NL-only condition, and the command admits the generated reading (post-hoc judgment)
  prompt_rule      IR condition, and a rule of the production lowering prompt produces the error
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

LABELS = {
    # ── qwen9b (thinking off) ──
    ("qwen9b", "IR", "T02", 1): ("tick_conversion", "implementation"),
    ("qwen9b", "IR", "T02", 2): ("control_misuse", "implementation"),
    ("qwen9b", "IR", "T02", 3): ("tick_conversion", "implementation"),
    ("qwen9b", "IR", "T03", 2): ("tick_conversion", "implementation"),
    ("qwen9b", "IR", "T03", 3): ("broken_state_logic", "implementation"),
    ("qwen9b", "IR", "T08", 3): ("spurious_operation", "implementation"),
    # IR T10-T12 regenerated after the count-rule fix in files/joi_cycle.md (pre-fix labels: git history / archive)
    ("qwen9b", "IR", "T10", 2): ("broken_state_logic", "implementation"),
    ("qwen9b", "IR", "T12", 1): ("tick_conversion", "implementation"),
    ("qwen9b", "IR", "T12", 2): ("counter_per_tick", "implementation"),
    ("qwen9b", "IR", "T12", 3): ("counter_per_tick", "implementation"),
    ("qwen9b", "NL", "T01", 1): ("no_temporal_logic", "implementation"),
    ("qwen9b", "NL", "T02", 1): ("control_misuse", "implementation"),
    ("qwen9b", "NL", "T02", 3): ("no_temporal_logic", "implementation"),
    ("qwen9b", "NL", "T04", 3): ("no_temporal_logic", "implementation"),
    ("qwen9b", "SPEC", "T04", 2): ("no_temporal_logic", "implementation"),
    ("qwen9b", "SPEC", "T04", 3): ("no_temporal_logic", "implementation"),
    # ── gpt54mini ──
    ("gpt54mini", "NL", "T01", 1): ("inverted_condition", "implementation"),
    ("gpt54mini", "NL", "T01", 2): ("repeat_policy", "interpretation"),
    ("gpt54mini", "NL", "T01", 3): ("repeat_policy", "interpretation"),
    ("gpt54mini", "NL", "T02", 1): ("sustain_as_delay_recheck", "implementation"),
    ("gpt54mini", "NL", "T02", 2): ("sustain_as_delay_recheck", "implementation"),
    ("gpt54mini", "NL", "T02", 3): ("sustain_as_delay_recheck", "implementation"),
    ("gpt54mini", "NL", "T12", 1): ("sustain_as_delay_recheck", "implementation"),
    ("gpt54mini", "NL", "T12", 2): ("repeat_policy", "interpretation"),
    ("gpt54mini", "NL", "T12", 3): ("sustain_as_delay_recheck", "implementation"),
    ("gpt54mini", "SPEC", "T05", 2): ("broken_state_logic", "implementation"),
    ("gpt54mini", "SPEC", "T09", 2): ("snapshot_lifetime", "implementation"),
    ("gpt54mini", "SPEC", "T12", 3): ("sustain_as_delay_recheck", "implementation"),
}


def main(models):
    out, missing = [], []
    table = defaultdict(Counter)
    for model in models:
        path = HERE / "runs" / f"results_{model}.jsonl"
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            r = json.loads(line)
            if r["stage_failed"] not in ("nominal", "boundary"):
                continue
            key = (model, r["condition"], r["task"], r["sample"])
            if key not in LABELS:
                missing.append(key)
                continue
            mech, layer = LABELS[key]
            kind = "silent" if r["stage_failed"] == "boundary" else "visible"
            out.append({"model": model, "condition": r["condition"], "task": r["task"], "sample": r["sample"],
                        "level": r["level"], "kind": kind, "mechanism": mech, "layer": layer})
            table[(model, r["condition"], kind, layer)][mech] += 1
    (HERE / "runs" / "divergence_classification.json").write_text(json.dumps(out, indent=1))
    for k in sorted(table):
        print(k, dict(table[k]))
    if missing:
        print("UNLABELED:", missing)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["qwen9b", "qwen9b_think", "gpt54mini"]))
