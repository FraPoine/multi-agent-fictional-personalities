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
  "character_id": "naruto_uzumaki",
  "name": "Naruto Uzumaki",
  "fictional_universe": "Naruto",
  "description": "Energetic ninja who wants recognition and values friendship.",
  "tags": ["energetic", "optimistic", "stubborn", "loyal"],
  "corpus_ids": ["corpus_naruto_001", "corpus_naruto_002"],
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
  "document_id": "corpus_naruto_001",
  "character_id": "naruto_uzumaki",
  "source_type": "dialogue_excerpt",
  "source_reference": "manual_curation_v1",
  "text": "I never go back on my word. That's my ninja way!",
  "metadata": {
    "scene": "example",
    "language": "en",
    "curated_by": "team"
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
  "persona_id": "persona_naruto_uzumaki_v1",
  "character_id": "naruto_uzumaki",
  "version": "v1",
  "created_at": "2026-05-05T00:00:00Z",
  "created_by": "extract_persona_prompt_v1",
  "model": "model_name_here",
  "source_document_ids": ["corpus_naruto_001", "corpus_naruto_002"],
  "style": {
    "tone": "energetic and direct",
    "sentence_length": "short to medium",
    "formality": "informal",
    "emotion_level": "high"
  },
  "values": [
    "friendship",
    "recognition",
    "persistence"
  ],
  "motivations": [
    "being accepted",
    "protecting friends",
    "proving himself"
  ],
  "speech_patterns": [
    "uses direct emotional statements",
    "often expresses determination",
    "uses simple vocabulary"
  ],
  "interaction_rules": [
    "respond with optimism unless the situation is threatening",
    "challenge people who give up",
    "avoid overly formal language"
  ],
  "example_utterances": [
    "I am not giving up.",
    "We can still do this together."
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
  "agent_id": "agent_naruto_run_001",
  "persona_id": "persona_naruto_uzumaki_v1",
  "model": "model_name_here",
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

One complete simulated multi-agent conversation.

### Storage

- run metadata: `logs/runs/{run_id}/run.json`
- messages: `logs/runs/{run_id}/messages.jsonl`
- transcript: `logs/runs/{run_id}/transcript.md`

### Fields

```json
{
  "run_id": "run_001",
  "created_at": "2026-05-05T00:00:00Z",
  "topic": "The team must decide who should lead a dangerous mission.",
  "agent_ids": [
    "agent_naruto_run_001",
    "agent_sasuke_run_001",
    "agent_sakura_run_001",
    "agent_kakashi_run_001"
  ],
  "turn_count": 12,
  "seed": 42,
  "config_path": "configs/dev.yaml",
  "config_hash": "hash_here",
  "status": "completed"
}
```

### Relationships

- A `ConversationRun` contains many `Message` objects.
- A `ConversationRun` is created from a config and a character set.

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
  "turn_index": 1,
  "speaker_agent_id": "agent_naruto_run_001",
  "speaker_character_id": "naruto_uzumaki",
  "text": "We cannot just stand here. If someone needs to go, I will go first.",
  "prompt_id": "agent_reply_v1",
  "prompt_hash": "hash_here",
  "model": "model_name_here",
  "input_tokens": 500,
  "output_tokens": 35,
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
  "display_text": "We cannot just stand here. If someone needs to go, I will go first.",
  "candidate_character_ids": [
    "naruto_uzumaki",
    "sasuke_uchiha",
    "sakura_haruno",
    "kakashi_hatake"
  ],
  "correct_character_id": "naruto_uzumaki",
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
  "selected_character_id": "naruto_uzumaki",
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
  "config_hash": "hash_here",
  "model": "model_name_here",
  "inputs": {
    "agent_id": "agent_naruto_run_001",
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
