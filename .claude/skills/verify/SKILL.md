---
name: verify
description: Verify an implemented spec against its acceptance criteria and report coverage. Phase 5 of spec-driven development.
argument-hint: <spec number, e.g. 001>
disable-model-invocation: true
---

Verify spec **$ARGUMENTS** is fully and correctly implemented.

1. Read the spec's `spec.md`, `plan.md`, and `tasks.md`.
2. Run the full test suite, lint, and type check.
3. Use a subagent to independently review the implementation against the spec, so the check isn't biased by the
   context that wrote the code. For **each** acceptance criterion, determine:
   - Is it implemented? Where (file:line)?
   - Which test(s) cover it? Does the test actually assert the *Then* clause, not just exercise the code?
   - Status: ✅ met · ⚠️ partially met / weakly tested · ❌ not met
4. Also check: any behavior in the code that is **not** in the spec (scope creep)? Any non-goal accidentally implemented?
   All tasks checked off?
5. Present a table of AC → status → evidence, plus findings. If everything is ✅, propose setting the spec Status
   to `Done`; otherwise propose follow-up tasks. Change the Status only after the user agrees.
