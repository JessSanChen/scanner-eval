# trajscan: Evaluating LLM scanners for intent across multi-turn conversations

trajscan is an open-source harness for evaluating LLM scanners of conversation logs. It generates multi-turn conversations about dual-use biology research from personas with known objectives. Scanner variants then return a structured assessment for each conversation (risk level, threat category, actor profile, evidence cited by message), which is scored against the personas. Refusals and failures are recorded at every stage as outcomes, not dropped.

**Headline results** (64 transcripts; 2 scanner variants × 5 models; full write-up in [`docs/FINDINGS.md`](docs/FINDINGS.md)):

- **Scanner refusal is a property of the model.**
  - Claude Opus 5 refused to assess 27–29 of 64 transcripts, including every transcript from the overt concerning persona and from one benign persona.
  - On the same transcripts, Haiku 4.5 and Gemini 3.8 Flash refused none, and every other model flagged every overt-persona transcript it assessed at risk 4.
- **The cheaper scanners did as well or better.** Gemini 3.8 Flash hit the achievable recall ceiling, flagged no hard negatives, and had the highest category F1, at a seventh to a tenth of Opus 5's cost per transcript.
- **Per-turn vs. whole-transcript scanning depends on the model.** Per-turn improved category F1 for Opus 5 and Haiku 4.5, cost 1.6–2.6× as much, and was about half as unstable under benign padding.
- **"Persona risk" and "observable risk" diverge.** Blind self-labeling traced every disagreement with ground truth to that gap.

## Quick start

Requires [uv](https://docs.astral.sh/uv/). Python 3.12 is installed automatically.

```
git clone https://github.com/JessSanChen/scanner-eval && cd scanner-eval
uv sync
uv run pytest                        # ~60 tests, including the leakage test
uv run python -m trajscan.validate   # recompute all results from committed scans, no API key needed
```

`validate` writes `results/*.csv` and `figures/*.png` from the scans listed in `scans/manifest.yaml`.

### Browsing transcripts and scans

```
uv run inspect view --log-dir logs/raw        # conversations, as generated (Inspect's log viewer)
uv run scout view --scans scans               # scanner results, with explanations and cited messages
```

In `inspect view`, each sample's **Messages** tab is exactly what the scanners see. The event history also shows the user simulator's own model calls, including its persona prompt; scanners never load those.

## Running the pipeline

Each stage is one command that reads files and writes files, so any stage can be re-run alone.

```
personas/*.yaml ──generate──▶ logs/raw ──perturb──▶ logs/perturbed ──scan──▶ scans/ (+ manifest.yaml) ──validate──▶ results/, figures/
```

**Setup for stages 1 and 3:** copy `.env.example` to `.env` and add `ANTHROPIC_API_KEY`, plus `OPENROUTER_API_KEY` for `openrouter/...` models. Inspect and Scout read `.env` automatically.

### 1. Generate conversations (Inspect)

```
uv run inspect eval src/trajscan/generate.py \
    --model anthropic/claude-sonnet-5 \
    --model-role user_simulator=anthropic/claude-sonnet-5 \
    -T seeds=8 --log-dir logs/raw
```

- `--model` is the target (the assistant); `--model-role user_simulator=...` plays the persona. Any Inspect model string works.
- `-T personas=grad_student,journalist` selects personas (default: `grad_student,overt_evader`); `-T seeds=8`; `-T turns=4` (exchanges, for simulated personas; scripted personas use their script length).
- Each sample's metadata records `user_source` (scripted or simulated), `refusal` (`user_simulator`, `target` or none) and `turns_completed`.

### 2. Perturb (label-preserving variants)

```
uv run python -m trajscan.perturb      # logs/raw -> logs/perturbed (base + pad-pre2 + pad-post2)
```

### 3. Scan (Inspect Scout)

```
uv run python -m trajscan.scan                                  # every model in configs/scan.yaml, base transcripts
uv run python -m trajscan.scan --models openrouter/openai/gpt-6-luna
uv run python -m trajscan.scan --models anthropic/claude-opus-5 --where "task_id LIKE '%pad-%'"
```

Runs every scanner in `scanners.SCANNERS` (`whole_transcript`, `per_turn`) for each model and appends each scan to `scans/manifest.yaml`. `--where` is a SQL filter on transcripts; the default is base transcripts only. You can also call Scout directly: `uv run scout scan src/trajscan/scanners.py -T logs/perturbed --model <model>`.

### 4. Validate

```
uv run python -m trajscan.validate                            # all scans in the manifest
uv run python -m trajscan.validate --scan scans/scan_id=...   # specific scans (repeatable)
```

| Output | Contents |
|---|---|
| `results/predictions.csv` | One row per scanner variant × transcript: outcome, category, confidence, cost |
| `results/metrics.csv` | Per variant: coverage, accuracy, kappa, category F1, hard-negative false-positive rate and review burden, concerning recall (strict and fail-safe), with 95% bootstrap intervals and paired per-turn − whole differences |
| `results/refusals.csv` | Refusal rate per persona at each stage (simulator, target, each scanner) |
| `results/flips.csv` | Perturbation flip rates |
| `results/costs.csv` | Scan cost per variant, from recorded token usage and `configs/prices.yaml` |
| `figures/` | Refusal heatmap, cost vs. metrics, one confusion matrix per variant |

### Blind self-labeling

```
uv run python -m trajscan.label export   # labels/transcripts.md + blank labels/labels.csv (codes hide persona IDs)
uv run python -m trajscan.label score    # agreement with ground truth and with each scanner
```

## Extending

| To add | Do this |
|---|---|
| A scanner model | One line in `configs/scan.yaml` (any Inspect model string) and a price row in `configs/prices.yaml` |
| A scanner variant | One `@scanner` in `src/trajscan/scanners.py` that emits `Assessment`, registered in `SCANNERS` |
| A perturbation | One entry in `PERTURBATIONS` in `src/trajscan/perturb.py` |
| A persona | One YAML in `personas/` (add `script:` if simulators refuse to play it) |

Validation, metrics, figures and the leakage test pick up new pieces automatically.

## Stack

- **[Inspect](https://inspect.aisi.org.uk/)** runs generation: a custom solver alternates user-simulator and target models (via Inspect model roles), with concurrency, retries and `.eval` logs.
- **[Inspect Scout](https://meridianlabs-ai.github.io/inspect_scout/)** runs scanning: `llm_scanner` with a Pydantic `Assessment` as a structured (tool-call) answer, and message-level references.
- **Providers:** Anthropic directly, and OpenAI and Google via OpenRouter (the `openai` package). Refusals count as refusals however a provider reports them: a content-filter stop, or an HTTP error such as OpenAI's bio-policy 403.
- **Analysis:** pandas and numpy (metrics, persona-stratified bootstrap, quadratic weighted kappa), matplotlib (figures).
- **Engineering:** uv, ruff, pytest and GitHub Actions CI. Data contracts (persona YAML, transcript IDs, `Assessment`) live in `src/trajscan/schema.py`.

## Costs

Measured from recorded token usage at the prices in `configs/prices.yaml` (retrieved 2026-09-28):

| Item | Cost |
|---|---|
| Generating 64 transcripts (Sonnet 5 as target and simulator) | $3.42 (≈ $0.05 each) |
| Scanning 64 base transcripts, per variant | $0.03 (GPT-6 Luna, whole) to $9.82 (Opus 5, per-turn) |
| Scanning base transcripts, all 10 variants | $20.00 |
| Scanning 124 padded transcripts, Opus 5, both scanners | $48.04 |

Per transcript, scanning ranges from $0.0005 (GPT-6 Luna, whole) to $0.16 (Opus 5, per-turn); see `results/costs.csv`. Reproducing the results from committed scans costs nothing. A fresh generation plus a base scan with one mid-priced model costs about $5.

## Layout

- `personas/`: one YAML per persona (ground truth; never shown to scanners)
- `src/trajscan/`: `schema.py` (data contracts), `generate.py`, `perturb.py`, `scanners.py`, `scan.py`, `validate.py`, `metrics.py`, `figures.py`, `label.py`
- `configs/`: scanner models (`scan.yaml`) and prices (`prices.yaml`)
- `logs/`, `scans/`, `results/`, `figures/`, `labels/`: committed artifacts (`logs/archive/` and `logs/refusal-evidence/` hold earlier runs and refusal probes)
- `tests/`: unit tests, plus a leakage test that loads every committed log as each scanner sees it
- `docs/`: [`DESIGN.md`](docs/DESIGN.md) (architecture, contracts, extension, scaling), [`FINDINGS.md`](docs/FINDINGS.md), [`DECISIONS.md`](docs/DECISIONS.md) (every design choice, with alternatives), [`SAFETY.md`](docs/SAFETY.md)

## Safety

Every turn stays at undergraduate-textbook level; intent is expressed through behavior, not technical content. See [`docs/SAFETY.md`](docs/SAFETY.md).

## Development

```
uv run ruff format && uv run ruff check --fix
uv run pytest
```
