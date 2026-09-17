# E4 combined configuration preview

Seven existing combined-scaling configurations from `gen_grid.DIAGONAL`. W is sensor count, B is stage count, and K is repetition count. Wait duration is fixed at 2 min. These seven programs are a subset of the full 30-program E4 set.

Source files: `runs/e4_free_serial.jsonl`, `runs/e4_explicit_w4.jsonl`. Each point is the slowest of three completed runs; completion requires EQUIV and closed exploration in all three runs. All other displayed cases timed out in all three runs. The timeout strip is categorical; its marker locations do not encode runtimes. Lines connect measured configurations as visual guides, not fitted curves.

Explorer ran serially, while explicit-state exploration used four concurrent workers on an eight-core host. The comparison describes these configurations and is not a matched-load speedup measurement. No new experiment was performed.
