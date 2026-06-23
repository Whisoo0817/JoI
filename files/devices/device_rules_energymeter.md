[Device Summary]
<Device "EnergyMeter">
  <Service "TotalEnergyConsumption" type="value">Lifetime cumulative energy consumed, in kWh (DOUBLE)</Service>
  <Service "CurrentDayConsumption" type="value">Energy consumed since the start of today, in kWh (DOUBLE)</Service>
  <Service "CurrentWeekConsumption" type="value">Energy consumed since the start of this week, in kWh (DOUBLE)</Service>
  <Service "CurrentMonthConsumption" type="value">Energy consumed since the start of this month, in kWh (DOUBLE)</Service>
</Device>

# Rules

- EnergyMeter is **read-only** (cumulative energy in kWh) — no actions.
- Pick the period the command names: 오늘 → `CurrentDayConsumption`, 이번 주 → `CurrentWeekConsumption`, 이번 달 → `CurrentMonthConsumption`, 누적/전체 → `TotalEnergyConsumption`. Default a bare "전력 사용량/소비량" to `CurrentDayConsumption`.
- This is ENERGY over time (kWh). For instantaneous power draw (W) use the `PowerMeter` skill instead.

# EnergyMeter Examples

[Command]
How much energy was used today?
["EnergyMeter.CurrentDayConsumption"]

[Command]
Tell me this month's electricity usage
["EnergyMeter.CurrentMonthConsumption"]
