# E1 depth additions — encoding and execution of the eight frozen cases

Frozen semantics: `../frozen_cases/*.md` (hashes in `../FREEZE_MANIFEST.md`, commit `35e6043`).

## Freeze of the executable transcription (before any encoding)

`depth_cases.py` transcribes the frozen records into runner input (histories, expected ACTIONs, devices) and fixes
the uniform rules T1–T7 (time origin, pulses, comparison, sampling, fault injection). `fixture.py` defines the
E1-local leaf stubs; `runs/fixture_catalog.json` is the global catalog plus those stubs. All three were hashed and
committed before any Timeline IR or JoI was written:

| File | sha256 |
|---|---|
| depth_cases.py | `af08252992faa333d72f95177e3bb57da32511156801409b11d60dd4d228c5d0` |
| fixture.py | `4540b35c7d670bcba89381d7faf6c938090b82fa92fdffbd54f6305e63852bd1` |
| runs/fixture_catalog.json | `1ffb63636d6056e33d7648a5f2ef7b48e591f9c32ad2d3a70a98a05717f5e9de` |

The global catalog `files/service_list_ver2.0.7.json`, the Timeline IR frontend, the reference runner and the
Explorer are not modified. A post-freeze correction to a transcription must be logged here with before/after
hashes and a reason taken from the frozen record, never from an encoding result.

## Outcome fields (protocol §8)

1. Timeline-language result: complete / partial / impossible / held.
2. Frontend: `timeline_ir.validate_ir` + catalog check against the fixture catalog, and `../../grammar_check.py`
   (constructs outside `files/timeline_ir/extractor.md`).
3. Reference runner: compile result, tolerance match and exact match per history (rule T5).
4. Catalog: which leaves needed an E1 stub.
5. JoI fallback: only when (1) is partial or impossible.
6. Explorer: auxiliary; never in the E1 adequacy numerator or denominator.
