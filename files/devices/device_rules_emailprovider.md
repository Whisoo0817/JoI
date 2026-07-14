[Device Summary]
<Device "EmailProvider">
  <Service "SendMail" type="action">Send an email. Args: ToAddress (recipient), Title (subject), Body (message text).</Service>
  <Service "SendMailWithFile" type="action">Send an email with a file attachment by path. Args: ToAddress, Title, Body, File (attachment path or base64 string).</Service>
  <Service "SendMailWithBinaryFile" type="action">Send an email with an IN-MEMORY binary attachment (e.g. a captured image/video clip). Args: ToAddress, Title, Body, Data (binary bytes, e.g. $CaptureImage), Filename (name+extension shown to recipient).</Service>
</Device>

# Rules

- No attachment → `SendMail`.
- Attachment that is **in-memory binary produced by another service** (a captured image/video, e.g. `$CaptureImage` / `$CaptureVideo`) → `SendMailWithBinaryFile` (Data = the `$Var`, Filename = a sensible name like "capture.jpg").
- Attachment that is a **named file/path on disk** ("the report file", a path) → `SendMailWithFile` (File = the path).
- A `$Var` (e.g. a sensor read) can also fill the Body via chaining.

# @ArgResolve

`SendMail` / `SendMailWithFile` arguments:
- **ToAddress** — the recipient. Use the literal email address the command states if it gives one. **If the command names NO recipient at all (no address, no name), default to `mysmaxlab@gmail.com`.** 🛑 NEVER invent a plausible-looking address (e.g. `admin@home.io`, `john@home.io`) — if it isn't in the command, use the `mysmaxlab@gmail.com` default. Only use a bare name ("John", "the team") verbatim when the command actually names that recipient.
- **Title** — a short subject derived from the command's TRIGGER/ACTION context (presence detected → "재실 감지 알림"; smoke → "화재 경보"; scheduled recording → "녹화 시작 알림"). Match the user's language (Korean input → Korean subject), like the Speaker/Toast text rule.
- **Body** — the message text. Use the command's quoted/stated message if it gives one; **otherwise write a concise one-line body that describes the SCENARIO that fired this email — what was detected / what action ran — NOT an unrelated placeholder.** 🛑 Never emit a "늦었습니다 / I will arrive at 10 / Running late" style body unless the command is actually about the user being late. A `$Var` is placed here when a read feeds the message.
- **File** (SendMailWithFile only) — the attachment path/name the command names.
- **Data** + **Filename** (SendMailWithBinaryFile only) — `Data` is the `$Var` of the binary-producing service (`$CaptureImage`, `$CaptureVideo`); `Filename` is a sensible name with extension (`"capture.jpg"` for an image, `"clip.mp4"` for a video).

```
[Command] Send an email to john@home.io with subject "Late" saying I will arrive at 10.
[Selected Services] ["EmailProvider.SendMail"]
Output:
{"EmailProvider.SendMail": {"ToAddress": "john@home.io", "Title": "Late", "Body": "I will arrive at 10."}}
```
```
[Command] 사람이 감지되면 메일 보내줘   (no recipient stated → default address; message derived from the scenario)
[Selected Services] ["EmailProvider.SendMail"]
Output:
{"EmailProvider.SendMail": {"ToAddress": "mysmaxlab@gmail.com", "Title": "재실 감지 알림", "Body": "사람이 감지되었습니다."}}
```
