---
name: implement
description: Implement the next unchecked task(s) of a spec test-first. Phase 4 of spec-driven development.
argument-hint: <spec number> [task id, e.g. T3 | all]
disable-model-invocation: true
---

Implement spec tasks: **$ARGUMENTS**

The first argument is the spec number; an optional second argument is a task ID or `all`. With no task ID, do only
the next unchecked task.

1. Read `CLAUDE.md`, and the spec's `spec.md`, `plan.md`, and `tasks.md`. If tasks were not reviewed by the user, stop.
   Set the spec Status to `In progress` if it isn't already.
2. For each task to implement:
   1. **Red** — write the test(s) named in the task, referencing the AC ID. Run them and confirm they fail for the
      right reason.
   2. **Green** — write the minimum code to make them pass. Follow the plan; don't add unrequested features.
   3. **Refactor** — clean up while keeping tests green.
   4. **Check** — run the full test suite, lint, and type check (commands in `CLAUDE.md`). Fix all failures.
   5. Tick the task's checkbox in `tasks.md`.
3. **If reality diverges from the spec or plan** (missing requirement, wrong assumption, better approach), stop and
   explain. Propose the spec/plan edit, and continue only after the user agrees. Record the deviation under Notes in
   `tasks.md` and in the spec's Changelog.
4. Report what was done, the test results, and the next task. Offer to commit (message format in `CLAUDE.md`);
   don't commit without approval.
