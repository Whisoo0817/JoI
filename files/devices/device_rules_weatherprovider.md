[Device Summary]
<Device "WeatherProvider">
  <Service "TemperatureWeather" type="value">Current outdoor temperature (DOUBLE)</Service>
  <Service "HumidityWeather" type="value">Current outdoor humidity (DOUBLE, 0–100)</Service>
  <Service "Pm10Weather" type="value">Current PM10 level (DOUBLE)</Service>
  <Service "Pm25Weather" type="value">Current PM25 level (DOUBLE)</Service>
  <Service "PressureWeather" type="value">Current atmospheric pressure (DOUBLE)</Service>
  <Service "Weather" type="value">Current weather condition (ENUM: thunderstorm, drizzle, rain, snow, mist, smoke, haze, dust, fog, sand, ash, squall, tornado, clear, clouds)</Service>
  <Service "GetWeatherInfo" type="action">Get full weather info as a formatted string. ONLY use when latitude and longitude are explicitly given in the command. Arguments: Lat (DOUBLE), Lon (DOUBLE)</Service>
</Device>

# Rules

⚠️ **HARD RULE — `GetWeatherInfo` is COORDINATES-ONLY.**
- ✅ Use `GetWeatherInfo` **ONLY** when the command literally contains a number for latitude AND a number for longitude (e.g., "37.5", "127.0").
- ❌ If the command does NOT contain both coordinate numbers, `GetWeatherInfo` is **FORBIDDEN**. This includes general phrasings like "announce the weather", "tell me the weather", "weather information" — these are NOT coordinate-specified, so use the individual value services instead.
- ❌ `GetWeatherInfo` is NOT a fallback / NOT a default / NOT a "general weather" service. The model's intuition that "no coords → use GetWeatherInfo as default" is WRONG. Default = individual values.

For non-coordinate weather commands (the common case), pick **only the value(s) explicitly mentioned**:
- Temperature → `WeatherProvider.TemperatureWeather`
- Humidity → `WeatherProvider.HumidityWeather`
- Sky state (sunny/cloudy/rain/snow/...) → `WeatherProvider.Weather`
- Fine dust (PM10, PM25) → `WeatherProvider.Pm10Weather` / `Pm25Weather`
- Pressure → `WeatherProvider.PressureWeather`
- **General "weather" / "weather information"** (no specific quantity named) → just `Weather` alone. Do NOT bundle Temperature + Humidity + others. Only chain multiple if the command explicitly lists them (e.g., "tell me the temperature AND humidity").

# WeatherProvider Examples

[Command]
What's the weather like today?
["WeatherProvider.Weather"]

[Command]
Check the outdoor temperature
["WeatherProvider.TemperatureWeather"]

[Command]
Tell me the current humidity outside
["WeatherProvider.HumidityWeather"]

[Command]
Announce the weather information through the speaker
<Reasoning>
General "weather" with NO coordinates and no specific quantity → `Weather` alone, NOT GetWeatherInfo, and NOT bundled with temperature/humidity.
</Reasoning>
["WeatherProvider.Weather", "Speaker.Speak"]

[Command]
Tell me the temperature and humidity outside
<Reasoning>
Two specific quantities explicitly named → chain both.
</Reasoning>
["WeatherProvider.TemperatureWeather", "WeatherProvider.HumidityWeather", "Speaker.Speak"]

[Command]
Get the weather for latitude 37.5 and longitude 127.0
<Reasoning>
Both coordinate numbers given → GetWeatherInfo is correct.
</Reasoning>
["WeatherProvider.GetWeatherInfo"]

[Command]
Check the fine dust level
["WeatherProvider.Pm25Weather"]

# ❌ FORBIDDEN (do NOT do this)

[Command]
Announce the weather every morning at 6 AM
❌ WRONG (uses forbidden coords-only service): `["WeatherProvider.GetWeatherInfo", "Speaker.Speak"]`
❌ WRONG (over-fetches uncalled-for quantities): `["WeatherProvider.Weather", "WeatherProvider.TemperatureWeather", "WeatherProvider.HumidityWeather", "Speaker.Speak"]`
✅ RIGHT: `["WeatherProvider.Weather", "Speaker.Speak"]` — only what was asked.
