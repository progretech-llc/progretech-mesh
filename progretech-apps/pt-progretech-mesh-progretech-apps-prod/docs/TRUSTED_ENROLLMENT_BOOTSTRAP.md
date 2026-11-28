# Optional PTM1 Enrollment Recognizer

Some agents may include a small PTM1 recognizer for faster deterministic routing. It is an **optional accelerator**, not a Mesh prerequisite and not part of the universal acceptance starting state.

The authoritative v1 onboarding contract is the website-generated self-describing enrollment message plus the Mesh-hosted protocol and adapter catalog. An unfamiliar capable agent must be able to enroll with zero ProgreTech software preinstalled.

A recognizer, when present, may detect `PTM1:` before ordinary conversational reasoning and hand the same message to the agent's local enrollment workflow. Its presence must never change the security model: it grants no authority, may not bypass policy, and must preserve plug-and-monitor/non-interference guarantees.
