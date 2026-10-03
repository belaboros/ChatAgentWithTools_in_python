---
name: plan
description: Write the technical plan (specs/NNN-name/plan.md) for an approved spec. Phase 2 of spec-driven development.
argument-hint: <spec number, e.g. 001>
disable-model-invocation: true
---

Write the technical plan for spec **$ARGUMENTS**.

1. Locate `specs/$ARGUMENTS-*/spec.md`. If its Status is not `Approved` (or later), stop and tell the user it must be
   approved first. If it has unresolved open questions, raise them before planning.
2. Read `CLAUDE.md` and explore the existing codebase thoroughly so the plan fits current architecture and conventions.
   Do not write any code.
3. Think hard about the design. Consider at least one alternative approach and why it's worse. Prefer the simplest
   design that satisfies every acceptance criterion; do not add features beyond the spec.
4. Copy `specs/_template/plan.md` into the spec folder and fill it in. The **Test strategy** table must list every
   AC from the spec.
5. If planning reveals the spec is wrong, incomplete, or infeasible, stop and propose a spec change instead of
   working around it.
6. Summarize the plan (approach, new dependencies, risks) and ask the user to review. When approved, set the plan
   Status to `Approved` and the spec Status to `Planned`. Do **not** proceed to tasks in the same step.
