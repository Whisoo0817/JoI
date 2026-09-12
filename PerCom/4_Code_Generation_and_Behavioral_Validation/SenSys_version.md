# Code Generation and Behavioral Validation — SenSys version

The SenSys verifier extracted transition boundaries from Timeline IR, synthesized event scenarios around those boundaries, co-simulated the IR and JoI candidate, and compared observed action traces. It described omission detection, rejection soundness for replayed counterexamples, a finite bounded region, and a feedback loop in which counterexamples guided LLM repair.

That account used an `IR→FSM→boundary event→bounded trace-equivalence` pipeline and presented the verifier as a deterministic deployment gate. The current Explorer has a different contract: it explores reachable product states on demand, supports multiple proof paths, distinguishes finite-horizon agreement from horizon-free closure, and makes its trust base explicit.
