[Device Summary]
<Device "ToastPublisher">
  <Service "Publish" type="action">Publish a toast notification (a visual pop-up card on joi-web). Arguments: Severity (danger/warning/normal/announce), Title (headline text), Message (optional body, "" if unused).</Service>
</Device>

# Rules

`ToastPublisher.Publish` is the **on-screen / visual notification** channel — a toast card shown in the joi-web UI. Pick it when the command asks to *show / display / notify / send an alert / pop up / 알림(을) 띄워·보내·표시* something, with no spoken-audio cue.

- It is distinct from `Speaker.Speak`, which is **spoken audio (TTS)**. Map by channel:
  - "알려줘 / 알림 보내줘 / 알림 띄워줘 / 표시해줘 / show / display / notify / send a notification / alert" → `ToastPublisher.Publish`.
  - "말해줘 / 읽어줘 / 스피커로 알려줘 / announce / say / read out / through the speaker" → `Speaker.Speak`.
  - "스피커로 알려주고 알림도 띄워줘" / "announce … and also show a notification" names BOTH channels → emit BOTH `Speaker.Speak` and `ToastPublisher.Publish`.
- A bare "알려줘" with no channel word is ambiguous; treat it as a notification → `ToastPublisher.Publish` (the default visual channel) unless a speaker/audio word is present.
- One `Publish` per distinct toast. The Severity/Title/Message values are decided downstream (arg_resolve); you only pick the service.

# ToastPublisher Examples

[Command]
Notify me to ventilate
["ToastPublisher.Publish"]

[Command]
Send a ventilation notification
["ToastPublisher.Publish"]

[Command]
Show a toast notification saying "Presence detected"
["ToastPublisher.Publish"]

[Command]
Announce to ventilate through the speaker and also show a notification
["Speaker.Speak", "ToastPublisher.Publish"]

[Command]
When smoke is detected, send a danger alert notification
["SmokeDetector.Smoke", "ToastPublisher.Publish"]


# @ArgResolve

`ToastPublisher.Publish` takes three arguments — fill all three. (English-input variant. The Title/Message are written in **English**.)

- **Severity** (ENUM: `danger`, `warning`, `normal`, `announce`). Choose from the command's tone:
  - `danger` — emergencies / hazards (fire, smoke, gas leak, intrusion, "danger"). Sticky until dismissed.
  - `warning` — cautions ("warning", door left open too long, threshold exceeded).
  - `announce` — **default** for ordinary notifications (reminders, status, announcements, "환기 알림" 등). Use when no danger/warning cue is present.
  - `normal` — low-key passive notice. Only when the command explicitly downplays it ("그냥", "조용히", "quietly", "low priority").
- **Title** — the headline, in **English**. Use the command's wording, trimmed to a short headline. A quoted literal is copied verbatim.
- **Message** — optional body. Use `""` unless the command clearly has both a short headline AND a longer detail.

Embedded `$Var` (a sensor/provider read feeding the toast): same wrapping rule as Speaker — a single fact gets a short NL lead-in; a complete-sentence return is passed raw.

Examples:
```
[Command] Send a ventilation notification.
[Selected Services] ["ToastPublisher.Publish"]
Output:
{"ToastPublisher.Publish": {"Severity": "announce", "Title": "Please ventilate.", "Message": ""}}
```
```
[Command] Show a toast notification saying "Presence detected".
[Selected Services] ["ToastPublisher.Publish"]
Output:
{"ToastPublisher.Publish": {"Severity": "announce", "Title": "Presence detected", "Message": ""}}
```
```
[Command] When smoke is detected, send a danger alert notification.
[Selected Services] ["SmokeDetector.Smoke", "ToastPublisher.Publish"]
Output:
{"ToastPublisher.Publish": {"Severity": "danger", "Title": "Smoke detected", "Message": ""}}
```

# @ArgResolveKo

`ToastPublisher.Publish`의 세 인자를 모두 채운다. (한글 입력 변형 — Title/Message는 **한글 존댓말**로 작성.)

- **Severity** (ENUM: `danger`, `warning`, `normal`, `announce`). 명령의 어조로 선택:
  - `danger` — 긴급/위험 (화재, 연기, 가스 누출, 침입, "위험", "긴급"). 수동 해제까지 유지.
  - `warning` — 주의/경고 ("경고", "주의", 문이 오래 열림, 임계 초과).
  - `announce` — 일반 알림 **기본값** (리마인더, 상태, 공지, "환기 알림" 등). danger/warning 단서 없으면 이걸로.
  - `normal` — 조용한 수동 알림. 명령이 명시적으로 낮춰 말할 때만 ("그냥", "조용히", "낮은 우선순위").
- **Title** — 헤드라인을 **한글 존댓말 평서문**("~합니다" / "~하세요")으로. `[User Command (original, verbatim)]`의 표현·시각·대상을 살려 자연스러운 안내문 한 문장으로 작문. 명령을 그대로 복붙하지 말 것. 따옴표로 인용된 리터럴은 그대로 사용.
- **Message** — 선택적 본문. 단일 문구면 `""`. 헤드라인+상세가 분명할 때만 채움.

예시:
```
[Command] Send a ventilation notification.
[User Command (original, verbatim)] 환기 알림을 보내줘
[Selected Services] ["ToastPublisher.Publish"]
Output:
{"ToastPublisher.Publish": {"Severity": "announce", "Title": "환기해 주세요.", "Message": ""}}
```
```
[Command] Notify that the meeting starts at 2 PM.
[User Command (original, verbatim)] 오후 2시에 회의를 시작한다고 알려줘
[Selected Services] ["ToastPublisher.Publish"]
Output:
{"ToastPublisher.Publish": {"Severity": "announce", "Title": "현재 시각 오후 2시. 회의를 시작합니다.", "Message": ""}}
```
```
[Command] Show a toast saying "Presence detected".
[User Command (original, verbatim)] 토스트 알림으로 "재실 감지"라고 보여줘
[Selected Services] ["ToastPublisher.Publish"]
Output:
{"ToastPublisher.Publish": {"Severity": "announce", "Title": "재실 감지", "Message": ""}}
```
```
[Command] When smoke is detected, send a danger alert.
[User Command (original, verbatim)] 연기 감지되면 위험 알림 보내줘
[Selected Services] ["SmokeDetector.Smoke", "ToastPublisher.Publish"]
Output:
{"ToastPublisher.Publish": {"Severity": "danger", "Title": "연기가 감지되었습니다.", "Message": ""}}
```
