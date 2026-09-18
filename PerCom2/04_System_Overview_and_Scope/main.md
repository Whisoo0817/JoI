# System Overview and Scope — SenSys version

The SenSys system accepted a natural-language request, generated Timeline IR, rendered the IR into plain language for user approval, lowered the approved IR to JOI, and placed a deterministic verifier before deployment. Failed candidates entered an automatic repair loop or were rejected; accepted candidates were deployed to a commercial edge hub. Timeline IR was described as the authoritative intent contract, and the verifier synthesized a compact boundary-event suite from the IR.

The design divided assurance into Layer A, where a user approved an IR rendering, and Layer B, where generated code was checked against the approved IR. The paper emphasized local operation, privacy, low latency, and fail-closed deployment.
