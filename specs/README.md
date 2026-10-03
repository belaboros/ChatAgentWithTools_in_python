# Specs

Each feature lives in its own numbered folder:

```
specs/
  _template/            # copied for every new feature
  001-basic-chat-loop/
    spec.md             # WHAT and WHY  (requirements, acceptance criteria) — no implementation details
    plan.md             # HOW           (architecture, modules, data structures, test strategy)
    tasks.md            # STEPS         (ordered, small, independently testable tasks)
```

## Lifecycle

`Draft → Approved → Planned → In progress → Done` (or `Superseded by NNN`)

1. **spec.md** is written by interviewing the user (`/spec`). It describes behavior visible from the outside:
   user stories, acceptance criteria, non-goals, open questions. It must not prescribe implementation.
2. **plan.md** (`/plan`) translates the approved spec into a technical design and maps every acceptance criterion to how it will be tested.
3. **tasks.md** (`/tasks`) breaks the plan into tasks of roughly < 1 hour each, each tied to the ACs it satisfies.
4. **Implementation** (`/implement`) works through tasks test-first and checks them off.
5. **Verification** (`/verify`) confirms every acceptance criterion is met and tested.

## Writing good acceptance criteria

- Give each one a stable ID: `AC-1`, `AC-2`, … (never renumber; strike through removed ones).
- Make them testable and unambiguous. Prefer **Given / When / Then**:
  > **AC-3** — *Given* the model requests a tool that is not registered, *when* the agent processes the response,
  > *then* it returns an error result to the model and the conversation continues.
- Cover error paths and edge cases, not just the happy path.

## Changing a spec

Specs are living documents. If behavior needs to change, edit the spec first (add a line to its Changelog),
get approval, then update plan/tasks/code. Closed features stay in place as documentation of current behavior.
