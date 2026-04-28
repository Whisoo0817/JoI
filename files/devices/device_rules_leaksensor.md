[Device Summary]
<Device "LeakSensor">
  <Service "Leakage" type="value">Water leak detection status (true/false)</Service>
</Device>

⚠️ "leak is detected / water leak" → ALWAYS include `LeakSensor.Leakage` for the cond read. NEVER put a `leak`/`detected` attr on the action device (e.g. Valve/Siren).

# LeakSensor Examples

[Command]
Check for water leaks (Ask LeakSensor)
["LeakSensor.Leakage"]

[Command]
If a leak is detected, close the valve.
<Reasoning>
LeakSensor reads the leak; Valve is the action target.
</Reasoning>
["LeakSensor.Leakage", "Valve.Close"]
