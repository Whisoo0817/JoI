---
slug: tapinspector
type: paper
strand: reactive-temporal-iot
year: 2022
authors: [Yu, Liu]
venue: IEEE Transactions on Information Forensics and Security
doi: 10.1109/TIFS.2022.3214084
url: https://arxiv.org/abs/2102.01468
license: unknown
modalities: [smart-home, concurrent-TAP]
tags: [model-checking, concurrency, rule-latency, safety, liveness, state-space]
relevance: high
imported_from: ../../../docs/OVLA_SenSys2027.pdf
added: 2026-09-04
pdf_status: not-redistributable
pdf_path: null
md_path: source.md
md_quality: clean
---

# TL;DR

TAPInspector models concurrent trigger-action systems with rule latency and physical interactions, then checks fixed safety/liveness properties; it is close on temporal/concurrent modeling but has a different reference and verification question.

## Summary

TAPInspector extracts rules from real IoT apps, translates them to a hybrid model, applies model slicing and state compression, and performs model checking. It reports 533 interaction-related violations across 1,108 market apps and a large speedup over an unoptimized baseline. Its checked targets are safety and liveness properties rather than equality with a user-confirmed per-automation behavior trace.

## Relevance to the review

It is a primary closest-work comparator for modeling concurrency, latency, and reachability. OVLA's delta must be framed by reference: per-request implementation equivalence instead of violation of a predefined safety/liveness property.

## Notable details

- Models concurrency, rule latency, tardy physical attributes, and device connections.
- Uses state-space reduction, which raises soundness questions relevant to any future OVLA abstraction.

## Open questions / limitations

- It analyzes TAP rules as the program, not separately generated arbitrary code against a confirmed IR.
- Its optimizations cannot be reused as OVLA evidence without matching semantic models.

## Citations

- Primary key: `yu2022tapinspector`.

