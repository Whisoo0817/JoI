#!/usr/bin/env bash
# Phase 0 baseline driver. Runs eval_harness per category, segmented logs to /tmp.
# Usage: ./paper/eval/run_baseline.sh [CAT1 CAT2 ...]
# If no args, runs all 17 categories in dataset order.

set -u
cd "$(dirname "$0")/../.."   # → joi/

TS=$(date +%Y%m%d_%H%M%S)
LOG_DIR=/tmp
SUMMARY="${LOG_DIR}/joi_eval_summary_${TS}.txt"

CATS=("$@")
if [ ${#CATS[@]} -eq 0 ]; then
    CATS=(C01 C02 C03 C04 C05 C07 C08 C09 C10 C11 C12 C13 C14 C15 C16 C17 C18)
fi

echo "=== Phase 0 baseline ===" | tee "$SUMMARY"
echo "TS=$TS" | tee -a "$SUMMARY"
echo "Categories: ${CATS[*]}" | tee -a "$SUMMARY"
echo "" | tee -a "$SUMMARY"

for cat in "${CATS[@]}"; do
    log="${LOG_DIR}/joi_eval_${cat}_${TS}.log"
    echo "── $cat → $log" | tee -a "$SUMMARY"
    t0=$(date +%s)
    python3 -m paper.simulators.eval_harness --cat "$cat" >"$log" 2>&1
    rc=$?
    dt=$(( $(date +%s) - t0 ))
    # Extract the per-class one-liner from the summary block
    summary_line=$(awk '/^By class:$/{flag=1;next} flag && /^By category:/{flag=0} flag && NF' "$log" | tr '\n' ' ')
    echo "    rc=$rc dt=${dt}s  ${summary_line}" | tee -a "$SUMMARY"
done

echo "" | tee -a "$SUMMARY"
echo "=== Done ===" | tee -a "$SUMMARY"
echo "Summary: $SUMMARY"
