---
name: tasks
description: Break an approved plan into an ordered, test-first task checklist (specs/NNN-name/tasks.md). Phase 3 of spec-driven development.
argument-hint: <spec number, e.g. 001>
disable-model-invocation: true
---

Create the task list for spec **$ARGUMENTS**.

1. Read `specs/$ARGUMENTS-*/spec.md` and `plan.md`. If the plan is not `Approved`, stop and say so.
2. Copy `specs/_template/tasks.md` into the spec folder and write tasks that are:
   - **Small** — roughly under an hour of work, one logical change, one commit.
   - **Ordered** — dependencies first; project scaffolding (if needed) as T1.
   - **Testable** — each names the test(s) that prove it, and the AC IDs it satisfies.
3. Check coverage: every AC in the spec must be satisfied by at least one task. List any gap explicitly.
4. Show the task list and ask the user to review. Do **not** start implementing.
