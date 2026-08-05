# Data Model

## Purpose

This document defines the main entities used by the project, their attributes, relationships, and storage locations.

The goal is to avoid ad-hoc dictionaries and make the system easier to test, log, and reproduce.

## Entity overview

```txt
CharacterCatalog
  └── CharacterCatalogEntry
        └── CharacterConfig
              └── ConversationParticipant
                    └── ConversationRun
                          └── Message
                                └── EvaluationTrial
                                      └── RaterResponse
```

`Character`, `CorpusDocument`, `PersonaProfile`, and `Agent` below describe the
conceptual source and persona domain. The catalog-to-participant chain above is
the currently implemented configuration and conversation-runtime flow; these
layers are related adapters and bindings, not interchangeable domain entities.

## Character catalog configuration

```text
CharacterCatalog
└── characters: ordered tuple of CharacterCatalogEntry
```

`CharacterCatalog` is an immutable, validated, non-empty catalog loaded from
YAML. It preserves declaration order and is the source of supported runtime-
character declarations. The production catalog is `configs/characters.yaml`;
Sherlock Holmes and Hercule Poirot are currently its only entries.

Each immutable `CharacterCatalogEntry` contains:

```text
slug
character_id
display_name
description
corpus_path
persona_fixture_path
mock_response_fixture_path
```

All string values are required and non-empty, and slugs use a validated
lowercase alphanumeric format with optional hyphen or underscore separators.
Slugs and `character_id` values must each be unique. Every declared path is
resolved relative to the catalog file, must exist, and must be a regular file.
The persona fixture's character ID and display name must match the catalog
entry. Declaration order is preserved.

Persona and mock-response fixtures temporarily remain under `tests/fixtures/`.
Moving runtime assets to a production-owned location is future cleanup.

The three implemented representation layers have separate responsibilities:

- `CharacterCatalogEntry` is persistent validated configuration with metadata
  and resolved local asset paths.
- `CharacterConfig` is the pipeline/application compatibility adapter that maps
  catalog fields to the existing pipeline API.
- `ConversationParticipant` is the immutable, runtime-only binding of a
  validated `Persona` and its provider plus provider/model declarations.

## Evaluation pilot records

`EvaluationTrial` is an immutable internal record with stable trial,
source-run, and source-message IDs; condition; anonymized text; candidate and
correct character IDs; source provider; and a synthetic-data flag. Its
rater-safe `PublicEvaluationTrial` counterpart structurally omits the correct
character and source provenance. Private `TrialAnswer` stores ground truth plus
source run and message IDs.

`RaterResponse` is immutable and records a stable response ID, trial ID,
anonymous rater ID, selected pilot character, confidence from 1 through 5,
timezone-aware timestamp, optional nonnegative duration, and synthetic-data
flag. Persistence rejects unknown trials, unsupported choices, and duplicate
rater/trial answers.

Pilot records live under `outputs/evaluation/pilots/<pilot-id>/`; source IDs
preserve traceability to normal conversation artifacts.
`responses.jsonl` is reserved for genuine interface submissions, while
`synthetic_responses.jsonl` is an explicitly selected development fixture.

## 1. Character

### Definition

A fictional character selected for simulation and evaluation.

### Storage

Conceptual target: `data/characters.json`. This file is not currently
implemented; supported runtime declarations instead live in
`configs/characters.yaml` as `CharacterCatalogEntry` records.

### Fields

```json
{
  "character_id": "sherlock_holmes",
  "name": "Sherlock Holmes",
  "fictional_universe": "Sherlock Holmes canon",
  "description": "Consulting detective known for observation and deductive reasoning.",
  "tags": ["observant", "analytical", "direct"],
  "corpus_ids": ["corpus_sherlock_001", "corpus_sherlock_002"],
  "notes": "Initial MVB character."
}
```

### Relationships

- A `Character` has many `CorpusDocument` records.
- A `Character` has one or more `PersonaProfile` versions.
- A `Character` is the ground-truth label for evaluation.

## 2. CorpusDocument

### Definition

A text artifact used as evidence for building a persona profile.

### Storage

- raw text: `data/raw/`
- processed metadata: `data/processed/corpus_documents.jsonl`

### Fields

```json
{
  "document_id": "corpus_sherlock_001",
  "character_id": "sherlock_holmes",
  "source_type": "dialogue_excerpt",
  "source_reference": "manual_curation_v1",
  "text": "A manually selected public-domain corpus excerpt goes here.",
  "metadata": {
    "scene": "example",
    "language": "en"
  }
}
```

### Relationships

- Each `CorpusDocument` belongs to one `Character`.
- Multiple `CorpusDocument` objects are used to create one `PersonaProfile`.

## 3. PersonaProfile

### Definition

A structured representation of a character used to condition an LLM agent.

### Storage

Conceptual target: `data/personas/{character_id}_persona_v{version}.json`. That
production store is not currently implemented; validated mock persona fixtures
temporarily live under `tests/fixtures/`.

### Fields

```json
{
  "persona_id": "persona_sherlock_holmes_v1",
  "character_id": "sherlock_holmes",
  "version": "v1",
  "created_at": "2026-05-05T00:00:00Z",
  "created_by": "extract_persona_prompt_v1",
  "model": "configured_model_name",
  "source_document_ids": ["corpus_sherlock_001", "corpus_sherlock_002"],
  "style": {
    "tone": "analytical and direct",
    "sentence_length": "short to medium",
    "formality": "informal",
    "emotion_level": "restrained"
  },
  "values": [
    "reasoning",
    "evidence",
    "solving difficult cases"
  ],
  "motivations": [
    "resolving mysteries",
    "testing hypotheses"
  ],
  "speech_patterns": [
    "states observations precisely",
    "explains deductions in ordered steps"
  ],
  "interaction_rules": [
    "ask for evidence when claims are unsupported",
    "separate observation from inference"
  ],
  "example_utterances": [
    "A short corpus-grounded example would be inserted here after curation."
  ],
  "limitations": [
    "Profile is based on a small curated corpus.",
    "The model may exaggerate recognizable traits."
  ]
}
```

### Relationships

- A `PersonaProfile` belongs to one `Character`.
- A `PersonaProfile` can instantiate many `Agent` objects.
- Different versions support ablation and comparison.

## 4. Agent

### Definition

A runtime instance of a persona profile connected to a model configuration.

### Storage

Agents may be created dynamically from config files.

### Fields

```json
{
  "agent_id": "agent_sherlock_run_001",
  "persona_id": "persona_sherlock_holmes_v1",
  "model": "configured_model_name",
  "temperature": 0.7,
  "max_output_tokens": 300,
  "tools_enabled": [],
  "memory_policy": "per_run_history_only"
}
```

### Relationships

- An `Agent` uses one `PersonaProfile`.
- An `Agent` produces many `Message` records during a `ConversationRun`.

## Runtime conversation participant binding

`ConversationParticipant` is an immutable runtime-only dependency binding, not
a persisted domain record. It binds one validated `Persona` to one provider
instance plus non-empty provider metadata and an optional non-empty model name.
Its character ID and display name come only from the persona.

Mock conversation construction gives each participant a distinct file-backed
provider configured only with that participant's `agent_reply` fixture. The
binding contains no turn index, history, run ID, output path, selection state,
or investigation state. It is never serialized into `run.json`.

One conversation currently requires uniform declared provider and model names
across all bindings. `ConversationRun` remains unchanged and stores those
validated values once at run level, while each generated `Message` retains its
compatible top-level provider and model fields.

## 5. ConversationRun

### Definition

An immutable, validated snapshot of a multi-agent conversation. Its participant
and message collections are tuples in memory, while JSON serialization still
uses arrays. Messages must form the chronological turn-index prefix
`0..len(messages)-1`. Mutable simulation history is maintained separately and
used to construct new snapshots.

### Storage

- complete run: `<output_root>/conversations/runs/{run_id}/run.json`
- messages: `<output_root>/conversations/runs/{run_id}/messages.jsonl`
- transcript: `<output_root>/conversations/runs/{run_id}/transcript.md`

`run.json` is the canonical complete `ConversationRun`; JSONL and Markdown are
ordered message and human-readable views. Conversation persistence is separate
from the Sprint 2 single-agent writer described below.

### Fields

```json
{
  "run_id": "run_001",
  "topic": "The participants must decide how to investigate a difficult case.",
  "character_ids": [
    "sherlock_holmes",
    "hercule_poirot"
  ],
  "turn_count": 12,
  "seed": 42,
  "provider": "mock",
  "model": "mock-round-robin",
  "created_at": "2026-05-05T00:00:00Z",
  "status": "completed",
  "messages": []
}
```

### Relationships

- A `ConversationRun` contains many `Message` objects.
- A `ConversationRun` is created from a config and a character set.

## Single-agent run artifacts

The Sprint 2 pipeline persists its validated persona and reply through the
canonical writer at:

`outputs/{character-slug}/runs/{run-id}/`

Each directory contains `persona.json`, `system_prompt.txt`, `response.txt`,
and `metadata.json`. Metadata uses `run_id`, `created_at`, `character_id`,
`character_slug`, `task_name`, `provider`, `model`, `is_synthetic`,
`user_message`, and the three artifact filename fields. Agent response data is
derived from the validated `Message` returned by `generate_reply()`.

## 6. Message

### Definition

One generated message in a simulated conversation.

### Storage

`<output_root>/conversations/runs/{run_id}/messages.jsonl`

Mock simulation uses the run's `created_at` value for every message timestamp
to remain deterministic. Distinct real-provider timing can be added later.

### Fields

```json
{
  "message_id": "msg_001",
  "run_id": "run_001",
  "turn_index": 0,
  "speaker_character_id": "sherlock_holmes",
  "speaker_name": "Sherlock Holmes",
  "text": "A generated response is stored here at runtime.",
  "provider": "mock",
  "model": "mock-round-robin",
  "timestamp": "2026-05-05T00:00:00Z",
  "error": null
}
```

### Relationships

- Each `Message` belongs to one `ConversationRun`.
- Each `Message` is produced by one `Agent`.
- A `Message` can become the source for one or more `EvaluationTrial` records.

## 7. EvaluationTrial

### Definition

One anonymized item shown to a rater.

### Storage

Public: `outputs/evaluation/pilots/<pilot-id>/trials_public.jsonl`

Private ground truth/provenance: `answer_key.jsonl`

### Fields

```json
{
  "trial_id": "trial_001",
  "condition": "persona_seeded_mock",
  "display_text": "An anonymized generated response is stored here.",
  "candidate_character_ids": [
    "sherlock_holmes",
    "hercule_poirot"
  ],
  "synthetic_data": true
}
```

The private record adds `correct_character_id`, `source_run_id`, and
`source_message_id`. Those fields never appear in the public schema.

### Relationships

- Each `EvaluationTrial` is derived from one `Message`.
- Each `EvaluationTrial` can have many `RaterResponse` records.

## 8. RaterResponse

### Definition

One human answer to one evaluation trial.

### Storage

Genuine: `outputs/evaluation/pilots/<pilot-id>/responses.jsonl`

Development-only: `synthetic_responses.jsonl`

### Fields

```json
{
  "response_id": "response_001",
  "trial_id": "trial_001",
  "rater_id": "anon_001",
  "selected_character_id": "sherlock_holmes",
  "confidence": 4,
  "timestamp": "2026-05-05T00:00:00Z",
  "response_duration_seconds": 18.4,
  "synthetic_data": false
}
```

### Relationships

- Each `RaterResponse` belongs to one `EvaluationTrial`.
- Each response is compared with the correct character label during analysis.

## 9. RunLogRecord

### Definition

A structured log entry for observability and replay.

### Storage

`logs/runs/{run_id}/steps.jsonl`

### Fields

```json
{
  "run_id": "run_001",
  "step_id": "step_001",
  "timestamp": "2026-05-05T00:00:00Z",
  "step_type": "agent_reply",
  "seed": 42,
  "config_hash": "computed_config_hash",
  "model": "configured_model_name",
  "inputs": {
    "agent_id": "agent_sherlock_run_001",
    "history_length": 3
  },
  "outputs": {
    "message_id": "msg_001"
  },
  "errors": null
}
```

## Data flow

```txt
Character metadata
      ↓
Corpus documents
      ↓
Persona extraction prompt
      ↓
PersonaProfile JSON
      ↓
Agent runtime
      ↓
ConversationRun + Message logs
      ↓
EvaluationTrial generation
      ↓
RaterResponse collection
      ↓
Analysis results
```

## Versioning rules

- Persona profiles must include a version.
- Prompt hashes must be recorded in logs.
- Config hashes must be recorded in runs.
- Generated data should be traceable back to the run that created it.
- Any change to schema should be documented in this file.
