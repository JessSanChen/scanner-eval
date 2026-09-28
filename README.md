# trajscan

A small, reproducible harness for evaluating LLM scanners of conversation logs about dual-use biology. It generates multi-turn conversations from personas with known ground truth, scans them with an LLM judge that returns a structured risk assessment, and scores the scanner against the ground truth.

**Headline results** (64 transcripts, two scanner variants on Claude Opus 5; see [`docs/FINDINGS.md`](docs/FINDINGS.md)):

- **Refusals at every stage, and they depend on the prompt.** The user simulator, the target and the scanner all refused, including on benign-but-alarming personas. The scanner refused 13 of 24 hard-negative transcripts, and a prompt change alone moved one benign persona's refusal rate from 0% to 50%.
- **Concerning recall: no risk-4 transcript was flagged by either scanner.** Each was refused or scored low.
- **Per-turn vs. whole-transcript:** per-turn scanning had higher threat-category macro-F1 (+0.34, 95% CI 0.19–0.46) and caught the ambiguous persona that whole-transcript scanning averaged down. It produced no additional false flags.

## Pipeline

Each stage is one command that reads files and writes files:

```
uv run inspect eval src/trajscan/generate.py --model anthropic/claude-sonnet-5 \
    --model-role user_simulator=anthropic/claude-sonnet-5 -T seeds=8 --log-dir logs/raw
uv run python -m trajscan.perturb                      # logs/raw -> logs/perturbed
uv run scout scan src/trajscan/scanners.py -T logs/perturbed --scans scans \
    --model anthropic/claude-opus-5
uv run python -m trajscan.validate                     # -> results/, figures/
```

Logs, scans and results are committed, so the last step runs without an API key. Generation and scanning need `ANTHROPIC_API_KEY` in `.env` (see `.env.example`).

## Layout

- `personas/`: one YAML per persona (ground truth; never shown to the scanner)
- `src/trajscan/`: `schema.py` (data contracts), `generate.py`, `perturb.py`, `scanners.py` (add a variant: one `@scanner` emitting `Assessment`), `validate.py`, `metrics.py`, `figures.py`
- `tests/`: including a leakage test that loads every committed log as the scanner sees it
- `docs/`: [`PLAN.md`](docs/PLAN.md), [`DECISIONS.md`](docs/DECISIONS.md) (every design choice, with alternatives), [`SAFETY.md`](docs/SAFETY.md), [`FINDINGS.md`](docs/FINDINGS.md)

## Development

```
uv sync
uv run ruff format && uv run ruff check --fix
uv run pytest
```
