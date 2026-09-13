# Frozen depth-case records

These records freeze the external source, user-approved interpretation, bounded input histories, and reference action traces before a Timeline IR encoding is attempted. Times are relative to the stated scenario start except where clock time is integral to the requirement. `--` means that the expected externally observable action trace has no action at that input.

The records are source/semantics artifacts, not IR encodings and not Explorer results. Claude must preserve them when attempting Timeline IR and ordinary JoI implementations.

