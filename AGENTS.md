# AGENTS.md

## Project name

Multi-Agent Fictional Personalities

## Purpose

This repository contains a multi-agent LLM system for simulating fictional characters and evaluating whether generated agent behavior remains recognizable to human raters.

## High-level architecture

The system has five main stages:

1. **Corpus preparation**
   - Collect character-specific text examples.
   - Store raw text in `data/raw/`.
   - Convert raw text into structured corpus documents.

2. **Persona extraction**
   - Use a prompt-based extraction method to create one structured persona profile per character.
   - Store generated profiles in `data/personas/`.

3. **Agent runtime**
   - Instantiate one LLM agent per persona profile.
   - Generate replies using the current conversation history and the agent's persona.

4. **Conversation simulation**
   - Run multi-agent conversations on fixed topics.
   - Save transcripts and structured logs.

5. **Evaluation**
   - Build blind identification trials from generated messages.
   - Collect rater guesses.
   - Analyze accuracy, confidence intervals, and per-character confusion.

## Coding conventions

- Keep reusable code under `src/`.
- Keep executable entry points under `scripts/`.
- Keep prompts under `prompts/`.
- Do not hard-code long prompts inside Python functions.
- Use config files for models, seeds, character sets, and experimental conditions.
- Every run should produce a structured log.
- Errors should fail loudly unless they are explicitly handled and logged.

## Important entities

- `Character`: source fictional character.
- `CorpusDocument`: text evidence associated with one character.
- `PersonaProfile`: structured persona extracted from the corpus.
- `Agent`: runtime instance of a persona profile.
- `ConversationRun`: one complete simulation.
- `Message`: one generated chat message.
- `EvaluationTrial`: one anonymized rater task.
- `RaterResponse`: one rater answer.

## Minimal success criterion

A fresh clone of the repository should eventually support a command like:

```bash
bash scripts/smoke_test.sh
```

That command should run a toy end-to-end pipeline and write logs to a documented location.
