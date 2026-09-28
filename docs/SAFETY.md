# Safety design

This project generates synthetic conversations about dual-use biology research in order to evaluate a log scanner. **It generates no hazardous biological content, and it needs none.**

## Principle: intent is behavioral, not technical

In real logs, most signals of concerning intent come from how someone behaves, not from technical detail:

- asking who reviews a protocol, or whether a step can skip institutional approval
- asking whether records are kept, or how to avoid them
- asking how to obtain materials without a purchase order or other institutional controls
- splitting requests up so that no single one looks concerning

Personas differ in these conversational moves and in their hidden persona spec, which the scanner never sees. They do not differ in technical depth.

## Rules

1. **Content ceiling.** Every turn stays at the level of an undergraduate textbook. No synthesis routes, enhancement methods, acquisition specifics for regulated agents, or step-by-step protocols for anything hazardous.
2. **Drop, don't escalate.** If a turn would only make sense with hazardous specificity, drop that turn.
3. **Hidden objectives stay hidden.** A persona's objective lives only in the user simulator's own model call (scripted personas have no simulator call). It never appears in the transcript the scanner sees.
4. **Review.** Transcripts are read by hand during development (via `inspect view`) before they are committed.

## Consequence

Because the content is safe by design, we commit the generated logs and scan results. Anyone can then reproduce the analysis without API keys.

## Checks

- **Automated:** `tests/test_leakage.py` loads every committed log exactly as each scanner does and fails if any persona's hidden objective appears (rule 3).
- **Human review:** transcripts were read by hand, and the author wrote every scripted persona turn at a behavioral, textbook level (rules 1–2). A 24-transcript blind labeling pass (`labels/`) was a second read.
- **Not built:** an automated tripwire for the content ceiling (rule 1). Model safety classifiers refused many conversations at generation and scan time; those refusals are recorded but are not a substitute for this check.
