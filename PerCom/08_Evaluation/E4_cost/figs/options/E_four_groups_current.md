# Four-group E4 preview

Restores the historical W / B / K / combined layout from commit e61f2de, using current Explorer and explicit-state runs. Upper plots use the slowest of three runs, only where all three return EQUIV with closed exploration. Gray strips show categorical timeout markers; their heights do not represent runtimes. Lower plots show completed runs out of three. Each configuration has three runs; shared configurations occur in multiple panels. The wait-duration sweep is not shown here.

Sources: `runs/e4_free_serial.jsonl` and `runs/e4_explicit_w4.jsonl`. Explorer ran serially and the explicit-state baseline ran four workers on an eight-core host. This is a descriptive comparison of those configurations, not a matched-load speedup claim. No new measurements were made. The older horizon-limited baselines are not included.
