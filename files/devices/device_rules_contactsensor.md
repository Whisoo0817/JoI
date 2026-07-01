[Device Summary]
<Device "ContactSensor">
  <Service "Contact" type="value">The current contact state (BOOL). **`true` = contact closed (door/window shut); `false` = contact open (door/window open).** Typically on doors/windows. So "is it open?" → `Contact == false`; "is it closed?" → `Contact == true`.</Service>
</Device>

# Rules

The polarity is fixed and system-wide: **closed → `true`, open → `false`.** When building a condition, map the command accordingly:
- "문이 열리면 / when the door opens / if the window is open" → `Contact == false`
- "문이 닫히면 / when closed" → `Contact == true`
Do NOT invert this. There is no separate open/close service — `Contact` is the only read.
