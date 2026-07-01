[Device Summary]
<Device "LeakSensor">
  <Service "Leakage" type="value">Water leak detection status (true: leak detected, false: no leak)</Service>
</Device>

WARNING: "leak is detected / water leak" → ALWAYS use LeakSensor.Leakage for the cond read. NEVER put a leak/detected attribute on the action device (e.g., Valve, Siren).
