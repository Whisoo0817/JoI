# Condition and Execution Frequency Analyzer

Analyze the English command to determine the checking condition (Polling, Immediate Snapshot, Schedule) and its action timeline.

## 🚨 CRITICAL RULE: Schedules vs. Conditions
- **Specific Time Only (Snapshot)** (e.g., "At 6 PM", "At midnight", "On weekdays at 3 PM"): A one-time action schedule at that specific moment.
  - Example: "Turn on the light at 6 PM" -> `[Analysis] 'At 6 PM' is a Snapshot schedule.`
- **Date/Day Only (Duration)** (e.g., "On weekends", "On Christmas", "On weekdays"): A duration covering the entire day/period.
  - Example: "On weekends, check every hour." -> `[Analysis] 'On weekends' is a Duration. 'every hour' is a recurring period (Snapshot).`
- A **time schedule** (e.g., "Every night at 10 PM", "Every 10 minutes") implies an action at that explicit time/period without checking a condition, UNLESS paired with a sensor check.
  - Example: "When Christmas begins, greet with the robot arm" -> `[Conclusion] Act at 12/25 0AM.` (No condition check, explicit date triggers at 0AM).
  - Example: "Take a picture with the camera every hour" -> `[Conclusion] Act every 1 hour.` (No condition check).

## Execution Categories (For Analysis)

### 1. Continuous Monitoring (Polling)
The system must constantly poll an IoT device's sensor in real-time to catch a state change. English grammar distinguishes between a one-time event catch and an infinite recurring catch.
- **Continuous_When (One-Time Event Trigger)**: Constantly monitor until the event happens ONCE.
  - Cues: Explicit time is absent. Starts with **`When`** or **`Once`** + an action/change verb (e.g., "When it rains", "Once the door opens").
  - Conclusion Format: `Poll [Sensor]. Act once when satisfied.`
- **Continuous_Whenever (Infinite Recurring Trigger)**: Constantly monitor and trigger EVERY TIME the event happens.
  - Cues: **`Whenever`**, **`Each time`**, **`Every time`**.
  - Conclusion Format: `Infinite polling on [Sensor]. Act on every state change.`

### 2. Scheduled Snapshot (Scheduled_If)
The system wakes up on a specific schedule (e.g., every 10 minutes, at 8 PM) AND checks a device sensor's snapshot state EXACTLY ONCE, then action.
- Cues: Explicit scheduling words (`Every 10 minutes`, `At 8 PM`) + A device condition check (`If the temperature is...`, `Check if the door is...`).
- Conclusion Format: `At [Period/Time], check [Sensor] and act based on result.`

### 3. Immediate Snapshot (If)
The system checks a device sensor EXACTLY ONCE right now, and then the task is completely finished. No scheduling, no continuous monitoring. Time delays ("after 30 minutes") are simply evaluated as a delay.
- Cues: **`If`** + state check (e.g., "If it is raining", "If the window is open"). 
- Conclusion Format: `Immediately check [Sensor] and act based on result.` (If no condition, `Immediately act and delay.`)
- **CRITICAL DISTINCTION (If vs When/Once/Whenever)**: 
  - **`When / Once`**: Waiting for a future state change/event -> **Polling**
  - **`Whenever / Each time / Every time`**: Waiting for a future state change/event infinitely -> **Infinite Polling**
  - **`If`**: Checking if the state is ALREADY happening / being maintained right now -> **Immediate Snapshot**
  - [Contrast] "**If** it is raining..." -> Check current state -> **[Conclusion] Immediately check Rain Sensor...**
  - [Contrast] "**When** it rains..." -> Wait for rain -> **[Conclusion] Poll Rain Sensor...**
  - [Contrast] "**Whenever** it rains..." -> Wait for rain infinitely -> **[Conclusion] Infinite polling on Rain Sensor...**

### 4. Pure Action Schedule
The system wakes up on a specific schedule (fixed time, period, or duration) and simply executes an action WITHOUT checking any device condition.
- Cues: Explicit scheduling words (`Every 10 AM`, `Every 1 hour`), but NO state or sensor check.
- Conclusion Format: `Act at [Specific Time]` or `From [Start] to [End], act every [Interval].`

### 5. Hybrid Patterns
A single command can combine multiple patterns, e.g., Continuous Monitoring to start, followed by a Scheduled Snapshot loop.
- Example: "When the door opens, check the living room temperature every minute thereafter, and if it's 30 degrees or higher, turn on the AC." (Continuous_When -> Scheduled_If)
- Conclusion Format: `Poll [Sensor1]. When satisfied, perform periodic state checks from [Start] to [End] every [Interval].`

## Output Format
Output a concise natural language explanation in **ENGLISH** in two steps: [Analysis] and [Conclusion]. DO NOT output ANY Korean.

- [Analysis]: Describe clearly and briefly. Extract cues like "If", "When", "Whenever", and state whether it waits for a state transition (polling) or checks the current state (snapshot). Extract time components and delays.
- [Conclusion]: Summarize the execution timing following the `Conclusion Format` strictly without unnecessary words.

## Examples

[Command]
If [Condition A] is true, do [Action B]. If not, do [Action C].
[Analysis] 'If' denotes a snapshot to check the current state.
[Conclusion] Immediately check [Device A] state and act based on result.

[Command]
Start [Device A] in [Mode 1] and change to [Mode 2] after 30 minutes.
[Analysis] 'after 30 minutes' is a delay.
[Conclusion] Immediately act and delay.

[Command]
If [Sensor A] is [Value] or higher, do [Action B].
[Analysis] 'If' denotes a snapshot.
[Conclusion] Immediately check [Sensor A] and act based on result.

[Command]
If [State A] is active right now, do [Action B].
[Analysis] 'If' with 'right now' is an immediate snapshot.
[Conclusion] Immediately check [Sensor A] and act based on result.

[Command]
When [Event A] occurs, do [Action B] after 5 minutes.
[Analysis] 'When' indicates waiting for the [Event A] transition. 'after 5 minutes' is a delay.
[Conclusion] Poll [Sensor A]. Act once when satisfied.

[Command]
Whenever [Event A] occurs, do [Action B].
[Analysis] 'Whenever' indicates infinite event-based triggering.
[Conclusion] Infinite polling on [Sensor A]. Act on every state change.

[Command]
Once [Sensor A] drops below [Value X], do [Action B].
[Analysis] 'Once' indicates waiting for the condition to be met (transition).
[Conclusion] Poll [Sensor A]. Act once when satisfied.

[Command]
Do [Action A] every noon.
[Analysis] 'every noon' is a recurring snapshot schedule.
[Conclusion] Act at 12 PM.

[Command]
Every 11 PM, do [Action A].
[Analysis] 'Every 11 PM' is a recurring snapshot schedule.
[Conclusion] Act at 11 PM.

[Command]
When Christmas begins, do [Action A].
[Analysis] 'When Christmas begins' represents a specific starting point in time.
[Conclusion] Act at 12/25 0 AM.

[Command]
Every hour, do [Action A].
[Analysis] 'Every hour' is a recurring interval.
[Conclusion] Act every 1 hour.

[Command]
Every hour on Christmas, do [Action A].
[Analysis] 'Every hour on Christmas' is a recurring snapshot schedule within a specific duration.
[Conclusion] From 12/25 0 AM to 12/26 0 AM, act every 1 hour.

[Command]
If any [Sensor A] is in [State X], do [Action B].
[Analysis] 'If' and 'in [State X]' refer to current snapshot state.
[Conclusion] Immediately check [Sensor A] and act based on result.

[Command]
When [Sensor A] goes above [Value X], do [Action B].
[Analysis] 'When' indicates waiting for the state transition to exceed [Value X].
[Conclusion] Poll [Sensor A]. Act once when satisfied and stop polling.

[Command]
Repeatedly do [Action A] every 10 minutes in the afternoon.
[Analysis] 'in the afternoon' is a duration. 'every 10 minutes' is the repetition interval.
[Conclusion] During the afternoon, act every 10 minutes.

[Command]
On weekdays at 7 AM, do [Action A].
[Analysis] 'On weekdays at 7 AM' refers to a specific recurring snapshot time, not a duration.
[Conclusion] At 7 AM on weekdays, act.

[Command]
On weekdays at 3 PM, if [State X], do [Action A].
[Analysis] 'On weekdays at 3 PM' refers to a specific recurring snapshot time, not a duration. 'if' is a snapshot check.
[Conclusion] At 3 PM on weekdays, check [Sensor A] and act based on result.

[Command]
On weekdays, check [Sensor A] every 3 minutes.
[Analysis] 'On weekdays' is a duration. 'every 3 minutes' is the repetition interval within that duration.
[Conclusion] From Monday 0 AM to Saturday 0 AM, check [Sensor A] every 3 minutes and act based on result.

[Command]
Do [Action A] every 10 minutes from now until 3 PM.
[Analysis] 'from now until 3 PM' is a specific duration. 'every 10 minutes' is the interval.
[Conclusion] From now until 3 PM, act every 10 minutes.

[Command]
When [Event A] occurs, do [Action B], and 5 minutes later, check [Sensor C] and if [State X], do [Action D].
[Analysis] 'When' indicates polling. '5 minutes later' is a delay. 'if' is a snapshot check.
[Conclusion] Poll [Sensor A]. When satisfied, act and delay. Thereafter, check [Sensor C] and act based on result.

[Command]
When [Event A] occurs, check [Sensor B] every 5 minutes from then on, and if [State X], do [Action C].
[Analysis] 'When' indicates polling for a trigger. 'every 5 minutes' is the subsequent recurrence interval.
[Conclusion] Poll [Sensor A]. When satisfied, check [Sensor B] every 5 minutes and act based on result.

[Command]
When [Sensor A] drops below [Value X], do [Action B] every hour.
[Analysis] 'When' indicates polling for a trigger. 'every hour' is the subsequent recurrence interval.
[Conclusion] Poll [Sensor A]. When satisfied, act every 1 hour.

[Command]
Check [Sensor A] at 3 PM on weekends, and if [State X], do [Action B].
[Analysis] 'at 3 PM on weekends' is a specific recurring snapshot schedule. 'if' is a snapshot check.
[Conclusion] At 3 PM on weekends, check [Sensor A] and act based on result.

[Command]
Every time [Sensor A] drops below [Value X], do [Action B].
[Analysis] 'Every time' indicates infinite polling on the [Sensor A] value.
[Conclusion] Infinite polling on [Sensor A]. Act on every state change.

[Command]
If [Event A] is detected on February 2nd, do [Action B].
[Analysis] 'on February 2nd' is a specific duration. 'If [Event A] is detected' implies monitoring for an event within that window.
[Conclusion] From 2/2 0 AM to 2/3 0 AM, poll [Sensor A]. Act when satisfied.

[Command]
Every 30 minutes on weekend afternoons, do [Action A].
[Analysis] 'on weekend afternoons' is a duration that applies to both Saturday and Sunday from 12 PM to midnight. 'Every 30 minutes' is the repetition interval.
[Conclusion] On Saturday and Sunday, from 12 PM to midnight each day, act every 30 minutes.

[Command]
Check [Sensor A] now and again in 10 minutes. If it has changed by [Value X], do [Action B].
[Analysis] 'now' is an immediate snapshot. 'and again in 10 minutes' is a single delay for a second snapshot check, not a recurring schedule. 'If' is a condition check based on the two snapshots.
[Conclusion] Immediately check [Sensor A]. Delay 10 minutes, then check [Sensor A] again and act based on result.
