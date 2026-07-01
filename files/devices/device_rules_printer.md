[Device Summary]
<Device "Printer">
  <Service "PrinterState" type="value">Operational state (ENUM: idle, processing, stopped, unknown)</Service>
  <Service "PrinterStateReasons" type="value">List of reasons describing the current state (LIST)</Service>
  <Service "InkStatus" type="value">Overall ink/toner status (ENUM: ok, low, empty, unknown)</Service>
  <Service "InkLevels" type="value">Per-cartridge ink/toner levels (LIST of {name, color, level, type})</Service>
  <Service "LowInkColors" type="value">Comma-separated cartridge colors that are low/empty (STRING)</Service>
  <Service "QueuedJobCount" type="value">Number of jobs in the queue (INTEGER)</Service>
  <Service "IsAcceptingJobs" type="value">Whether the printer accepts new jobs (BOOL)</Service>
  <Service "ColorSupported" type="value">Whether color printing is supported (BOOL)</Service>
  <Service "GetJobs" type="action">Retrieve the current print-job queue (list of {job_id, job_name, state})</Service>
  <Service "PrintFile" type="action">Submit a print job from a URI (file://, http://, https://). Args: Uri (required), JobName, Copies, Sides, ColorMode (optional)</Service>
  <Service "CancelJob" type="action">Cancel a queued/in-progress job. Arg: JobId (INTEGER)</Service>
  <Service "PausePrinter" type="action">Pause the printer</Service>
  <Service "ResumePrinter" type="action">Resume a paused printer</Service>
</Device>

# Rules

- Print a document/file/URI → `PrintFile` (Uri is required; the file path/URL the command names).
- Pause / resume the printer → `PausePrinter` / `ResumePrinter`. Cancel a specific job → `CancelJob` (needs a JobId).
- Status questions: 잉크/토너 → `InkStatus` (low/empty), 어떤 색이 부족 → `LowInkColors`, 프린터 상태 → `PrinterState`, 대기 작업 수 → `QueuedJobCount`.
