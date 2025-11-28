# Custom global instructions for developers
_Exported on 11/9/2025 at 22:50:33 PST from Cursor (2.0.69)_

---

**User**

can you generate a general custom set of global instructions to paste inside of cursor in the settings? i currently don't have anything loaded. 



generate a list of general rulesets that developers recommend and why they use them.



then generate a more advanced list of clever and innovative rulesets that developers have come up with in the past 6 months that are becoming more and more utilized by all. 





Implement the plan as specified, it is attached for your reference. Do NOT edit the plan file itself.

To-do's from the plan have already been created. Do not create them again. Mark them as in_progress as you work, starting with the first one. Don't stop until you have completed all the to-dos.

---

**Cursor**

## Global Cursor Instructions

Paste this into the Cursor settings’ global instructions:

- Default mindset: prioritize clarity, defensive coding, and incremental delivery; always surface unknowns or missing context before assuming.
- Interaction: respond concisely, highlight blockers first, and propose next steps or tests even if code change isn’t requested.
- Code edits: propose minimal diffs, preserve existing style/naming, document assumptions, and avoid introducing global side effects.
- Safety: refuse tasks involving credential exposure, malware, or policy-violating content; flag security concerns and recommend mitigations.
- Tool use: prefer repo-aware tools over shell commands; announce long-running actions and only modify files relevant to the request.
- Testing: recommend or run fast automated checks when feasible; call out coverage gaps and edge cases explicitly.
- Reviews: when asked to review, lead with bugs/regressions, reference files directly, and keep summaries brief.
- Communication: match the user’s tone, avoid redundant explanations, and confirm completion status before signing off.
- Version control: assume a dirty tree; never revert user changes; suggest commits only when work is self-contained.
- Accessibility & performance: highlight opportunities to improve accessibility, internationalization, and runtime/memory characteristics.

## Established Rulesets Developers Recommend (and Why)

- Clean Diff Policy – Keep patches tight, contextual, and reversible; simplifies code reviews and reduces merge risk.
- Continuous Testing Gate – Run unit/integration suites on every substantive edit; prevents regressions from shipping.
- Principle of Least Surprise – Align new code with existing patterns; lowers onboarding friction and maintenance cost.
- Explicit Error Handling – Require graceful degradation and logging for failure paths; improves observability and resiliency.
- Documentation on Touch – Any file you modify gets updated comments or README notes; keeps tribal knowledge from decaying.
- Dependency Hygiene – Prohibit adding packages without justification and audit trail; curbs bloat and supply-chain exposure.

## Emerging Rulesets Gaining Traction (last ~6 months)

- AI Guardrails-as-Code – Maintain prompt guardrails in versioned YAML alongside tests; teams like it because reviewers can diff conversational behavior the same way as code.
- Context Budgeting – Enforce a per-task token budget with auto-truncation rules; keeps AI responses deterministic and avoids runaway context windows.
- Intent-first Pull Requests – Require recording the problem statement and acceptance criteria before writing code; improves reviewer alignment and postmortem traceability.
- Telemetry-driven Refactor Triggers – Gate large refactors on live usage metrics (e.g., p95 latency or error counts) to ensure effort maps to measurable wins.
- Pair-LLM Spot Checks – Schedule asynchronous “second-model” reviews for risky changes (security, data privacy); reduces single-model blind spots that dev teams have reported.

Let me know if you’d like any of these tailored for a specific project or team workflow.

