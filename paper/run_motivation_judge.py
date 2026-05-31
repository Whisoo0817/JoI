#!/usr/bin/env python3
"""MOTIVATION (§1/§2): can a strong LLM verify reactive-automation code from the
NL intent alone? Shows the problem is intrinsic -- multiplicity + temporal
opacity -- so an LLM-reviewer is NOT a trustworthy safety net. No IR, no
mutation: ground truth is the NATURAL pipeline output (correct vs naturally
buggy programs our own generator produced).

Setup (deliberately the realistic developer/reviewer setting):
  input  = NL command (intent) + candidate JoI program
  ask    = "does this code correctly implement the command?"
  label  = behavioral match of joi_block vs ground-truth IR (ir_gt) -- the same
           E2E-correctness oracle used in e2e_382 (308 correct / ~74 wrong).
  give   = JoI grammar/semantics + the +/-500ms tolerance + CoT. NOT the IR
           (that is our artifact), NOT our simulator.
  metric = positive = "wrong". recall = caught buggy programs (the headline:
           a verifier that MISSES bugs is unsafe); FP = flagged a correct one.

Backends: qwen (local 9B) | gpt4o (needs paper/openai.txt).

Usage:
  PYTHONPATH=/home/gnltnwjstk/joi python3 paper/run_motivation_judge.py \
      --backend qwen --dump-dir <e2e off dump> --out <dir>
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "paper"))

from paper.run_mutation_test import load_meta, load_catalog, _verify
from paper.run_judge_compare import gen_qwen, parse_verdict

DATASET = os.path.join(ROOT, "dataset.csv")

_OAI = None


def gen_openai(prompt, model="gpt-4o", max_tokens=4096):
    """Chat completion for both gpt-4* and gpt-5* (reasoning) families."""
    global _OAI
    if _OAI is None:
        from openai import OpenAI
        _OAI = OpenAI(api_key=open(os.path.join(ROOT, "paper", "openai.txt")).read().strip())
    kwargs = {"model": model, "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.0, "seed": 42}
    if model.startswith("gpt-5"):
        kwargs["max_completion_tokens"] = max_tokens   # gpt-5* accepts temperature=0
    else:
        kwargs["max_tokens"] = max_tokens
    r = _OAI.chat.completions.create(**kwargs)
    return r.choices[0].message.content or ""

# Rows held out as few-shot exemplars -> EXCLUDED from the test set (no leakage).
FEWSHOT_NAMES = {"C09_10", "C07_10", "C20_1", "C03_10", "C17_1", "C08_1"}

# A purpose-built JoI reference for a JUDGE (NOT the lowering-compiler prompt).
# Explains syntax + every behavioral idiom this dataset uses, with snippets.
JOI_JUDGE_REF = """A JoI program is a small reactive home-automation script. The
runtime RE-EXECUTES the whole `script` once every `period` milliseconds (a polling
cycle). If `period` is 0 the script runs once. `cron` (e.g. "0 18 * * *") anchors
the start to a wall-clock schedule.

STATE PERSISTENCE -- read carefully:
- `x := v` is a PERSISTENT-STATE DECLARATION. Its initializer runs ONLY on the
  FIRST cycle. On every LATER cycle the `:=` line is SKIPPED entirely; the variable
  keeps the value it held at the end of the previous cycle. So `prev := false`
  sets prev=false ONCE at startup -- it does NOT reset prev to false each cycle.
- `x = v` is a plain assignment that runs every cycle.
- Example: after `n := 0` (cycle 1 only), a later `n = n + 1` accumulates across
  cycles; n is NOT reset to 0 on cycles 2,3,... because the `:=` line is skipped.

SYNTAX
- Device action (observable):  (#Tag #Tag).service_method(args)
- Multiplicity: all(#Tag ...) / any(#Tag ...) target many devices; `==|` compares
  a broadcast attribute (all(...).attr ==| true).
- Read into a variable:  x = (#TemperatureSensor).temperatureSensor_temperature
- Branch:  if (cond) { ... } else { ... }
- Fixed wait:  delay(10 MIN)   delay(1 HOUR)   delay(30 SEC)
- Blocking wait until a condition holds (level / "when"):  wait until(cond)
- Stop the current periodic cycle early:  break

BEHAVIORAL IDIOMS (how intent maps to code -- judge against these)
1. "When X happens, do Y" (one-shot, level): wait until(X)\\n Y
   -- fires once when X first holds.
2. "Every N minutes do Y" : block period = N*60000, body = Y (re-runs each cycle).
   "Stop after K times": n := 0\\n if (n >= K) { break }\\n Y\\n n = n + 1
3. "Each time / whenever X (edge), do Y" under a poll: use a one-shot guard so Y
   fires ONCE PER rising edge, not every cycle while X stays true:
       triggered := false
       if (X) { if (triggered == false) { Y\\n triggered = true } }
       else   { triggered = false }
4. "If X stays true FOR N seconds, do Y" (sustain): count cycles at period=100ms
   (0.1s), so N seconds = N*10 ticks:
       hold_ticks := 0
       if (X) { hold_ticks = hold_ticks + 1
                if (hold_ticks >= N*10) { Y\\n break } }
       else  { hold_ticks = 0 }      // reset when X breaks
5. "After 1 hour, do Z" (sequence): A\\n delay(1 HOUR)\\n Z
6. Hysteresis / alternation / counters use a persistent `:=` variable.

EQUIVALENT REALIZATIONS (do NOT flag these as errors -- they are CORRECT)
- "turn on" a light may be written as switch_on() OR moveToBrightness(B) with any
  B>0 (e.g. 100); "turn off" may be switch_off() OR moveToBrightness(0). These are
  the SAME action -- judge by EFFECT, not method name.
- Turning a device on may also be written as setting it to its normal working mode
  (e.g. a dehumidifier: switch_on() == setDehumidifierMode("dehumidifying")).
- Omitting a default-valued argument (e.g. TransitionTime=0, Rate=0) is NOT an error.
- Equivalent phrasings of an announced/spoken string, or a broader-but-correct form
  of the same trigger, are NOT errors.
A program is CORRECT if it achieves the commanded effect, even via a different but
behaviorally-equivalent method, argument form, or wording.

WHAT MAKES A PROGRAM WRONG (subtle, behavior-level)
- wrong trigger semantics: using `if (X)` under a nonzero period where the intent
  is one-shot -> Y re-fires every cycle while X holds (should fire once).
- off-by-tick timing: hold_ticks/period threshold gives the wrong duration.
- comparator/direction errors: >= vs >, <= vs <, or wrong branch.
- missing/extra/duplicated actions (a genuinely different effect), wrong device.
- missing the reset/break that bounds a counter or sustain timer.
Two action sequences are EQUIVALENT if they produce the same device EFFECTS at the
same times within +/-500ms; sub-500ms timing differences are NOT errors."""


def _fewshot_block(meta, catalog, commands, dump_dir):
    """Build worked examples from held-out rows: correct ones verbatim + two
    annotated WRONG variants (subtle temporal bugs) so the judge is TOLD what to
    look for. Returns the prompt text."""
    def load_joi(name):
        try:
            d = json.load(open(os.path.join(dump_dir, name + ".json"), encoding="utf-8"))
            return d.get("joi_block")
        except Exception:
            return None

    parts = ["# WORKED EXAMPLES\n"]
    # correct exemplars (verbatim, verifier-clean)
    for name in ["C03_10", "C07_10", "C09_10", "C20_1"]:
        jb = load_joi(name)
        if jb:
            parts.append("## Example (CORRECT)\nCOMMAND: " + commands.get(name, "") +
                          "\nPROGRAM: " + json.dumps(jb, ensure_ascii=False) +
                          '\nVERDICT: {"correct": true, "problem": "none"}\n')
    # annotated WRONG exemplars (generous: shows the bug classes)
    w1_cmd = commands.get("C08_1", "When button 1 is pressed, turn on all bedroom lights.")
    parts.append(
        "## Example (WRONG -- one-shot intent implemented as a level poll)\n"
        "COMMAND: " + w1_cmd + "\n"
        'PROGRAM: {"name":"Scenario","cron":"","period":100,'
        '"script":"if ((#MultiButton).multiButton_button1 == \\"pushed\\") '
        '{ all(#Light #Bedroom).light_moveToBrightness(100.0, 0.0) }"}\n'
        'VERDICT: {"correct": false, "problem": "period=100 re-runs the script '
        'every 0.1s, so while the button reads pushed the lights are re-commanded '
        'every cycle. A press should fire the action ONCE; needs wait until(...) '
        'or a one-shot triggered guard."}\n')
    w2_cmd = commands.get("C20_1", "If no motion for 30 seconds, turn off the plug.")
    parts.append(
        "## Example (WRONG -- sustain timer off by 10x)\n"
        "COMMAND: " + w2_cmd + "\n"
        'PROGRAM: {"name":"Scenario","cron":"","period":100,'
        '"script":"hold_ticks := 0\\nif ((#MotionSensor #LivingRoom).motionSensor_motion '
        '== false) { hold_ticks = hold_ticks + 1\\n if (hold_ticks >= 30) '
        '{ (#Plug #Switch #LivingRoom #Strip).switch_off()\\n break } }\\nelse '
        '{ hold_ticks = 0 }"}\n'
        'VERDICT: {"correct": false, "problem": "period is 100ms, so hold_ticks>=30 '
        'fires after 3 seconds, not 30. For 30s the threshold must be 300."}\n')
    return "\n".join(parts)


def load_commands():
    """name (e.g. C01_1) -> English NL command."""
    out = {}
    with open(DATASET, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = f"{row['category_v2']}_{row['index']}"
            out[name] = (row.get("command_eng") or row.get("command_kor") or "").strip()
    return out


def judge_prompt(command: str, joi_block: dict, fewshot: str) -> str:
    return (
        "# ROLE\nYou are reviewing an automatically generated home-automation "
        "program before it is deployed. Decide whether the JoI program correctly "
        "implements the user's natural-language command.\n"
        "CORRECT iff, under every relevant situation over time, the program performs "
        "exactly the device actions the command asks for -- right triggers, right "
        "conditions, right timing, no missing or extra actions. Timing differences "
        "within +/-500ms do NOT count as errors.\n\n"
        "# JoI LANGUAGE & IDIOM REFERENCE\n" + JOI_JUDGE_REF + "\n\n"
        + fewshot + "\n"
        "# NOW JUDGE THIS ONE\n"
        "USER COMMAND (intent): " + command + "\n"
        "PROGRAM: " + json.dumps(joi_block, ensure_ascii=False) + "\n\n"
        "# TASK\nReason step by step about the program's behavior over time -- at "
        "triggers, boundaries, branches, and over repeated cycles (you may think "
        "first). Then output ONLY a JSON object:\n"
        '{"correct": true|false, "problem": "<what is wrong, or none>"}\n'
    )


_RETRANS = None


def describe_prompt(joi_block: dict) -> str:
    """Step 1 of back-translation: code -> NL sentence, using the project's own
    re-translation prompt (paper/re_translate.md). Command NOT shown."""
    global _RETRANS
    if _RETRANS is None:
        _RETRANS = open(os.path.join(ROOT, "paper", "re_translate.md"), encoding="utf-8").read()
    return (_RETRANS + "\n\n# Now translate\nInput: `[Code] " +
            json.dumps(joi_block, ensure_ascii=False) + "`\nOutput:")


def match_prompt(command: str, description: str) -> str:
    """Step 2 of back-translation: does the description match the command?"""
    return (
        "# USER COMMAND (intended automation)\n" + command + "\n\n"
        "# DESCRIPTION OF A GENERATED PROGRAM\n" + description + "\n\n"
        "# TASK\nDoes the described program do EXACTLY what the command asks -- same "
        "trigger, conditions, timing, and actions, with nothing missing, wrong, or "
        "extra? Output ONLY:\n"
        '{"correct": true|false, "problem": "<mismatch, or none>"}\n')


def parse_correct(text):
    """True (correct) / False (buggy) / None (unparseable)."""
    s = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    m = re.findall(r'"correct"\s*:\s*(true|false)', s, re.I)
    if m:
        return m[-1].lower() == "true"
    # fall back to the equivalence parser shape if the model reused it
    return parse_verdict(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["qwen", "openai"], default="qwen")
    ap.add_argument("--model", default="gpt-4o", help="openai model id (e.g. gpt-5.1)")
    ap.add_argument("--dump-dir", default="", help="e2e off-mode dump (joi_block per row)")
    ap.add_argument("--stress-file", default="", help="pre-labeled items JSON [{name,command,joi,label}]")
    ap.add_argument("--out", default="/tmp/motivation_judge")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--names", default="", help="comma-separated row names to restrict to")
    ap.add_argument("--method", choices=["direct", "roundtrip"], default="direct",
                    help="direct = judge IR-free; roundtrip = back-translation (code->NL->match)")
    a = ap.parse_args()
    only = set(x.strip() for x in a.names.split(",") if x.strip())

    os.makedirs(a.out, exist_ok=True)
    meta = load_meta()
    catalog = load_catalog()
    commands = load_commands()

    # few-shot exemplars always come from the e2e off-dump
    fewshot_dir = a.dump_dir or "experiments/e2e_382/20260528_150445__d886015/intermediate/off"

    # Build labeled items.
    items = []
    files = [] if a.stress_file else sorted(
        f for f in os.listdir(a.dump_dir)
        if f.endswith(".json") and not f.startswith("_"))
    if a.stress_file:
        for it in json.load(open(a.stress_file, encoding="utf-8")):
            if only and it["name"] not in only:
                continue
            items.append({"name": it["name"], "cmd": it["command"],
                          "joi": it["joi"], "label": it["label"],
                          "fault_family": it.get("fault_family", ""),
                          "construct": it.get("construct", ""),
                          "operator": it.get("operator", "")})
    for fn in files:
        name = fn[:-5]
        if only and name not in only:
            continue
        if name in FEWSHOT_NAMES:
            continue  # held-out exemplar -> not a test item (no leakage)
        m = meta.get(name)
        cmd = commands.get(name)
        if not m or not isinstance(m.get("ir_gt"), dict) or not cmd:
            continue
        try:
            d = json.load(open(os.path.join(a.dump_dir, fn), encoding="utf-8"))
        except Exception:
            continue
        jb = d.get("joi_block")
        if not isinstance(jb, dict) or not (jb.get("script") or "").strip():
            continue
        try:
            flagged, _, _ = _verify(jb, m["ir_gt"], m["devs"], catalog)
        except Exception:
            continue  # pipeline/sim error -> drop (not a clean label)
        items.append({"name": name, "cmd": cmd, "joi": jb,
                      "label": "wrong" if flagged else "correct"})
    if a.limit:
        items = items[: a.limit]

    n_wrong = sum(1 for it in items if it["label"] == "wrong")
    n_correct = len(items) - n_wrong
    fewshot = _fewshot_block(meta, catalog, commands, fewshot_dir)
    print(f"[motiv] backend={a.backend} items={len(items)} (correct={n_correct} wrong={n_wrong})")

    if a.backend == "openai":
        gen = lambda p: gen_openai(p, a.model)
        tag = a.model.replace(".", "").replace("-", "")
    else:
        gen = gen_qwen
        tag = "qwen"
    tag = f"{tag}_{a.method}"
    verbose = bool(only) or bool(a.stress_file)
    # positive = "wrong/buggy"
    cm = {"TP": 0, "FP": 0, "TN": 0, "FN": 0, "unparsed": 0}
    miss = []           # buggy programs the judge called correct (the headline)
    dumped = []
    t0 = time.time()
    for i, it in enumerate(items, 1):
        gt_wrong = it["label"] == "wrong"
        try:
            if a.method == "roundtrip":
                desc = gen(describe_prompt(it["joi"]))
                raw = gen(match_prompt(it["cmd"], desc))
            else:
                raw = gen(judge_prompt(it["cmd"], it["joi"], fewshot))
            v = parse_correct(raw)
        except Exception as e:
            print(f"  [{i}] {it['name']} GEN-ERR {type(e).__name__}: {str(e)[:60]}")
            cm["unparsed"] += 1
            continue
        if v is None:
            cm["unparsed"] += 1
            jpred_wrong = None
        else:
            jpred_wrong = (v is False)   # correct=False => judge says buggy
            if gt_wrong:
                cm["TP" if jpred_wrong else "FN"] += 1
                if not jpred_wrong:
                    miss.append(it["name"])
            else:
                cm["FP" if jpred_wrong else "TN"] += 1
        prob = ""
        mprob = re.search(r'"problem"\s*:\s*"([^"]*)"', re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL))
        if mprob:
            prob = mprob.group(1)
        dumped.append({"name": it["name"], "gt": it["label"],
                       "judge_says_wrong": jpred_wrong, "problem": prob,
                       "fault_family": it.get("fault_family", ""),
                       "construct": it.get("construct", ""),
                       "operator": it.get("operator", "")})
        if verbose:
            verdict = "WRONG" if jpred_wrong else ("CORRECT" if jpred_wrong is False else "??")
            print(f"  {it['name']:9s} gt={it['label']:7s} judge={verdict:7s} :: {prob[:110]}")
        if i % 25 == 0:
            print(f"  [{i}/{len(items)}] {time.time()-t0:.0f}s  cm={cm}")

    tp, fp, fn, tn = cm["TP"], cm["FP"], cm["FN"], cm["TN"]
    rec = tp / (tp + fn) if tp + fn else 0.0
    prec = tp / (tp + fp) if tp + fp else 0.0
    print("\n" + "=" * 64)
    print(f"GROUND TRUTH (natural pipeline output): wrong={n_wrong} correct={n_correct}")
    print(f"{a.backend}-judge (NL command + code, no IR): {cm}")
    print(f"   recall={rec:.3f} (buggy programs CAUGHT)  precision={prec:.3f}")
    print(f"   -> MISSED {len(miss)} buggy programs (judged correct = would deploy a bug)")
    if miss:
        print("   missed:", ", ".join(miss[:40]))
    summary = {"backend": a.backend, "n_items": len(items),
               "n_wrong": n_wrong, "n_correct": n_correct,
               "judge": {**cm, "recall": rec, "precision": prec},
               "missed_buggy": miss, "detail": dumped}
    with open(os.path.join(a.out, f"_motiv_{tag}.json"), "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\n[motiv] -> {a.out}/_motiv_{tag}.json")


if __name__ == "__main__":
    main()
