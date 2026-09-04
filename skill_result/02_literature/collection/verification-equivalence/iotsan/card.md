---
slug: iotsan
type: paper
strand: verification-equivalence
year: 2018
authors: [Nguyen, Song, Qian, Krishnamurthy, Colbert, McDaniel]
venue: ACM CoNEXT 2018
doi: 10.1145/3281411.3281440
url: https://arxiv.org/abs/1810.09551
license: unknown
modalities: [SmartThings, smart-home]
tags: [model-checking, safety, interaction, attribution, state-explosion]
relevance: medium
imported_from: ../../../docs/OVLA_SenSys2027.pdf
added: 2026-09-04
pdf_status: not-redistributable
pdf_path: null
md_path: source.md
md_quality: clean
---

# TL;DR

IoTSan translates installed IoT applications and environments into a model and finds executions that violate fixed safety properties; it does not compare a generated implementation with a per-request expected behavior.

## Summary

IoTSan builds a holistic model of apps, devices, configurations, and interactions and uses model checking to find unsafe states. It includes domain-specific state-explosion reductions and vulnerability attribution. On 76 configured SmartThings systems it reports 147 vulnerabilities.

## Relevance to the review

IoTSan establishes that reachability and state explosion are central in IoT verification. The closest-work contrast must be stated by property/reference: unsafe-state reachability versus observational equivalence to an authoritative Timeline IR.

## Notable details

- Evaluated on a commercial IoT ecosystem.
- Includes app attribution, which new OVLA explicitly excludes as localization/repair.

## Open questions / limitations

- Physical/device models and safety properties differ from OVLA's code-equivalence observation model.
- Results do not imply coverage of generated reactive-temporal code idioms.

## Citations

- Primary key: `nguyen2018iotsan`.

