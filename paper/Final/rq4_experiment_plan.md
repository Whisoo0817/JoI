The off-run's verifier_trace is `enabled: False` (verifier off = no verdict stored), confirming the off/on pass counts (35/25) are computed at aggregation time by grading each off/on joi_block against gt_ir via the verifier-as-grader. This is the honest provenance for the demo-pool selection: the 9 "verifier-value" cases must be re-derived by grading, and the buggy "off" JoI is the artifact to register. I have full understanding now. Let me compile the protocol.

# Experiment Design Protocol — OVLA RQ4 (fig:rq4(a) feasibility, fig:rq4(b) deployment)

Prepared 2026-06-04. Read-only investigation complete. All file paths absolute. This protocol is executable as-is; provenance for every load-bearing number is pinned to existing artifacts.

---

## 0. Key provenance findings (read before running anything)

These are facts I verified in the existing data; several correct or sharpen claims now in the tex.

1. **The "52 of 382 physically realizable" claim reproduces exactly.** Script over `/home/gnltnwjstk/joi/dataset.csv` with the physical device set `{Plug, MotionSensor, AirQualitySensor, CarbonDioxideSensor, AirConditioner, PresenceSensor, Light, ContactSensor, Speaker, Clock}` and the realizability rule "all primary device categories of a row ⊆ physical set" yields **52** strict; adding `TemperatureSensor` yields **73**. The tex's "52 of 382" and the memo's "~73 with temp" are both correct and reproducible.

2. **The RQ1 repair accounting in the tex is OFF BY ONE versus the committed data.** `/home/gnltnwjstk/joi/experiments/stageB_382/20260528_170116__d886015/intermediate/_summary.json` shows `off.fail=35`, `on.fail=25` → **10 repaired, 25 still rejected**. The tex (§8.1, line 273) says "**11 repaired, 24 rejected**". `aggregate.json` confirms `stageB_on_pass=357` (357−347=10 repaired) and `recovery.helped=12, hurt=0`. The "11/24" and "12 helped" numbers do not all reconcile with off/on=35/25. **This must be re-derived and made internally consistent before submission** (see §C). Do not ship 11/24 unverified.

3. **The "9 cases (7 rejects, 2 repairs)" deployment claim is from the design memo, NOT from a graded artifact.** The 9 demo-pool cases (C23_1/3/4/5, C20_9, C24_2, C24_4, C16_5, C03_24) are listed in `project-rq4-deployment-efficiency-2026-06-01.md` as "silent-wrong-OFF 35 ∩ realizable". But in the committed `off/*.json` files the per-file `status` field is just `"ok"` (pipeline completion), and `verifier_trace` is `{"enabled": false}` for the off run. **The pass/fail verdict is computed at aggregation time by grading each off/on `joi_block` against `gt_ir`, not stored per row.** So the 9-case split is not yet backed by a regenerable table. This is the honest provenance and it must be regenerated (see §B.1) before the "7 rejects, 2 repairs" sentence can stand.

4. **C23_1 (the stated hero, "living-room motion 10 min") PASSED clean** — its off and on JoI are byte-identical and correct (`hold_ticks >= 600`, i.e. 600 ticks at 1 s = 10 min). The tex's hero is the **meeting-room** sustain (presence false 10 min → off, buggy fires at 1 min). That maps to **C24** (meeting-room) or **C20_9** (meeting-room 2 min). The hero's *buggy* variant is not a naturally-occurring failed row for C23_1; the buggy 1-min variant shown in fig:rq4(b) is a **demonstration artifact** (either a real failed row or a deliberately injected `hold_ticks >= 60` variant). Phrase this honestly (see §B threats).

5. **Judge latency for fig:rq4(a) is NOT yet measured.** `run_judge_compare.py` (line 211) only prints wall-clock progress; the saved `_judge_qwen.json` has no per-judgment latency. The local-9B-judge seconds-per-check number must be **newly timed**, not pulled from existing files. The cloud-judge number is also unmeasured (GPT arm "pending key re-add").

6. **fig:arch (`figs/system.pdf`) is ALSO missing**, not just fig:rq4. `ls figs/` shows only `Rendering1.pdf, Rendering2.pdf, trace.pdf`. The brief says fig:rq4 is the only placeholder; in fact `figs/system.pdf` referenced at line 190 is absent too. Flag to authors (out of RQ4 scope but a compile blocker).

7. **Verifier cost depends on simulation horizon, not LLM.** Both simulators fix a 7-day horizon (`MAX_T_MS = 7*86_400_000` in `ir_simulator.py:36`) with iteration caps (`MAX_TICKS=300_000` in `joi_simulator.py:43`). Verifier latency = L1 static + IR-FSM + event synthesis + 2 simulations + trace compare. This is the quantity to instrument for fig:rq4(a) "verifier ms" and the complexity-stratified worst case.

---

## DESIGN A — Mac Mini M4 16GB On-Device Feasibility

### A.1 What is measured vs cited (the integrity rule for fig:rq4(a))

Three bars in fig:rq4(a). Each must be labeled MEASURED or CITED in the caption:

| Bar | Quantity | Source | Status |
|---|---|---|---|
| OVLA verifier | per-automation verifier wall-time (L1+FSM+synth+2 sims+compare) | newly run on M4, **MEASURED** | run §A.4 |
| Local 9B judge | per-check judge wall-time (same IR↔code question, 9B on M4 via MLX) | newly timed via `run_judge_compare.py` + a timing patch, **MEASURED** | run §A.5 |
| Cloud judge | per-check latency + \$/check + network dependency | **CITED** (public API latency + token price) — do NOT claim you measured cloud unless you actually call it | §A.6 |

Do not present a cited cloud number as measured. The honest framing already in the tex ("a cloud judge costs seconds plus fees plus a network dependency") supports a cited bar; keep the caption explicit.

### A.2 Metric list (exact)

Per **pipeline stage** (intent analysis / device+tool mapping / IR extraction / lowering / **verifier**), report a **distribution p50 / p95 / worst** (DISTRIBUTION LOCK — no means in prose):

- LLM-stage latency (s): per-stage, from `time.perf_counter()` already wired in `pipeline_helpers.py:19,36` (`run_llm_inference`) and `run_local_ir.py:693,1237`. Structure these into a `timings:{stage: ms, total_ms}` dict (the memo's TODO — currently emitted only as log strings).
- Decode throughput (tok/s) per LLM stage: `completion_tokens/elapsed` already computed (`pipeline_helpers.py:41`).
- **Verifier latency (ms)**: wrap `verifier/retry_harness.py:run` (and inside it `l1_analyze`, `l2_check`) with `perf_counter`. Report L1, L2, and total separately. This is the headline "ms" bar.
- **Verifier worst-case by complexity** (NOT LOC): stratify each automation by (# triggers/waits, # timers/delays, # state vars, # devices, # boundary events synthesized, # cycle iterations simulated). Plot verifier-ms vs each axis to show it scales with structure, not code length.
- Peak unified memory (MB): `psutil` RSS around the pipeline + MLX process; for the verifier specifically use `tracemalloc`.
- Model load time (s): time from `mlx_lm` server start to first token ready (one-time, report once, not in the distribution).
- Power (W): `sudo powermetrics --samplers cpu_power,gpu_power -i 1000 -n <N>` during a sustained run; report idle baseline and active mean/peak.
- Repair-loop cost: # attempts, added latency per repaired row, oscillation count (from `retry_harness` AttemptRecord list, `max_attempts=3`).

### A.3 Sample, repetitions, conditions

- **Sample for the latency distribution: full 382** for the verifier (cheap, deterministic, no LLM — run all). For LLM-stage latency, the full 382 is ideal; if the M4 run is slow, a **justified stratified subset of ~80** (≥3 per the 24 `category_v2` classes, covering all idiom families) is defensible — state the stratification.
- **Repetitions:** LLM stages are nondeterministic in latency → **5 repetitions per item**, report p50/p95/worst across all (item × rep). Verifier is deterministic in output but variable in wall-time → **10 repetitions per item**, drop the first (warm cache). Power: 3 sustained sweeps.
- **Conditions:** single hardware = M4 16GB, MLX 4-bit, model = the ≤9B used elsewhere. The accuracy headline stays on 5090-AWQ (safety is backend-independent per the memo); M4 produces only feasibility numbers + a per-backend yield re-tally. Make this split explicit in §8 setup (already partially there, line 269).

### A.4 Commands (macOS, M4)

```bash
# 0. serve the 9B model OpenAI-compatibly (only LLM_BASE_URL changes vs the 5090 path)
mlx_lm.server --model <9B-4bit-mlx-repo> --port 8002
export LLM_BASE_URL=http://localhost:8002/v1

# 1. verifier-only latency over all 382 (no LLM; instrument retry_harness/l1/l2)
#    add perf_counter hooks + tracemalloc, write timings to results/feasibility_verifier.json
PYTHONPATH=/home/gnltnwjstk/joi python3 paper/feasibility.py   # extend this file: it currently only checks grammar G; add a --bench mode

# 2. end-to-end per-stage latency, 5 reps, stratified subset (reuse run_local_ir timing block)
PYTHONPATH=/home/gnltnwjstk/joi BATCH_WORKERS=1 \
  python3 paper/run_lower_gt_batch.py   # workers=1 so latency is not contended

# 3. power, in a second terminal, during step 2
sudo powermetrics --samplers cpu_power,gpu_power -i 1000 -n 600 > results/m4_power.txt

# 4. peak memory: wrap the runner with /usr/bin/time -l (macOS gives "maximum resident set size")
/usr/bin/time -l python3 paper/run_lower_gt_batch.py 2> results/m4_mem.txt
```

The memo's instrumentation TODO list (structure `timings` dict, add `hardware{}` block to `experiments/init_run.py` run.json, `psutil`/`tracemalloc`/`powermetrics`) is the implementation work; it is small (a few perf_counter wraps + a JSON aggregator). `feasibility.py` is currently only the grammar-G checker — extend it or add `paper/rq4_efficiency.py` as a separate runner+aggregator+plotter (per memo).

### A.5 Local-9B-judge latency (the comparison bar)

`run_judge_compare.py` already issues the exact IR↔code judge call (`gen_qwen`, line 71) at temp 0. It does NOT save latency. Minimal patch: wrap the `gen(prompt)` call (line 221) with `perf_counter`, append `latency_ms` to each `dumped` record, and dump a p50/p95 summary. Run on the M4 against the same 9B server:

```bash
PYTHONPATH=/home/gnltnwjstk/joi python3 paper/run_judge_compare.py \
  --backend qwen --seed-dir /home/gnltnwjstk/joi/experiments/stageB_382/20260528_170116__d886015/intermediate/on \
  --max 200 --out /home/gnltnwjstk/joi/experiments/judge_compare/m4_timed
```

This yields the "9B judge = seconds" bar from the SAME machine as the verifier bar (apples-to-apples: both on M4). The judge also re-confirms the RQ2 over-rejection story (existing `_judge_qwen.json`: judge FP=20/20 correct flagged wrong, P=0.75, vs verifier P=1.0).

### A.6 Cloud-judge bar (cited)

State it as cited: typical hosted-LLM chat latency for a ~2k-token reasoning judge is on the order of 1–5 s, plus per-call token cost (cite the provider's published per-1M-token price × the prompt+completion token count you already log), plus a network round-trip (the privacy/latency disqualifier from §1/§3). If you want one measured anchor, the existing `gen_gpt4o` path (line 85, needs `openai.txt` which is committed-banned — do NOT commit it) can produce a handful of timed calls for an appendix footnote, but treat cloud as CITED in the figure.

### A.7 Figure/table design for fig:rq4(a)

- **Primary panel: grouped bar, LOG y-axis (ms), three bars** (verifier ≈ low ms, 9B judge ≈ 10³–10⁴ ms, cloud judge ≈ 10³ ms + network). Log scale is mandatory: the verifier is ~3 orders below the judges; linear hides the verifier. Annotate each bar with \$/check (verifier \$0, cloud \$X) and "network: none/none/required".
- **Inset or companion small-multiple: verifier-ms vs complexity** (x = # boundary events or # state vars; y = verifier ms, linear). Shows the worst-case scaling claim.
- **Companion table** (the distribution): rows = pipeline stages + verifier; columns = p50 / p95 / worst (ms), decode tok/s, peak MB. One row "verifier" with sub-ms–to–few-ms; LLM stages in the 100s ms–s. Footnote: model load time (one-time) + idle/active power (W).
- Caption must mark MEASURED (verifier, 9B judge — on M4) vs CITED (cloud).

### A.8 Effort & riskiest step (Design A)

- **Wall-clock: ~1.5–2 days.** ~0.5 day instrumentation (perf_counter wraps, timings dict, judge-latency patch, aggregator/plotter); ~0.5 day M4 runs (382 verifier ×10 reps is minutes; LLM stages ×5 reps is the long pole, ~few hours); ~0.5 day power/memory + plotting.
- **Riskiest step: getting the 9B model to run under MLX on the M4 at all and matching the pipeline's expected output format.** The repo path uses vLLM/AWQ on the 5090; MLX 4-bit is a re-quantization, so generation *quality* (hence yield) shifts — but the memo's safety-invariance split protects the headline (only re-tally per-backend yield; keep 5090 accuracy headline). If MLX serving slips, fall back: measure verifier latency on M4 (the headline bar, LLM-free, no model needed) and cite the LLM-stage latency from the 5090 logs as an upper-reference. The verifier bar — the actual contribution — does not need the model at all.

---

## DESIGN B — Live Deployment (Mysmax / RasPi hub, ~10 devices)

### B.1 Selecting the N≈12–15 automations (do this from data first)

Two pools, combined:

**Pool 1 — verifier-value cases (regenerate the table; do NOT trust the memo's hand-list).** Run a grading pass that, for each of the 52 realizable rows, grades off-JoI and on-JoI against gt_ir using the verifier-as-grader, and emits per-row `{off_verdict, on_verdict, outcome ∈ {clean, repaired, rejected}}`:

```bash
# grade off & on joi_blocks in the committed stageB run against gt_ir, restricted to the 52 realizable rows
PYTHONPATH=/home/gnltnwjstk/joi python3 - <<'PY'
# load realizable indices (the 52), load gt_ir + off/on joi_block, call _verify from run_mutation_test
# emit results/realizable_verifier_outcomes.json with off_fail / on_pass / outcome per row
PY
```
This produces the regenerable basis for "K rejects, M repairs" among realizable rows. **Replace the memo's "9 (7 reject, 2 repair)" with whatever this grading yields, and cite the run dir + dataset SHA as provenance.** The 9-case list is plausible (all sustain-class, all realizable) but is currently unbacked by a stored verdict (finding #3).

**Pool 2 — clean idiom-family coverage:** 5–6 rows that pass clean, chosen to cover the idiom families named in §8 setup (edge/whenever, cycle/periodic, multi-step sequence, branch, counting). One per family, all realizable, distinct device types.

**Selection criteria, stated for the paper:** (a) physically realizable on the ~10-device testbed; (b) Pool 1 supplies both verifier outcomes (reject and repair) so the demo shows *both* endings; (c) Pool 2 supplies idiom-family breadth so the demo is not all-sustain; (d) the hero (meeting-room presence-false sustain) is included. N = |Pool1 realizable verifier-value| + |Pool2| ≈ 12–15.

### B.2 The hero scenario (fig:rq4(b)) and its honest provenance

Hero = meeting-room sustain: presence false for 10 min → all meeting-room lights off; buggy variant fires at 1 min. Map to the real meeting-room rows (C24 group; C20_9 is meeting-room 2-min). Two honest options for the buggy variant:

- **Preferred:** use a *real* failed-then-repaired meeting-room row from Pool 1 (off-JoI = the actual LLM bug, on-JoI = the verifier-repaired code). This makes the before/after a genuine pipeline output, not a hand-edited strawman.
- **If no real meeting-room row failed:** state plainly that the 1-min variant is a representative injected fault of the same class the verifier catches in the mutation study (the `tick_scale` / comparator-threshold operator, Table 1), deployed to show the physical consequence. Do not imply it was an organic generation error if it was injected.

The committed off-JoI artifacts live in `…/stageB_382/20260528_170116__d886015/intermediate/off/` — register those verbatim (the memo's plan). Note C23_1's off and on are identical/correct (finding #4), so it is the wrong source for a buggy hero; pick a meeting-room (C24/C20) row that actually diverges, or inject.

### B.3 Evidence to capture (rigor order)

1. **Timeline-trace figure (fig:rq4(b)) — the core.** For the hero, overlay three signals on a shared time axis: (i) sensor input (presence boolean), (ii) actuator commands issued by the deployed JoI (light off events), (iii) IR-predicted trace (the oracle). Plot OFF (buggy) and ON (repaired) on the same axes or stacked. **Window:** compress 10 min → ~10 s of real time (the memo's N-second compression) so the whole sustain fits one figure; label the axis with the compression factor honestly, OR show real minutes with a broken axis. The contrast is: buggy actuator-off lands at the 1-min mark while the IR-predicted off is at 10 min; repaired actuator-off coincides with the IR prediction at 10 min. **Signal source:** confirm you can extract the Mysmax/JoI hub device-event log (sensor state + issued command + timestamp) — this is the open question flagged in the memo ("(2) device event log API/file extractable?"). If not extractable, fallback = screen-recording + a hand-built timeline table.
2. **Functional results table:** columns = automation | idiom family | devices | verifier outcome (clean/repair/reject) | physical behavior matches IR? (✓/✗). One row per registered automation.
3. **Verifier-value before/after timeline:** the OFF-misfire vs ON-correct overlay (subset of #1, for the 2 repair cases).
4. **Testbed photo + layout** (see anonymity §B.5).
5. **Real-loop latency:** NL→registration time, sensor-event→actuation lag (a few representative numbers; not a distribution — this is a demo).

### B.4 Functional success criterion (per automation)

An automation "succeeds" iff, on the physical testbed, the deployed (verifier-passed) JoI produces actuator commands whose (device, method, timing-within-tolerance) match the IR-predicted trace, under at least one triggering scenario and one non-triggering scenario. For the 2 repair cases: success = ON-code matches IR AND OFF-code demonstrably misfired (both endings shown). For reject cases: success = the rejected code never reaches the hub (fail-closed), demonstrated by the pipeline refusing to emit deployable code.

### B.5 Anonymity (double-blind) — Mysmax is a leak

**Risk:** "Mysmax" appears in tex line 369 and is the advisor's company; a reviewer can de-anonymize via the platform name + JoI DSL. Under double-blind this is a real exposure.

**Fix (wording):** replace "a commercial platform (Mysmax)" with "**a deployed commercial smart-home platform (name withheld for blind review)**" and similarly anonymize JoI if it is uniquely identifying ("the platform's execution DSL"). Add a camera-ready note: "platform name to be restored." **Photo policy:** crop/blur any logo, brand label, app UI chrome, or product housing in the testbed photo; show generic devices + RasPi hub only. Avoid reflections/screens showing the app name. The functional table and timeline figures carry no brand and are safe.

### B.6 Threats to validity to preempt (put in §9)

- **Demo not statistics:** the tex already says "existence proof, not statistics" (line 369) — keep it; explicitly state N and that statistical claims rest on the 382-row simulation (RQ1–RQ3), the physical run only grounds realizability.
- **Cherry-picking:** disclose the selection rule (§B.1) and that the realizable subset is 52/382, fixed by device availability not by OVLA's favor; report any registered automation that failed physically (don't hide).
- **Sim-vs-hub drift:** the simulator is the oracle source; note any observed divergence between simulated and physical actuation timing (tolerance is max(500 ms, 10%)).
- **Injected vs organic bug** (hero): disclose per §B.2 if the buggy variant was injected.
- **Time compression:** disclose the compression factor in fig:rq4(b).

### B.7 Effort & riskiest step (Design B)

- **Wall-clock: ~2–3 days.** ~0.5 day device wiring + ~10-device registration; ~0.5 day regenerating the verifier-outcome table on the 52 realizable rows (§B.1, pure analysis, can run today); ~1 day registering N≈12–15 + running hero/repair/reject scenarios + capturing logs; ~0.5 day building timeline figures + table + anonymized photo.
- **Riskiest step: extracting timestamped sensor+command logs from the Mysmax/RasPi hub** (memo open question #2). The entire rigor of fig:rq4(b) depends on it. If the hub exposes no log API/file, the timeline figure degrades to a hand-transcribed table from a screen recording — much weaker. **Resolve this on day 1** before committing to the timeline-overlay figure design; have the screen-recording fallback ready.

---

## C. Exactly what changes in the current RQ4 text once data lands

| Location (tex) | Current text | Action |
|---|---|---|
| §8.1 line 273 | "11 repaired, 24 rejected fail-closed" | **Reconcile with data.** Committed `_summary.json` gives off=35/on=25 → 10 repaired / 25 rejected. Verify which is right (re-grade) and make 11/24, 10/25, and the "12 helped/0 hurt" in aggregate.json all consistent. **P0 — internal inconsistency a reviewer will catch.** |
| §8.1 line 273 | "rises from 90.84% to 93.19%" | aggregate.json says on=93.46%. 93.19 vs 93.46 differ because one is "deployed-correct" (excludes over-rejects) and one is gt_ir pass-rate. Confirm which metric the 93.19 is and footnote the difference. |
| §8.4 line 369 | "The verifier intervened in 9 cases (7 rejects, 2 repairs)." | **Replace with the regenerated count from §B.1** (grade the 52 realizable rows). State provenance: "among the 52 realizable automations, the verifier rejected K and repaired M (run `…/stageB_382/20260528_170116__d886015`, dataset SHA fff8f04…)." |
| §8.4 line 369 | "a commercial platform (Mysmax)" | Anonymize: "a deployed commercial smart-home platform (name withheld for blind review)." **P0 double-blind.** |
| fig:rq4 line 372–376 | `\figtodo{...}` placeholder | Replace with real fig:rq4(a) (log-scale 3-bar verifier/9B/cloud, MEASURED/CITED labeled) + fig:rq4(b) (hero timeline overlay). |
| §8 setup line 269 | "feasibility (latency distribution, memory, power)" | Fill with measured M4 p50/p95/worst, peak MB, W, model-load-time once §A runs. |
| §8.4 line 367 | "the LLM-free verifier costs milliseconds and \$0, a local 9B judge costs seconds and VRAM, a cloud judge costs seconds plus fees" | Replace "milliseconds"/"seconds" with the measured M4 numbers; keep cloud as cited. |
| §8.4 line 369 | "N≈12-15" and "52 of the 382" | 52 is **verified correct**; keep. Fix final N to the actual registered count. |
| (separate) line 190 | `figs/system.pdf` referenced, file missing | **Not RQ4 but a compile blocker** — flag to authors. |

---

## D. Two things authors can run TODAY (no hardware)

1. **Regenerate the realizable verifier-outcome table** (§B.1) — pure re-analysis of committed `stageB_382` artifacts; settles the "7 rejects, 2 repairs" provenance and the 11/24 reconciliation. No M4, no hub.
2. **Patch `run_judge_compare.py` to record per-judgment latency** (§A.5) and the verifier instrumentation (§A.4) — code-only, testable on the 5090 box now, then just re-point `LLM_BASE_URL` at the M4.

The single highest-risk dependency across both experiments is **hub log extraction** (Design B, fig:rq4(b)); resolve it day 1. The single highest-value cheap win is the **today-runnable re-grading** that fixes the unbacked "9 cases" and the off-by-one repair count — both are P0 reviewer-facing inconsistencies in the current draft.