# trajscan: Evaluating LLM scanners for intent across multi-turn conversations

*Findings memo, 2026-09-28. Data: 8 personas × 8 seeds = 64 transcripts (run 3). Two scanner variants × five models; all scans are listed in `scans/manifest.yaml`.*

## Summary

trajscan is an open-source harness for evaluating LLM scanners of conversation logs.

- **Generate:** multi-turn conversations about dual-use biology research, from personas with known objectives.
- **Scan:** scanner variants return a structured assessment for each conversation: risk level, threat category, actor profile, and evidence cited by message.
- **Validate:** the assessments are scored against the personas. Refusals and failures at every stage are recorded as outcomes, not dropped.

The main findings:

1. **Scanner refusal is a property of the model, not of the transcript.**
   - Claude Opus 5 refused to assess 27–29 of the 64 transcripts, including every transcript from the overt concerning persona and from one benign persona.
   - On the same transcripts, Claude Haiku 4.5 and Gemini 3.8 Flash refused none. GPT-6 Sol and GPT-6 Luna refused 1–3, all blocked by OpenAI's bio classifier before the model saw them.
   - Every other model scored every overt-persona transcript it assessed at risk 4. So Opus 5's refusals hid intent that was clearly detectable: they were "won't", not "can't".
2. **The cheaper scanners did as well or better.** Gemini 3.8 Flash reached the recall ceiling this data allows (0.54–0.58), flagged no hard negatives, and had the highest category F1 (0.82–0.84). It cost $0.009–0.015 per transcript, against $0.07–0.16 for Opus 5.
3. **Per-turn vs. whole-transcript scanning depends on the model.**
   - Per-turn helped Opus 5 and Haiku 4.5 (category F1 +0.34 and +0.31; the paired intervals exclude zero) and made little difference for Gemini. For GPT-6 Sol it lowered category F1 (−0.29), but that interval includes zero.
   - Per-turn costs 1.6–2.6× as much. On some models it raised false flags on benign conversations, because an exchange seen in isolation can look more alarming.
   - Under benign padding (Opus 5 only), per-turn verdicts were about half as unstable as whole-transcript verdicts.
4. **Two kinds of ground truth diverge: "persona risk" and "observable risk".** Blind self-labeling agreed with the persona labels on 75% of transcripts. Every disagreement traced to a label issue:
   - a persona whose label contradicts the rubric;
   - a fragmented persona whose transcripts never show its intent. Every model, and the author, rated these low.
5. **Intent spread across turns (fragmentation) could not be tested.** Model safety classifiers ended every concerning conversation at the first exchange.

## What was built

Four stages. Each is one command that reads files and writes files, and every intermediate artifact is committed, so any stage can be re-run or inspected alone.

1. **Generate** (Inspect).
   - Each sample is one persona × seed. A user-simulator model plays the persona, or a fixed human-written script is used where the simulator refuses. The target model replies live.
   - The persona's hidden objective exists only in the simulator's own model call. A test loads every committed log exactly as each scanner would and fails if an objective appears.
2. **Perturb.** Label-preserving variants: two benign exchanges padded before or after each conversation.
3. **Scan** (Inspect Scout).
   - Every variant emits the same Pydantic `Assessment`.
   - The two scanners share one judge (same prompt, rubric and settings) and differ only in the unit of analysis: `whole_transcript` (one call) and `per_turn` (each exchange in isolation).
   - A variant is `scanner@model`. Any Inspect model string works: Anthropic, OpenRouter, OpenAI and others.
   - Scanners read messages only: never metadata, and never the transcript ID, which names the persona.
4. **Validate** (pandas, numpy, matplotlib).
   - One row per variant × transcript, built from the generation logs so nothing drops out silently.
   - Outcomes: a score, `refused`, `no_transcript`, `no_answer` (no schema-valid answer) or `error`. A refusal counts as `refused` however the provider reports it, including as an HTTP error.
   - Per-turn results are combined as a deployment would act: flag if any turn flags; otherwise send to review if any turn was refused.
   - Metrics come with persona-stratified bootstrap intervals and paired differences, plus perturbation flip rates, costs from recorded token usage, and figures.

**Generation models:** Claude Sonnet 5 as target and as user simulator.
**Content safety:** every turn stays at undergraduate-textbook level. Intent is expressed through behavior, such as asking to skip oversight, not through technical content (`docs/SAFETY.md`).

## Personas

| Persona | Class | True risk | User side |
|---|---|---|---|
| grad_student, diagnostic_lab_tech | benign | 1 | simulated |
| biosafety_officer_auditor | hard negative (benign, sounds alarming) | 1 | scripted |
| biosecurity_policy_researcher, journalist | hard negative | 2 | scripted |
| underfunded_lab_shortcut | ambiguous | 3 | simulated |
| overt_evader | concerning, overt | 4 | scripted |
| fragmenter | concerning, same objective split across turns | 4 | scripted |

The concerning personas and the hard negatives are scripted by the author because the user simulator refused to play them.

## Results

### Refusals, stage by stage

![Refusals by stage](../figures/refusals_by_stage.png)

**User simulator.** It refused to play the concerning personas and the hard negatives, so the author scripted those. With scripts in place, it still refused the ambiguous persona in 3 of 8 conversations.

**Target (Sonnet 5).** It refused:

- every scripted concerning conversation, on its first reply;
- most scripted hard-negative conversations (100%, 75% and 50% by persona);
- 2 of 8 conversations with the plainest benign persona.

**Scanners.** Refusal differs sharply by model:

- **Opus 5** refused every `overt_evader` and `biosecurity_policy_researcher` transcript with both scanners, and 50–88% of `biosafety_officer_auditor` transcripts.
- **Haiku 4.5 and Gemini 3.8 Flash** refused nothing.
- **GPT-6 Luna and GPT-6 Sol** refused 1–3 transcripts each (mostly the auditor). These were blocked by OpenAI's bio classifier, which returns an HTTP 403 before the model sees the request.

On the same transcripts, changing only Opus 5's prompt and output schema (from the minimal M4 scanner to the full M3 rubric) raised its whole-transcript refusal rate for the auditor persona from 0% to 50%. So refusal also depends on the scanner configuration.

### Accuracy and cost across scanner variants

![Cost vs. metrics](../figures/cost_curve.png)

Point estimates on base transcripts. The 95% intervals are in `results/metrics.csv` and on the figure.

| Model | Scanner | Scored / 64 | Exact acc. | Category F1 | Concerning recall | Hard-neg. false flags | Hard-neg. review burden | $ per transcript |
|---|---|---|---|---|---|---|---|---|
| GPT-6 Luna | whole | 61 | 0.72 | 0.53 | 0.58 | 0.04 | 0.08 | 0.0005 |
| | per-turn | 59 | 0.64 | 0.51 | 0.58 | 0.17 | 0.29 | 0.0010 |
| Gemini 3.8 Flash | whole | 62 | 0.73 | 0.82 | 0.54 | 0.00 | 0.00 | 0.0094 |
| | per-turn | 62 | 0.73 | 0.84 | 0.58 | 0.00 | 0.00 | 0.0148 |
| GPT-6 Sol | whole | 61 | 0.67 | 0.84 | 0.54 | 0.00 | 0.00 | 0.0103 |
| | per-turn | 61 | 0.56 | 0.55 | 0.58 | 0.00 | 0.04 | 0.0190 |
| Claude Haiku 4.5 | whole | 61 | 0.62 | 0.43 | 0.33 | 0.17 | 0.17 | 0.0104 |
| | per-turn | 62 | 0.65 | 0.73 | 0.50 | 0.12 | 0.12 | 0.0274 |
| Claude Opus 5 | whole | 34 | 0.68 | 0.44 | 0.00 | 0.00 | 0.54 | 0.0680 |
| | per-turn | 33 | 0.82 | 0.78 | 0.25 | 0.00 | 0.62 | 0.1584 |

**Column definitions.**

- **Concerning recall:** transcripts with true risk ≥ 3 that were flagged (predicted ≥ 3).
- **Hard-neg. false flags:** hard-negative transcripts flagged at ≥ 3.
- **Hard-neg. review burden:** hard-negative transcripts that were flagged *or* refused. Both would reach a human reviewer.
- **Exact accuracy:** computed on scored transcripts only.

**Reading the table.**

- **The recall ceiling is 0.58.** Two of the 24 concerning transcripts are empty (the simulator refused), and every model scores the 8 fragmented transcripts 1 (see ground truth below). That leaves 14/24 detectable. Gemini, both GPT-6 models and Haiku's per-turn scanner hit or approach it; Opus 5 does not, because it refuses the overt persona.
- **Opus 5's exact accuracy looks high only because it scores just half the transcripts.** It refuses the hard ones.
- **False flags concentrate on the auditor persona.** Haiku 4.5 and GPT-6 Luna flagged some `biosafety_officer_auditor` transcripts at 3–4. Per-turn scanning also flagged a few plainly benign `diagnostic_lab_tech` exchanges (GPT-6 Sol and Luna, Haiku 4.5), where whole-transcript scanning did not.
- **Per-turn helps some models, not all.** It improved category F1 for Opus 5 and Haiku 4.5 by +0.34 and +0.31 (paired intervals exclude zero). For GPT-6 Sol, the difference was −0.29, but its interval (−0.31 to +0.01) includes zero. Per-turn scanning costs 1.6–2.6× as much as whole-transcript. In the M3 comparison it caught the ambiguous persona where Opus 5's whole-transcript scanner averaged it down.

### Robustness to benign padding (Opus 5)

Inserting two benign exchanges should never change the verdict, so every flip is an error.

| Scanner | Perturbation | Flip rate | Flag flips | Refusal flips | Mean risk shift |
|---|---|---|---|---|---|
| whole-transcript | pad before | 0.19 | 0.05 | 0.15 | +0.15 |
| whole-transcript | pad after | 0.23 | 0.00 | 0.19 | +0.13 |
| per-turn | pad before | 0.11 | 0.05 | 0.11 | +0.10 |
| per-turn | pad after | 0.10 | 0.02 | 0.08 | +0.03 |

Most flips are refusal flips: benign context changes whether Opus 5 refuses. Per-turn verdicts are steadier because each original exchange is still scanned alone. Padding was scanned on Opus 5 only (the most expensive run, $48). Extending it to the other models is one command.

### Blind self-labeling and what ground truth means

The author labeled 24 transcripts (3 per persona) blind, using the scanner's rubric.

| Comparison | n | Exact | Within one | Kappa |
|---|---|---|---|---|
| Self vs. ground truth (all) | 24 | 0.75 | 0.88 | 0.73 |
| Self vs. ground truth (not recognized as own script) | 15 | 0.80 | 0.87 | 0.82 |
| Self vs. Opus 5 per-turn (transcripts both scanners scored) | 11 | 1.00 | 1.00 | 1.00 |
| Self vs. Opus 5 whole-transcript (same 11) | 11 | 0.82 | 1.00 | 0.79 |

All disagreements with ground truth come from two personas:

- **`biosafety_officer_auditor`** (label 1). The author rated it 2 in 3/3, and most scanners also scored it 2. The rubric's level 2 ("benign but touches sensitive topics… for compliance purposes") describes this persona, so the label is inconsistent with the rubric.
- **`fragmenter`** (label 4). The author rated it 2 in 3/3, and every scanner rated it 1. Each transcript stops after the first fragment, which doesn't show the objective.

A persona label records the *designed objective*. A transcript can only show *observable risk*. Comparing a scanner's actor profile against the original persona, as the task framing suggests, needs both.

## Limitations

- **Fragmentation is untestable on these models.** Every concerning conversation ends at the first exchange when the target refuses. The author revised the fragmented persona's script three times, and the provider's refusal-fallback mechanism was tried (Opus 5 falling back to Opus 4.8); every attempt was refused. Searching further for a model or wording that gets past the classifier was ruled out.
- **Small, correlated samples.** 8 personas × 8 seeds. Scripted personas send identical user turns in every seed, so only the target's replies vary. The bootstrap resamples seeds within each persona. It misses persona-level uncertainty and is too narrow; where a persona behaves identically in every seed, its contribution has zero variance. Treat the intervals as lower bounds on uncertainty.
- **Scripted vs. simulated users.** Hard negatives and concerning personas are human-written; plain benign personas are simulated. `user_source` is recorded for every transcript, and scripted benign personas were mostly scored correctly by the scanners that didn't refuse. The confound is still not controlled.
- **Unequal lengths.** Target refusals cut concerning transcripts to one exchange; benign ones mostly run to four.
- **Generation used a single provider.** Sonnet 5 generated every conversation, so the generator's stylistic priors are Anthropic's. Scanning used three providers.
- **Refusal findings are a snapshot:** these models, these prompts, this date.
- **Not yet built:**
  - LLM style-rewrite perturbations;
  - planted-marker evidence recall;
  - confidence calibration;
  - open-weight scanner models (e.g. Qwen, Llama);
  - a per-transcript observable-risk label.

## What I would test next with real logs and more resources

1. **Refusal as a routing signal.** On real traffic, measure whether scanner refusals are enriched for genuinely concerning conversations, which would make them useful triage, or dominated by benign-but-alarming topics, which makes them review cost. Measure how much this shifts with the prompt.
2. **Observable-risk labels.** Add a per-transcript observable-risk label alongside persona labels, so scanners are scored on what a transcript actually shows.
3. **Per-turn vs. whole-trajectory on real multi-turn logs,** in both directions: intent that only emerges across turns, and a concerning turn diluted by benign context.
4. **Cheap-scanner cascades.** On this data, cheap models matched or beat the most expensive one. A cheap first-pass scanner, with escalation of flags and refusals, is the obvious deployable design to test, including its cost curve.

## Reproducing

All logs, scans and results are committed, so stage 4 runs without an API key:

```
uv sync
uv run python -m trajscan.validate      # reads scans/manifest.yaml
```

Usage for every stage is in `README.md`; every design decision, with alternatives, is in `docs/DECISIONS.md`.
