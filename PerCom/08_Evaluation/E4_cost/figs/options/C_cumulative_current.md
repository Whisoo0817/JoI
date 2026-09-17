# E4 cumulative figure preview

For each of 30 programs, a method counts as complete only if all three runs return EQUIV with closed exploration. The plotted time is the slowest of those three runs. Undecided programs remain in the denominator of 30 and do not appear as completed at the budget limit. The horizontal axis is logarithmic. The run budget is 120 s.

Source: `runs/e4_free_serial.jsonl` and `runs/e4_explicit_w4.jsonl`. Explorer ran serially; explicit-state exploration used four concurrent workers on an eight-core host. These curves describe those configurations, not a matched-load speedup experiment.

The proposed fixed-step exploration with the same completion criterion has not been measured. Historical bounded fixed-step results are not included in this comparison.

Suggested caption: Cumulative number of programs decided within each checking time. Times are the slowest of three runs, and a program counts as decided only when all three runs complete. Explorer decided 28 of 30 programs; explicit-state exploration decided 12.
