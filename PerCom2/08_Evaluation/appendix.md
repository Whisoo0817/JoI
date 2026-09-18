# Dataset Sources and Pattern Breakdown

**External sources and selection.** The 25 official examples comprise 22 Google Home scripts and three Home Assistant documentation or blueprint examples. The 26 research items comprise 12 from Ur et al.~\cite{ur2014}, ten from Huang and Cakmak~\cite{huang2015}, two from TAPInspector~\cite{tapinspector}, one from AutoTap~\cite{autotap}, and one from Brackenbury et al.~\cite{brackenbury2019}. The 24 participant statements are traceable to AutoTap's released study data; they are statements, not necessarily distinct participants. The 25 community items come from Home Assistant Community. Collection initially targeted 25 items per source type; provenance review moved one item from participant responses to research without rebalancing. The 150-item screening log contains the retained 100 and 50 AutoTap statements beyond the source cap. Duplicates were defined by matching trigger, timing, guard, action, and reset semantics after device renaming. Six retained items leave behavior-defining choices unresolved, and two concern online-service rather than smart-home automation. Structured examples and community posts may be normalized; per-item records distinguish these from verbatim text and retain source locators and assumptions.

**JOI patterns and structure.** Table D2 reports the 24-pattern breakdown of the 382 author-written commands. These are automation patterns rather than device categories. The development CSV contains 388 rows; E3 excludes six references containing `timeout` or `on_timeout`. In the evaluated references, every IR contains `start_at` and `call`; 150 contain `if`, 125 `wait`, 108 `cycle`, 52 `delay`, 34 `read`, and one `break`. Of these, 27 have sustained waits and 43 have cron anchors; 54 combine waits with cycles. Each count is the number of IRs containing that feature, with overlap allowed. IR size ranges from two to eight operator nodes (median three). Maximum nesting of `if`/`cycle` is zero, one, two, and three in 166, 172, 31, and 13 cases, respectively. Static call-node counts are one in 265 cases, two in 112, and three in five; these are not dynamic action counts, which depend on repetition and device selection.

**Table D2. Automation patterns in the 382-command JOI dataset.**

| ID | Pattern | n |
| --- | --- | ---: |
| C01 | Single device action | 28 |
| C02 | Action with device selector | 33 |
| C03 | Single-condition `if` (incl. if-else) | 34 |
| C05 | AND-compound `if` | 30 |
| C06 | OR-compound / chained `if-elif-else` | 7 |
| C07 | Level-triggered wait (“when X, do Y”) | 32 |
| C08 | Rising-edge trigger (“whenever”) | 41 |
| C09 | Sequential delay | 18 |
| C10 | Trigger + delayed action | 9 |
| C11 | Snapshot, delay, and re-read comparison | 8 |
| C12 | Phase lifecycle (“when X, every N thereafter”) | 15 |
| C13 | Alternation / binary toggle | 7 |
| C14 | Progressive update with counter and stop | 7 |
| C15 | Cron-scheduled action | 21 |
| C16 | Cron + branch | 13 |
| C17 | Periodic polling + branch | 12 |
| C18 | Bounded duration (time-window cycle) | 10 |
| C19 | Hysteresis (double-threshold deadband) | 8 |
| C20 | Sustained condition (“for at least N”) | 17 |
| C21 | Group consensus (all/any quantifier) | 7 |
| C22 | Counted repetition (“repeat N times, stop”) | 10 |
| C23 | Sustained trigger + multi-step sequence | 5 |
| C24 | Sustained trigger + repeating alert | 5 |
| C25 | Periodic polling + if-else | 5 |
| | **Total** | **382** |
