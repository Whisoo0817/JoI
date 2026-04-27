======================================================================
[1] 섹터 A에 있는 조명을 켜줘.
----------------------------------------------------------------------
Translated: Turn on the light in Sector A.

IR:
"timeline": [
{
    "op": "start_at",
    "anchor": "now"
},
{
    "op": "call",
    "target": "Light.on",
    "args": {}
}
]

📋 실행 순서:
• 지금부터 시작
• 실행: Light.on()

Joi:
{
  "cron": "",
  "period": 0,
  "script": "(#SectorA #Light).switch_on()"
}
======================================================================
[2] 온도가 30도 이상이면 에어컨을 냉방모드로 설정해주고 20도 미만이면 난방모드로 설정해줘.
----------------------------------------------------------------------
Translated: If the temperature is >= 30 degrees, set the air conditioner to cooling mode; if the temperature is < 20 degrees, set the air conditioner to heating mode.

IR:
"timeline": [
{
    "op": "start_at",
    "anchor": "now"
},
{
    "op": "if",
    "cond": "TempSensor.temperature >= 30",
    "then": [
    {
        "op": "call",
        "target": "AirConditioner.setMode",
        "args": {
        "mode": "cool"
        }
    }
    ],
    "elif": [
    {
        "op": "if",
        "cond": "TempSensor.temperature < 20",
        "then": [
        {
            "op": "call",
            "target": "AirConditioner.setMode",
            "args": {
            "mode": "heat"
            }
        }
        ],
    }
    ]
}
]

📋 실행 순서:
• 지금부터 시작
• 만약 [TempSensor.temperature ≥ 30]이면:
  • 실행: AirConditioner.setMode(mode=cool)
• 만약 [TempSensor.temperature < 20]이면:
  • 실행: AirConditioner.setMode(mode=heat)

Joi:
{
  "cron": "",
  "period": 0,
  "script": "if (#TemperatureSensor).temperatureSensor_temperature >= 30 {
    (#AirConditioner).airConditioner_setAirConditionerMode('cool')
  }
  elif (#TemperatureSensor).temperatureSensor_temperature < 20 {
    (#AirConditioner).airConditioner_setAirConditionerMode('heat')
  }"
}

======================================================================
[3] 온도가 20도 미만이고 습도가 50% 이하이면, 조명을 끄고 스피커로 알려줘.
----------------------------------------------------------------------
Translated: If the temperature is < 20 degrees and the humidity is <= 50%, turn off the light and announce it through the speaker.

IR:
"timeline": [
{
    "op": "start_at",
    "anchor": "now"
},
{
    "op": "if",
    "cond": "TempSensor.temperature < 20 && HumiditySensor.humidity <= 50",
    "then": [
    {
        "op": "call",
        "target": "Light.off",
        "args": {}
    },
    {
        "op": "call",
        "target": "Speaker.say",
        "args": {
        "text": "temperature is low and humidity is low"
        }
    }
    ],
    "else": []
}
]

📋 실행 순서:
• 지금부터 시작
• 만약 [TempSensor.temperature < 20  그리고  HumiditySensor.humidity ≤ 50]이면:
  • 실행: Light.off()
  • 실행: Speaker.say(text=temperature is low and humidity is low)

Joi:
{
  "cron": "",
  "period": 0,
  "script": "if (#TemperatureSensor).temperatureSensor_temperature < 20 and (#HumiditySensor).humiditySensor_humidity <= 50 {
    (#Light).light_switch_Off()
    (#Speaker).speaker_speak("Temperature is under 20 degrees and humidity is under 50%")
  }"
}

======================================================================
[4] 문이 열리면 조명을 켜줘.
----------------------------------------------------------------------
Translated: When the door opens, turn on the light.

IR:
"timeline": [
{
    "op": "start_at",
    "anchor": "now"
},
{
    "op": "wait",
    "cond": "Door.value == \"open\"",
    "edge": "none"
},
{
    "op": "call",
    "target": "Light.on",
    "args": {}
}
]

📋 실행 순서:
• 지금부터 시작
• [Door.value == "open"]이(가) 참인 상태가 될 때까지 대기
• 실행: Light.on()

Joi:
{
  "cron": "",
  "period": 0,
  "script": "wait until((#Door).Door_doorState == "open")
  (#Light).light_switch_On()"
}

======================================================================
[5] 문이 열릴 때마다 조명을 모두 켜줘.
----------------------------------------------------------------------
Translated: Every time the door opens, turn on all lights.

IR:
"timeline": [
{
    "op": "start_at",
    "anchor": "now"
},
{
    "op": "cycle",
    "until": null,
    "body": [
    {
        "op": "wait",
        "cond": "Door.value == \"open\"",
        "edge": "rising"
    },
    {
        "op": "call",
        "target": "Light.on",
        "args": {}
    }
    ]
}
]

Joi:
{
  "cron": "",
  "period": 100,
  "script": "triggered := false
if ((#Door).door_doorState == 'open') {
    if (triggered == false) {
        all(#Light).light_switch_On()
        triggered = true
    }
} else {
    triggered = false
}"
}

======================================================================
[6] 문이 열리면 조명을 3분마다 켜줘.
----------------------------------------------------------------------
Translated: When the door opens, turn on the light every 3 minutes.

IR:
"timeline": [
{
    "op": "start_at",
    "anchor": "now"
},
{
    "op": "wait",
    "cond": "Door.value == \"open\"",
    "edge": "none"
},
{
    "op": "cycle",
    "until": null,
    "body": [
    {
        "op": "call",
        "target": "Light.on",
        "args": {}
    },
    {
        "op": "delay",
        "ms": 180000
    }
    ]
}
]

📋 실행 순서:
• 지금부터 시작
• [Door.value == "open"]이(가) 참인 상태가 될 때까지 대기
• 반복:
  • 실행: Light.on()
  • 3분 대기

Joi:
{
  "cron": "",
  "period": 180000,
  "script": "phase := 0
if (phase == 0) {
    wait until ((#Door).door_doorState == 'open')
    phase = 1
    (#Light).light_switch_On()
}
if (phase == 1) {
    (#Light).light_switch_On()
}"
}

======================================================================
[7] 10초마다 조명 색을 파란색과 빨간색으로 번갈아 바꿔줘.
----------------------------------------------------------------------
Translated: Every 10 seconds, alternate the light color between blue and red.

IR:
"timeline": [
{
    "op": "start_at",
    "anchor": "now"
},
{
    "op": "cycle",
    "until": null,
    "body": [
    {
        "op": "call",
        "target": "Light.setColor",
        "args": {
        "color": "blue"
        }
    },
    {
        "op": "delay",
        "ms": 10000
    },
    {
        "op": "call",
        "target": "Light.setColor",
        "args": {
        "color": "red"
        }
    },
    {
        "op": "delay",
        "ms": 10000
    }
    ]
}
]

📋 실행 순서:
• 지금부터 시작
• 반복:
  • 실행: Light.setColor(color=blue)
  • 5초 대기
  • 실행: Light.setColor(color=red)
  • 5초 대기

Joi:
{
  "cron": "",
  "period": 10000,
  "script": "color := 'red'
  if (color == 'red') {
    (#Light).light_setColor('blue')
    color = 'blue'
  } else {
    (#Light).light_setColor('red')
    color = 'red'
  }"
}

======================================================================
[8] 월요일이 되면 창문을 열어줘.
----------------------------------------------------------------------
Translated: On Mondays, open the window.

IR:
"timeline": [
{
    "op": "start_at",
    "anchor": "cron",
    "cron": "0 0 * * MON"
},
{
    "op": "call",
    "target": "Window.open",
    "args": {}
}
]

📋 실행 순서:
• 매주 월요일 0시 0분에 시작
• 실행: Window.open()

Joi:
{
  "cron": "0 0 * * 1",
  "period": 0,
  "script": "(#Window).windowCovering_downOrClose()"
}

======================================================================
[9] 오전 9시에 문을 열어줘. 근데 사람이 없으면 문을 닫아.
----------------------------------------------------------------------
Translated: At 9 AM, open the door. If no one is present, close the door.

IR:
"timeline": [
{
    "op": "start_at",
    "anchor": "cron",
    "cron": "0 9 * * *"
},
{
    "op": "if",
    "cond": "MotionSensor.detected == true",
    "then": [
    {
        "op": "call",
        "target": "Door.open",
        "args": {}
    }
    ],
    "else": [
    {
        "op": "call",
        "target": "Door.close",
        "args": {}
    }
    ]
}
]

📋 실행 순서:
• 매일 9시 0분에 시작
• 만약 [MotionSensor.detected == true]이면:
  • 실행: Door.open()
  그렇지 않으면:
    • 실행: Door.close()

Joi:
{
  "cron": "0 9 * * *",
  "period": 0,
  "script": "if (#MotionSensor).MotionSensor_motion == 'detected' {
    (#Door).door_open()
  } else {
    (#Door).door_close()
  }"
}

======================================================================
[10] 온도를 체크하고 10분 뒤에도 체크해. 온도 차이가 10도 이상이 나면 조명을 켜.
----------------------------------------------------------------------
Translated: Check the temperature and check again 10 minutes later; if the temperature difference is >= 10 degrees, turn on the light.

IR:
"timeline": [
{
    "op": "start_at",
    "anchor": "now"
},
{
    "op": "read",
    "var": "t1",
    "src": "TempSensor.temperature"
},
{
    "op": "delay",
    "ms": 600000
},
{
    "op": "read",
    "var": "t2",
    "src": "TempSensor.temperature"
},
{
    "op": "if",
    "cond": "abs($t2 - $t1) >= 10",
    "then": [
    {
        "op": "call",
        "target": "Light.on",
        "args": {}
    }
    ],
    "else": []
}
]

📋 실행 순서:
• 지금부터 시작
• TempSensor.temperature 값을 읽어 `$t1`에 저장
• 10분 대기
• TempSensor.temperature 값을 읽어 `$t2`에 저장
• 만약 [abs($t2 - $t1) ≥ 10]이면:
  • 실행: Light.on()

Joi:
{
  "cron": "",
  "period": 0,
  "script": "t1 = (#TemperatureSensor).temperatureSensor_temperature
  delay(10 MIN)
  t2 = (#TemperatureSensor).temperatureSensor_temperature
  if t2 - t1 >= 10 or t1 - t2 >= 10 {
    (#Light).light_switch_on()
  }"
}

======================================================================
[11] 10초마다 볼륨을 5씩 높여. 만약 최대값이 되면 중단해.
----------------------------------------------------------------------
Translated: Every 10 seconds, increase the volume by 5. If the maximum value is reached, stop.

IR:
"timeline": [
{
    "op": "start_at",
    "anchor": "now"
},
{
    "op": "cycle",
    "until": null,
    "body": [
    {
        "op": "delay",
        "ms": 10000
    },
    {
        "op": "call",
        "target": "Speaker.setVolume",
        "args": {
        "value": "Speaker.volume + 5"
        }
    },
    {
        "op": "if",
        "cond": "Speaker.volume >= 100",
        "then": [
        {
            "op": "break"
        }
        ],
        "else": []
    }
    ]
}
]

📋 실행 순서:
• 지금부터 시작
• 반복:
  • 10초 대기
  • 실행: Speaker.setVolume(value=Speaker.volume + 5)
  • 만약 [Speaker.volume ≥ 100]이면:
    • 반복 중단

Joi:
{
  "cron": "",
  "period": 10000,
  "script": "new_vol = (#Speaker).speaker_volume + 10
  if new_vol >= 100 {
    (#Speaker).speaker_setVolume(100)
    break
  } else {
    (#Speaker).speaker_setVolume(new_vol)
  }"
}
