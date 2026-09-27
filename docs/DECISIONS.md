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

## 2026-09-26 — Docs in `docs/`, README and CLAUDE.md at root

**Choice:** `PLAN.md`, `DECISIONS.md` and `SAFETY.md` live in `docs/`. `README.md` and `CLAUDE.md` stay at the repo root.
**Alternatives:** All markdown at the root (cluttered next to code and config); all markdown in `docs/` (tried; it broke three things).
**Why:** Each root file has a job that depends on where it sits. `pyproject.toml` declares `readme = "README.md"`, and the build fails without it. GitHub shows the root README as the repo's landing page. Claude Code auto-loads `CLAUDE.md` only from the root. Everything else is reference material, so it goes in `docs/` to keep the root readable.

## 2026-09-26 — Models: Sonnet 5 generates, Opus 5 scans

**Choice:** Target model `anthropic/claude-sonnet-5`; user simulator `anthropic/claude-sonnet-5`; scanner `anthropic/claude-opus-5`.
**Alternatives:** Opus 5 for generation (costlier, and a realistic target doesn't need it); Haiku 4.5 as scanner (cheapest, but saved for the M7 cost-curve variants); the same model for generation and scanning (maximizes leakage risk).
**Why:** Sonnet 5 ($2/$10 per MTok) is a realistic production chat model for the target and follows personas well enough for the simulator. The scanner uses a different, stronger model (Opus 5, $5/$25), because using a different model from the generator is our main leakage mitigation while we stay Anthropic-only. Refusals from the models' bio safety classifiers are a known risk. They will be recorded and counted, not silently retried.

## 2026-09-26 — M1 size: 2 personas × 2 seeds × 4 turns

**Choice:** The walking skeleton uses `grad_student` and `overt_evader`, 2 seeds each, 4 user turns per conversation (4 transcripts).
**Alternatives:** Starting at full size (8 personas × ~8 seeds, 8–12 turns).
**Why:** M1 only proves the pipeline runs end to end; the numbers don't matter yet. One clearly benign persona and one clearly concerning persona give the confusion matrix both classes. Full sizes are decided in M2.

## 2026-09-26 — All three data contracts live in `schema.py`

**Choice:** `Persona`, the transcript-ID helpers and `Assessment` share one module.
**Alternatives:** One module per contract (`personas.py`, `ids.py`, `schema.py`).
**Why:** These are the stable interfaces every stage depends on. One file makes them easy to find, review and defend, and each is only a few lines.

## 2026-09-26 — No `labels.csv` for now; persona YAMLs are the label source

**Choice:** Validation gets the persona from the transcript ID and reads ground truth from `personas/{persona}.yaml`.
**Alternatives:** Generation writes `labels.csv` (the original plan).
**Why:** `inspect eval` doesn't naturally write extra files, and a second copy of the ground truth can drift from the YAML. We can revisit this if M5's blind self-labels need a home.

## 2026-09-26 — User simulator sees the conversation with roles flipped

**Choice:** The simulator is a separate model call. Its system prompt holds the persona, and it sees the target's replies as "user" turns and its own previous lines as "assistant" turns.
**Alternatives:** Pass the whole conversation as one text block and ask the simulator for the next user line.
**Why:** With flipped roles, the simulator is just continuing a chat from its own side, which is what chat models do best. Its prompt never enters `state.messages`, so the hidden objective can't reach the transcript.

## 2026-09-26 — "Seed" means replicate index, not an RNG seed

**Choice:** `seedNN` numbers independent samples of the same persona. Variation comes from ordinary sampling.
**Alternatives:** Seeded, deterministic generation.
**Why:** The Anthropic API has no sampling seed, so re-runs can't be bit-for-bit identical. Reproducibility comes from committing the generated logs, not from regenerating them.

## 2026-09-26 — Test for hidden-objective leakage

**Choice:** A pytest loads each committed log the way the scanner does and fails if any persona's `hidden_objective` text appears.
**Alternatives:** Rely on library defaults. Today Scout's `llm_scanner` loads only messages, not events, and its default template shows no metadata or IDs.
**Why:** Inspect logs the simulator's call, including its persona prompt, in the event history. Only those two Scout defaults keep it away from the scanner, so a library upgrade could change that silently. The test turns a hard rule into something checked on every run.
