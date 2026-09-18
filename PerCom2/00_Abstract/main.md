# Abstract — SenSys version

Smart home automation increasingly relies on large language models (LLMs) to translate natural-language user intents into executable reactive rules. Deploying these rules directly on edge hubs creates reliability and safety risks because reactive IoT automations involve precise triggers, durations, and repetitions. OVLA addressed this problem with a typed Timeline IR that users confirmed through a deterministic plain-language rendering. It then synthesized boundary-event scenarios, co-simulated the IR and generated rule code, and compared their action traces before deployment.

The SenSys manuscript reported results on 382 natural-language automations, 1,552 injected faults, an end-to-end local-generation pipeline, and a commercial home-automation deployment. It framed the principal outcome as an on-device, deterministic, LLM-free deployment gate and reported a 0.97 ms median verification time on a Mac mini M4.

> Source-preservation note: this is a Markdown rendering of the argument and headline results in `docs/ovla0606.tex`, not evidence authorized for the redesigned PerCom paper.
