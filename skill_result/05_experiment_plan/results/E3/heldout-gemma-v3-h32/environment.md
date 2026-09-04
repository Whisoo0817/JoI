# Measurement environment

- Date: 2026-09-04 (Asia/Seoul)
- Evaluator commit: `91a1b393e6ba6845d99d974ba94a06d7be33e861`
- OS/kernel: Linux 5.15.0-139-generic, x86-64
- Python: 3.8.10
- CPU: Intel Core i9-11900K at 3.50 GHz, 8 cores / 16 hardware threads
- Memory: 125 GiB
- Evaluation mode: single `explorer.differential_sweep` process; H=32

Reported Explorer latency measures only the bounded Explorer call for each
READY pair. It excludes model generation, manifest construction, exact-oracle
execution, file loading, and aggregate report writing.
