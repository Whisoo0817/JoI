[Device Summary]
<Device "WeatherProvider">
  <Service "TemperatureWeather" type="value">Current outdoor temperature (DOUBLE)</Service>
  <Service "HumidityWeather" type="value">Current outdoor humidity (DOUBLE, 0–100)</Service>
  <Service "Pm10Weather" type="value">Current PM10 level (DOUBLE)</Service>
  <Service "Pm25Weather" type="value">Current PM25 level (DOUBLE)</Service>
  <Service "PressureWeather" type="value">Current atmospheric pressure (DOUBLE)</Service>
  <Service "Weather" type="value">Current weather condition (ENUM: thunderstorm, drizzle, rain, snow, mist, smoke, haze, dust, fog, sand, ash, squall, tornado, clear, clouds)</Service>
  <Service "Forecast" type="action">Get the forecasted weather condition N hours from now, returned as a weather name string (rain/clouds/clear/...). Argument: Hour (INTEGER, hours from now; 0 = now). Use for "will it rain", "weather in N hours", forecast-before-it-happens.</Service>
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

- 🛑 "날씨 알려줘"(general) → `Weather` ALONE. Do NOT over-fetch Temperature + Humidity + others alongside it. Only fetch a quantity that was explicitly named.
