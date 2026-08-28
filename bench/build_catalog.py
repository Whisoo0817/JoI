# -*- coding: utf-8 -*-
"""service_list_ver2.1.0 → ver3.0.0 (벤치마크용 카탈로그 확장).

넓히는 기준: Home Assistant 도메인 + SmartThings capability 에 실제로 있는
기기·센서·모드까지를 "상식 선"으로 본다. 집 밖 웹서비스(SNS·쇼핑·금융)와
애매한 시간 표현(해질녘 anchor)은 넣지 않는다 — 되묻기/거절 예시로만 쓴다.

  python bench/build_catalog.py          # files/service_list_ver3.0.0.json 생성
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = os.path.join(HERE, "..", "files")
SRC, DST = "service_list_ver2.1.0.json", "service_list_ver3.0.0.json"


# ── 짧은 생성기 ────────────────────────────────────────────────────────────
def V(desc, ret, *, ret_desc=None, enums=None, bounds=None, unit=None):
    d = {"type": "value", "descriptor": desc, "return_descriptor": ret_desc or desc,
         "return_type": ret}
    if enums: d["enums_descriptor"] = enums
    if bounds: d["return_bounds"] = bounds
    if unit: d["unit"] = unit
    return d


def F(desc, *, arg=None, arg_desc=None, fmt=None, enums=None, bounds=None, unit=None,
      ret="VOID"):
    d = {"type": "function", "descriptor": desc, "argument_descriptor": arg_desc or desc}
    if arg: d["argument_type"] = arg
    if fmt: d["argument_format"] = fmt
    if enums: d["argument_enums"] = enums
    if bounds: d["argument_bounds"] = bounds
    if unit: d["argument_unit"] = unit
    d["return_type"] = ret
    return d


def E(*names):
    return list(names)


# ── 신규 카테고리 ──────────────────────────────────────────────────────────
NEW = {}

# ── 1. 공통 / 알림 채널 ────────────────────────────────────────────────────
NEW["GlobalVariable"] = {
    "Value": V("Stored value of a named global variable", "STRING"),
    "GetValue": F("Read a named global variable", arg="STRING", fmt="name", ret="STRING"),
    "SetValue": F("Store a value in a named global variable", arg="STRING | STRING",
                  fmt="name | value"),
    "Increment": F("Add a number to a named global variable", arg="STRING | DOUBLE",
                   fmt="name | amount", ret="DOUBLE"),
    "Reset": F("Reset a named global variable to its initial value", arg="STRING", fmt="name"),
}
NEW["NotificationProvider"] = {
    "LastMessage": V("Text of the most recently sent notification", "STRING"),
    "SendToast": F("Show a short toast notification on the user's screen",
                   arg="STRING", fmt="message"),
    "SendPush": F("Send a push notification to the user's phone", arg="STRING | STRING",
                  fmt="title | body"),
    "SendAlert": F("Send a notification with an urgency level", arg="STRING | ENUM",
                   fmt="message | level", enums=[None, E("info", "warning", "critical")]),
}
NEW["MessageSender"] = {
    "DeliveryState": V("Delivery result of the last message sent", "ENUM",
                       enums=["sent - Message was sent", "failed - Sending failed",
                              "pending - Sending in progress"]),
    "SendSMS": F("Send an SMS text message to a phone number", arg="STRING | STRING",
                 fmt="phone_number | message"),
    "SendKakaoTalk": F("Send a KakaoTalk message to a contact", arg="STRING | STRING",
                       fmt="contact | message"),
}

# ── 2. 가정 기기 ───────────────────────────────────────────────────────────
NEW["GarageDoor"] = {
    "GarageDoorState": V("Current state of the garage door", "ENUM",
                         enums=["closed - Fully closed", "closing - Closing",
                                "open - Fully open", "opening - Opening",
                                "stopped - Stopped midway", "unknown - State unknown"]),
    "Open": F("Open the garage door"),
    "Close": F("Close the garage door"),
    "Stop": F("Stop the garage door where it is"),
}
NEW["Doorbell"] = {
    "DoorbellPressed": V("Whether the doorbell button is being pressed", "BOOL"),
    "LastPressTime": V("Timestamp of the last doorbell press", "STRING"),
    "Chime": F("Play a chime sound on the doorbell", arg="ENUM", fmt="tone",
               enums=E("ding", "westminster", "bell", "beep", "silent")),
}
NEW["WaterHeater"] = {
    "CurrentTemperature": V("Current water temperature", "DOUBLE", bounds=[0, 90],
                            unit="celsius"),
    "TargetTemperature": V("Target water temperature", "DOUBLE", bounds=[30, 80],
                           unit="celsius"),
    "WaterHeaterMode": V("Current operating mode of the water heater", "ENUM",
                         enums=["off - Heater is off", "heat - Normal heating",
                                "eco - Energy-saving heating", "boost - Rapid heating",
                                "away - Away mode with minimal heating",
                                "vacation - Vacation mode"]),
    "HotWaterAvailable": V("Whether hot water is available now", "BOOL"),
    "SetTargetTemperature": F("Set the target water temperature", arg="DOUBLE",
                              bounds=[30, 80], unit="celsius"),
    "SetWaterHeaterMode": F("Set the operating mode of the water heater", arg="ENUM",
                            enums=E("off", "heat", "eco", "boost", "away", "vacation")),
}
NEW["RangeHood"] = {
    "HoodMode": V("Current operating mode of the range hood", "ENUM",
                  enums=["off - Hood is off", "low - Low extraction",
                         "medium - Medium extraction", "high - High extraction",
                         "auto - Automatic extraction by smoke level",
                         "boost - Maximum extraction"]),
    "LightOn": V("Whether the range hood light is on", "BOOL"),
    "FilterStatus": V("Remaining life of the grease filter", "DOUBLE", bounds=[0, 100],
                      unit="percent"),
    "SetHoodMode": F("Set the operating mode of the range hood", arg="ENUM",
                     enums=E("off", "low", "medium", "high", "auto", "boost")),
    "SetLight": F("Turn the range hood light on or off", arg="BOOL", fmt="on"),
}
NEW["CoffeeMaker"] = {
    "BrewState": V("Current brewing state", "ENUM",
                   enums=["idle - Idle", "brewing - Brewing", "ready - Drink is ready",
                          "cleaning - Cleaning cycle", "error - Error state"]),
    "WaterLevel": V("Water tank level", "DOUBLE", bounds=[0, 100], unit="percent"),
    "CupCount": V("Number of cups brewed since the last reset", "INTEGER"),
    "Brew": F("Brew a drink at the given strength", arg="ENUM", fmt="strength",
              enums=E("mild", "normal", "strong", "espresso", "americano", "latte")),
    "Stop": F("Stop brewing"),
}
NEW["Microwave"] = {
    "MicrowaveMode": V("Current operating mode of the microwave", "ENUM",
                       enums=["off - Off", "microwave - Microwave heating",
                              "grill - Grill", "defrost - Defrosting",
                              "convection - Convection", "combo - Microwave plus grill"]),
    "RemainingTime": V("Remaining cooking time", "INTEGER", bounds=[0, 5400],
                       unit="seconds"),
    "PowerLevel": V("Current power level", "INTEGER", bounds=[0, 100], unit="percent"),
    "SetCookingParameters": F("Set microwave mode and duration", arg="ENUM | DOUBLE",
                              fmt="mode | duration_minutes",
                              enums=[E("microwave", "grill", "defrost", "convection",
                                       "combo"), None],
                              bounds=[None, [1, 90]], unit=[None, "minutes"]),
    "AddMoreTime": F("Add cooking time to the running program", arg="DOUBLE",
                     fmt="minutes", bounds=[1, 60], unit="minutes"),
    "Stop": F("Stop the microwave"),
}
NEW["ElectricBlanket"] = {
    "BlanketMode": V("Current operating mode of the electric blanket", "ENUM",
                     enums=["off - Off", "low - Low heat", "medium - Medium heat",
                            "high - High heat", "sleep - Sleep mode with gentle heat"]),
    "TargetTemperature": V("Target surface temperature", "DOUBLE", bounds=[20, 50],
                           unit="celsius"),
    "SetBlanketMode": F("Set the operating mode of the electric blanket", arg="ENUM",
                        enums=E("off", "low", "medium", "high", "sleep")),
    "SetTargetTemperature": F("Set the target surface temperature", arg="DOUBLE",
                              bounds=[20, 50], unit="celsius"),
}
NEW["ClothingCare"] = {
    "ClothingCareMode": V("Current operating mode of the clothing care machine", "ENUM",
                          enums=["off - Off", "quick - Quick refresh", "normal - Normal course",
                                 "sanitize - Sanitizing course", "dry - Drying course",
                                 "deodorize - Deodorizing course"]),
    "RemainingTime": V("Remaining course time", "INTEGER", bounds=[0, 300], unit="minutes"),
    "SetClothingCareMode": F("Set the operating mode of the clothing care machine",
                             arg="ENUM",
                             enums=E("off", "quick", "normal", "sanitize", "dry",
                                     "deodorize")),
}
NEW["WaterPurifier"] = {
    "FilterStatus": V("Remaining life of the water filter", "DOUBLE", bounds=[0, 100],
                      unit="percent"),
    "WaterTemperatureMode": V("Temperature setting of dispensed water", "ENUM",
                              enums=["cold - Cold water", "room - Room temperature",
                                     "hot - Hot water"]),
    "Dispense": F("Dispense water of the given amount", arg="DOUBLE", fmt="milliliters",
                  bounds=[50, 2000], unit="milliliters"),
    "SetWaterTemperatureMode": F("Set the temperature of dispensed water", arg="ENUM",
                                 enums=E("cold", "room", "hot")),
}
NEW["EvCharger"] = {
    "ChargingState": V("Current charging state", "ENUM",
                       enums=["idle - Not charging", "charging - Charging",
                              "complete - Charging complete", "scheduled - Waiting for schedule",
                              "fault - Fault detected"]),
    "ChargingPower": V("Current charging power", "DOUBLE", bounds=[0, 350], unit="kilowatts"),
    "EnergyDelivered": V("Energy delivered in the current session", "DOUBLE",
                         bounds=[0, 200], unit="kilowatt_hours"),
    "StartCharging": F("Start charging the vehicle"),
    "StopCharging": F("Stop charging the vehicle"),
    "SetChargeLimit": F("Set the battery charge limit", arg="INTEGER", fmt="percent",
                        bounds=[50, 100], unit="percent"),
}
NEW["PetFeeder"] = {
    "FoodLevel": V("Remaining food in the hopper", "DOUBLE", bounds=[0, 100], unit="percent"),
    "LastDispenseTime": V("Timestamp of the last feeding", "STRING"),
    "Dispense": F("Dispense a portion of food", arg="DOUBLE", fmt="grams",
                  bounds=[10, 500], unit="grams"),
}

# ── 3. 센서 ────────────────────────────────────────────────────────────────
NEW["GasSensor"] = {
    "Gas": V("Whether combustible gas is detected", "BOOL"),
    "GasLevel": V("Combustible gas concentration", "DOUBLE", bounds=[0, 10000], unit="ppm"),
}
NEW["CarbonMonoxideSensor"] = {
    "CarbonMonoxide": V("Carbon monoxide concentration", "DOUBLE", bounds=[0, 1000],
                        unit="ppm"),
    "Alarm": V("Whether the carbon monoxide alarm is active", "BOOL"),
}
NEW["VibrationSensor"] = {
    "Vibration": V("Whether vibration is detected", "BOOL"),
    "VibrationLevel": V("Vibration velocity", "DOUBLE", bounds=[0, 100],
                        unit="millimeters_per_second"),
}
NEW["TiltSensor"] = {
    "Tilt": V("Whether the device is tilted beyond its threshold", "BOOL"),
    "TiltAngle": V("Tilt angle from the vertical", "DOUBLE", bounds=[0, 180], unit="degrees"),
}
NEW["WaterLevelSensor"] = {
    "WaterLevel": V("Water level in the tank", "DOUBLE", bounds=[0, 100], unit="percent"),
    "LevelState": V("Coarse water level state", "ENUM",
                    enums=["empty - Tank is empty", "low - Level is low",
                           "normal - Level is normal", "high - Level is high",
                           "full - Tank is full"]),
}
NEW["SoilMoistureSensor"] = {
    "SoilMoisture": V("Volumetric soil moisture", "DOUBLE", bounds=[0, 100], unit="percent"),
    "SoilTemperature": V("Soil temperature", "DOUBLE", bounds=[-20, 60], unit="celsius"),
}
NEW["UvSensor"] = {
    "UvIndex": V("Ultraviolet index", "DOUBLE", bounds=[0, 15], unit="uv_index"),
}
NEW["WindSensor"] = {
    "WindSpeed": V("Current wind speed", "DOUBLE", bounds=[0, 80],
                   unit="meters_per_second"),
    "GustSpeed": V("Peak gust speed", "DOUBLE", bounds=[0, 120],
                   unit="meters_per_second"),
    "WindDirection": V("Wind direction", "ENUM",
                       enums=["north - North", "northeast - Northeast", "east - East",
                              "southeast - Southeast", "south - South",
                              "southwest - Southwest", "west - West",
                              "northwest - Northwest"]),
}
NEW["FlowSensor"] = {
    "FlowRate": V("Current flow rate", "DOUBLE", bounds=[0, 500], unit="liters_per_minute"),
    "TotalVolume": V("Cumulative volume since the last reset", "DOUBLE", bounds=[0, 1000000],
                     unit="liters"),
}
NEW["EnergyMeter"] = {
    "Power": V("Instantaneous active power", "DOUBLE", bounds=[0, 100000], unit="watts"),
    "Voltage": V("Line voltage", "DOUBLE", bounds=[0, 500], unit="volts"),
    "Current": V("Line current", "DOUBLE", bounds=[0, 200], unit="amperes"),
    "EnergyConsumed": V("Cumulative energy consumed", "DOUBLE", bounds=[0, 1000000],
                        unit="kilowatt_hours"),
    "PowerFactor": V("Power factor", "DOUBLE", bounds=[0, 1], unit="ratio"),
}
NEW["ProximitySensor"] = {
    "Proximity": V("Whether an object is within the detection range", "BOOL"),
    "Distance": V("Distance to the nearest object", "DOUBLE", bounds=[0, 1000],
                  unit="centimeters"),
}
NEW["WeightSensor"] = {
    "Weight": V("Measured weight", "DOUBLE", bounds=[0, 5000], unit="kilograms"),
    "Stable": V("Whether the reading has settled", "BOOL"),
    "Tare": F("Zero the scale at the current load"),
}
NEW["OccupancyCounter"] = {
    "PeopleCount": V("Number of people currently inside", "INTEGER", bounds=[0, 10000],
                     unit="people"),
    "EntryCount": V("Cumulative number of entries", "INTEGER", bounds=[0, 1000000]),
    "ExitCount": V("Cumulative number of exits", "INTEGER", bounds=[0, 1000000]),
    "ResetCount": F("Reset the entry and exit counters"),
}
NEW["WaterQualitySensor"] = {
    "Ph": V("Acidity of the water", "DOUBLE", bounds=[0, 14], unit="ph"),
    "ElectricalConductivity": V("Electrical conductivity of the water", "DOUBLE",
                                bounds=[0, 20], unit="millisiemens_per_centimeter"),
    "Turbidity": V("Turbidity of the water", "DOUBLE", bounds=[0, 1000], unit="ntu"),
    "DissolvedOxygen": V("Dissolved oxygen concentration", "DOUBLE", bounds=[0, 20],
                         unit="milligrams_per_liter"),
    "WaterTemperature": V("Water temperature", "DOUBLE", bounds=[-5, 100], unit="celsius"),
}

# ── 4. 농장 ────────────────────────────────────────────────────────────────
NEW["Sprinkler"] = {
    "SprinklerState": V("Whether the sprinkler is running", "BOOL"),
    "RemainingTime": V("Remaining watering time", "INTEGER", bounds=[0, 600],
                       unit="minutes"),
    "Start": F("Start watering for the given duration", arg="DOUBLE", fmt="minutes",
               bounds=[1, 600], unit="minutes"),
    "Stop": F("Stop watering"),
}
NEW["GrowLight"] = {
    "LightSpectrum": V("Current light spectrum", "ENUM",
                       enums=["full - Full spectrum", "vegetative - Vegetative growth",
                              "bloom - Flowering", "red - Red only", "blue - Blue only",
                              "uv - Ultraviolet supplement"]),
    "Intensity": V("Current light intensity", "DOUBLE", bounds=[0, 100], unit="percent"),
    "SetSpectrum": F("Set the light spectrum", arg="ENUM",
                     enums=E("full", "vegetative", "bloom", "red", "blue", "uv")),
    "SetIntensity": F("Set the light intensity", arg="DOUBLE", bounds=[0, 100],
                      unit="percent"),
}
NEW["Ventilator"] = {
    "VentilatorMode": V("Current operating mode of the ventilator", "ENUM",
                        enums=["off - Off", "low - Low airflow", "medium - Medium airflow",
                               "high - High airflow", "auto - Automatic by air quality",
                               "exhaust - Exhaust only", "intake - Intake only"]),
    "AirflowRate": V("Current airflow rate", "DOUBLE", bounds=[0, 5000],
                     unit="cubic_meters_per_hour"),
    "SetVentilatorMode": F("Set the operating mode of the ventilator", arg="ENUM",
                           enums=E("off", "low", "medium", "high", "auto", "exhaust",
                                   "intake")),
    "SetAirflowRate": F("Set the airflow rate", arg="DOUBLE", bounds=[0, 5000],
                        unit="cubic_meters_per_hour"),
}
NEW["FeedDispenser"] = {
    "FeedLevel": V("Remaining feed in the hopper", "DOUBLE", bounds=[0, 100], unit="percent"),
    "LastDispenseTime": V("Timestamp of the last dispense", "STRING"),
    "Dispense": F("Dispense feed of the given weight", arg="DOUBLE", fmt="kilograms",
                  bounds=[0.1, 100], unit="kilograms"),
}
NEW["Chamber"] = {
    "ChamberMode": V("Current operating mode of the climate chamber", "ENUM",
                     enums=["off - Off", "auto - Hold the setpoints automatically",
                            "heat - Heating", "cool - Cooling", "humidify - Humidifying",
                            "dehumidify - Dehumidifying", "sterilize - Sterilizing"]),
    "CurrentTemperature": V("Temperature inside the chamber", "DOUBLE", bounds=[-40, 150],
                            unit="celsius"),
    "CurrentHumidity": V("Relative humidity inside the chamber", "DOUBLE", bounds=[0, 100],
                         unit="percent"),
    "TargetTemperature": V("Target temperature of the chamber", "DOUBLE", bounds=[-40, 150],
                           unit="celsius"),
    "TargetHumidity": V("Target relative humidity of the chamber", "DOUBLE", bounds=[0, 100],
                        unit="percent"),
    "SetChamberMode": F("Set the operating mode of the chamber", arg="ENUM",
                        enums=E("off", "auto", "heat", "cool", "humidify", "dehumidify",
                                "sterilize")),
    "SetTargetTemperature": F("Set the target temperature of the chamber", arg="DOUBLE",
                              bounds=[-40, 150], unit="celsius"),
    "SetTargetHumidity": F("Set the target humidity of the chamber", arg="DOUBLE",
                           bounds=[0, 100], unit="percent"),
}

# ── 5. 공장 ────────────────────────────────────────────────────────────────
NEW["ConveyorBelt"] = {
    "ConveyorState": V("Current state of the conveyor", "ENUM",
                       enums=["stopped - Stopped", "running - Running", "paused - Paused",
                              "jammed - Jammed", "fault - Fault detected"]),
    "BeltSpeed": V("Current belt speed", "DOUBLE", bounds=[0, 120],
                   unit="meters_per_minute"),
    "Start": F("Start the conveyor"),
    "Stop": F("Stop the conveyor"),
    "SetBeltSpeed": F("Set the belt speed", arg="DOUBLE", bounds=[0, 120],
                      unit="meters_per_minute"),
}
NEW["AirCompressor"] = {
    "CompressorState": V("Current state of the air compressor", "ENUM",
                         enums=["off - Off", "running - Running",
                                "unloading - Unloading", "fault - Fault detected"]),
    "TankPressure": V("Pressure in the air tank", "DOUBLE", bounds=[0, 20], unit="bar"),
    "RunHours": V("Cumulative running hours", "DOUBLE", bounds=[0, 100000], unit="hours"),
    "Start": F("Start the air compressor"),
    "Stop": F("Stop the air compressor"),
}
NEW["ProductionMachine"] = {
    "MachineState": V("Current state of the production machine", "ENUM",
                      enums=["idle - Idle", "running - Running", "paused - Paused",
                             "error - Error state", "maintenance - Under maintenance",
                             "setup - Being set up"]),
    "CycleCount": V("Number of completed cycles since the last reset", "INTEGER",
                    bounds=[0, 10000000]),
    "ProductionRate": V("Current production rate", "DOUBLE", bounds=[0, 10000],
                        unit="units_per_hour"),
    "ErrorCode": V("Error code reported by the machine", "STRING"),
    "Start": F("Start the production machine"),
    "Stop": F("Stop the production machine"),
    "ResetCounter": F("Reset the cycle counter"),
}
NEW["EmergencyStop"] = {
    "EmergencyStopState": V("Current state of the emergency stop circuit", "ENUM",
                            enums=["normal - Circuit is normal",
                                   "triggered - Emergency stop is engaged"]),
    "Trigger": F("Engage the emergency stop"),
    "Reset": F("Release the emergency stop after the cause is cleared"),
}
NEW["SafetyBarrier"] = {
    "BarrierState": V("Current state of the safety light curtain", "ENUM",
                      enums=["clear - Beam is clear", "blocked - Beam is blocked",
                             "fault - Fault detected"]),
    "Muted": V("Whether the barrier is muted for a pass-through", "BOOL"),
}
NEW["StatusLight"] = {
    "StatusColor": V("Colour currently shown on the stack light", "ENUM",
                     enums=["off - No colour", "green - Green", "yellow - Yellow",
                            "red - Red", "blue - Blue", "white - White"]),
    "Blinking": V("Whether the stack light is blinking", "BOOL"),
    "SetStatus": F("Set the colour of the stack light", arg="ENUM",
                   enums=E("off", "green", "yellow", "red", "blue", "white")),
    "SetBlinking": F("Turn blinking on or off", arg="BOOL", fmt="blinking"),
}

# ── 6. 오피스 ──────────────────────────────────────────────────────────────
NEW["Projector"] = {
    "ProjectorState": V("Current state of the projector", "ENUM",
                        enums=["off - Off", "on - Projecting", "warming - Warming up",
                               "cooling - Cooling down", "standby - Standby"]),
    "InputSource": V("Currently selected input source", "ENUM",
                     enums=["hdmi1 - HDMI 1", "hdmi2 - HDMI 2", "usbc - USB-C",
                            "wireless - Wireless casting", "vga - VGA"]),
    "LampHours": V("Cumulative lamp hours", "DOUBLE", bounds=[0, 20000], unit="hours"),
    "PowerOn": F("Turn the projector on"),
    "PowerOff": F("Turn the projector off"),
    "SetInputSource": F("Select the input source", arg="ENUM",
                        enums=E("hdmi1", "hdmi2", "usbc", "wireless", "vga")),
}
NEW["Printer"] = {
    "PrinterState": V("Current state of the printer", "ENUM",
                      enums=["idle - Idle", "printing - Printing", "error - Error state",
                             "offline - Offline", "outOfPaper - Out of paper",
                             "lowToner - Toner is low"]),
    "TonerLevel": V("Remaining toner", "DOUBLE", bounds=[0, 100], unit="percent"),
    "PaperLevel": V("Remaining paper", "DOUBLE", bounds=[0, 100], unit="percent"),
    "QueueLength": V("Number of jobs waiting in the queue", "INTEGER", bounds=[0, 1000]),
    "PrintFile": F("Print a file", arg="STRING", fmt="file_path"),
    "CancelJobs": F("Cancel every queued print job"),
}
NEW["Display"] = {
    "DisplayState": V("Current state of the display", "ENUM",
                      enums=["off - Off", "on - On", "standby - Standby"]),
    "Brightness": V("Current screen brightness", "DOUBLE", bounds=[0, 100], unit="percent"),
    "PowerOn": F("Turn the display on"),
    "PowerOff": F("Turn the display off"),
    "ShowMessage": F("Show a message on the display for a duration",
                     arg="STRING | DOUBLE", fmt="message | duration_seconds",
                     bounds=[None, [1, 3600]], unit=[None, "seconds"]),
    "SetBrightness": F("Set the screen brightness", arg="DOUBLE", bounds=[0, 100],
                       unit="percent"),
}
NEW["RfidReader"] = {
    "LastTagId": V("Identifier of the most recently read tag", "STRING"),
    "ReaderState": V("Current state of the reader", "ENUM",
                     enums=["idle - Idle", "reading - Reading a tag",
                            "fault - Fault detected"]),
    "LastReadTime": V("Timestamp of the most recent read", "STRING"),
}

# ── 7. 실제 허브(run.py)에 있으나 2.1.0 에 없던 것 ────────────────────────
NEW["PowerMeter"] = {
    "Power": V("Instantaneous active power", "DOUBLE", bounds=[0, 100000], unit="watts"),
    "Voltage": V("Line voltage", "DOUBLE", bounds=[0, 500], unit="volts"),
    "Current": V("Line current", "DOUBLE", bounds=[0, 200], unit="amperes"),
    "PowerFactor": V("Power factor", "DOUBLE", bounds=[0, 1], unit="ratio"),
}
NEW["ChatProvider"] = {
    "LastAnswer": V("Answer text of the most recent question", "STRING"),
    "Ask": F("Ask the AI assistant a question and get an answer", arg="STRING",
             fmt="question", ret="STRING"),
}
NEW["NewsProvider"] = {
    "TodayHeadlines": V("Today's news headlines", "STRING"),
    "GetNews": F("Get a news digest on a topic", arg="STRING | INTEGER",
                 fmt="topic | count", bounds=[None, [1, 20]], ret="STRING"),
}

# ── 8. 해의 위치 (실사용 12.4% — IFTTT 설치 2위 "lights on at sunset") ────
# Clock 과 같은 값 서비스. 조건식에서 읽어 비교하므로 IR 확장이 필요 없다.
# HA 의 sun.sun (state=above_horizon/below_horizon, elevation, azimuth,
# next_rising, next_setting) 을 그대로 본뜬다.
# 잔디깎이 로봇 — HA lawn_mower 도메인이 있다. IFTTT 설치수로 액션의 2.1%.
NEW["Mower"] = {
    "Power": V("Whether the robot lawn mower is running", "BOOL"),
    "State": V("What the mower is doing now", "ENUM", enums=[
        "mowing - Cutting the grass",
        "docked - Parked in its dock",
        "paused - Paused in the middle of a run",
        "returning - Heading back to the dock",
        "error - Stopped with a fault"]),
    "BatteryLevel": V("Battery charge of the mower", "DOUBLE",
                      bounds=[0, 100], unit="percent"),
    "StartMowing": F("Start cutting the lawn"),
    "Pause": F("Pause the run that is going on"),
    "Dock": F("Send the mower back to its dock"),
}
NEW["SunProvider"] = {
    "SunState": V("Whether the sun is above or below the horizon", "ENUM",
                  enums=["aboveHorizon - The sun is up",
                         "belowHorizon - The sun is down"]),
    "Elevation": V("Current elevation angle of the sun above the horizon", "DOUBLE",
                   bounds=[-90, 90], unit="degrees"),
    "Azimuth": V("Current compass direction of the sun", "DOUBLE", bounds=[0, 360],
                 unit="degrees"),
    "SunriseTime": V("Clock time of today's sunrise", "STRING"),
    "SunsetTime": V("Clock time of today's sunset", "STRING"),
    "IsDaylight": V("Whether it is currently daylight", "BOOL"),
}

# ── 9. 외부 정보 제공자 ────────────────────────────────────────────────────
# 폰: IFTTT IoT 규칙의 15.7%(설치 314,051)가 모바일 앱을 요구한다. 위치가 최대
# 덩어리(13%)이고 통화·와이파이·블루투스·충전도 실제로 쓰인다. 허브 위치가 아니라
# **사용자 폰 1대**를 가리킨다 (HA device_tracker/person, SmartThings presence sensor).
NEW["PersonTracker"] = {
    "Zone": V("Which named area the user is currently in", "ENUM",
              enums=["home - At home", "work - At work", "school - At school",
                     "gym - At the gym", "away - Somewhere else",
                     "unknown - Location unknown"]),
    "IsHome": V("Whether the user is at home", "BOOL"),
    "DistanceToHome": V("Straight-line distance from home", "DOUBLE", bounds=[0, 20000],
                        unit="kilometers"),
    "LastArrivalTime": V("Timestamp the user last arrived home", "STRING"),
    "LastDepartureTime": V("Timestamp the user last left home", "STRING"),
    "BatteryLevel": V("Phone battery level", "DOUBLE", bounds=[0, 100], unit="percent"),
    "Charging": V("Whether the phone is charging", "BOOL"),
    "OnCall": V("Whether the user is on a phone call", "BOOL"),
    "ConnectedWifi": V("Name of the Wi-Fi network the phone is joined to", "STRING"),
    "ConnectedBluetooth": V("Name of the Bluetooth device the phone is connected to",
                            "STRING"),
    "SleepMode": V("Whether the phone is in sleep or focus mode", "BOOL"),
}
NEW["CalendarProvider"] = {
    "IsBusy": V("Whether an event is happening right now", "BOOL"),
    "NextEventTitle": V("Title of the next scheduled event", "STRING"),
    "NextEventStart": V("Start time of the next scheduled event", "STRING"),
    "NextEventEnd": V("End time of the next scheduled event", "STRING"),
    "TodayEventCount": V("Number of events scheduled today", "INTEGER", bounds=[0, 100]),
    "GetNextEvent": F("Get the next event from a named calendar", arg="STRING",
                      fmt="calendar_name", ret="STRING"),
}


# ── 기존 카테고리 확장 (enum 추가 / 서비스 추가) ───────────────────────────
ENUM_ADD = {
    ("AirConditioner", "AirConditionerMode"): [("dry", "Dehumidifying mode"),
                                               ("fan", "Fan-only mode"),
                                               ("off", "Air conditioner is off")],
    ("Fan", "FanMode"): [("turbo", "Maximum speed")],
    ("AirPurifier", "AirPurifierMode"): [("turbo", "Maximum fan speed")],
    ("Humidifier", "HumidifierMode"): [("sleep", "Sleep mode with reduced noise"),
                                       ("turbo", "Maximum humidification")],
    ("RobotVacuumCleaner", "RobotVacuumCleanerMode"): [("spot", "Intensive spot cleaning"),
                                                       ("edge", "Edge and corner cleaning"),
                                                       ("silent", "Quiet cleaning"),
                                                       ("charge", "Return to the dock and charge")],
    ("Siren", "SirenMode"): [("intruder", "Intruder alert"), ("gas", "Gas leak alert"),
                             ("test", "Short test sound")],
    ("WindowCovering", "WindowCoveringType"): [("curtain", "Curtain"),
                                               ("shutter", "Shutter"),
                                               ("awning", "Awning"),
                                               ("rollerShade", "Roller shade"),
                                               ("screen", "Insect or sun screen")],
    ("Thermostat", "ThermostatMode"): [("dry", "Dehumidifying mode"),
                                       ("fanOnly", "Fan-only mode")],
}

SERVICE_ADD = {
    "AirConditioner": {
        "FanMode": V("Current fan speed of the air conditioner", "ENUM",
                     enums=["auto - Automatic fan speed", "low - Low", "medium - Medium",
                            "high - High", "turbo - Maximum"]),
        "SwingMode": V("Current air-flow swing setting", "ENUM",
                       enums=["off - No swing", "vertical - Vertical swing",
                              "horizontal - Horizontal swing", "both - Both directions"]),
        "SetFanMode": F("Set the fan speed of the air conditioner", arg="ENUM",
                        enums=E("auto", "low", "medium", "high", "turbo")),
        "SetSwingMode": F("Set the air-flow swing of the air conditioner", arg="ENUM",
                          enums=E("off", "vertical", "horizontal", "both")),
    },
    "Camera": {
        "RecordingState": V("Whether the camera is recording", "ENUM",
                            enums=["idle - Not recording", "recording - Recording",
                                   "uploading - Uploading the clip"]),
        "StartRecording": F("Start recording video"),
        "StopRecording": F("Stop recording video", ret="BINARY"),
    },
    "WindowCovering": {
        "CurrentTiltAngle": V("Current slat tilt angle", "DOUBLE", bounds=[0, 90],
                              unit="degrees"),
        "SetTiltAngle": F("Set the slat tilt angle", arg="DOUBLE", bounds=[0, 90],
                          unit="degrees"),
    },
}


def main():
    src = json.load(open(os.path.join(FILES, SRC), encoding="utf-8"))
    out = dict(src)
    added_enums = []

    for (cat, svc), pairs in ENUM_ADD.items():
        for name, desc in pairs:
            out[cat][svc].setdefault("enums_descriptor", []).append(f"{name} - {desc}")
            added_enums.append(f"{cat}.{svc}:{name}")
        setter = "Set" + svc
        if setter in out[cat] and "argument_enums" in out[cat][setter]:
            out[cat][setter]["argument_enums"] += [n for n, _ in pairs]

    for cat, svcs in SERVICE_ADD.items():
        out[cat].update(svcs)

    for cat, svcs in NEW.items():
        if cat in out:
            raise SystemExit(f"이미 있는 카테고리: {cat}")
        out[cat] = svcs

    ordered = {"$schema_version": "3.0.0", "$changelog": dict(src.get("$changelog", {}))}
    ordered["$changelog"]["3.0.0"] = [
        "Benchmark catalog expansion. Admission rule: a device, sensor or mode that "
        "exists in Home Assistant domains or SmartThings capabilities counts as "
        "common-sense and may be added; off-premise web services and vague time "
        "anchors (dusk/sunset) are excluded on purpose.",
        f"Added {len(NEW)} categories: " + ", ".join(sorted(NEW)),
        "Added services to existing categories: " + ", ".join(
            f"{c}.{m}" for c, s in SERVICE_ADD.items() for m in s),
        "Added enum members: " + ", ".join(added_enums),
    ]
    for k in sorted(k for k in out if not k.startswith("$")):
        ordered[k] = out[k]

    dst = os.path.join(FILES, DST)

    # ── 효과 (effects) ────────────────────────────────────────────────
    # 함수 서비스마다 "실행하면 세상에서 무엇이 바뀌나" 를 정해진 어휘로 적는다.
    # bench/effects.py 가 원본이다. 여기서는 그걸 읽어 카탈로그에 박기만 한다.
    import importlib.util as ilu
    spec = ilu.spec_from_file_location(
        "effects", os.path.join(HERE, "..", "bench", "effects.py"))
    eff = ilu.module_from_spec(spec)
    spec.loader.exec_module(eff)
    n_eff = 0
    for c, svcs in eff.E.items():
        for m, v in svcs.items():
            if c in ordered and m in ordered[c]:
                ordered[c][m]["effects"] = v
                n_eff += 1
    # ContactSensor.Contact 의 극성이 안 적혀 있었다. 기존 정답 IR 은 true = 닫힘(감지됨)이다
    # — HA 의 binary_sensor door(on = open)와 반대라 반드시 적어 둔다.
    ordered["ContactSensor"]["Contact"]["return_descriptor"] = (
        "true when the contact is made (door or window CLOSED), "
        "false when it is broken (OPEN). Note this is the opposite of "
        "Home Assistant's binary_sensor door convention.")

    ordered["$effects_vocab"] = eff.VOCAB
    ordered["$switch_carries"] = eff.SWITCH_CARRIES
    ordered["$changelog"]["3.0.0"].append(
        "effects: every function service lists what it changes in the real world, "
        "using a fixed vocabulary ($effects_vocab). Direct effects only. "
        "Switch.On/Off inherit the effects of whatever category the switch is "
        "attached to ($switch_carries).")
    print(f"effects 붙임: {n_eff}개 함수 서비스")

    # ══ joi usecase 맞춤 (dataset-usecase.xlsx) ═══════════════════════════════
    # 위의 확장 층 위에 usecase 에서 필요해진 것만 더한다.
    # 난방기 — usecase 의 "온도 낮으면 난방 켜줘"(농장). HA climate/generic_thermostat.
    #          WaterHeater(온수기)와 다르다 — 이건 방 공기를 데우는 기기다.
    ordered["Heater"] = {
        "HeaterState": V("Current state of the heater", "ENUM",
                         enums=["off - Not heating", "heating - Actively heating",
                                "idle - At target temperature, standing by"]),
        "TargetTemperature": V("Target temperature of the heater", "DOUBLE",
                               bounds=[5, 35], unit="°C"),
        "On": F("Turn the heater on"),
        "Off": F("Turn the heater off"),
        "SetTargetTemperature": F("Set the target temperature of the heater",
                                  arg="DOUBLE", fmt="temperature",
                                  bounds=[5, 35], unit="°C"),
    }
    # 슬랙 — 팀 채널이라 받는 사람 주소가 필요 없다. 문자·카톡·메일은 주소가
    # 인자로 필요해서 주소를 모르면 되묻지만, 슬랙은 바로 보낼 수 있다.
    ordered["MessageSender"]["SendSlack"] = F(
        "Send a message to the team Slack channel", arg="STRING", fmt="message")
    for c, m in [("Heater", "On"), ("Heater", "Off"),
                 ("Heater", "SetTargetTemperature"), ("MessageSender", "SendSlack")]:
        if c in eff.E and m in eff.E[c]:
            ordered[c][m]["effects"] = eff.E[c][m]
    ordered = {k: ordered[k] for k in
               [k for k in ordered if k.startswith("$")]
               + sorted(k for k in ordered if not k.startswith("$"))}
    ordered["$schema_version"] = "3.0.0"
    ordered["$changelog"]["3.0.0"] += [
        "JoI usecase alignment (dataset-usecase.xlsx).",
        "Added category: Heater (space heater — HA climate/generic_thermostat). "
        "Distinct from WaterHeater.",
        "Added MessageSender.SendSlack — team channel message; unlike SMS/KakaoTalk/"
        "mail it needs no per-recipient address, so it can be sent without asking.",
        "History reads: Timeline IR may read PAST values of any value service with "
        "the invented @ notation on read.src — src@-1HOUR / src@-1DAY (value back "
        "then), src@count:today (event count since midnight), and the aggregates "
        "src@avg:today, src@min:today, src@max:today. IR-spec notation, not catalog "
        "services; the hub's recorder answers them.",
    ]

    json.dump(ordered, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cats = [k for k in ordered if not k.startswith("$")]
    n = sum(len(ordered[c]) for c in cats)
    old_cats = [k for k in src if not k.startswith("$")]
    old_n = sum(len(src[c]) for c in old_cats)
    print(f"{DST}: {len(old_cats)} → {len(cats)} categories, {old_n} → {n} services "
          f"(+{len(NEW)} new categories, +{len(added_enums)} enum members)")


if __name__ == "__main__":
    main()
