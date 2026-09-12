# Implementation — PerCom working draft

We implemented VETS as a Python prototype with separate preparation, execution, and verification components. Preparation parses Timeline and JoI, validates the supported syntax and type constraints, resolves the binding plan against the device and service catalog, identifies behavior-relevant inputs and initial global state, and selects an applicable verification path. Unsupported ownership, selectors, code constructs, or input models fail closed before exploration.

The runtime layer provides a Timeline interpreter and supported JoI runners under the same logical-time and service model. The verification layer constructs typed input domains, schedules input and timer events, normalizes ACTION observations, maintains the product-state frontier, and replays candidate counterexamples. Concrete breadth-first exploration is supplemented by restricted symbolic-value and integer-relation paths when their preconditions hold. Each path exposes its completion status and work limits to the final gate.

The current artifact implements one JoI backend and a catalog-driven device model. Exact source size, dependency versions, hardware, process limits, and public artifact entry points will be inserted from the frozen evaluation environment: **[IMPLEMENTATION SNAPSHOT AND REPRODUCIBILITY DETAILS PENDING]**.
