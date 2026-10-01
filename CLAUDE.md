# CLAUDE.md

Project: trajscan, an open-source harness for evaluating LLM scanners of conversation logs. The design is in `docs/DESIGN.md` and the decision log in `docs/DECISIONS.md`; read both at the start of each session.

## How I want to work

- **Every line must be explainable and defensible.** Explain the design before writing code, then implement in small, reviewable steps.
- **Propose, then build.** For anything non-trivial, describe the approach and alternatives in a few sentences and wait for my go-ahead.
- **Walking skeleton first.** Don't scaffold modules, abstractions, or config options ahead of need. Get the four stages running end to end on tiny data before expanding any of them.
- **Ask before adding dependencies.**
- **Log decisions.** When we make a design choice, append a dated entry to `docs/DECISIONS.md`: the choice, alternatives considered, and why.
- **Verify library APIs against current docs** (Inspect, Inspect Scout) before writing code that uses them. Don't guess parameter names.

## Hard rules

- The persona's hidden objective must **never** appear in the transcript the scanner sees. User-simulator instructions stay in their own model call.
- **No hazardous biological content.** Every turn stays at undergraduate-textbook level; intent signals are behavioral. If a turn would need hazardous specificity, drop it. See `docs/SAFETY.md`.
- Transcript IDs follow `{persona}__seed{NN}__{variant}` — this is the join key across all stages.
- Every scanner variant emits the same `Assessment` schema.

## Conventions

- uv for environment and dependencies; `uv run` for commands
- `ruff format && ruff check --fix` before committing
- `pytest` must pass
- Type hints throughout
- Each pipeline stage is one command that reads files and writes files