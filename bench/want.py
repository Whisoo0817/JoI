#!/usr/bin/env python3
"""기기를 안 댄 명령 37종이 원하는 효과 — effects.py 의 어휘로 적는다.

이게 policy.py 의 INTENT(손으로 쓴 한국어 37줄)를 대신한다.
"시원하게 해줘" 가 원하는 건 thermal_comfort- 다. 그걸 내는 서비스를 effects.py 에서
찾으면 후보가 나온다. 후보 기기가 그 공간에 하나면 실행, 여럿이면 되묻기, 없으면 거절.
"""
WANT = {
    "ac":          ["thermal_comfort-"],
    "fan":         ["air_motion+"],
    "thermostat":  ["thermal_comfort+"],
    "cover":       ["openness-"],
    "light.on":    ["illuminance+"],
    "light.off":   ["illuminance-"],
    "light.dim":   ["illuminance-"],
    "light.color": ["color="],
    "light.scene": ["color="],
    "purifier":    ["air_quality+"],
    "humidity":    ["humidity+", "humidity-"],        # 건조하면 +, 눅눅하면 -
    "ventilator":  ["air_quality+", "air_motion+"],
    "vacuum":      ["floor_clean+"],
    "mower":       ["floor_clean+"],
    "coffee":      ["cooked+"],
    "waterheater": ["water_temperature+"],
    "media":       ["media=", "media+", "media-"],    # "뭐 좀 틀어줘" — 소리 크기가 아니라 콘텐츠
    "speaker":     ["audio_signal+"],
    "lock":        ["locked+"],
    "garage":      ["openness-"],
    "camera":      ["recording+"],
    "siren":       ["audio_signal+"],
    "switch":      ["running-"],
    "plug":        ["running-"],
    "query":       ["data_out+"],
    "notify":      ["message_sent+"],     # 후보 여럿이어도 되묻지 않는다 — policy.NOTIFY_ORDER
    "timer":       [],                                # 세상을 안 바꾼다 — Clock.Delay
    "sprinkler":   ["soil_moisture+", "water_flow+"],
    "growlight":   ["illuminance+", "light_spectrum="],
    "feeder":      ["feed+"],
    "pump":        ["water_flow+", "water_level+"],
    "valve":       ["water_flow-"],
    "compressor":  ["motion_run+"],
    "statuslight": ["visual_signal="],
    "armrobot":    ["position="],
    "conveyor":    ["motion_run-", "halted+"],
    "chamber":     ["temperature="],
}
