# Decision gates

| Gate ID | Opens after | Decision question | Proceed if | Revise if | Stop if | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| E3-G0 | preflight | Is a full exploratory H=None recheck valid? | 388/388 hashes match and all outcomes are retained | snapshot mismatch is explainable before execution | selection or loss contract is incomplete | author |
| E3-G1 | E3-B1 | Are reported positives and divergences valid under the frozen contract? | every positive is closed/H=None, every divergence replay-confirmed, IDs and hashes complete | only explicit non-decisions/resource failures occur | any semantic invariant or snapshot check fails | author |
| E3-G2 | fresh generation | Can E3 be promoted beyond exploratory recheck? | new model endpoint, pre-generation freeze, unseen candidate bytes, full audit | endpoint or reproducibility remains unavailable | outcome-informed exclusions or protocol changes occur | author |
