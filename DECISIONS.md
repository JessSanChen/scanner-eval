# Decisions

Append-only log. Each entry: the choice, alternatives considered, and why. Decisions made during planning, before this log existed, are summarized in `PLAN.md` under "Decisions already made".

---

## 2026-09-26 — Project name: `trajscan`

**Choice:** Call the project and package `trajscan` (trajectory scanner).
**Alternatives:** `scanner-eval` (the repo directory name; accurate, but it describes the harness rather than the idea); a name that echoes the RAND team's tool.
**Why:** The name is generic and points at the main research question: does scanning the whole conversation trajectory catch intent that per-turn scanning misses? It also avoids implying that this is the RAND team's own tool, which it is not.

## 2026-09-26 — Anthropic models only (for now)

**Choice:** Use Anthropic models for the target, the user simulator and the scanner, with a single `ANTHROPIC_API_KEY`.
**Alternatives:** Different providers for the generator and the scanner (the original plan), which reduces generator–scanner leakage.
**Why:** It keeps setup to one key and one billing account. The cost: same-provider models may share stylistic priors, so the leakage mitigation is weaker. We partly compensate by using different models for generation and scanning, and we name the issue as a limitation. Because Inspect switches providers with a single model string, a cross-provider scanner variant stays cheap to add later.

## 2026-09-26 — Flat repo layout

**Choice:** Put `pyproject.toml`, `src/trajscan/`, `personas/`, etc. directly at the repo root, not nested under a further subdirectory.
**Alternatives:** A nested project directory, as the first draft of `PLAN.md` sketched.
**Why:** The repo holds exactly one project, so an extra level would only add path noise.
