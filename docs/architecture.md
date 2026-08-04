# Architecture

## Purpose

This document describes the conceptual architecture, main components, data flow, and public interfaces of the project.

The architecture is intentionally simple for Sprint 1. It should be updated whenever the implementation diverges from this design.

The first delivered interface was the CLI. Sprint 4 completed an additional
minimal local FastAPI/Jinja web interface over the same importable conversation
logic. The currently
implemented conversation provider is the network-free mock provider; live
OpenAI-backed conversation execution remains future work. Provider and model
selection remain behind configurable boundaries, Pydantic schemas validate
structured boundaries, and JSONL is an execution-log format.

## High-level architecture

```txt
Character metadata → Corpus documents → Persona extraction → Persona profiles
                                                               │
                                                               │ selected profiles
                                                               ▼
Browser / web page → Web route or controller → Application service ← CLI
                                                               │
                                                               ▼
                                                      Simulation engine
                                                               │
                                                               ▼
                                                        Agent runtime
                                                               │
                                                               ▼
                                             Deterministic mock provider
                                                               │
                                                               ▼
                                                 Conversation persistence
                                                               │
                                                               ▼
                               ConversationRun, transcript, and artifact path
                                              │                    │
                                              ▼                    ▼
                                    Rendered web result    Evaluation trial builder
                                                                   │
                                                                   ▼
                                                        Separate rater web app
                                                                   │
                                                                   ▼
                                                          Analysis artifacts
```

The browser, FastAPI route, framework-independent application service, and
rendered-result path were implemented and verified in Sprint 4. Both the CLI
and browser path reuse the agent runtime, deterministic round-robin simulation,
and atomic conversation persistence for local mock conversations. Evaluation
and analysis remain future components.

## Main components

## Corpus manager

### Responsibility

Load and validate character-specific text examples.

### Input

- character metadata;
- raw text files;
- source metadata.

### Output

- structured `CorpusDocument` records.

### Owner

Francesco (individual Track B project).

## Persona extractor

### Responsibility

Convert a character corpus into a structured persona profile.

### Input

- `Character`
- list of `CorpusDocument`
- extraction prompt
- model config

### Output

- `PersonaProfile`

### Notes

This component should validate that the generated profile follows the expected schema.

## Agent runtime

### Responsibility

Wrap LLM calls and produce one in-character reply at a time.

### Input

- `PersonaProfile`
- conversation history
- model config
- prompt template

### Output

- `Message`
- structured generation metadata

### Notes

The public `generate_reply` runtime function generates exactly one validated
`Message`. The caller passes the selected persona, topic, ordered history, run
and turn identifiers, and an `LLMProvider`. History is explicit per call: the
runtime stores no persistent state or memory between runs. Speaker selection
and turn scheduling remain responsibilities of the simulation engine.
The Sprint 2 single-response pipeline also uses this public runtime, so all
agent replies pass through the same validation and message-construction path.

## Simulation engine

### Responsibility

Coordinate multiple agents in a turn-based group chat.

### Input

- list of agents
- topic seed
- turn count
- turn-taking policy
- seed
- config

### Output

- `ConversationRun`

The run contains its ordered tuple of `Message` records. Transcript and file
generation belong to the separate artifact writer.

`ConversationRun` is an immutable validated snapshot, not simulation state.
The implemented simulation engine maintains a separate mutable local history,
passes the complete ordered history explicitly, and calls `generate_reply()`
exactly once per turn before returning the completed snapshot. `Message`
objects are also immutable.

### Turn-taking policy

Initial version:

```txt
round_robin
```

Each agent speaks in a fixed order until the configured number of turns is reached.

`ConversationRun.created_at` identifies the start of a run. Mock-generated
messages share this timestamp to keep simulation deterministic; real-provider
timing may be refined later without adding clock calls inside the turn loop.

Persistence remains separate from simulation. `save_conversation_run()` writes
a complete run beneath `conversations/runs/{run_id}/`, while the existing
`save_single_agent_run()` continues to write the older Sprint 2 persona and
single-response artifacts. Conversation persistence uses an atomically created
per-run reservation file and a temporary sibling directory. It never
intentionally overwrites a completed run, and removes its reservation and
temporary directory after success or handled failure. This is process-safe for
writers using this persistence function; it is not a distributed lock or a
machine-crash recovery mechanism.

## Application service boundary

### Responsibility

Sprint 4 implemented a framework-independent conversation application service
between the CLI or web delivery layer and the existing conversation
components. It:

- accept validated conversation parameters;
- resolve supported Sherlock Holmes and Hercule Poirot personas and the local
  mock provider;
- invoke the existing simulation engine;
- invoke the existing conversation persistence layer;
- return a structured result suitable for CLI or web presentation.

The service is implemented under `application/conversation_service.py` and
does not depend on FastAPI or another web framework. Web routes delegate to
this importable service instead of duplicating conversation orchestration. The
service reuses the simulation engine and conversation writer, the simulation
engine remains independent of web concerns, and the existing CLI remains
supported.

## Minimal web UI

### Responsibility

The implemented Sprint 4 web interface does the following:

- display the conversation configuration form;
- collect supported character selections, topic, and turn count;
- submit a local mock conversation request;
- render the transcript in speaker and turn order;
- render the run ID, artifact directory, and artifact filenames;
- present readable validation, simulation, and persistence errors.

It also provides loading feedback while a request is in progress. The form
requires Sherlock Holmes and Hercule Poirot, accepts a nonblank topic and a
bounded turn count from 2 through 12, and renders the completed run ID plus the
paths for `run.json`, `messages.jsonl`, and `transcript.md`.

The web layer does not own persona loading rules, turn scheduling, reply
generation, `ConversationRun` construction, persistence semantics, run ID
reservation, or artifact generation. Simulation and persistence remain
authoritative for those responsibilities. Mock is the only enabled
conversation provider during Sprint 4, and the complete path requires no
network access.

### Error flow

```txt
Invalid user input
→ web validation error
→ readable feedback

Simulation or persistence failure
→ application error
→ web layer renders a concise message
→ failure is not reported as success
```

## Logger

### Responsibility

Write structured records for every important step.

### Logged information

- run ID;
- timestamp;
- seed;
- config hash;
- model name;
- prompt ID;
- prompt hash;
- inputs;
- outputs;
- errors;
- token counts when available.

### Output format

Initial format:

```txt
JSONL
```

The implemented single-agent pipeline uses one canonical artifact writer. It
stores each run under `outputs/{character-slug}/runs/{run-id}/` with
`persona.json`, `system_prompt.txt`, `response.txt`, and `metadata.json`.

## Evaluation builder

### Responsibility

Convert generated messages into blind evaluation trials.

### Input

- transcript/messages;
- character set;
- sampling config.

### Output

- `EvaluationTrial` records.

The implemented builder filters completed conversation messages, records every
exclusion reason, then deterministically samples three messages per pilot
character. Public trials and private answers use separate schemas and files.
Source run/message provenance is private because deterministic turn indexes can
leak speaker identity. Selection is stratified by source run and character.

## Rater interface

### Responsibility

Show anonymized messages and collect rater guesses.

### Initial implementation

A separate local FastAPI/Jinja application presents one unanswered trial at a
time and appends validated responses under a per-pilot lock. It never supplies
the answer key to template context or browser-visible responses. Complete
pilot directories are published through a temporary sibling and atomic rename.
Genuine and synthetic responses use separate JSONL files. A per-pilot lock
covers validation, atomic response-set replacement, and analysis/report refresh.

## Analyzer

### Responsibility

Compute evaluation metrics and produce figures/tables.

### Input

- `EvaluationTrial`
- `RaterResponse`

### Output

- accuracy;
- confidence interval;
- confusion matrix;
- per-character breakdown.

The analyzer also reports a 2×2 confusion matrix, confidence by correctness,
response counts per rater, and a 95% Wilson score interval. Results are derived
only from public trials, the answer key, and persisted responses.

## Public interfaces

## Persona extraction API

```python
def extract_persona(
    character: Character,
    documents: list[CorpusDocument],
    config: PersonaExtractionConfig,
) -> PersonaProfile:
    ...
```

### Errors

- missing corpus;
- invalid generated JSON;
- model call failure;
- schema validation failure.

## Agent reply API

```python
def reply(
    agent: Agent,
    history: list[Message],
    config: AgentRuntimeConfig,
) -> Message:
    ...
```

### Errors

- missing persona profile;
- model call failure;
- malformed response;
- context too long.

## Simulation API

```python
def simulate_chat(
    agents: list[Agent],
    topic: str,
    config: SimulationConfig,
) -> ConversationRun:
    ...
```

### Errors

- fewer than two agents;
- invalid turn count;
- failed agent reply;
- logging failure.

## Evaluation trial API

```python
def build_trials(
    run: ConversationRun,
    messages: list[Message],
    config: EvaluationConfig,
) -> list[EvaluationTrial]:
    ...
```

### Errors

- insufficient messages;
- unbalanced character samples;
- missing ground-truth labels.

## Analysis API

```python
def analyze_responses(
    trials: list[EvaluationTrial],
    responses: list[RaterResponse],
    config: AnalysisConfig,
) -> AnalysisResult:
    ...
```

### Errors

- missing responses;
- unknown trial ID;
- unknown character ID;
- inconsistent candidate set.

## Configuration

Configuration should live under `configs/`.

Example:

```yaml
project:
  name: multi_agent_fictional_personalities

model:
  provider: openai
  name: ${OPENAI_MODEL}
  temperature: 0.7
  max_output_tokens: 300

simulation:
  turn_policy: round_robin
  turn_count: 12
  seed: 42

evaluation:
  characters_per_trial: 4
  trials_per_character: 5
  collect_confidence: true

logging:
  output_dir: logs/
  format: jsonl
```

## Memory and context policy

The first version uses only per-run working memory.

- Conversation history is passed explicitly to each agent.
- No cross-run memory is used.
- Persistent memory is not enabled.
- This avoids leakage across experimental conditions.

## Prompt policy

Prompts are stored as files:

```txt
prompts/
├── extract_persona.md
├── agent_reply.md
└── style_neutralize.md
```

Each log should record:
- prompt file name;
- prompt hash;
- resolved prompt inputs.

## Logging policy

Implemented conversation persistence writes each complete conversation beneath
the configured output root:

```txt
<output-root>/conversations/runs/<run-id>/
├── run.json
├── messages.jsonl
└── transcript.md
```

This structure is distinct from the older Sprint 2 single-agent structure at
`outputs/<character-slug>/runs/<run-id>/`, which contains `persona.json`,
`system_prompt.txt`, `response.txt`, and `metadata.json`. Conversation
persistence does not create `steps.jsonl`.

## Planned smoke test path

The planned smoke test should exercise the current critical path:

```txt
Sherlock Holmes and Hercule Poirot
→ load validated synthetic personas
→ run a short deterministic round-robin mock conversation
→ save the complete conversation
→ verify run.json, messages.jsonl, and transcript.md
```

Target command:

```bash
bash scripts/smoke_test.sh
```

## Architecture decisions

## ADR-001 — Start with fictional characters

Reason:
- reduces privacy risk;
- makes the rater task easier;
- supports controlled group dynamics.

Tradeoff:
- results do not generalize directly to real human personalities.

## ADR-002 — Stage two then four characters

Reason:
- Sherlock and Poirot keep the first pipeline small;
- L and Professor Layton extend the final experiment to four characters;
- the final four-way chance baseline is 25%.

Tradeoff:
- the two-character development pilot has a 50% chance baseline and cannot be interpreted as the final experiment.

## ADR-003 — Use one model in the first version

Reason:
- avoids confounding model comparison with persona evaluation;
- reduces cost and complexity.

Tradeoff:
- results are model-specific.

## ADR-004 — Use round-robin chat simulation first

Reason:
- simple and reproducible;
- avoids needing a speaker-selection model.

Tradeoff:
- less natural than free-form conversation.

## ADR-005 — No persistent memory

Reason:
- explicit per-run history is reproducible and avoids cross-run leakage.

Tradeoff:
- agents cannot retain information between runs.

## Package structure

The implementation already separates persona extraction, agent runtime,
simulation, models, providers, artifacts, and CLI concerns beneath
`src/multi_agent_personalities/`, with executable entry points under
`scripts/`. Sprint 4 added the `application/` and `web/` areas while keeping
framework-independent conversation orchestration separate from FastAPI/Jinja
delivery. The web layer reuses the implemented simulation, runtime, provider,
and artifact boundaries.
