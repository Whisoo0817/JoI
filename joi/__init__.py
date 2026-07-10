"""JoI code generation: a Korean/English command → a JoI automation block.

The single entry point is `generate_joi_code(sentence, connected_devices,
other_params)`. It runs a device-first pipeline that interleaves LLM stages
with deterministic Python steps:

    device targeting → translation → Timeline IR extraction → lowering → naming

Modules:
    generate     the pipeline itself; owns stage order and prompt assembly
    ir           Timeline IR extraction, schema validation, device/catalog checks
    feasibility  can this IR run on the connected devices? which lowering bucket?
    examples     few-shot example block for the lowering prompt
    catalog      service_list_ver*.json loader (capabilities, value domains)
    expr         expression parser for the IR's condition strings

Prompts live in files/*.md and are loaded by loader.py.
"""

from joi.generate import generate_joi_code

__all__ = ["generate_joi_code"]
