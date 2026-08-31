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

## Successful generation result schemas

```text
GenerationResult
├── text: required non-empty string
└── metadata: GenerationMetadata
    ├── provider: required non-empty string
    ├── model: optional non-empty string
    ├── usage: TokenUsage | None
    │   ├── input_tokens: optional non-negative integer
    │   └── output_tokens: optional non-negative integer
    ├── finish_reason: optional non-empty string
    ├── request_id: optional non-empty string
    ├── latency_ms: optional non-negative number
    └── retry_count: non-negative integer, default 0
```

`TokenUsage`, `GenerationMetadata`, and `GenerationResult` are immutable
provider-neutral Pydantic models, and all forbid undeclared fields. Token usage
may be absent; when present, either counter may independently be absent or
zero. `GenerationResult.text` must contain non-whitespace content, but
validation preserves the supplied text rather than stripping it.

`GenerationResult` represents successful generation only. It has no error,
status, cost, provider-SDK object, or provider-specific metadata field.
Generation failures continue to be exceptions. No persisted total-token or
cost field exists, and no pricing calculation is defined.

Task 8 implemented these schemas and validation. Task 9 migrates
`LLMProvider.generate()` and the file-backed `MockProvider` to return
`GenerationResult`. Mock metadata is deterministic: provider `mock`, no model
or usage, finish reason `completed`, no request ID or latency, and retry count
zero. Persona extraction consumes only `result.text`. Task 10 makes
`generate_reply()` store both `result.text` and `result.metadata` in newly
generated messages. Run-level aggregation remains future work.

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

`run.json` is the canonical complete `ConversationRun` snapshot.
`messages.jsonl` is the canonical ordered per-turn generation trace, with one
complete `Message` per line. Both structured artifacts include identical
nested generation metadata for new messages. Artifacts created before that
optional field existed remain deserializable. `transcript.md` is the ordered
human-readable view and does not duplicate technical metadata. Conversation
persistence is separate from the Sprint 2 single-agent writer described below.

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
  "generation_metadata": {
    "provider": "mock",
    "model": null,
    "usage": null,
    "finish_reason": "completed",
    "request_id": null,
    "latency_ms": null,
    "retry_count": 0
  },
  "timestamp": "2026-05-05T00:00:00Z",
  "error": null
}
```

`generation_metadata` is optional and defaults to `null`, so pre-Task-10
messages and runs that omit it remain valid without migration. Newly generated
successful messages store the exact provider metadata. The top-level provider
must match its nested counterpart. When metadata reports a model, the top-level
model must match it; when metadata reports no model, the top-level model may
preserve a configured compatibility value such as `mock-round-robin`.

Provider and consistency failures remain exceptions, and `generate_reply()`
does not construct an error message after failure. New `run.json` and
`messages.jsonl` records include nested metadata automatically, while
`transcript.md` remains human-readable and does not print it.

Mock metadata is deterministic and mostly contains `null`: it does not measure
real token counts, latency, or request identifiers. Those values require a
future provider. Persistence currently defines neither monetary cost fields
nor a broader logging system.

An error-bearing message is a failed legacy record and must not contain
successful `generation_metadata`. For every message stored in a
`ConversationRun`, the top-level provider and model must equal the run-level
provider and model. Participant declarations provide the expected provider and
configured model; provider metadata provides reported values. A configured
model is used only as a fallback when metadata omits the model, and the uniform
effective message model becomes the run model.

### Relationships

- Each `Message` belongs to one `ConversationRun`.
- Each `Message` is produced by one `Agent`.
- A `Message` can become the source for one or more `EvaluationTrial` records.

## 7. Lead, visit, revealed information, and evidence

### Authoritative Lead/Visit foundation

```text
InvestigationLead
├── lead_id
├── session_id
├── label
└── kind

LeadVisit
├── visit_id
├── session_id
├── lead_id
├── visit_index
├── revealed_information_ids
└── conversation_run_ids

RevealedInformation
├── information_id
├── session_id
├── text
├── reveal_index
├── optional lead_id and visit_id
└── optional source_kind and source_id

EvidenceReference
├── information_id (authoritative) or clue_id (transitional)
└── relation: supports | contradicts | context
```

Leads are persistent semantic tracks and carry no lifecycle state. Visits are
one-based, contiguous, and chronological across the whole session. Multiple
visits may reference the same lead, so `A → B → A` is valid without duplicating
Lead A. There is no maximum collection size and no requirement to complete a
lead or visit before focusing elsewhere.

Revealed information is zero-based and contiguous in disclosure order. Once
present in the aggregate it is globally known. Any number of information
records may reference one lead or one visit; there is deliberately no
one-information-per-visit rule. Optional generic source fields form a small
future case-resource boundary without specialized PDF, map, newspaper, or
directory models.

The aggregate rejects duplicate IDs, foreign session ownership, unknown lead
or visit references, mismatched visit/lead sources, inconsistent bidirectional
visit-information links, and unknown information evidence. It never repairs a
malformed snapshot. `conversation_run_ids` attach ordered bounded generation
segments to visits. The aggregate owns the corresponding immutable
`conversation_runs`, requires every referenced run to exist, requires every
stored run to be referenced by one visit, rejects duplicate run IDs, and
requires exact session participant order.

The logical history for a semantic lead is projected by global visit
chronology, then run order within a visit, then message turn index. It may span
revisits while leaving every original `ConversationRun` unchanged. Application
discussion context deterministically includes the case opening, current lead
and visit, globally revealed information, visit chronology, and this same-lead
projection. The participant runtime supplies persona context and the simulation
engine supplies current-segment message history.

### Transitional round records

### Definition

The existing Sprint 6/Sprint 7 workflow continues temporarily to use:

```text
Clue
├── clue_id
├── text
└── reveal_order

EvidenceReference.clue_id (legacy target)
```

`Clue.text` contains only revealed information, and `reveal_order` records its
position in progressive disclosure. Stateless application operations assign
IDs from a caller-injected deterministic namespace: `session_001`,
`session_001_clue_0001`, and `session_001_round_0001`. It contains no hidden
information, deduction, interpretation, hypothesis, or confidence. Clue IDs
are unique within a validated collection.

Legacy evidence points to a clue through its stable ID rather than copying the
clue text. Exactly one target is required: new records use `information_id`;
existing round records use `clue_id`. `Clue`, `InvestigationRound`, and
`InvestigationRoundStatus` remain for application/web compatibility only and
do not constrain the authoritative Lead/Visit graph. Deductions, explanations,
and agent interpretations belong to the reasoning records below.

## 8. Investigation reasoning and decisions

On the authoritative Lead/Visit path, reasoning is optional and non-gating.
`AgentAnalysis` uses `origin_visit_id` plus `lead_id`; `Hypothesis` may use an
`origin_visit_id` with backward-only revisions; and `GroupDecision` uses an
origin visit and lead without completing that visit. Their evidence targets
revealed information. Zero analyses, hypotheses, and decisions is valid.

The old `round_id` fields remain mutually exclusive compatibility alternatives
until Task 4. Legacy validators apply only to round-owned records; Lead/Visit
records validate visit ownership, lead agreement, session references, and
revealed-information evidence.

The investigation reasoning layer uses three distinct immutable record types:

```text
AgentAnalysis
├── session and round IDs
├── ordered visible-clue ID snapshot
├── agent-owned facts
├── agent-owned deductions
├── evidence references
└── proposed leads

Hypothesis
├── session and originating round IDs
├── statement
├── active/discarded status
├── evidence references
└── optional previous hypothesis ID

GroupDecision
├── session and owning round IDs
├── explicit decision type
├── summary
├── referenced analysis IDs
├── referenced hypothesis IDs
└── evidence references
```

Facts and deductions remain separate and each analysis belongs to the session,
round, and participant identified by `session_id`, `round_id`, and `agent_id`.
Its required `visible_clue_ids` tuple is an independently auditable, ordered
copy of the exact clue snapshot stored by its round. Proposed leads are
individual suggestions; they do not imply agreement and never become group
decisions automatically.

The session aggregate enforces exact tuple equality between an analysis and
its round visibility snapshot. Analysis evidence may reference only IDs in
that snapshot, even when a later clue already exists in the current session.
It also permits at most one analysis per participant per round. Each round's
ordered `analysis_ids` must exactly match the analyses assigned to that round
as filtered from session analysis storage order; unknown, duplicated, omitted,
misordered, or cross-round IDs are rejected. These invariants are enforced by
the aggregate and the implemented provider-driven analysis operation.

Hypotheses are optional, append-only, session- and round-owned records. Their
evidence is limited to the owning round's visible-clue snapshot, so an earlier
hypothesis cannot cite evidence revealed later. A revision receives a new ID
and may point backward to an earlier stored hypothesis from the same session
and the same or an earlier round; the old record is not mutated. Forward,
future-round, self, and cyclic revision links are rejected. Both active and
discarded hypotheses remain part of the history.

A `GroupDecision` must be created explicitly with one of `pursue_lead`,
`adopt_hypothesis`, `discard_hypothesis`, or `request_information`. It does not
result from a consensus algorithm. Each decision belongs to one session and
round, may reference analyses only from that round, and may reference
hypotheses from its current or previous rounds. Direct evidence is restricted
to the decision round's visible-clue snapshot; future-round references are
invalid. Evidence references contain only clue IDs and relations, while
decisions reference analyses and hypotheses only by ID; complete entities are
never nested or copied.

The aggregate validates `InvestigationRound.decision_id` and session decisions
in both directions. Non-completed rounds have no decision, while a completed
round has exactly one valid linked decision. A completed round may still have
no hypotheses and a decision may keep an empty `hypothesis_ids` tuple.
Cross-record referential integrity is enforced without automatic hypothesis or
decision execution. Provider-neutral prompt and generation orchestration and
local web delivery are implemented; investigation persistence is not.

### InvestigationSession aggregate

```text
InvestigationSession
├── case introduction
├── participant IDs
├── status
├── persistent leads
├── chronological lead visits
├── revealed information
├── ordered revealed clues
├── ordered investigation rounds
├── agent analyses
├── append-only hypotheses
├── group decisions
└── optional final theory
```

`InvestigationSession` is the immutable aggregate root. Its new authoritative
collections are `leads`, `visits`, and `revealed_information`; the remaining
round collections are transitional until later redesign tasks. It validates entity
IDs, round and participant ownership, exact per-analysis temporal visibility,
clue and record references, contiguous clue and round order, round-analysis
consistency, and backward-only hypothesis revision links without executing
agents. Every stored round must identify the clue at its historical position
and contain exactly the ordered clue prefix visible at that point. This rejects
coordinated forgeries in which a round and its analyses agree on a future,
unknown, missing, additional, or reordered clue. Legacy snapshots may still
contain revealed clues without corresponding rounds. Clues contain only
information explicitly revealed by the game master, and nested references use
stable IDs rather than copies of complete entities.

Round lifecycle state is enforced by the aggregate. `awaiting_analyses`
contains no analyses, discussion, or decision; `awaiting_discussion` contains
exactly one analysis per participant in participant order and no discussion or
decision; `awaiting_decision` additionally contains a completed discussion
whose participant IDs exactly match the session; and `completed` additionally
contains a resolving decision. Attached discussion run IDs are unique across
rounds. Invalid snapshots are rejected rather than normalized.

Partial `setup`, `active`, `ready_for_final`, and `abandoned` sessions are valid
without clues, analyses, hypotheses, decisions, or a final theory. Only a
`completed` session requires a `FinalTheory`. The first stateless operations
create an active session and explicitly reveal one caller-supplied clue while
opening its round; they require an immutable deterministic ID factory and do
not perform a `setup`-to-`active` transition. No autonomous controller, game
loop, persistence, or automatic clue disclosure exists. The implemented web
delivery invokes these operations one explicit action at a time.

### Web registry records are outside the aggregate

Sprint 7 adds no runtime fields to `InvestigationSession`. The web application
instead owns an `InMemoryInvestigationRegistry` whose process-local records
have this delivery/runtime shape:

```text
InvestigationSessionRecord
├── session_sequence
├── session: InvestigationSession
└── runtime: InvestigationMockRuntime
```

The runtime contains the deterministic ID factory, catalogue-derived character
configuration, participant/provider bindings, decision and final-theory
providers, and mock capabilities. Registry locks and allocation counters are
also infrastructure state, not Pydantic domain fields. A successful mutation
replaces the record with a new immutable session snapshot while retaining its
runtime; failed mutations retain the prior record.

The current runtime advertises two supported clue rounds and two discussion
turns because that is the committed fixture inventory. The aggregate and its
public operations do not encode a two-round limit. Final-theory semantics are
unchanged: only an explicit successful finalization creates both the theory
and `completed` status. Registry records are neither serialized nor restored,
and application restart discards them.

### Investigation provider payloads

The application layer defines immutable `GeneratedAnalysisPayload`,
`GeneratedHypothesisPayload`, `GeneratedDecisionPayload`, and
`GeneratedFinalTheoryPayload` schemas. These represent JSON content a provider
may propose: reasoning text, evidence references, decision types, summaries,
and references to already authoritative records. They deliberately omit the
authoritative IDs and ownership fields that a later workflow service must
assign before constructing `AgentAnalysis`, `Hypothesis`, `GroupDecision`, or
`FinalTheory` domain records. Extra JSON fields are forbidden.

`parse_structured_generation()` validates the exact `GenerationResult.text`
with the selected payload model's `model_validate_json()` method and returns an
immutable `StructuredGenerationResult` containing both the typed value and the
original `GenerationResult`. Provider, model, usage, timing, request, finish,
and retry metadata therefore remain unchanged. Empty text, malformed JSON,
schema errors, extra fields, and invalid enums fail explicitly; no retry,
Markdown-fence removal, substring extraction, or automatic repair occurs.

The implemented group-decision operation consumes `GeneratedDecisionPayload`
only after a completed current-round discussion. The application service owns
the resulting decision ID, session and round ownership, validates all analysis,
hypothesis, and visible-clue references, and appends optional hypotheses with
service-generated IDs. New hypothesis revisions may target only hypotheses in
the pre-decision snapshot. Recording a decision completes its round while the
session remains active; clue revelation, subsequent rounds, and finalization
remain explicit caller actions.

Explicit finalization requires an active session whose rounds and decisions are
complete, plus at least one hypothesis and structured evidence reference. The
final prompt is bounded by the last completed round's visibility snapshot and
the provider result traverses the same structured adapter. The service owns
`session_NNN_final_theory` identity and atomically adds the theory together
with `completed` status. The aggregate enforces both directions: completed
sessions require a final theory, and non-completed sessions cannot contain one.
`ready_for_final` does not trigger generation. No official-solution scoring or
persistence is implemented. The web finalization route delegates to this
operation only after an explicit Game Master submission.

Prompt context comes from four version-1 files under `prompts/`. Their closed
placeholder contracts are loaded and rendered in the application layer, while
record helpers preserve supplied collection order. These facilities do not
perform provider calls or implement analysis, discussion, decision, or final-
theory generation.

## 9. EvaluationTrial

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

## 10. RaterResponse

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

## 11. RunLogRecord

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
