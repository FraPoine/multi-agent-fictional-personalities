# Functional Specification

## Purpose

This document describes what the system should do from the point of view of its users.

The system supports the creation, simulation, and blind recognizability
evaluation of persona-seeded fictional-character agents. It also plans a
user-moderated *Sherlock Holmes: Consulting Detective* capability in which the
project user controls case information. Recognizability is the primary
quantitative experiment; investigation behavior is secondary and exploratory.

This is an individual Track B project. The CLI is the first implemented
interface and remains supported. Sprint 4 completed an additional minimal local
FastAPI/Jinja web interface that uses the same conversation functionality and
is mock-only.
The working runtime exposes only Sherlock Holmes and Hercule Poirot. The final
study aims for four characters, but characters three and four are not finalized
or implemented. L and Professor Layton are historical candidates.

## User types

### 1. Project user

The project user is a student, researcher, or developer using the system to run simulations.

The project user needs to:
- select characters;
- enter an investigation topic and select a turn count;
- run a local mock conversation;
- read the ordered transcript and locate its saved artifacts;
- understand visible validation or runtime errors;
- inspect or edit character corpora;
- generate persona profiles;
- run multi-agent chat simulations;
- inspect transcripts and logs;
- export evaluation trials;
- analyze results.
- act as investigation game master by supplying an introduction and revealing
  clues progressively in future investigation sessions.

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

`LLMProvider.generate()` returns a successful `GenerationResult` containing
required text and structured metadata. Persona extraction consumes
`result.text`; agent runtime stores the text and metadata in `Message` while
validating provider/model consistency. Provider failures continue to propagate
as exceptions, not as a nullable error inside a success result.

### Acceptance criteria

- The agent reply function has a clear input/output interface.
- The model name and temperature are configurable.
- The runtime does not rely on hidden global state.
- The system records the prompt version used for each reply.

## F5 — Multi-agent chat simulation

### Description

The system runs a group conversation between multiple persona-seeded agents.
The current `simulate_chat()` boundary accepts a configurable ordered sequence
of at least two unique runtime participant bindings and an injected
`SpeakerSelector`. Each binding associates one persona with its own provider
instance and uniform declared provider/model metadata. The application service
supplies `RoundRobinSelector` for normal deterministic execution. Only Sherlock
and Poirot have working runtime fixtures and interfaces.

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
- Provider failures fail loudly rather than being silently ignored.
- Run-level provider/model values match every generated message.
- Speaker selection can be replaced without giving the selector ownership of
  response generation, prompts, history, investigation reasoning, or
  persistence.

Sprint 5 isolates current behavior behind `SpeakerSelector` and
`RoundRobinSelector`. A future `ConversationManager` may choose speakers
dynamically, but rule-based, LLM-based, content-dependent, and investigation-
specific scheduling remain outside Sprint 5.

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

F6, F7, and F8 now have a minimal two-character, mock-only technical-pilot
implementation: deterministic blind trials, a separate local rater page,
structured filesystem responses, and reproducible analysis. It remains
separate from the Sprint 4 conversation UI and is not a scientific evaluation.

## F9 — Minimal conversation web interface

### Description

A completed local web interface exposes the existing deterministic mock
multi-agent simulation to a project user. It is an additional interface and
does not replace the existing CLI or the separate technical-pilot blind-rater
interface.

### Inputs

- selected supported character IDs or slugs;
- investigation topic;
- conversation turn count;
- fixed `mock` provider;
- default or configured seed;
- configured output root.

The Sprint 4 page does not expose the seed or output root as editable controls.

### Outputs

- rendered conversation transcript;
- run ID;
- artifact directory;
- generated artifact filenames;
- readable validation or execution error.

### Validation rules

- The topic must not be empty or whitespace-only.
- At least two supported, unique characters must be selected.
- Unsupported character slugs must be rejected.
- The turn count must be an integer within a documented bounded range.
- The provider must remain `mock`.
- Validation, simulation, and persistence failures must not be silently
  converted into successful responses.

The implemented runtime currently requires a positive turn count but has no
upper bound. The bounded UI range is an implementation-level Sprint 4 decision
and must be documented and applied consistently when selected.

### Acceptance criteria

- The main page can be opened locally through a documented startup command.
- Sherlock Holmes and Hercule Poirot are available.
- A topic and turn count can be submitted.
- Valid input invokes the existing local mock conversation pipeline.
- Messages are displayed in speaker and turn order.
- The run ID and artifact directory are displayed.
- `run.json`, `messages.jsonl`, and `transcript.md` are generated and identified
  by the completed view.
- Invalid input produces understandable feedback.
- Runtime or persistence failures are not hidden or reported as success.
- No API key or network access is required.
- The existing CLI continues to work.

## F10 — Moderated investigation domain (future)

### Description

The future system will support a game of *Sherlock Holmes: Consulting
Detective*. The project user is the game master: they manually provide the case
introduction, progressively reveal clues, control their order, and prevent
agents from accessing unrevealed material.

Sprint 5 models the domain and partial session states only. It does not
implement the investigation loop, investigation persistence, scheduling,
reasoning prompts, UI, or a playable game.

### Future inputs and records

- case introduction and ordered revealed clues;
- individual analyses separating facts and deductions;
- evidence references and supporting or contradicting evidence;
- active and discarded hypotheses;
- proposed next leads;
- group decisions;
- final theory and session status.

Conceptual entities include `InvestigationSession`, `Clue`,
`EvidenceReference`, `AgentAnalysis`, `Hypothesis`, `GroupDecision`, and
`FinalTheory`. Partial states similar to `setup`, `active`, `ready_for_final`,
`completed`, and `abandoned` must be representable. Only a completed session
requires a final theory.

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

Real token counts, latency, request IDs, retry observations, and cost are not
currently collected. Sprint 5 mock metadata must remain deterministic; cost
calculation and real provider observability are future work.

## Modularity

The project should keep separate modules for:
- persona extraction;
- agent runtime;
- simulation;
- framework-independent application orchestration;
- web delivery;
- evaluation;
- logging;
- analysis.
- investigation-domain models (planned in Sprint 5, without orchestration).

## Prompt versioning

Prompts must live in the `prompts/` directory, not inside long source-code strings.

## Configuration and provider

Configuration uses YAML and structured inputs/outputs use Pydantic schemas.
The current conversation flow enables only the local mock provider. OpenAI is
a planned live provider, but no OpenAI-backed conversation execution has been
implemented or verified. Any future exact model must be configurable and not
hard-coded, and API keys and other secrets must be loaded from environment
variables.

## Error handling

The system should:
- retry transient API errors;
- fail loudly on permanent errors;
- log malformed outputs;
- validate structured JSON outputs.

Sprint 5 does not introduce real API calls or retries. Its planned successful
generation result has no nullable `error`; a separate failure entity may be
added later if persistent failure records become necessary.

## Usability

The existing CLI supports configuring and saving local deterministic mock
conversations. Sprint 4 completed a minimal local project-user web interface
with only the actions needed to select Sherlock Holmes and Hercule Poirot,
enter a topic and turn count, run the same mock conversation flow, read the
ordered transcript, and locate the saved artifacts.

The implemented page distinguishes empty, loading, completed, and error states.
It does not require a dashboard, authentication, database, history browser,
evaluation statistics, or live-provider configuration.

The implemented technical-pilot rater interface remains separate: it presents
anonymized mock evaluation trials and collects local responses without exposing
ground truth. It is not the Sprint 4 conversation UI or a final experiment.

## Security and ethics

The project should avoid private personal data unless explicit consent and course approval are obtained. The first version uses fictional characters to reduce privacy risk.

## Memory and scheduling

Agents use explicit complete per-run conversation history as working memory and
no persistent memory. Multi-agent simulation currently uses deterministic
round-robin turn taking. Sprint 5 will preserve that behavior behind a
replaceable selector; the future dynamic manager is not part of the sprint.
