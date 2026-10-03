---
name: spec
description: Start a new feature spec by interviewing the user, then write specs/NNN-name/spec.md. Phase 1 of spec-driven development.
argument-hint: <short feature idea>
disable-model-invocation: true
---

Create a new feature specification for: **$ARGUMENTS**

1. **Explore first.** Read `CLAUDE.md`, `specs/README.md`, and existing specs in `specs/` to understand context and avoid
   overlap. Skim relevant code if any exists. Do not write any code.
2. **Interview the user.** Use the AskUserQuestion tool to ask about anything that is ambiguous: goals, users,
   expected behavior, edge cases, error handling, non-goals, constraints (security, cost, performance), and trade-offs.
   Ask focused questions in rounds (up to 4 per round); skip anything already clear. Don't ask about implementation
   details — those belong in the plan. Keep going until you could write testable acceptance criteria for everything.
3. **Write the spec.** Pick the next free number `NNN` and a short kebab-case name. Copy `specs/_template/spec.md` to
   `specs/NNN-name/spec.md` and fill it in:
   - Status `Draft`, today's date.
   - Acceptance criteria numbered `AC-1…`, in Given/When/Then form, covering error paths and edge cases.
   - Explicit non-goals.
   - Any unresolved items under Open questions.
   - No implementation details (no module names, libraries, or code).
4. **Review and stop.** Summarize the spec (number of ACs, key non-goals, open questions) and ask the user to review it.
   When they approve, set Status to `Approved`. Do **not** proceed to planning in the same step.
