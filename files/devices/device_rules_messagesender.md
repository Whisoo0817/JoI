[Device Summary]
<Device "MessageSender">
  <Service "SendSms" type="action">Send an SMS/LMS text message. Args: To (recipient phone number), Text (message body), Subject ("" = SMS; a non-empty subject forces LMS).</Service>
  <Service "SendKakaoTalk" type="action">Send a KakaoTalk notification from a pre-approved template. Args: To (recipient phone number), TemplateId (approved template id), VariablesJson (template '#{key}' values as a JSON object string; "" = none).</Service>
</Device>

# Rules

- "문자/SMS 보내줘" → `SendSms`.
- "카톡/카카오톡 보내줘" → `SendKakaoTalk` ONLY when the command supplies a template id — KakaoTalk needs a pre-approved template, free-form text is impossible. No template id stated → use `SendSms` instead.
- Like email: the recipient phone number and the message text are ARGUMENTS.
- A `$Var` (a sensor read, a chatbot reply) can fill `Text` via chaining.

# @ArgResolve

`SendSms` arguments:
- **To** — the phone number the command states, digits/hyphens verbatim. 🛑 NEVER invent a number — if the command names no recipient, pass "" and let the runtime reject it.
- **Text** — the message the command states (quoted part verbatim); otherwise a concise one-line body describing the scenario that fired (like the email Body rule). A `$Var` is placed here when a read feeds the message.
- **Subject** — "" unless the command gives a subject/title (a non-empty value forces LMS).

```
[Command] Send an SMS to 010-1234-5678 saying the meeting is starting.
[Selected Services] ["MessageSender.SendSms"]
Output:
{"MessageSender.SendSms": {"To": "010-1234-5678", "Text": "회의가 시작됩니다.", "Subject": ""}}
```

# @ArgResolveKo

`SendSms` 인자:
- **To** — 명령의 전화번호를 숫자/하이픈 그대로. 🛑 번호를 지어내지 마라 — 명령에 수신자가 없으면 "".
- **Text** — 명령이 말한 메시지(따옴표 부분 그대로); 없으면 발동한 시나리오를 설명하는 간결한 한 줄 (이메일 Body 규칙과 동일). `$Var` 체이닝 가능.
- **Subject** — 제목/타이틀이 있을 때만 (LMS 강제); 없으면 "".

```
[Command] 010-1234-5678로 회의 시작한다고 문자 보내줘
[Selected Services] ["MessageSender.SendSms"]
Output:
{"MessageSender.SendSms": {"To": "010-1234-5678", "Text": "회의 시작합니다.", "Subject": ""}}
```
