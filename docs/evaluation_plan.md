# Evaluation Plan

## Purpose

This document defines how the project will measure whether persona-seeded LLM agents preserve recognizable fictional-character identity.

The evaluation is designed before the main experiment to avoid changing metrics after seeing results.

## Primary research question

Can human raters identify which fictional character generated a message produced by a persona-seeded LLM agent?

## Primary hypothesis

Persona-seeded agent messages will be attributed to the correct character at above-chance accuracy in a blind multiple-choice task.

## Primary outcome

The primary outcome is **identification accuracy**.

```txt
accuracy = number of correct rater guesses / total number of rater guesses
```

Chance accuracy depends on the number of candidate characters.

For the initial 4-character setup:

```txt
chance accuracy = 1 / 4 = 25%
```

## Experimental unit

The main unit of evaluation is a rater response to one anonymized generated message.

## Conditions

## Condition A — Persona-seeded agent

The agent receives a structured persona profile extracted from the character corpus.

This is the main experimental condition.

## Condition B — Generic agent baseline

The agent receives only the task context and no character-specific persona profile.

Purpose:
- test whether persona profiles improve recognizability compared with generic LLM behavior.

## Condition C — Style-neutralized control

A generated message is rewritten in a more neutral style before being shown to raters.

Purpose:
- test whether raters rely mainly on surface style cues.

## Condition D — Wrong-persona control

The model is instructed using a mismatched or random persona profile.

Purpose:
- test whether raters are detecting true persona alignment or unrelated artifacts.

## Evaluation task

Raters see:

1. one anonymized generated message;
2. a list of candidate characters;
3. an optional confidence scale.

Raters answer:

> Which character most likely produced this message?

They choose exactly one character.

## Candidate characters for the first version

Initial MVB candidate set:

1. Naruto Uzumaki
2. Sasuke Uchiha
3. Sakura Haruno
4. Kakashi Hatake

This set may change if corpus collection becomes difficult.

## Trial construction

Generated conversations are sampled to create evaluation trials.

Rules:

- Do not show the speaker name.
- Do not show the conversation context if it reveals the speaker directly.
- Do not include messages that mention the speaker's own name.
- Prefer messages generated on topics not directly copied from the source corpus.
- Balance the number of trials per character when possible.

## Sample size plan

For the first pilot:

- 4 characters;
- 2–3 messages per character;
- 1–3 raters;
- goal: test whether the pipeline works.

For the main small study:

- 4 characters;
- 5–10 messages per character;
- 5–10 raters if feasible;
- goal: estimate whether accuracy is clearly above 25%.

For an expanded version:

- 6–8 characters;
- more trials per character;
- more raters;
- confidence intervals and per-character breakdowns.

## Metrics

## Primary metric

### Overall identification accuracy

Computed across all trials and raters.

## Secondary metrics

### Per-character accuracy

Accuracy for each character separately.

Purpose:
- identify which personas are easier or harder to recognize.

### Confusion matrix

Rows are true characters and columns are selected characters.

Purpose:
- identify which characters are confused with each other.

### Mean confidence

Average rater confidence for correct and incorrect responses.

Purpose:
- examine whether raters are calibrated.

### Turn-share in generated chats

Proportion of messages produced by each character in the simulated group conversation.

Purpose:
- measure group dominance or passivity.

### Message length

Average number of words or tokens per character.

Purpose:
- detect stylistic differences and possible artifacts.

### Generic voice indicators

Qualitative or programmatic checks for whether generated messages sound too similar across characters.

Purpose:
- detect collapse into a default LLM voice.

## Statistical analysis

## Primary analysis

Compare overall accuracy against chance.

For 4 characters:

```txt
H0: accuracy = 0.25
H1: accuracy > 0.25
```

The analysis will report:

- observed accuracy;
- number of trials;
- number of correct responses;
- chance baseline;
- 95% confidence interval.

## Confidence interval

The project will use a binomial confidence interval for the primary accuracy estimate.

If sample size is small, results will be interpreted cautiously.

## Secondary analysis

Secondary analysis will include:

- per-character accuracy;
- confusion matrix;
- confidence by correctness;
- qualitative examples of success and failure;
- comparison between persona-seeded and generic-agent conditions.

Secondary analyses are exploratory unless explicitly pre-registered before data collection.

## Success criteria

The project will be considered successful if it produces a reproducible pipeline and interpretable results.

A positive result would be:

- accuracy above chance;
- confidence interval mostly above the chance baseline;
- clear examples of recognizable persona behavior.

A negative result would still be valuable if it shows:

- characters are not distinguishable;
- all agents collapse into a generic LLM voice;
- persona prompting produces exaggerated stereotypes;
- raters rely only on superficial style cues.

## Threats to validity

### Rater familiarity

Raters may not know the characters well.

Mitigation:
- include a familiarity question;
- use well-known characters;
- analyze familiar raters separately if possible.

### Prompt leakage

The generated message may reveal the character directly.

Mitigation:
- remove messages that mention character names;
- inspect samples before evaluation;
- use automatic filtering where possible.

### Small sample size

The study may not have enough responses for strong claims.

Mitigation:
- report confidence intervals;
- avoid over-interpreting per-character results;
- frame pilot results as preliminary.

### Corpus bias

Persona profiles may over-represent a few iconic phrases.

Mitigation:
- use multiple examples per character;
- avoid using only catchphrases;
- evaluate on new topics.

### Generic LLM voice

Agents may sound too similar.

Mitigation:
- include a generic-agent baseline;
- examine confusion matrix;
- report failure honestly.

## Ethical considerations

The project uses fictional characters in the first version to reduce privacy and consent concerns.

The report should avoid claiming that the system captures real personality, consciousness, or authentic identity. The project only evaluates recognizability under controlled conditions.

## Pre-registration statement

Before running the main evaluation, the team will record:

- character set;
- number of trials;
- rater recruitment plan;
- primary metric;
- chance baseline;
- planned statistical test;
- planned controls.

Any later changes will be marked as exploratory.
