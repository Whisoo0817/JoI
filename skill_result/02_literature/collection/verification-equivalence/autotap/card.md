---
slug: autotap
type: paper
strand: verification-equivalence
year: 2019
authors: [Zhang, He, Martinez, Brackenbury, Lu, Ur]
venue: IEEE/ACM ICSE 2019
doi: 10.1109/ICSE.2019.00043
url: https://doi.org/10.1109/ICSE.2019.00043
license: publisher-paywall
modalities: [smart-home, TAP]
tags: [LTL, synthesis, repair, property-specification, model-checking]
relevance: high
imported_from: ../../../docs/OVLA_SenSys2027.pdf
added: 2026-09-04
pdf_status: not-redistributable
pdf_path: null
md_path: source.md
md_quality: clean
---

# TL;DR

AutoTap synthesizes or repairs trigger-action rules so they satisfy user-specified Linear Temporal Logic properties; the property is a fixed requirement, not a complete per-request observable behavior oracle.

## Summary

AutoTap provides a property-specification interface for novice users, translates properties into Linear Temporal Logic, and synthesizes or repairs trigger-action programs. Its user studies show fewer mistakes than direct trigger-action authoring. Its formal check asks whether the rule system satisfies a property, which may permit many behaviors.

## Relevance to the review

AutoTap is close on user-specified temporal requirements and formal analysis. OVLA must not claim formal IoT verification is new; it should claim a different verification target: exact bounded observable behavior of generated code relative to a confirmed executable specification.

## Notable details

- Separates the property interface from the TAP program.
- Demonstrates that user-facing formal-property authoring can be studied, but new OVLA intentionally does not make that usability claim.

## Open questions / limitations

- Satisfaction of selected properties is weaker than full trace equality to a deterministic reference.
- TAP synthesis does not address arbitrary host-language idioms implementing the same rule.

## Citations

- Primary key: `zhang2019autotap`.

