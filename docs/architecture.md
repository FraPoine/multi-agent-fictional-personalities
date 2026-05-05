# Architecture

## Purpose

This document describes the conceptual architecture, main components, data flow, and public interfaces of the project.

The architecture is intentionally simple for Sprint 1. It should be updated whenever the implementation diverges from this design.

## High-level architecture

```txt
               ┌────────────────────┐
               │ Character metadata  │
               └─────────┬──────────┘
                         │
                         ▼
               ┌────────────────────┐
               │ Corpus documents   │
               └─────────┬──────────┘
                         │
                         ▼
               ┌────────────────────┐
               │ Persona extraction │
               └─────────┬──────────┘
                         │
                         ▼
               ┌────────────────────┐
               │ Persona profiles   │
               └─────────┬──────────┘
                         │
                         ▼
               ┌────────────────────┐
               │ Agent runtime      │
               └─────────┬──────────┘
                         │
                         ▼
               ┌────────────────────┐
               │ Chat simulation    │
               └─────────┬──────────┘
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
┌────────────────────┐        ┌────────────────────┐
│ Transcript/logs    │        │ Evaluation trials  │
└────────────────────┘        └─────────┬──────────┘
                                        │
                                        ▼
                              ┌────────────────────┐
                              │ Rater responses    │
                              └─────────┬──────────┘
                                        │
                                        ▼
                              ┌────────────────────┐
                              │ Analysis results   │
                              └────────────────────┘
```

## Main components

## 1. Corpus manager

### Responsibility

Load and validate character-specific text examples.

### Input

- character metadata;
- raw text files;
- source metadata.

### Output

- structured `CorpusDocument` records.

### Owner

Dataset/persona team member.

## 2. Persona extractor

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

## 3. Agent runtime

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

The runtime should not know about evaluation. It only generates messages.

## 4. Simulation engine

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
- list of `Message` records
- transcript
- logs

### Turn-taking policy

Initial version:

```txt
round_robin
```

Each agent speaks in a fixed order until the configured number of turns is reached.

## 5. Logger

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

## 6. Evaluation builder

### Responsibility

Convert generated messages into blind evaluation trials.

### Input

- transcript/messages;
- character set;
- sampling config.

### Output

- `EvaluationTrial` records.

## 7. Rater interface

### Responsibility

Show anonymized messages and collect rater guesses.

### Initial implementation options

- Google Form;
- simple Streamlit page;
- simple web page;
- command-line dry run for development.

## 8. Analyzer

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
  provider: placeholder
  name: placeholder-model
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

Every run should create:

```txt
logs/runs/{run_id}/
├── run.json
├── messages.jsonl
├── steps.jsonl
└── transcript.md
```

## Smoke test path

The smoke test should run the smallest possible pipeline:

```txt
2 toy characters
↓
2 tiny corpora
↓
2 persona profiles
↓
4-turn chat
↓
2 evaluation trials
↓
accuracy computation on fake responses
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

## ADR-002 — Start with 4 characters

Reason:
- chance baseline is simple;
- small enough for manual inspection;
- feasible within the project timeline.

Tradeoff:
- less variety and less statistical power than an 8-character setup.

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
