[Device Summary]
<Device "EmailProvider">
  <Service "SendMail" type="action">Send an email. Args: ToAddress (recipient), Title (subject), Body (message text).</Service>
  <Service "SendMailWithFile" type="action">Send an email with a file attachment. Args: ToAddress, Title, Body, File (attachment path).</Service>
</Device>

# Rules

- Pick `SendMailWithFile` ONLY when the command mentions an attachment / file / report-file. Otherwise `SendMail`.
- A `$Var` (e.g. a sensor read or `$CaptureImage`) can fill the Body or File via chaining.

# EmailProvider Examples

[Command]
Send an email to John saying I'm late
["EmailProvider.SendMail"]

[Command]
Email the report file to the team
["EmailProvider.SendMailWithFile"]

[Command]
When smoke is detected, email an alert to admin@home.io
["SmokeDetector.Smoke", "EmailProvider.SendMail"]


# @ArgResolve

`SendMail` / `SendMailWithFile` arguments:
- **ToAddress** — the recipient. Use a literal email address if the command states one; otherwise the named recipient as written ("John", "the team", "admin@home.io"). Do NOT invent an address that isn't implied.
- **Title** — a short subject derived from the command's TRIGGER/ACTION context (presence detected → "재실 감지 알림"; smoke → "화재 경보"; scheduled recording → "녹화 시작 알림"). Match the user's language (Korean input → Korean subject), like the Speaker/Toast text rule.
- **Body** — the message text. Use the command's quoted/stated message if it gives one; **otherwise write a concise one-line body that describes the SCENARIO that fired this email — what was detected / what action ran — NOT an unrelated placeholder.** 🛑 Never emit a "늦었습니다 / I will arrive at 10 / Running late" style body unless the command is actually about the user being late. A `$Var` is placed here when a read feeds the message.
- **File** (SendMailWithFile only) — the attachment path/name the command names, or a `$Var` producing a file (e.g. `$CaptureImage`).

```
[Command] Send an email to john@home.io with subject "Late" saying I will arrive at 10.
[Selected Services] ["EmailProvider.SendMail"]
Output:
{"EmailProvider.SendMail": {"ToAddress": "john@home.io", "Title": "Late", "Body": "I will arrive at 10."}}
```
```
[Command] 사람이 감지되면 메일 보내줘   (no recipient / message stated → derive from the scenario)
[Selected Services] ["EmailProvider.SendMail"]
Output:
{"EmailProvider.SendMail": {"ToAddress": "admin@home.io", "Title": "재실 감지 알림", "Body": "사람이 감지되었습니다."}}
```
