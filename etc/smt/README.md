# Archived SMT Experiments

This directory preserves symbolic-verification experiments conducted after the
SenSys submission. They were introduced on the `test` branch in commit
`0ca73f8` (2026-08-05) and later copied into the current line of development in
commit `5091e3c` (2026-08-13).

The code is retained for reference, not as part of the current paper pipeline.
It intentionally keeps its historical imports from the former `sim` and
`adapt` packages. Those packages are not included in the current working tree,
so the scripts are not expected to run without recovering the matching files
from Git history.

Current `timeline_ir`, `lowering`, `explorer`, and `sensys` code must not import
this archive, and this archive must not be redirected to those current packages.
