# Verify

Does the translation produce the **same real-world outcome** as the original command?
Same devices + actions + conditions + timing → `true`. Otherwise → `false`.

### Leniency Rules
- Tag/location names are approximate. "bedroom" = "master bedroom", "living room" = "lounge" → same outcome.
- Synonym actions are equal: "change to" = "set to", "turn on" = "activate", "stop" = "stop playback", "open" = "unlock" (for locks/safes), "close" = "lock".
- Sensor state descriptions are equal: "is detected" = "detects movement" = "is closed" (contact sensor), "detects presence" = "is occupied".
- Time expressions: "afternoon" = "from noon until 0 AM", "on Christmas" = "from Dec 25 0 AM to Dec 26 0 AM", "on weekends" = "from Saturday 0 AM until Monday 0 AM", "midnight" = "0 AM". Vague time words and specific time ranges are equal if they cover the same period.
- Filler words ("immediately", "thereafter", "right away") can be ignored.
- Text content (email body, speaker message) does not need to match exactly. Same intent = OK.

## Output Format
```
true
```
or
```
false
[max 15 words reason: what is different]
```

⛔ No other text. No reasoning before true/false.

---

[Original Command]
{command}

[Translation]
{translation}
