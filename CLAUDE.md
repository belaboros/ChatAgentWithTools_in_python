# ChatAgentWithTools_in_python

A Python chat agent that can call tools. This project uses **specification-driven development (SDD)**:
specs are the source of truth, and code is derived from them.

## Workflow (mandatory)

Every non-trivial change goes through these phases. Each phase ends with a **human approval gate** —
stop and wait for the user to approve before starting the next phase.

| Phase | Command | Output | Gate |
|---|---|---|---|
| 1. Specify | `/spec <idea>` | `specs/NNN-name/spec.md` — *what* and *why* | User approves spec |
| 2. Plan | `/plan NNN` | `specs/NNN-name/plan.md` — *how* | User approves plan |
| 3. Tasks | `/tasks NNN` | `specs/NNN-name/tasks.md` — ordered checklist | User approves tasks |
| 4. Implement | `/implement NNN` | Code + tests, one task at a time | Tests green |
| 5. Verify | `/verify NNN` | Acceptance-criteria report | User accepts |

Rules:
- **No production code without an approved spec.** If asked to code something with no spec, propose writing one first
  (trivial fixes — typos, formatting, dependency bumps — are exempt).
- **The spec wins.** If code and spec disagree, the code is wrong — or the spec must be updated *first*, with user approval.
- **Never silently change scope.** If implementation reveals the spec is wrong or incomplete, stop, explain, and propose a spec edit.
- **Traceability.** Acceptance criteria have IDs (`AC-1`, `AC-2`, …). Every AC is covered by at least one test that
  references its ID in the test name or docstring (e.g. `test_ac3_unknown_tool_returns_error`).
  Exception: browser-only UI behavior has no automated browser tests (by decision); it is covered by a step in the
  spec's manual checklist (`tests/manual/`, referencing the AC ID), plus the strongest automated check possible
  without a browser.
- **Test first.** For each task: write the failing test, confirm it fails, implement, confirm it passes.
- Update the spec's `Status` field as it moves: `Draft → Approved → Planned → In progress → Done`.

See [specs/README.md](specs/README.md) for the spec format and lifecycle.

## Tech stack & commands

- Python 3.14 (latest stable; pinned in `.python-version`, `requires-python = ">=3.14"`), managed with [uv](https://docs.astral.sh/uv/).
  Use modern 3.14 features freely (e.g. PEP 649 deferred annotations, `match`, PEP 695 type parameter syntax).
- Tests: `uv run pytest` (single test: `uv run pytest path/to/test_file.py::test_name`)
- Lint/format: `uv run ruff check --fix . && uv run ruff format .`
- Type check: `uv run pyright`

Before declaring any task done, run tests, lint, and type check, and fix failures.

## Conventions

- Source in `src/`, tests in `tests/` mirroring the source layout.
- Type hints on all public functions.
- Keep secrets (API keys) in environment variables / `.env`; never commit them.
- Commits: one task (or a small group of related tasks) per commit, message references the spec, e.g. `feat(001): add tool registry [T3]`.
