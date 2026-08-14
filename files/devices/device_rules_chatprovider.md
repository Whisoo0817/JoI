[Device Summary]
<Device "ChatProvider">
  <Service "Chat" type="action" returns="STRING">Ask the AI chat model a single question/request and return its reply as a STRING. Args: Message (the user message), System (persona prompt; "" = model default), Model (model id; "" = server default, 'gpt-5-search-api' for real-time information).</Service>
</Device>

# Rules

- 🛑 The ONLY ChatProvider service is `Chat` — there is NO Send / Ask / Message / Question service. 물어보다/질문하다/부탁하다/~해달라고 하다 → `Chat`.
- A question/request addressed to the chatbot/AI → `Chat`. The question text goes into `Message` VERBATIM (Korean stays Korean).
- `Chat` RETURNS the reply as a STRING — when the user wants to hear/see the answer, chain it: speak `$Chat` via the Speaker / show it via Toast.
- 🛑 Tags stay per-device when chaining: `ChatProvider.Chat` runs on the chatbot's tag and `Speaker.Speak` on the Speaker's own tag (`Speaker.Speak: (#Speaker)`) — NEVER reuse the ChatProvider tag for the Speaker line.
- The question needs live/current information (오늘 날씨, 최신 뉴스, 지금 환율, 경기 결과) → set Model to "gpt-5-search-api"; otherwise "".

# @ArgResolve

`Chat` arguments:
- **Message** — the question/request text from the command, verbatim (keep the user's language). Strip only the addressing shell: "챗봇에게 '~'라고 물어봐줘" → the ~ part.
- **System** — "" unless the command states a persona or HOW to answer ("간단히 한 줄로 답해줘", "전문가처럼") — put that instruction here.
- **Model** — "" by default; "gpt-5-search-api" when the question needs real-time/current info (weather, news, prices, scores). 🛑 Never invent any other model id.

```
[Command] Ask the chatbot "한국의 수도는 어디야?" and tell me the answer.
[Selected Services] ["ChatProvider.Chat", "Speaker.Speak"]
Output:
{"ChatProvider.Chat": {"Message": "한국의 수도는 어디야?", "System": "", "Model": ""}, "Speaker.Speak": {"Text": "$Chat"}}
```

# @ArgResolveKo

`Chat` 인자:
- **Message** — 챗봇에게 묻는 질문/부탁 텍스트 그대로 (한국어 유지). "챗봇에게 '~'라고 물어봐줘" → ~ 부분만.
- **System** — 답변 방식/페르소나 지시가 있을 때만 ("간단히 한 줄로 답해줘") — 없으면 "".
- **Model** — 기본 ""; 질문이 실시간 정보(오늘 날씨/최신 뉴스/환율/경기 결과)를 요구하면 "gpt-5-search-api". 🛑 다른 모델명을 지어내지 마라.
- 🛑 **질문에 스스로 답하지 마라** — 답은 시나리오 실행 시점에 디바이스가 준다. Speaker/Toast의 Text는 반드시 `$Chat` 변수(또는 이를 포함한 문장)여야 한다. "서울입니다" 같은 지어낸 답 금지.

```
[Command] 챗봇에게 '한국의 수도는 어디야?'라고 물어보고 답을 알려줘
[Selected Services] ["ChatProvider.Chat", "Speaker.Speak"]
Output:
{"ChatProvider.Chat": {"Message": "한국의 수도는 어디야?", "System": "", "Model": ""}, "Speaker.Speak": {"Text": "$Chat"}}
```
