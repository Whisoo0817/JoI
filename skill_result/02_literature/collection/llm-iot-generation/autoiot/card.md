---
slug: autoiot
type: paper
strand: llm-iot-generation
year: 2025
authors: [Shen, Yang, Zheng, Li]
venue: ACM MobiCom 2025
doi: null
url: https://arxiv.org/abs/2503.05346
license: unknown
modalities: [AIoT, sensor-programming]
tags: [LLM, program-synthesis, execution-feedback, local-execution, AIoT]
relevance: medium
imported_from: ../../../docs/OVLA_SenSys2027.pdf
added: 2026-09-04
pdf_status: not-redistributable
pdf_path: null
md_path: source.md
md_quality: partial
---

# TL;DR

AutoIOT synthesizes and iteratively improves AIoT programs using background retrieval, decomposition, and compiler/interpreter feedback; it treats test execution as a development signal rather than deriving a per-request behavioral oracle.

## Summary

AutoIOT targets broad AIoT applications, decomposes requirements, generates code, and feeds execution errors back to the LLM. It emphasizes local execution of the synthesized program for privacy and cost, although synthesis uses remote models. Its empirical case is program synthesis capability across AIoT tasks.

## Relevance to the review

It is close on natural-language-to-IoT-code generation but not on the reference artifact. OVLA should compare what is checked: compiler/interpreter feedback and task tests versus trace equivalence to a user-confirmed Timeline IR.

## Notable details

- Published at MobiCom 2025; an author-hosted paper and arXiv record are public.
- Program optimization uses iterative execution feedback.

## Open questions / limitations

- The paper does not establish general reactive-temporal equivalence for generated code.
- Its task domain includes algorithmic AIoT programs for which ordinary execution tests may already exist.

## Citations

- Primary key: `shen2025autoiot`.

