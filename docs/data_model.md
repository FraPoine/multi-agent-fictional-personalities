# Data Model

## Purpose

This document defines the main entities used by the project, their attributes, relationships, and storage locations.

The goal is to avoid ad-hoc dictionaries and make the system easier to test, log, and reproduce.

## Entity overview

```txt
Character
  └── CorpusDocument
        └── PersonaProfile
              └── Agent
                    └── ConversationRun
                          └── Message
                                └── EvaluationTrial
                                      └── RaterResponse
```

## 1. Character

### Definition

A fictional character selected for simulation and evaluation.

### Storage

`data/characters.json`

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

`data/personas/{character_id}_persona_v{version}.json`

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

## 5. ConversationRun

### Definition

An immutable, validated snapshot of a multi-agent conversation. Its participant
and message collections are tuples in memory, while JSON serialization still
uses arrays. Messages must form the chronological turn-index prefix
`0..len(messages)-1`. Mutable simulation history is maintained separately and
used to construct new snapshots.

### Storage

- run metadata: `logs/runs/{run_id}/run.json`
- messages: `logs/runs/{run_id}/messages.jsonl`
- transcript: `logs/runs/{run_id}/transcript.md`

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
  "provider": "openai",
  "model": "configured_model_name",
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

`logs/runs/{run_id}/messages.jsonl`

### Fields

```json
{
  "message_id": "msg_001",
  "run_id": "run_001",
  "turn_index": 0,
  "speaker_character_id": "sherlock_holmes",
  "speaker_name": "Sherlock Holmes",
  "text": "A generated response is stored here at runtime.",
  "provider": "openai",
  "model": "configured_model_name",
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

`data/evaluation/trials.jsonl`

### Fields

```json
{
  "trial_id": "trial_001",
  "message_id": "msg_001",
  "condition": "persona_seeded",
  "display_text": "An anonymized generated response is stored here.",
  "candidate_character_ids": [
    "sherlock_holmes",
    "hercule_poirot",
    "l",
    "professor_layton"
  ],
  "correct_character_id": "sherlock_holmes",
  "source_run_id": "run_001"
}
```

### Relationships

- Each `EvaluationTrial` is derived from one `Message`.
- Each `EvaluationTrial` can have many `RaterResponse` records.

## 8. RaterResponse

### Definition

One human answer to one evaluation trial.

### Storage

`data/evaluation/responses.jsonl`

### Fields

```json
{
  "response_id": "response_001",
  "trial_id": "trial_001",
  "rater_id": "anon_001",
  "selected_character_id": "sherlock_holmes",
  "confidence": 4,
  "timestamp": "2026-05-05T00:00:00Z",
  "response_time_seconds": 18.4
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
