[Device Summary]
<Device "Slack">
  <Service "SendMessage" type="action">Post a message to a Slack channel. Args: Channel ('#name' or channel ID; empty string = the Thing's default channel), Text (message body).</Service>
  <Service "SendDirectMessage" type="action">Send a direct message to a Slack user. Args: User (user ID 'U0123ABCD' or '@handle'), Text (message body).</Service>
</Device>

# Rules

- A channel is named ("#alerts", "general 채널") or no target given → `SendMessage` (Channel = the named channel, or "" for the default).
- A specific USER is named ("@john에게", "DM으로", "유저 …에게") → `SendDirectMessage`.

# @ArgResolve

`SendMessage` / `SendDirectMessage` arguments:
- **Channel** (SendMessage) — the literal channel the command names ("#alerts"); if none stated, use "" (the Thing's default channel). Do NOT invent a channel name.
- **User** (SendDirectMessage) — the user the command names ('@handle' or an ID), verbatim.
- **Text** — the message body. Use the command's quoted/stated message; otherwise a concise one-line body describing the SCENARIO that fired it (same rule as Speaker/Toast/Email). Match the user's language.
