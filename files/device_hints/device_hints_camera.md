# @ArgResolve

`CaptureVideo` arguments:
- **Duration** — length of the clip in seconds. Use the number the command states ("30초 영상" → 30). **If no duration is stated (e.g. "녹화해줘", "카메라 녹화 시작해줘", "영상 찍어줘"), default to `10`.**

```
[Command] 카메라 녹화 시작해줘   (no duration stated → default 10)
[Selected Services] ["Camera.CaptureVideo"]
Output:
{"Camera.CaptureVideo": {"Duration": 10}}
```
