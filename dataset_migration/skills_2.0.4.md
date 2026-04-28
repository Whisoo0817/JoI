# Service List 2.0.4 — Compact Reference
# Format: SkillId  | values: [...] | functions: [Name(arg:Type, ...)]

## AirConditioner
  values    : ['AirConditionerMode', 'TargetTemperature']
  functions : ['SetAirConditionerMode(Mode:ENUM<AirConditionerModeEnum>)', 'SetTargetTemperature(Temperature:DOUBLE)']
  enum AirConditionerModeEnum: ['auto', 'cool', 'heat']

## AirPurifier
  values    : ['AirPurifierMode']
  functions : ['SetAirPurifierMode(Mode:ENUM<AirPurifierModeEnum>)']
  enum AirPurifierModeEnum: ['auto', 'sleep', 'low', 'medium', 'high', 'quiet', 'windFree', 'off']

## AirQualitySensor
  values    : ['CarbonDioxide', 'DustLevel', 'FineDustLevel', 'Humidity', 'Temperature', 'TvocLevel', 'VeryFineDustLevel']

## ArmRobot
  values    : ['ArmRobotType', 'CurrentPosition']
  functions : ['Hello()', 'SendCommand(Command:ENUM<ArmRobotTypeEnum>)', 'SetPosition(Position:ENUM<ArmRobotPositionEnum>)']
  enum ArmRobotPositionEnum: ['mycobot280_pi']
  enum ArmRobotTypeEnum: ['mycobot280_pi']

## AudioRecorder
  values    : ['AudioFile', 'RecordStatus']
  functions : ['RecordStart()', 'RecordStop(File:BINARY<wav>)', 'RecordWithDuration(File:STRING, Duration:DOUBLE)']
  enum RecordStatusEnum: ['idle', 'recording']

## Button
  values    : ['Button']
  enum ButtonEnum: ['pushed', 'held', 'double', 'pushed_2x', 'pushed_3x', 'pushed_4x', 'pushed_5x', 'pushed_6x', 'down', 'down_2x', 'down_3x', 'down_4x', 'down_5x', 'down_6x', 'down_hold', 'up', 'up_2x', 'up_3x', 'up_4x', 'up_5x', 'up_6x', 'up_hold', 'swipe_up', 'swipe_down', 'swipe_left', 'swipe_right']

## Camera
  values    : ['CameraState', 'Image', 'Stream', 'Video']
  functions : ['CaptureImage()', 'CaptureVideo()', 'StartStream()', 'StopStream()']
  enum CameraStateEnum: ['off', 'on', 'restarting', 'unavailable']

## CarbonDioxideSensor
  values    : ['CarbonDioxide']

## Charger
  values    : ['ChargingState', 'Current', 'Power', 'Voltage']
  enum ChargingStateEnum: ['charging', 'discharging', 'stopped', 'fullyCharged', 'error']

## Clock
  values    : ['Date', 'Datetime', 'Day', 'Hour', 'IsHoliday', 'Minute', 'Month', 'Second', 'Time', 'Timestamp', 'Weekday', 'Year']
  functions : ['Delay(Hour:INTEGER, Minute:INTEGER, Second:INTEGER)']
  enum WeekdayEnum: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

## CloudServiceProvider
  values    : ['ChatSession', 'GeneratedImage', 'ImageExplanation', 'LLMModels', 'UploadedFile']
  functions : ['ChatWithAI(Prompt:STRING)', 'ExplainImage(ImageFile:BINARY)', 'GenerateImage(Prompt:STRING)', 'IsAvailable(ServiceName:BOOL)', 'SaveToFile(Data:BINARY, FilePath:STRING)', 'SpeechToText(AudioFile:STRING)', 'TextToSpeech(Text:STRING)', 'UploadFile(File:STRING)', 'UploadToCloudStorage(File:STRING)']
  enum LLMModelEnum: ['gemini_3_pro', 'gemini_2_5_pro', 'gemini_2_5_flash', 'gemini_2_5_flash_lite', 'gemini_2_0_flash', 'gemini_2_0_flash_lite', 'gpt_5_1', 'gpt_5', 'gpt_5_mini', 'gpt_5_nano', 'gpt_4_1', 'gpt_4_1_mini', 'gpt_4_1_nano', 'gpt_4o', 'gpt_4o_mini', 'gpt_4', 'gpt_3_5_turbo', 'gpt_o4_mini', 'gpt_o3', 'gpt_o3_mini', 'gpt_o1']
  enum LLMServiceEnum: ['openai', 'gemini']

## ColorControl
  values    : ['Color']
  functions : ['SetColor(Color:STRING<r|g|b>)']
  enum ColorModeEnum: ['HSV', 'RGB', 'XY', 'CT']

## ContactSensor
  values    : ['Contact']

## Dehumidifier
  values    : ['DehumidifierMode']
  functions : ['SetDehumidifierMode(Mode:ENUM<DehumidifierModeEnum>)']
  enum DehumidifierModeEnum: ['cooling', 'delayWash', 'drying', 'finished', 'refreshing', 'weightSensing', 'wrinklePrevent', 'dehumidifying', 'AIDrying', 'sanitizing', 'internalCare', 'freezeProtection', 'continuousDehumidifying', 'thawingFrozenInside']

## Dishwasher
  values    : ['DishwasherMode']
  functions : ['SetDishwasherMode(Mode:ENUM<DishwasherModeEnum>)']
  enum DishwasherModeEnum: ['eco', 'intense', 'auto', 'quick', 'rinse', 'dry']

## Door
  values    : ['DoorState']
  functions : ['Close()', 'Open()']
  enum DoorStateEnum: ['closed', 'closing', 'open', 'opening', 'unknown']

## DoorLock
  values    : ['DoorLockState']
  functions : ['Lock()', 'Unlock()']
  enum DoorLockStateEnum: ['closed', 'closing', 'open', 'opening', 'unknown']

## EmailProvider
  functions : ['SendMail(ToAddress:STRING, Title:STRING, Body:STRING)', 'SendMailWithFile(ToAddress:STRING, Title:STRING, Body:STRING, File:STRING)']

## FaceRecognizer
  values    : ['RecognizedResult']
  functions : ['AddFace(FaceID:STRING)', 'DeleteFace(FaceID:STRING)', 'End()', 'Start()']

## Humidifier
  values    : ['HumidifierMode']
  functions : ['SetHumidifierMode(Mode:ENUM<HumidifierModeEnum>)']
  enum HumidifierModeEnum: ['auto', 'low', 'medium', 'high']

## HumiditySensor
  values    : ['Humidity']

## LaundryDryer
  values    : ['LaundryDryerMode', 'SpinSpeed']
  functions : ['SetLaundryDryerMode(Mode:ENUM<LaundryDryerModeEnum>)', 'SetSpinSpeed(Speed:INTEGER)']
  enum LaundryDryerModeEnum: ['auto', 'quick', 'quiet', 'lownoise', 'lowenergy', 'vacation', 'min', 'max', 'night', 'day', 'normal', 'delicate', 'heavy', 'whites']

## LeakSensor
  values    : ['Leakage']
  enum LeakageEnum: ['detected', 'not detected']

## LevelControl
  values    : ['CurrentLevel', 'MaxLevel', 'MinLevel']
  functions : ['MoveToLevel(Level:DOUBLE, Rate:DOUBLE)']

## Light
  values    : ['ColorMode', 'ColorTempPhysicalMaxMireds', 'ColorTempPhysicalMinMireds', 'ColorTemperatureMireds', 'CurrentBrightness', 'CurrentHue', 'CurrentSaturation', 'CurrentX', 'CurrentY', 'EnhancedCurrentHue']
  functions : ['EnhancedMoveToHue(EnhancedHue:INTEGER, Direction:ENUM<HueDirectionEnum>, TransitionTime:DOUBLE)', 'EnhancedMoveToHueAndSaturation(EnhancedHue:INTEGER, Saturation:INTEGER, TransitionTime:DOUBLE)', 'MoveColor(RateX:DOUBLE, RateY:DOUBLE)', 'MoveColorTemperature(MoveMode:ENUM<MoveModeEnum>, Rate:INTEGER, ColorTemperatureMinimumMireds:INTEGER, ColorTemperatureMaximumMireds:INTEGER)', 'MoveHue(MoveMode:ENUM<MoveModeEnum>, Rate:INTEGER)', 'MoveToBrightness(Brightness:DOUBLE, Rate:DOUBLE)', 'MoveToColor(ColorX:DOUBLE, ColorY:DOUBLE, TransitionTime:DOUBLE)', 'MoveToColorTemperature(ColorTemperatureMireds:INTEGER, TransitionTime:DOUBLE)', 'MoveToHue(Hue:INTEGER, Direction:ENUM<HueDirectionEnum>, TransitionTime:DOUBLE)', 'MoveToHueAndSaturation(Hue:INTEGER, Saturation:INTEGER, TransitionTime:DOUBLE)', 'MoveToSaturation(Saturation:INTEGER, TransitionTime:DOUBLE)', 'StepColor(StepX:DOUBLE, StepY:DOUBLE, TransitionTime:DOUBLE)', 'StepColorTemperature(StepMode:ENUM<StepModeEnum>, StepSize:INTEGER, TransitionTime:DOUBLE, ColorTemperatureMinimumMireds:INTEGER, ColorTemperatureMaximumMireds:INTEGER)', 'StepHue(StepMode:ENUM<StepModeEnum>, StepSize:INTEGER, TransitionTime:DOUBLE)']
  enum ColorModeEnum: ['hsv', 'xy', 'ct']
  enum HueDirectionEnum: ['shortest_distance', 'longest_distance', 'up', 'down']
  enum MoveModeEnum: ['stop', 'up', 'down']
  enum StepModeEnum: ['up', 'down']

## LightSensor
  values    : ['Brightness']

## MenuProvider
  values    : ['Menu', 'TodayMenu', 'TodayPlace']
  functions : ['GetMenu(Command:STRING)']

## MotionSensor
  values    : ['Motion']

## MultiButton
  values    : ['Button1', 'Button2', 'Button3', 'Button4']
  enum ButtonEnum: ['pushed', 'held', 'double', 'pushed_2x', 'pushed_3x', 'down', 'down_hold', 'up', 'up_hold']

## Oven
  values    : ['OvenMode']
  functions : ['AddMoreTime(Time:DOUBLE)', 'SetCookingParameters(Mode:ENUM<OvenModeEnum>, Time:DOUBLE)', 'SetOvenMode(Mode:ENUM<OvenModeEnum>)']
  enum OvenModeEnum: ['heating', 'grill', 'warming', 'defrosting', 'Conventional', 'Bake', 'BottomHeat', 'ConvectionBake', 'ConvectionRoast', 'Broil', 'ConvectionBroil', 'SteamCook', 'SteamBake', 'SteamRoast', 'SteamBottomHeatplusConvection', 'Microwave', 'MWplusGrill', 'MWplusConvection', 'MWplusHotBlast', 'MWplusHotBlast2', 'SlimMiddle', 'SlimStrong', 'SlowCook', 'Proof', 'Dehydrate', 'Others', 'StrongSteam', 'Descale', 'Rinse']

## Plug
  values    : ['Current', 'Power', 'Voltage']

## PresenceSensor
  values    : ['Presence']

## PresenceVitalSensor
  values    : ['Awakeness', 'Distance', 'DwellTime', 'HeartRate', 'MovementIndex', 'Presence', 'RespiratoryRate']

## PressureSensor
  values    : ['Presence']

## Pump
  values    : ['PumpMode']
  functions : ['SetPumpMode(PumpMode:ENUM<PumpModeEnum>)']
  enum PumpModeEnum: ['normal', 'minimum', 'maximum', 'localSetting']

## RainSensor
  values    : ['Rain']

## RiceCooker
  values    : ['RiceCookerMode']
  functions : ['AddMoreTime(Time:DOUBLE)', 'SetCookingParameters(Mode:ENUM<RiceCookerModeEnum>, Time:DOUBLE)', 'SetRiceCookerMode(Mode:ENUM<RiceCookerModeEnum>)']
  enum RiceCookerModeEnum: ['cooking', 'keepWarm', 'reheating', 'autoClean', 'soakInnerPot']

## RobotVacuumCleaner
  values    : ['RobotVacuumCleanerCleaningMode', 'RobotVacuumCleanerRunMode']
  functions : ['SetRobotVacuumCleanerCleaningMode(Mode:ENUM<RobotVacuumCleanerCleaningModeEnum>)', 'SetRobotVacuumCleanerRunMode(Mode:ENUM<RobotVacuumCleanerRunModeEnum>)']
  enum RobotVacuumCleanerCleaningModeEnum: ['auto', 'part', 'repeat', 'manual', 'stop', 'map']
  enum RobotVacuumCleanerOperatingStateEnum: ['stopped', 'running', 'paused', 'seekingCharger', 'charging', 'docked', 'unableToStartOrResume', 'unableToCompleteOperation', 'commandInvalidInState', 'failedToFindChargingDock', 'stuck', 'dustBinMissing', 'dustBinFull', 'waterTankEmpty', 'waterTankMissing', 'waterTankLidOpen', 'mopCleaningPadMissing']
  enum RobotVacuumCleanerRunModeEnum: ['homing', 'idle', 'charging', 'alarm', 'powerOff', 'reserve', 'point', 'after', 'cleaning', 'pause', 'washingMop']

## RotaryControl
  values    : ['Rotation', 'RotationSteps']
  enum RotaryEnum: ['clockwise', 'counter_clockwise']

## Safe
  values    : ['SafeState']
  functions : ['Lock()', 'Unlock()']
  enum SafeStateEnum: ['closed', 'closing', 'open', 'opening', 'unknown']

## Siren
  values    : ['SirenMode']
  functions : ['SetSirenMode(Mode:ENUM<SirenModeEnum>)']
  enum SirenModeEnum: ['emergency', 'fire', 'police', 'ambulance']

## SmokeDetector
  values    : ['Smoke']

## SoundSensor
  values    : ['Sound']

## Speaker
  values    : ['PlaybackState', 'Volume']
  functions : ['FastForward()', 'Pause()', 'Play(MediaSource:STRING)', 'Rewind()', 'SetVolume(Volume:INTEGER)', 'Speak(Text:STRING)', 'Stop()', 'VolumeDown()', 'VolumeUp()']
  enum PlaybackStateEnum: ['paused', 'playing', 'stopped', 'fastforwarding', 'rewinding', 'buffering']

## Switch
  values    : ['Switch']
  functions : ['Off()', 'On()', 'Toggle()']

## Television
  values    : ['Channel']
  functions : ['ChannelDown()', 'ChannelUp()', 'SetChannel(Channel:INTEGER)']

## TemperatureSensor
  values    : ['Temperature']

## Valve
  values    : ['ValveState']
  functions : ['Close()', 'Open()']

## WeatherProvider
  values    : ['HumidityWeather', 'Pm10Weather', 'Pm25Weather', 'PressureWeather', 'TemperatureWeather', 'Weather']
  functions : ['GetWeatherInfo(Lat:DOUBLE, Lon:DOUBLE)']
  enum WeatherEnum: ['thunderstorm', 'drizzle', 'rain', 'snow', 'mist', 'smoke', 'haze', 'dust', 'fog', 'sand', 'ash', 'squall', 'tornado', 'clear', 'clouds']

## WindowCovering
  values    : ['CurrentPosition', 'WindowCoveringType']
  functions : ['DownOrClose()', 'SetLevel(Level:INTEGER)', 'Stop()', 'UpOrOpen()']
  enum WindowCoveringTypeEnum: ['window', 'blind', 'shade']
