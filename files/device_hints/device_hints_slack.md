# @ArgResolve

`SendMessage` / `SendDirectMessage` arguments:
- **Channel** (SendMessage) — the literal channel the command names ("#alerts"); if none stated, use "" (the Thing's default channel). Do NOT invent a channel name.
- **User** (SendDirectMessage) — the user the command names ('@handle' or an ID), verbatim.
- **Text** — the message body. Use the command's quoted/stated message; otherwise a concise one-line body describing the SCENARIO that fired it (same rule as Speaker/Toast/Email). Match the user's language.
