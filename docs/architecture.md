# Architecture

## Purpose

This document describes the conceptual architecture, main components, data flow, and public interfaces of the project.

This document distinguishes the implemented baseline, the Sprint 5 offline
target, and later provider, experiment, and investigation work.

The first delivered interface was the CLI. Sprint 4 completed an additional
minimal local FastAPI/Jinja web interface over the same importable conversation
logic. The currently
implemented conversation provider is the network-free mock provider; live
provider execution remains future work. Pydantic schemas validate structured
boundaries, and JSONL is an execution-log format. The repository is following
an offline-first sequence: finish the technical mock foundation, integrate a
real provider later, then run experiments and investigation sessions.

## High-level architecture

```txt
Character metadata → Corpus documents → Persona extraction → Persona profiles
                                                               │
                                                               │ selected profiles
                                                               ▼
Browser / web page → Web route or controller → Application service ← CLI
                                                               │
                                                               ▼
                                            `simulate_chat()` engine boundary
                                      Sprint 5: replaceable `SpeakerSelector`
                                        (`RoundRobinSelector` preserves order)
                              future: dynamic `ConversationManager` outside Sprint 5
                                                               │
                                                               ▼
                                                        Agent runtime
                                                               │
                                                               ▼
                                             Deterministic mock provider
                                      Sprint 5: participant-owned responses
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
rendered-result path were implemented and verified in Sprint 4. Both delivery
paths reuse the agent runtime, deterministic round-robin simulation, and atomic
conversation persistence. A two-character mock evaluation builder, rater app,
and analyzer are also implemented as technical tooling, not a scientific
experiment. Selector abstractions, engine injection, and participant-bound
mocks are implemented Sprint 5 work. Structured generation results and
investigation models remain Sprint 5 targets; a dynamic manager and live
provider remain later work.

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

- providers return a validated `GenerationResult`;
- agent runtime consumes `result.text` and stores `result.metadata` in the new
  message while retaining top-level provider and model compatibility fields.

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

The existing `simulate_chat()` function is the practical conversation-engine
boundary and already accepts an ordered sequence of at least two unique
personas. No concrete `ConversationEngine` class exists, and Sprint 5 need not
introduce one. Only Sherlock Holmes and Hercule Poirot have working runtime
fixtures despite the simulation core's sequence support.

## Speaker-selection boundary

```text
`simulate_chat()` engine boundary
              │
              ▼
      `SpeakerSelector`
          ├── `RoundRobinSelector`
          └── future `ConversationManager`
```

Task 5 implements `SpeakerSelector` as a structural protocol and
`RoundRobinSelector` as its stateless deterministic implementation. The public
contract accepts an ordered sequence of unique `character_id` strings,
read-only `Message` history, and an explicit zero-based `turn_index`. It returns
the selected stable identifier rather than a positional index. Round-robin uses
the configured order and `participant_ids[turn_index % len(participant_ids)]`;
it neither infers turns from history nor maintains a mutable call counter.

The public `select_valid_speaker()` boundary invokes any compatible selector
and rejects results outside the supplied participant identifiers. Direct
round-robin use also rejects empty or duplicate identifiers and negative turn
indexes. Neither participant input nor history is mutated.

The selector owns no response generation, prompt construction, provider calls,
investigation reasoning, persistence, catalog loading, or conversation history.
It can therefore be tested without fixtures or external services.

`simulate_chat()` requires a `SpeakerSelector`. Before each turn it passes the
configured participant IDs, zero-based turn index, and complete ordered history
as a tuple to `select_valid_speaker()`. The validated character ID resolves to
the corresponding `ConversationParticipant`, whose provider generates exactly
one message. Selector validation errors and selector exceptions propagate
before generation for that turn.

The application service owns the normal default policy: it constructs
`RoundRobinSelector` when callers do not inject a selector. CLI and web callers
therefore retain deterministic round-robin behavior without exposing selector
controls.

A future `ConversationManager` may implement dynamic selection. Rule-based,
LLM-based, content-dependent, priority-based, and investigation-specific
selection are all outside Sprint 5.

## Sprint 5 generation-result target

`LLMProvider.generate()` now returns this validated success boundary:

```text
GenerationResult
├── text: required
└── metadata: GenerationMetadata
    ├── provider: required
    ├── model: optional
    ├── usage: TokenUsage | None
    │   ├── input_tokens: optional, non-negative
    │   └── output_tokens: optional, non-negative
    ├── finish_reason: optional
    ├── request_id: optional
    ├── latency_ms: optional, non-negative
    └── retry_count: required, non-negative, default 0
```

`GenerationResult` represents success and therefore has no nullable `error`.
Provider failures continue to fail loudly through exceptions; a separate
failure entity can be added later if persistent failures become necessary.
Existing top-level `Message.provider` and `Message.model` fields remain for
compatibility alongside optional `Message.generation_metadata`. The top-level
provider must match the reported provider. A reported model must match the
top-level model; when no model is reported, the top-level model may retain the
configured compatibility value.

The file-backed `MockProvider`, currently the only production provider, returns
the exact file content with deterministic metadata: provider `mock`, no model
or usage, finish reason `completed`, no request ID or latency, and retry count
zero. Persona extraction consumes `result.text`. Agent runtime validates the
reported provider/model against its declarations, stores the exact metadata in
the new `Message`, and uses a configured model only when the provider reports
none. Provider and validation failures remain exceptions and produce no
successful message. New JSON artifacts serialize nested metadata naturally;
legacy messages without it remain valid, and transcripts do not display it.
Real token counts, latency, request IDs, retry observations, and monetary costs
are not collected in mock execution; live measurements and cost calculation
are future work.

## Participant-owned provider bindings

Task 6 implements immutable runtime-only `ConversationParticipant` bindings.
Each binding contains one `Persona`, one provider instance, and its declared
provider/model names. Identity delegates to the persona; the binding carries no
turn, history, persistence, or investigation state and is not serialized.

For mock conversations, the application service validates all fixtures before
simulation and gives every participant a separate file-backed `MockProvider`
whose `agent_reply` task points only to that participant's response fixture.
Fixture selection therefore cannot drift when a participant repeats, is
skipped, or changes position. The call-counter-based
`RoundRobinMockProvider` has been removed.

`simulate_chat()` accepts the ordered participant bindings and resolves the
selector's validated character ID through a lookup built once before the turn
loop. It invokes the provider owned by that participant. All participants in
one run must declare the same provider and model metadata, even though their
provider objects are distinct. The validated uniform values populate the
unchanged run-level and message-level fields; heterogeneous provider/model
conversations remain future work.

## Sprint 5 investigation-domain target

Sprint 5 will model, but not orchestrate, `InvestigationSession`, `Clue`,
`EvidenceReference`, `AgentAnalysis`, `Hypothesis`, `GroupDecision`, and
`FinalTheory`. The domain must represent a manually supplied case introduction,
progressively revealed clues and clue order, individual facts and deductions,
evidence references, supporting and contradicting evidence, active and
discarded hypotheses, proposed leads, group decisions, and a final theory.

Sessions must allow partial state. Conceptual statuses are `setup`, `active`,
`ready_for_final`, `completed`, and `abandoned`; only `completed` requires a
final theory. Investigation orchestration, persistence, prompts, UI, scheduling,
and a real game are future work.

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
- resolve requested supported personas and their participant-owned local mock
  providers from the configured project root;
- invoke the existing simulation engine;
- invoke the existing conversation persistence layer;
- return a structured result suitable for CLI or web presentation.

The service is implemented under `application/conversation_service.py` and
does not depend on FastAPI or another web framework. Web routes delegate to
this importable service instead of duplicating conversation orchestration. The
service reuses the simulation engine and conversation writer, the simulation
engine remains independent of web concerns, and the existing CLI remains
supported.

## Current configuration and runtime layers

`CharacterCatalogEntry` is the persistent validated declaration loaded from
`configs/characters.yaml`; it owns character metadata and resolved local asset
paths. `CharacterConfig` is the current compatibility adapter used by pipeline
and application boundaries. It maps catalog fields to the existing pipeline
API, is not a provider binding, and is retained intentionally for compatibility.
`ConversationParticipant` is the immutable runtime-only binding of a validated
`Persona`, provider instance, provider name, and model name. It is never
serialized and does not select turns.

These layers have distinct responsibilities. Consolidation may be evaluated
later, but no layer is removed as part of the current documentation cleanup.

The web application builds its character registry when the application is
created. The conversation service resolves a registry again from its configured
project root when it executes a run. In normal immutable-configuration usage
this is not a correctness failure, but catalog edits require restarting the web
application so rendered options refresh predictably. Passing one already-loaded
registry through both boundaries is a possible future dependency-injection
cleanup.

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
renders every catalog entry, selects all available characters by default, and
requires at least two unique supported slugs. It accepts a nonblank topic and a
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
    *,
    participants: Sequence[ConversationParticipant],
    speaker_selector: SpeakerSelector,
    topic: str,
    turn_count: int,
    seed: int,
    run_id: str | None = None,
    timestamp: datetime | None = None,
) -> ConversationRun:
    ...
```

### Errors

- fewer than two participants;
- duplicate participant identities;
- non-uniform provider or model metadata;
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

Offline development example:

```yaml
project:
  name: multi_agent_fictional_personalities

model:
  provider: mock
  name: mock-round-robin
  temperature: 0.7
  max_output_tokens: 300

simulation:
  turn_policy: round_robin
  turn_count: 12
  seed: 42

evaluation:
  characters_per_trial: 2  # technical pilot only
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
- the final experiment still targets four characters;
- characters three and four are not finalized; L and Professor Layton were
  earlier candidates;
- the final chance baseline depends on the pre-registered candidate design.

Tradeoff:
- the two-character technical pilot has a 50% chance baseline and cannot be
  interpreted as the final experiment.

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
- Sprint 5 introduces a selector contract without implementing dynamic choice.

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
