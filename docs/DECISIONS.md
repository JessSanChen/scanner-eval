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

## 2026-09-27 — A "turn" is one exchange

**Choice:** A turn means one user message plus the target's reply. `turns=4` gives 8 messages, and `turns_completed` counts exchanges.
**Alternatives:** Counting individual messages.
**Why:** The research questions are about what the *user* does across a conversation, and each user move comes with one reply. `PLAN.md`'s "8–12 turns" means exchanges.

## 2026-09-27 — Concerning personas are scripted; benign personas are simulated (B1)

**Choice:** Personas with a `script` in their YAML send fixed, human-written user turns. The others are played by the user-simulator model. Every sample records `user_source: scripted | simulated`.
**What failed first** (logs in `logs/refusal-evidence/`):
1. Sonnet 5 as simulator: its bio safety classifier refused to play `overt_evader` on the first turn, in both seeds (`stop_reason=content_filter`, category `bio`).
2. Refusal fallback: Sonnet 5 rejects the `fallbacks` parameter (400: "does not support the `fallbacks` parameter").
3. Opus 4.8, the suggested fallback model, used directly as simulator: refused on the first turn, category `bio`.
**Alternatives:** Script every persona (B2, the cleanest, but too much writing for the deadline). Search for a model or wording that gets past the classifier (rejected: that is classifier evasion, which is inappropriate, especially in a biosecurity work sample).
**Why:** It is the smallest change that gives M1 a concerning class. The scripts are written by the author, since the assistant's classifier also blocks drafting them.
**Limitation (must be stated in the write-up):** Benign and concerning conversations come from different processes. The scanner could key on "scripted vs. simulated" style rather than intent, which would inflate accuracy and bias the false-positive rate. `user_source` is recorded so results can be split by it. A future fix is to script some benign personas too, which gives a same-process comparison.
**Finding in its own right:** Current Anthropic models won't simulate a user who is behaviorally evading biosafety oversight, even at textbook level. An LLM user simulator can't produce the concerning half of a synthetic eval set on this provider.

## 2026-09-27 — Accept truncated concerning transcripts for M1

**Choice:** Keep the M1 run as is. The scripted `overt_evader` transcripts have 1 exchange each, because the target (Sonnet 5) refused the first scripted turn (category `bio`) and the solver stops at a target refusal.
**Alternatives:** For scripted personas, keep sending the remaining script turns after a target refusal, as a real persistent user would, so the transcript shows the whole trajectory. Deferred to M2; not yet tested whether the API accepts a conversation that continues after an empty refused turn.
**Why:** M1 only needs the pipeline to run end to end. The first user turn already carries the behavioral signal the scanner is judging.
**Limitation:** Concerning transcripts are much shorter than benign ones (2 vs. 8 messages). Length alone could separate the classes, and the fragmentation question (intent spread over many turns) can't be studied on 1-turn transcripts. Both must be fixed in M2 before any headline numbers are reported.

## 2026-09-27 — Scanner refusals are a predicted outcome, not missing data

**Choice:** In validation, a transcript the scanner refused to assess gets `predicted_risk = "refused"`. It stays in the confusion matrix, and refusal rate is reported by true risk level.
**Alternatives:** Drop refused transcripts (this hides the failure and inflates accuracy); retry on other models or rephrase the rubric until the scan succeeds (classifier evasion, rejected as before).
**Why:** In the first M1 scan, Opus 5 refused (category `bio`) to assess both `overt_evader` transcripts, and scored both benign ones correctly. The safety classifier blocks the detection side as well as data generation. A scanner that goes silent on exactly the concerning logs is a deployment-relevant failure mode: a real system would have to route "refused" to human review, so the rate must be measured, not hidden.
**Finding:** On current Anthropic models, the concerning class is blocked at three points: the user simulator, the target, and the scanner. For a biosecurity log scanner built on a single provider, this is probably the headline limitation.

## 2026-09-27 — Validation writes `results/predictions.csv`

**Choice:** `python -m trajscan.validate` writes one row per transcript (ID, persona, seed, variant, true risk, predicted risk) and prints the confusion matrix and refusal rates. By default it uses the most recent scan in `scans/`.
**Why:** Each stage reads files and writes files. The per-transcript CSV is what M4's metrics and bootstrap confidence intervals will build on.
