# Current E3 evaluation scope

Completed evaluation: [E3_QWEN_382_RESULT.md](E3_QWEN_382_RESULT.md).

E3 includes 382 confirmed IR/binding cases. Any IR containing a `timeout` or
`on_timeout` field is outside the evaluation scope, at any nesting depth.
This excludes C26_001 through C26_006, regardless of previous outcomes.

The original dataset retains all 388 cases. Full-catalog static validation
continues to check all 388; E3 generation, candidate manifests, preflight and
frozen evaluation select the same 382 cases through `e3.load_rows()`.
The lowering prompts are unchanged by this exclusion.

Historical 388-case protocols and results do not describe this scope and must
not be relabeled as 382-case evaluations. This exclusion provides no new model
results and does not resolve the previously identified prefix contamination.
