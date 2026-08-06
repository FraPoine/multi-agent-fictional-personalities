# AGENTS.md

## Project name

Multi-Agent Fictional Personalities

## Purpose

This repository contains a multi-agent LLM system with two connected goals:
evaluate whether fictional-detective agents are recognizable in blind
attribution, and let those agents participate in a user-moderated game of
*Sherlock Holmes: Consulting Detective*. Recognizability remains the primary
quantitative experiment. The investigation is a second system capability and
an environment for qualitative or exploratory observations, not a replacement
scientific hypothesis.

This is an individual Track B project with system-building and behavioral-
evaluation components. It measures observable recognizability under controlled
conditions; it does not claim that an LLM authentically is, understands, or
reproduces a fictional character's identity. Development is offline-first:
complete the deterministic technical foundation, integrate a real provider
later, and run experiments and investigation sessions afterward.

## Scope and schedule

- Currently supported runtime characters: Sherlock Holmes and Hercule Poirot.
- Final evaluation target: four characters, with characters three and four not
  yet finalized or implemented. L and Professor Layton were earlier candidates.
- Future participant configuration must support two or more agents; Sprint 5
  does not add a character.
- Basic working-version target: August 7, 2026.
- Final course deadline: September 2026

## Current offline implementation

Sprint 5 is complete. The repository provides both the existing conversation
CLI and a local FastAPI/Jinja web interface for deterministic mock
conversations between Sherlock Holmes and Hercule Poirot. Both delivery layers
reuse framework-independent application and runtime logic; the web path also
reuses the existing simulation and atomic conversation-persistence layers.

Completed runs persist `run.json`, `messages.jsonl`, and `transcript.md`. The
web interface provides bounded server-side validation, readable errors,
loading feedback, an ordered transcript, and visible run and artifact paths.
The verified Sprint 4 provider is `mock`, requires no API key or network
access, and does not establish real LLM persona quality or recognizability.
OpenAI-backed conversation execution was not part of Sprint 4.

The repository also contains a technical, two-character, mock-only blind-
evaluation pilot. It verifies tooling rather than persona recognizability and
does not provide scientifically interpretable results. The first stateless
investigation operations create active sessions and reveal clues with
deterministic IDs, but there is no dynamic conversation manager, complete
investigation workflow or persistence, third or fourth runtime character,
real investigation game, or final human/LLM-judge study.

## Sprint 5 foundation

Sprint 5 remains fully offline and requires no provider account, API key,
network access, real token/cost data, genuine rater response, or real game.
It generalized application/configuration boundaries for configurable
participants, isolated speaker choice behind `SpeakerSelector` with default
deterministic `RoundRobinSelector` behavior, and introduced structured
successful generation metadata with runtime/message propagation. It also added
validated investigation-domain entities and immutable partial session states,
and the complete offline regression passed.

The practical conversation-engine boundary may remain `simulate_chat()`; no
concrete `ConversationEngine` class is currently implemented or mandated.
A future `ConversationManager` may select speakers dynamically, but it is
outside Sprint 5. A selector owns only next-speaker choice: it must not own
generation, prompts, history, investigation reasoning, or persistence.

## High-level architecture

The system has six main stages:

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

6. **Investigation (models and initial operations implemented; workflow planned)**
   - Let the project user act as game master, manually provide the case
     introduction, and reveal clues progressively.
   - Keep unrevealed information unavailable to agents.
   - Create active sessions and reveal clues through the implemented stateless
     operations; analysis, decision, and final-theory orchestration remains
     planned Sprint 6 work.

## Coding conventions

- Keep reusable code under `src/`.
- Keep executable entry points under `scripts/`.
- Keep prompts under `prompts/`.
- Do not hard-code long prompts inside Python functions.
- Use config files for models, seeds, character sets, and experimental conditions.
- Use YAML configuration files and Pydantic schemas.
- Load secrets from environment variables; never commit API keys.
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
- Investigation entities include `InvestigationSession`, `Clue`,
  `EvidenceReference`, `AgentAnalysis`, `Hypothesis`, `GroupDecision`, and
  `FinalTheory`; their validated immutable models are implemented without
  orchestration, persistence, or UI.

## Minimal success criterion

A fresh clone of the repository should eventually support a command like:

```bash
bash scripts/smoke_test.sh
```

That command should run a toy end-to-end pipeline and write logs to a documented location.

The first implementation milestone is narrower: a CLI command generates a validated persona JSON from a processed Sherlock Holmes or Hercule Poirot corpus and uses it to produce one saved agent response.
