# Timeline IR — SenSys version

The SenSys manuscript introduced Timeline IR as a compact typed JSON representation containing `start_at`, `cycle`, `wait`, `delay`, `read`, `if`, `call`, and `break`. It described validation constraints, variable and service types, and deterministic English rendering for user confirmation. The IR was positioned as the canonical intent contract from which both rendering and boundary-event synthesis were derived.

The earlier section primarily explained syntax and examples. Its deterministic and compositional claims were less tightly connected to the later execution contract than the current formal artifacts require.
