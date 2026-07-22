# Functional Specification

## Purpose

This document describes what the system should do from the point of view of its users.

The system supports the creation, simulation, and evaluation of persona-seeded fictional-character agents.

This is an individual Track B project. The first interface is a CLI. The initial MVB exposes Sherlock Holmes and Hercule Poirot; L and Professor Layton are later extensions.

## User types

### 1. Project user

The project user is a student, researcher, or developer using the system to run simulations.

The project user needs to:
- select characters;
- inspect or edit character corpora;
- generate persona profiles;
- run multi-agent chat simulations;
- inspect transcripts and logs;
- export evaluation trials;
- analyze results.

### 2. Rater

The rater is a human participant who evaluates generated messages.

The rater needs to:
- read anonymized messages;
- choose which character likely produced each message;
- optionally report confidence;
- complete the task quickly and clearly.

### 3. Developer

The developer extends or maintains the system.

The developer needs to:
- add new characters;
- modify prompts;
- change model configuration;
- run smoke tests;
- inspect logs;
- reproduce previous runs.

## Core features

## F1 — Character management

### Description

The system stores a fixed list of fictional characters used in the experiment.

### Inputs

- character name;
- character ID;
- short description;
- source notes;
- tags;
- associated corpus documents.

### Outputs

- list of available characters;
- character metadata;
- corpus readiness status.

### Acceptance criteria

- The user can see which characters are included.
- Each character has a stable ID.
- Each character points to one or more corpus documents.
- Missing or incomplete corpus data is visible.

## F2 — Corpus preparation

### Description

The system loads text examples associated with each character.

### Inputs

- raw text;
- source label;
- character ID;
- optional metadata, such as scene, episode, or dialogue context.

### Outputs

- structured `CorpusDocument` records.

### Acceptance criteria

- Each corpus document is linked to exactly one character.
- Raw data and processed data are stored separately.
- The system can load the corpus from disk.
- The source of each document is documented.

## F3 — Persona profile generation

### Description

The system extracts a structured persona profile from each character corpus.

### Inputs

- one character;
- corpus documents for that character;
- persona extraction prompt;
- model configuration.

### Outputs

A `PersonaProfile` JSON object containing:
- speaking style;
- tone;
- motivations;
- values;
- common phrases;
- interaction style;
- behavioral rules;
- example utterances;
- known limitations.

### Acceptance criteria

- Each profile is saved as JSON.
- Each profile has a version.
- The prompt file used to create the profile is recorded.
- The model configuration is recorded.
- Invalid persona JSON fails loudly or is repaired through a documented validation step.

## F4 — Agent runtime

### Description

The system instantiates one LLM agent from each persona profile.

### Inputs

- persona profile;
- current conversation history;
- model configuration;
- generation parameters.

### Outputs

- one generated message;
- metadata about the generation call.

### Acceptance criteria

- The agent reply function has a clear input/output interface.
- The model name and temperature are configurable.
- The runtime does not rely on hidden global state.
- The system records the prompt version used for each reply.

## F5 — Multi-agent chat simulation

### Description

The system runs a group conversation between multiple persona-seeded agents.

### Inputs

- list of agents;
- topic seed;
- number of turns;
- turn-taking policy;
- random seed;
- simulation config.

### Outputs

- complete transcript;
- one structured log file;
- message records;
- run metadata.

### Acceptance criteria

- The same config and seed should produce a comparable run.
- Each message has a speaker, turn index, and text.
- Each run has a unique run ID.
- Every agent reply is logged.
- Errors are stored in the log rather than silently ignored.

## F6 — Evaluation trial generation

### Description

The system converts generated messages into blind rater trials.

### Inputs

- generated transcript;
- list of candidate characters;
- trial sampling configuration.

### Outputs

- anonymized evaluation trials.

### Acceptance criteria

- The true speaker is hidden from the rater.
- The correct answer is stored separately.
- Each trial has a stable ID.
- The candidate list is randomized or controlled.

## F7 — Rater interface

### Description

The rater interface presents anonymized messages and collects guesses.

### Inputs shown to rater

- generated message;
- list of possible characters;
- optional short descriptions of candidate characters;
- confidence scale.

### Outputs

- selected character;
- confidence score;
- timestamp;
- trial ID.

### Acceptance criteria

- The interface is simple enough to complete without explanation.
- The rater cannot see the correct answer.
- The response is saved in a structured format.
- The system supports at least a mock or form-based version during early development.

## F8 — Analysis

### Description

The system computes evaluation metrics from rater responses.

### Inputs

- evaluation trials;
- rater responses;
- character metadata.

### Outputs

- overall accuracy;
- chance baseline;
- confidence interval;
- per-character accuracy;
- confusion matrix;
- optional confidence analysis.

### Acceptance criteria

- The primary metric is computed before exploratory metrics.
- Results are reproducible from committed or documented inputs.
- Analysis distinguishes confirmatory and exploratory results.

## Non-functional requirements

## Reproducibility

Every run should include:
- run ID;
- seed;
- config hash;
- model name and version;
- prompt hash;
- timestamp;
- inputs;
- outputs;
- errors.

## Modularity

The project should keep separate modules for:
- persona extraction;
- agent runtime;
- simulation;
- evaluation;
- logging;
- analysis.

## Prompt versioning

Prompts must live in the `prompts/` directory, not inside long source-code strings.

## Configuration and provider

Configuration uses YAML and structured inputs/outputs use Pydantic schemas. OpenAI is the initial provider, but the exact model must be configurable and not hard-coded. API keys and other secrets must be loaded from environment variables.

## Error handling

The system should:
- retry transient API errors;
- fail loudly on permanent errors;
- log malformed outputs;
- validate structured JSON outputs.

## Usability

The first interface is a CLI. It should eventually support:
- choosing characters;
- running a simulation;
- viewing a transcript;
- exporting evaluation trials.

## Security and ethics

The project should avoid private personal data unless explicit consent and course approval are obtained. The first version uses fictional characters to reduce privacy risk.

## Memory and scheduling

Agents use explicit per-run conversation history as working memory and no persistent memory. Multi-agent simulation uses deterministic round-robin turn taking in the first implementation.
