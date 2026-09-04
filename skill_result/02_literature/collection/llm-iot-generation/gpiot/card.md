---
slug: gpiot
type: paper
strand: llm-iot-generation
year: 2025
authors: [Shen, Yang, Huang, Ma, Zheng]
venue: ACM SenSys 2025
doi: null
url: https://arxiv.org/abs/2503.00686
license: unknown
modalities: [AIoT, edge-ML]
tags: [SLM, IoTBench, code-generation, local-model, program-synthesis]
relevance: medium
imported_from: ../../../docs/OVLA_SenSys2027.pdf
added: 2026-09-04
pdf_status: not-redistributable
pdf_path: null
md_path: source.md
md_quality: partial
---

# TL;DR

GPIoT fine-tunes small local models for IoT program synthesis and evaluates task accuracy on IoTBench, providing a generation baseline but not an executable natural-language-derived behavioral specification.

## Summary

GPIoT uses specialized small language models for task decomposition, requirement transformation, and code generation. It constructs IoT-specific training data and IoTBench, and reports substantially higher task accuracy than general code models. The generated applications include signal-processing and machine-learning tasks whose correctness can be judged with executable tasks.

## Relevance to the review

The paper supports the existence and value of local IoT program synthesis. It also sharpens the OVLA boundary: its executable task oracle is available for algorithmic programs, whereas reactive-temporal automations require an explicit per-request expected trace.

## Notable details

- Reports average task-accuracy improvement of 64.7% over compared code models.
- Includes expert and non-expert user trials.

## Open questions / limitations

- Its benchmark task accuracy is not equivalent to behavior over asynchronous timed input histories.
- It should not be described as a direct verifier baseline without aligning tasks and oracle.

## Citations

- Primary key: `shen2025gpiot`.

