---
slug: practical-tap
type: paper
strand: reactive-temporal-iot
year: 2014
authors: [Ur, McManus, Ho, Littman]
venue: ACM CHI 2014
doi: 10.1145/2556288.2557420
url: https://doi.org/10.1145/2556288.2557420
license: publisher-paywall
modalities: [smart-home, end-user-programming]
tags: [trigger-action, IFTTT, usability, expressiveness, smart-home]
relevance: medium
imported_from: ../../../docs/OVLA_SenSys2027.pdf
added: 2026-09-04
pdf_status: not-redistributable
pdf_path: null
md_path: source.md
md_quality: partial
---

# TL;DR

Trigger-action programming lets users author explicit if-then behavior, making the rule itself the reference artifact, but it has expressiveness and authoring limitations for richer automations.

## Summary

The study evaluates whether average users can customize smart homes using trigger-action rules. It grounds the trigger-action abstraction in end-user programming and documents both its accessibility and limits. The user directly authors the rule; there is no separate generated host-language implementation whose intended behavior must be reconstructed.

## Relevance to the review

This distinction supports OVLA's problem formulation: classic TAP verification can treat the authored rule as the object of analysis, while generated reactive code needs a distinct authoritative specification.

## Notable details

- Canonical CHI paper on practical trigger-action programming.
- Relevant to target behavior taxonomy, but not evidence that all reactive-temporal behavior fits TAP.

## Open questions / limitations

- The paper does not define OVLA-style executable semantics or IR–code equivalence.
- Usability findings cannot be transferred to Timeline IR confirmation.

## Citations

- Primary key: `ur2014practical`.

