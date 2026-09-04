# @ArgResolve

For query / prompt args (`ChatWithAI.Prompt`, `ExplainImage.*`, etc.), reformulate the NL phrase as a **complete, grammatical question or imperative**, not a fragment.
- ❌ `Prompt: "what LLM is"`, `Prompt: "the weather"`.
- ✅ `Prompt: "What is an LLM?"`, `Prompt: "What is the weather?"`.

Function returns (BINARY image, STRING text) flow into the next call's args via `$<MethodName>`. Use raw — do NOT wrap with NL-implied lead-in when the return is already a complete sentence/payload.

Example — chain `ChatWithAI` → `Speaker.Speak`:
```
[Command] Ask the cloud AI what an LLM is and output the answer through the speaker.
Output:
{
  "CloudServiceProvider.ChatWithAI": {"Prompt": "What is an LLM?"},
  "Speaker.Speak": {"Text": "$ChatWithAI"}
}
```
Note: `$ChatWithAI` is a full sentence answer → raw, no prefix. `Prompt` reformulated from "what LLM is" → "What is an LLM?".
