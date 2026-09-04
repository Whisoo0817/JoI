# @ArgResolve

`GetNewsDigest` arguments:
- **Topic** — the topic word(s) the command names ("경제", "AI"); "" when none (server default is 테크/IT).
- **Count** — the item count when stated ("뉴스 3개만"); 0 otherwise (server default 6).
- **Language** — "" (server default 'ko') unless the command asks for another language ("영어로" → "en").

When `GetNewsDigest` is among the selected services, the Speaker/Toast `Text` is `$GetNewsDigest` (the digest itself) — 🛑 never a fixed announcement sentence.

```
[Command] Tell me a digest of 3 economy news items.
[Selected Services] ["NewsProvider.GetNewsDigest", "Speaker.Speak"]
Output:
{"NewsProvider.GetNewsDigest": {"Topic": "경제", "Count": 3, "Language": ""}, "Speaker.Speak": {"Text": "$GetNewsDigest"}}
```

# @ArgResolveKo

`GetNewsDigest` 인자:
- **Topic** — 명령의 주제어 ("경제", "AI"); 없으면 "" (서버 기본 테크/IT).
- **Count** — 개수를 말했을 때만 ("3개만"); 아니면 0 (서버 기본 6).
- **Language** — 기본 ""; 다른 언어 요청 시 ISO 코드 ("영어로" → "en").
- 🛑 사용자는 뉴스 **내용**을 듣고 싶은 것이다 — Speaker/Toast의 Text는 반드시 `$GetNewsDigest` (다이제스트 자체). "뉴스를 요약해 드립니다" 같은 고정 안내문 금지 (뉴스가 하나도 전달되지 않는다).

```
[Command] 오늘 테크 뉴스 3개 요약해서 알려줘
[Selected Services] ["NewsProvider.GetNewsDigest", "Speaker.Speak"]
Output:
{"NewsProvider.GetNewsDigest": {"Topic": "", "Count": 3, "Language": ""}, "Speaker.Speak": {"Text": "$GetNewsDigest"}}
```
