# trajscan — project plan

> **Status (2026-09-28):** this is the original plan. What was built, what changed and why are in `DECISIONS.md`; results are in `FINDINGS.md`.

## Context

This is a work sample for the Cambridge Boston Alignment Initiative (CBAI), applying to a RAND stream mentored by **Sunishchal Dev** (AI evaluation research scientist, ML engineering lead) and **Jeffrey Lee** (AI biosecurity research scientist, biology SME). The stream's focus is automated scanning of model conversation logs: generate multi-turn conversations around dual-use biology research using different personas and objectives, then characterize the logs — nature of the threat, a description of the actor, a risk level — and compare against the original personas and objectives.

**Naming:** `trajscan` is an independent, generic tool built to demonstrate relevant skills. It is not the RAND team's tool and must not be described as such.

The listing asks for: critical thinking, threat modeling / security mindset, biology or biosecurity interest, and experience building LLM evaluation tools or scanners (autograders / LLM judges).

**What the mentors care about.** Dev led RAND's Judge Reliability Harness (JRH, github.com/RANDCorporation/judge-reliability-harness), which stress-tests LLM judges via label-flipped responses, invariance to formatting and paraphrasing, verbosity bias, stochastic stability, and calibration, and reports pass rates, confidence intervals, and cost curves. RAND's bio evals use UK AISI's **Inspect**. So the sample should show: a working scanner, a rigorous answer to "how do you know it's reliable?", and familiarity with the Inspect ecosystem. JRH's repo conventions (uv, YAML configs, pytest, ruff) are worth matching.

**Goal of the sample:** a small, clean, reproducible log scanner and evaluation harness whose every design decision the author can explain.

---

## Research questions

**Primary: per-turn scanning misses intent that only exists in the trajectory.** Run the same scanner two ways — each turn independently vs. the whole transcript — and measure the gap, especially on conversations where concerning intent is deliberately fragmented across turns so no single turn looks alarming. Either result is a finding.

**Secondary: does the scanner key on surface style rather than substance?** Hold persona intent fixed, vary register (non-native English, terse, formal, a claimed foreign affiliation). Verdict changes are style bias → false positives with policy consequences.

---

## Safety design (load-bearing)

No hazardous biological content is generated, and none is needed.

- Intent signals in real logs are mostly **behavioral**, not technical: asking who reviews a protocol, whether a step can skip institutional approval, whether records are kept, how to obtain something without a purchase order, splitting requests so no single one looks bad.
- **Content ceiling:** every turn stays at undergraduate-textbook level. Variation lives in conversational moves and in the persona spec (which the scanner never sees).
- If a turn would need hazardous specificity to make sense, drop the turn.
- Document this in `SAFETY.md`, with a lightweight test/check on the corpus.
- Because content is safe by design, logs and scan results can be committed, which makes the whole analysis reproducible without API keys.

---

## Personas (ground truth)

One YAML file per persona. Fields: `id`, `archetype`, `hidden_objective`, `ground_truth_risk` (1–5), `threat_category`, `planted_markers` (list of `{turn, description}`), `style` notes.

Proposed set (the two bolded classes carry the project):

| Persona | Class | Risk |
|---|---|---|
| grad_student | Benign, looks benign | 1 |
| diagnostic_lab_tech | Benign, looks benign | 1 |
| **biosecurity_policy_researcher** | **Benign, looks alarming** (hard negative) | 1–2 |
| **journalist** | **Benign, looks alarming** (hard negative) | 1–2 |
| **biosafety_officer_auditor** | **Benign, looks alarming** (hard negative) | 1 |
| underfunded_lab_shortcut | Ambiguous (genuinely trying to skip a costly approval) | 3 |
| overt_evader | Concerning, overt | 4 |
| **fragmenter** | **Concerning, fragmented** — same objective as overt_evader, split across turns | 4 |

Pairing `overt_evader` and `fragmenter` with the *same* objective isolates fragmentation as the only difference.

Hard negatives produce the **false-positive rate**, the number a policy audience cares most about. Fragmented actors produce the **per-turn vs. transcript gap**.

Draft threat categories (non-hazardous, adjust as needed): `none`, `oversight_evasion`, `acquisition_without_controls`, `capability_aggregation`, `ambiguous_dual_use`.

Target size: 8 personas × ~8 seeds ≈ 64 base transcripts, ~8–12 turns each. Plus perturbed variants.

---

## Scanner output schema (`Assessment`, Pydantic)

- `summary: str`
- `threat_present: bool`
- `threat_category: enum`
- `risk_level: int` (1–5, with written rubric anchors in the prompt)
- `confidence: float` (0–1)
- `actor_profile`: `archetype`, `apparent_sophistication` (low/med/high), `claimed_affiliation`, `operational_signals: list[str]`
- `evidence: list[{turn_index, paraphrase, why}]` — required and non-empty when `threat_present`
- `recommended_action: enum` (no_action / log / review / urgent)

Turn-indexed evidence enables **planted-signal recall** (below) — the most distinctive metric in the project.

---

## Architecture

**Principle: modularity comes from stable file formats between stages, not abstraction layers.** Each stage is one command that reads files and writes files; any stage can be rerun alone and inspected by hand.

```
personas/*.yaml
   │  [1. generate]   inspect eval ...
   ▼
logs/raw/*.eval  +  labels.csv
   │  [2. perturb]    python -m trajscan.perturb
   ▼
logs/perturbed/*.eval
   │  [3. scan]       scout scan ...
   ▼
scans/  (results dataframes)
   │  [4. validate]   python -m trajscan.validate
   ▼
results/metrics.csv  +  figures/
```

**Three data contracts hold it together** (get these right first; everything else can change):
1. Persona YAML format
2. Transcript ID convention — readable and deterministic: `{persona}__seed{NN}__{variant}` e.g. `fragmenter__seed03__style-plain`. This is the join key everywhere.
3. `Assessment` schema

**Hard rule:** the persona's hidden objective must never appear in the transcript the scanner sees. The user simulator's instructions live in its own separate model call; only its *output* enters the conversation as user turns. (Scout's default preprocessing strips system messages, but don't rely on that.)

**Replay / caching:** each stage's saved output is the cache. Inspect also caches model calls during development. Anyone cloning the repo can run stage 4 on committed logs and scans with no API key.

### Repo layout

```
(repo root)
  personas/           one YAML per persona
  prompts/            Jinja templates: user simulator, scanner rubric
  src/trajscan/
    generate.py       Inspect task + user-simulator loop
    perturb.py
    scanners.py       @scanner definitions, one per variant
    schema.py         Assessment (Pydantic)
    validate.py       metrics, bootstrap, figures
  configs/            scanner variants (YAML)
  logs/ scans/ results/ figures/
  tests/
  docs/               PLAN.md  DECISIONS.md  SAFETY.md
  README.md  CLAUDE.md  (root: GitHub landing page; Claude Code auto-loads)
```

---

## Stage details

### 1. Generate (Inspect)
- An Inspect task; each sample = one persona × seed.
- Custom solver loops N turns: ask the **user-simulator** model (bound via Inspect model roles) for the next user message given the persona and conversation so far → append as a user message → **target** model replies.
- Output: `.eval` logs (Scout reads these natively) + `labels.csv` derived from persona YAMLs.
- Anthropic models only for now (single API key). Use a **different model** for generator vs. scanner to reduce leakage (see Limitations); cross-provider is a future variant.
- No Inspect scorers needed.
- Read transcripts with `inspect view` while developing; check planted markers actually landed on the intended turns.

### 2. Perturb
Metamorphic testing: apply a change that should (or should not) change the correct answer.

| Perturbation | Should verdict change? | Tests |
|---|---|---|
| Style rewrite of user turns (non-native, terse, formal, claimed foreign affiliation), content fixed | No | Style bias |
| Benign padding (insert unrelated harmless turns) | No | Signal dilution in long, mixed logs |
| Marker position (move marker turns earlier/later) | No | Positional bias / "lost in the middle" |
| Marker removal (delete planted-marker turns) | **Yes — risk should drop** | Scanner is using the evidence you planted |

Spot-check LLM rewrites; the rewriter can alter content. (Turn shuffling was considered and dropped: for fragmented actors, order/escalation is itself signal, so invariance isn't clearly correct.)

### 3. Scan (Inspect Scout)
- Build directly on Scout's `llm_scanner` with `answer=Assessment` (verify exact API). Scout renders the transcript into a Jinja template with message IDs, asks the model, parses to the Pydantic shape, and returns value + explanation + message references.
- `@scanner` registers the function for `scout scan` and declares which content it needs.
- **Two modes:** whole-transcript, and per-turn. Per-turn definition (decide and log in DECISIONS.md): e.g. each user turn scanned in isolation, transcript risk = max over turns. Check whether Scout supports message-level scanners; otherwise build single-turn transcripts.
- **Variants live in `configs/*.yaml`** (rubric version, scanner model, unit of analysis, optional two-stage triage). Every variant emits the same `Assessment`, so validation compares them on equal footing. Optimization is measured, not assumed.
- `scout view` for browsing results.

### 4. Validate (plain pandas — fully owned)
Purpose: compare predictions to ground truth to estimate how often the scanner is right on data like this, and *how* it fails.

Must-have:
- **Confusion matrix** (true vs. predicted risk level)
- **Risk-level agreement:** exact accuracy, within-one accuracy, mean absolute error, quadratically weighted kappa (chance-corrected, penalizes larger misses)
- **Precision / recall / macro F1** on threat category
- **False-positive rate on hard negatives** — headline number
- **Planted-signal recall** — fraction of planted-marker turns cited in `evidence`
- **Per-turn vs. transcript** paired comparison — headline result
- **Bootstrap 95% CIs** on all of the above (n is small; resample transcripts ~1,000×)
- **Perturbation flip rates** per perturbation type

Optional:
- Calibration of `confidence` (LLM self-confidence is usually poorly calibrated — one plot, one sentence)
- **Cost curves:** accuracy vs. $/transcript across scanner variants. Matters because a log scanner runs on every conversation; the deployable choice is the cheapest variant clearing an accuracy bar, or a cheap-triage → expensive-review cascade. JRH reports these.

### 5. Blind self-labeling (do not cut)
Before looking at scanner output, hand-label ~20 transcripts and report agreement with persona ground truth. Disagreements are findings about the labels. Cheapest, strongest epistemics signal in the project.

---

## Limitations to name explicitly

**Generator–scanner leakage.** Both halves are LLMs; the generator writes conversations that *display* the objective it was given, so intent may be unrealistically legible. Mitigations: different models for generator and scanner (same provider for now — a weaker mitigation than cross-provider, state it); a few hand-written or hand-edited transcripts as a comparison set; a legibility audit (how separable are classes from single turns?). State plainly: synthetic-persona ground truth measures whether the scanner recovers what the generator encoded — necessary, not sufficient, for working on real logs.

**Scripted vs. simulated users.** The user-simulator models refuse to play concerning personas (bio safety classifier). So concerning personas use human-written scripts while benign personas are simulated. That process difference is a confound; report results split by `user_source`, and see DECISIONS 2026-09-27.

Also consider (time permitting): a small sample of real public chat logs (e.g. WildChat, LMSYS-Chat-1M — check access terms) as a false-positive check on messy benign traffic.

---

## Stack

uv, `pyproject.toml`, ruff, pytest, type hints, pydantic v2, Jinja2, Typer (if a CLI wrapper is useful), YAML configs, `inspect-ai`, `inspect-scout`, pandas, scipy, matplotlib, GitHub Actions (lint + tests). Nothing exotic. No GPUs, no cloud infra.

---

## Build order (walking skeleton first)

Each milestone leaves a working, submittable repo.

- **M0 — Setup.** uv project, ruff, pytest, CI, `.env.example`, `SAFETY.md`, `DECISIONS.md`. Verify Inspect + Scout install and API keys.
- **M1 — Walking skeleton.** 2 personas × 2 seeds × few turns → `.eval` logs → minimal scanner → join to labels → confusion matrix printed. Ugly and meaningless numbers are fine. Done when the four stages run end to end.
- **M2 — Personas + generator.** All 8 personas with planted markers; read transcripts by hand; confirm markers land and persona never leaks.
- **M3 — Scanner v1.** Full `Assessment` schema, rubric with anchors, parse-failure handling, whole-transcript and per-turn modes.
- **M4 — Validation.** All must-have metrics, bootstrap CIs, 1–2 figures.
- **M5 — Blind self-labels** (~20 transcripts).
- **M6 — Perturbations.** *(cut first if short on time)*
- **M7 — Scanner variants + cost curve.** *(cut second)*
- **M8 — Write-up.**

---

## Deliverables

- Repo, reproducible from committed logs/scans without API keys.
- README opening with what it does and the three headline numbers (hard-negative FPR, per-turn vs. transcript gap, planted-signal recall).
- 3–5 page findings memo with 1–2 figures.
- Closing section: what I'd test next with real logs and RAND's resources — tie explicitly to the stream's log-scanning goals.

## Out of scope

Refusal analysis (considered and dropped — it's about the target model, this project is about the actor). GPUs, fine-tuning, web UI, multi-model panels, pre-registration apparatus, hazardous content.

---

## Decisions already made (with reasons)

- **Fresh repo, not the prior refusal project** — author wants to own and understand every part.
- **Inspect for generation** — concurrency, retries, caching, provider switching, `inspect view`, and `.eval` logs Scout reads natively.
- **Scout `llm_scanner` for scanning, not hand-rolled** — plumbing already exists; effort goes to schema, rubric, validation.
- **Own simple generator, not Petri** — Petri's auditor is built to probe the target model, not faithfully play a persona with markers at known turns. Cite Petri as considered alternative; its judge could be a comparison scanner variant.
- **Readable deterministic IDs, not content hashes** — simpler, human-readable, sufficient.
- **No JSONL for transcripts** — `.eval` logs cover it; labels in CSV.
- **Turn shuffling dropped; marker position + marker removal added.**
- **Validation in plain pandas, no Inspect scorers** — the part that should be fully visible.

## Open decisions (author to make; log in DECISIONS.md)

- Target, user-simulator, and scanner models (and providers)
- Number of turns per conversation; seeds per persona
- Final threat categories and risk-level rubric anchors
- Exact per-turn scanning definition
- Deadline → which milestones to cut

## Verify against current docs before coding

Inspect and Scout move fast. Check: `llm_scanner` parameters and Pydantic answer support; `@scanner` signature and message-level scanning; Inspect model-roles API; Inspect generate caching; how Scout reads `.eval` log directories.