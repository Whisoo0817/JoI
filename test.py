"""Local test entry point for generate_joi_code.

Modes:
    python3 test.py target           # run full pipeline on test_targets indices
    python3 test.py target confirm   # IR-only first, print readable, prompt
                                     # user (yes → lowering; else → re-gen
                                     # with feedback, NYI placeholder).
    python3 test.py pre              # translation + pre_analysis ONLY
    python3 test.py custom           # single CUSTOM_COMMAND interactively

When run with `target` or `pre`, all stdout is mirrored to a timestamped log file in /tmp.
The path is printed at start and end so the caller can grep / tail it.
"""

import os
import re
import sys
import time
import pandas as pd

from config import get_client, get_model_id
from loader import PROMPTS
from paper.run_local_ir import generate_joi_code
from paper.timeline_ir import extract_ir, ir_to_readable, _format_services_block
from pipeline_helpers import run_llm_inference

import json as _json

# [MODE: target | pre] Test targets (python3 test.py target | pre)
# Keys are category_v2 (e.g., "C01"..."C18"). Values: list of indices, or None for all rows in that category.
test_targets = {
    "C01": [1], "C02": [1], "C03": [2], "C05": [1], "C06": [1],
    "C07": [1], "C08": [1], "C09": [1], "C10": [1], "C11": [1],
    "C12": [1], "C13": [1], "C14": [1], "C15": [1], "C16": [1],
    "C17": [1], "C18": [1], "C19": [1], "C20": [1], "C21": [1],
    "C22": [1], "C23": [1], "C24": [1], "C25": [1],
}


class _Tee:
    """Write to multiple streams (e.g. real stdout + log file) at once."""
    def __init__(self, *streams):
        self._streams = streams
    def write(self, data):
        for s in self._streams:
            try:
                s.write(data)
                s.flush()
            except Exception:
                pass
    def flush(self):
        for s in self._streams:
            try:
                s.flush()
            except Exception:
                pass

# [MODE: custom] Direct-input test case (python3 test.py custom)
CUSTOM_COMMAND = "Change the living room light color to purple."

CUSTOM_DEVICES = {
    "LR_Light": {"category": ["Light"], "tags": ["LivingRoom", "Light"]},
}

csv_file_path = 'dataset.csv'


def _idx_sort_key(x):
    """Sort the (object-dtype) `index` column numerically when possible,
    falling back to string order so mixed/non-numeric ids never crash."""
    s = str(x)
    return (0, int(s)) if s.lstrip('-').isdigit() else (1, s)


def _reindent_joi(script, tab="    "):
    """Display-only: re-indent a JoI script by brace depth so nested blocks read
    cleanly. Does NOT alter the actual script used by the pipeline/verifier."""
    out, depth = [], 0
    for raw in str(script).replace("\\n", "\n").split("\n"):
        s = raw.strip()
        if s == "":
            continue
        this = depth - (1 if s.startswith("}") else 0)
        out.append(tab * max(0, this) + s)
        depth = max(0, depth + s.count("{") - s.count("}"))
    return "\n".join(out)


def _pretty_code(code):
    """Print the JoI block with its `script` field re-indented for readability."""
    m = re.search(r'^(.*?"script"\s*:\s*")(.*)("\s*\}\s*)$', str(code), re.DOTALL)
    if not m:
        return code
    head, script, tail = m.group(1), m.group(2), m.group(3)
    return head.rstrip() + "\n" + _reindent_joi(script) + "\n" + tail.strip()


def print_result(result):
    log = result.get('log', {})
    if log.get('logs'):
        print(f"{log.get('logs', '')}")
    print("\n⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️\n")
    precision = result.get('precision')
    if precision:
        print("\n[Selectors]")
        for svc, sel_list in precision.items():
            print(f"  {svc}: {sel_list}")
    if result.get('ir_readable'):
        print(f"\n[IR Readable]\n{result['ir_readable']}")
    print(f"\ncode           :\n{_pretty_code(result.get('code', ''))}")
    print(f"response_time  : {log.get('response_time', '')}")


def run_targeted_test(df):
    print("\n🎯 Running Targeted Tests...")
    for category, indices in test_targets.items():
        print(f"--- Category {category} ---")
        sub = df[df['category_v2'] == category]
        if indices is None:
            indices = sorted(sub['index'].tolist(), key=lambda x: _idx_sort_key(x))
        for idx in indices:
            match = sub[sub['index'].astype(str) == str(idx)]
            if match.empty:
                print(f"(Idx {idx}) - Not Found")
                continue
            row = match.iloc[0]
            eng = row['command_eng']
            print(f"({idx}) Command: {eng}")
            print(f"[connected_devices]\n{row['connected_devices']}")
            try:
                result = generate_joi_code(eng, row['connected_devices'], {})
                print_result(result)
            except Exception as e:
                print(f"Error at Idx {idx}: {e}")
                logs = getattr(e, 'logs', '')
                if logs:
                    print(f"[logs]\n{logs}")


def _lower_confirmed_ir(eng, connected_devices, ir):
    """Lower a user-confirmed IR to JoI. The confirmed IR is injected via
    JOI_GT_IR_PATH so the pipeline skips re-extraction (service_plan / resolve /
    extract_ir) and lowers EXACTLY what the user approved; precision (device
    match) + Stage 4 lowering still run. Returns the generate_joi_code result."""
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".json", prefix="confirmed_ir_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        _json.dump(ir, f, ensure_ascii=False)
    try:
        os.environ["JOI_GT_IR_PATH"] = path
        os.environ.pop("JOI_IR_ONLY", None)
        return generate_joi_code(eng, connected_devices, {})
    finally:
        os.environ.pop("JOI_GT_IR_PATH", None)
        try:
            os.remove(path)
        except OSError:
            pass


def run_targeted_test_confirm(df):
    """Interactive IR-confirm flow per test_targets row:
      1. produce the Timeline IR only (no lowering) and print its readable form,
      2. prompt the user — `yes`/`y`/Enter → lower the CONFIRMED IR; any other
         text is treated as a correction and the IR is re-extracted with that
         feedback, then re-rendered for another round.
    Lowering injects the confirmed IR (JOI_GT_IR_PATH) so the emitted JoI
    corresponds exactly to the IR the user approved — no silent re-extraction."""
    print("\n🎯 Running Targeted Tests with IR-Confirm...")
    for category, indices in test_targets.items():
        print(f"--- Category {category} ---")
        sub = df[df['category_v2'] == category]
        if indices is None:
            indices = sorted(sub['index'].tolist(), key=lambda x: _idx_sort_key(x))
        for idx in indices:
            match = sub[sub['index'].astype(str) == str(idx)]
            if match.empty:
                print(f"(Idx {idx}) - Not Found")
                continue
            row = match.iloc[0]
            eng = row['command_eng']
            print(f"\n({idx}) Command: {eng}")
            print(f"[connected_devices]\n{row['connected_devices']}")

            # ── Phase 1: IR only (short-circuit before Stage 4 lowering) ──
            os.environ["JOI_IR_ONLY"] = "1"
            try:
                ir_result = generate_joi_code(eng, row['connected_devices'], {})
            except Exception as e:
                print(f"IR Error at Idx {idx}: {e}")
                logs = getattr(e, 'logs', '')
                if logs:
                    print(f"[logs]\n{logs}")
                os.environ.pop("JOI_IR_ONLY", None)
                continue
            finally:
                os.environ.pop("JOI_IR_ONLY", None)

            current_ir = ir_result.get('ir')
            current_readable = ir_result.get('ir_readable') or ir_to_readable(current_ir)
            print(f"\n[IR Readable]\n{current_readable}")

            # Parse connected_devices once into a dict so extract_ir's retry
            # path can re-render the services block on a correction.
            try:
                devs_dict = _json.loads(row['connected_devices']) if isinstance(row['connected_devices'], str) else row['connected_devices']
            except Exception:
                devs_dict = row['connected_devices']

            # ── Phase 2: confirm / correct loop ──
            while True:
                try:
                    ans = input("\nConfirm IR? (yes/y → lower; or type a correction): ").strip()
                except EOFError:
                    ans = ""

                if ans.lower() in ("yes", "y", ""):
                    try:
                        full = _lower_confirmed_ir(eng, row['connected_devices'], current_ir)
                        print_result(full)
                    except Exception as e:
                        print(f"Lowering Error at Idx {idx}: {e}")
                        logs = getattr(e, 'logs', '')
                        if logs:
                            print(f"[logs]\n{logs}")
                    break

                # Correction path — re-run IR-extract multi-turn:
                # prior_user replays what the model saw (Command + Services),
                # prior_assistant = the IR it produced, hint = user's correction.
                prior_user = (
                    f"[Command]\n{eng}\n\n"
                    f"[Services]\n{_format_services_block(devs_dict)}"
                )
                prior_assistant = _json.dumps(current_ir, ensure_ascii=False, indent=2)
                try:
                    new_ir, *_rest = extract_ir(
                        eng,
                        devs_dict,
                        auto_translate=False,
                        retry_context=(prior_user, prior_assistant, ans),
                    )
                except Exception as e:
                    print(f"Re-IR Error: {e}")
                    continue

                current_ir = new_ir
                current_readable = ir_to_readable(new_ir)
                print(f"\n[IR Readable (after feedback)]\n{current_readable}")
                # loop — allow further feedback or yes


def run_pre_analysis_only(df):
    """Translation + pre_analysis only. No service_plan, no precision, no IR."""
    print("\n🔍 Running Pre-Analysis Only...")
    client = get_client()
    model = get_model_id(client)

    def infer(key, user_input):
        sys_content = PROMPTS.get(key, "")
        content, log_line = run_llm_inference(model, client, key, [
            {"role": "system", "content": sys_content},
            {"role": "user", "content": user_input},
        ])
        return content, log_line

    for category, indices in test_targets.items():
        print(f"--- Category {category} ---")
        sub = df[df['category_v2'] == category]
        if indices is None:
            indices = sorted(sub['index'].tolist(), key=lambda x: _idx_sort_key(x))
        for idx in indices:
            match = sub[sub['index'].astype(str) == str(idx)]
            if match.empty:
                print(f"(Idx {idx}) - Not Found")
                continue
            row = match.iloc[0]
            eng = row['command_eng']
            print(f"\n({idx}) Command: {eng}")
            t0 = time.perf_counter()
            try:
                sentence = eng
                logs = []
                pre, log_line = infer("pre_analysis", f"[Command]\n{sentence}")
                logs.append(log_line)
                elapsed = time.perf_counter() - t0
                print(f"\n[pre_analysis]\n{pre}")
                print(f"\n[stage timings]")
                for line in logs:
                    head = line.split("\n", 1)[0]
                    print(f"  {head}")
                print(f"[total: {elapsed:.2f}s]")
            except Exception as e:
                elapsed = time.perf_counter() - t0
                print(f"Error at Idx {idx} after {elapsed:.2f}s: {e}")


def run_custom_test():
    print("\n🛠️ Running Custom Test...")
    print(f"Command: {CUSTOM_COMMAND}")
    print(f"[connected_devices]\n{CUSTOM_DEVICES}")
    try:
        result = generate_joi_code(CUSTOM_COMMAND, CUSTOM_DEVICES, {})
        print_result(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")
        logs = getattr(e, 'logs', '')
        if logs:
            print(f"[logs]\n{logs}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "custom"
    submode = sys.argv[2] if len(sys.argv) > 2 else ""

    if mode in ("target", "pre"):
        suffix = f"_{submode}" if submode else ""
        log_path = f"/tmp/joi_{mode}{suffix}_{time.strftime('%Y%m%d_%H%M%S')}.log"
        log_fh = open(log_path, "w", encoding="utf-8")
        original_stdout = sys.stdout
        original_stdin = sys.stdin
        sys.stdout = _Tee(original_stdout, log_fh)
        try:
            print(f"📁 Log file: {log_path}")
            df = pd.read_csv(csv_file_path, encoding='utf-8-sig')
            if mode == "target":
                if submode == "confirm":
                    run_targeted_test_confirm(df)
                else:
                    run_targeted_test(df)
            else:
                run_pre_analysis_only(df)
            print(f"\n📁 Log file: {log_path}")
        except Exception as e:
            print(f"CSV Load Error: {e}")
        finally:
            sys.stdout = original_stdout
            sys.stdin = original_stdin
            log_fh.close()
            print(f"\n✅ Done. Log saved to: {log_path}")
    elif mode == "custom":
        run_custom_test()
    else:
        print("Usage: python3 test.py [target | pre | custom]")
