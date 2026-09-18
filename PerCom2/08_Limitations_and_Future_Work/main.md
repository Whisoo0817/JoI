# Limitations and Future Work

VETS checks generated code against user-confirmed Timeline IR. Whether the IR correctly captures the natural-language request remains a separate challenge: if a user approves an IR that differs from their intent, Explorer checks the code against that IR. The execution order and timing conditions made explicit in the IR could support plain-language explanations or time-axis views for user review. Whether these representations help users understand the behavior and identify errors requires future user studies.

Explorer's verdicts hold within the specified input ranges, execution rules, and device bindings, assuming correct parsing, interpretation, and constraint solving. Implementations outside the supported analysis, such as those with unbounded accumulated variables, and searches that cannot finish within the available resources receive no definitive verdict. The check compares device commands and their timestamps; it does not guarantee physical behavior under communication delays or device failures.

The evaluation is limited to JOI and the program structures examined. Applicability and checking cost on other platforms and automation structures require further evaluation. Future work will extend language and platform support and evaluate long-term operation in real environments.
