[Device Summary]
<Device "RotaryControl">
  <Service "Rotation" type="value">Rotary direction. Enum values: clockwise, counter_clockwise.</Service>
  <Service "RotationSteps" type="value">Number of rotation steps (INTEGER)</Service>
</Device>

# Rules

- RotaryControl is a **read-only** input device (no actions). Read direction → `Rotation` (clockwise/counter_clockwise); step count → `RotationSteps`. Typically used as a trigger/condition.
