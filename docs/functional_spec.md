# Functional Specification

## Integrated English demos

Three supplied demos are selectable. London aliases and exact four-digit
`time-code` inputs are supported; malformed syntax is distinct from a valid but
unknown case reference. Preloaded visits disclose eligible sections, revisits
can unlock gated sections, and applied effects are idempotent. Confirmation and
single-choice interactions require an explicit player POST. Repository-local
images are served through a path-confined endpoint and rendered in the case UI.

## Sprint 7 Lead/Visit web redesign

The catalogue-driven Lead/Visit browser flow described here is complete for
synthetic local fixtures. See the
[case-catalogue completion record](sprint_7_case_catalogue_completion.md).

The main FastAPI application now presents `GET /investigations` as a local
game-start lobby. It renders one selectable card per synthetic local
`CaseDefinition`, investigator identities from the character catalogue, and
the fixed mock-fixture limitation. `POST /investigations` accepts `case_id` and
investigator selection only; the server resolves the trusted definition and
creates the session through `InMemoryInvestigationRegistry`.

The canonical detail page now uses a shared three-region investigation shell.
An empty session renders the selected Case Opening, catalogue-derived
investigator identities, an empty Leads rail, and the compact resource toolbar.
Rules are local guidance and case resources resolve from the session's
`case_id`. No GET mutates the session.

The final route contract implements lead navigation, conversation projection,
information revelation, revisit behavior, resources, and finalization. The
original round POST routes and their presentation helpers are not installed.

Task 2 adds the core server-rendered Lead/Visit interaction. Selecting a
semantic lead uses `GET /investigations/{session_id}?lead={lead_id}` and never
changes the aggregate. The current lead is the lead referenced by the latest
chronological visit; any other selected lead is historical and read-only until
the user explicitly posts a revisit. A revisit appends a new `LeadVisit` while
preserving the original `InvestigationLead` identity and all earlier visits.

Game Master information disclosure and investigator discussion target only the
latest visit. Historical writes return `409` without replacing the registry
snapshot. Each discussion submission calls `continue_lead_discussion()` and
attaches one bounded immutable `ConversationRun`. The UI projects all runs for
the selected semantic lead through `project_lead_conversation()`, so an A → B
→ A chronology renders both A visits as one persistent thread with subtle visit
separators. Fixture exhaustion is a local `500` failure, not a domain limit.

Task 3 completes the remaining player-facing states. The investigation shell
provides a small resource toolbar and responsive drawer. Case Opening and
generic local Rules are functional and read-only. The later case-resource
foundation replaces its original hardcoded future buttons with validated
case-specific maps, newspapers, directory, informants, and document
placeholders. No copyrighted asset or external resource backend is included.
A disabled composer presents human participation honestly as future work and
has no POST route.

`POST /investigations/{session_id}/finalize` now delegates to
`finalize_lead_investigation()`. Availability reflects the Lead/Visit minimum:
an active session, at least one visit, retained revealed information, and no
existing final theory. It has no round, analysis, hypothesis, or decision
prerequisite. Success commits the completed snapshot atomically and redirects
to the canonical page.

A completed investigation is a process-local read-only archive. Its Final
Theory and supporting revealed information are presented as game content;
Case Opening, resources, semantic leads, visits, and all stored messages remain
readable. Every Lead/Visit mutation and repeated finalization request returns
`409`, and all mutation controls are absent. Durable persistence remains future
work.

## Lead/Visit application pathway (redesign complete)

Task 1 of the case-catalogue integration adds immutable local
`CaseDefinition` records loaded from synthetic YAML. Catalogue-backed registry
creation accepts a stable `case_id`, copies that definition's opening into the
new session, and stores no complete case definition in runtime state. Multiple
sessions may use the same case independently. Tasks 2–5 complete lead-code
input, case resources, catalogue selection, and the Figma-aligned presentation.
Only synthetic case content is included.

The repository ships no copyrighted Sherlock case text, maps, newspapers, or
handouts. Later user-owned material is configuration work: add a validated
case file, declare explicit resources and safe local asset paths, preserve
availability flags, then rerun the offline catalogue/Lead/Visit/resource/E2E
regressions. It is not integrated until the user supplies that material.

Lead entry accepts a physical case reference rather than a player-authored
label and kind. London aliases such as `42nw`, `NW42`, and `NW-42` resolve to
`42 NW`; interior aliases such as `gf26` resolve to `GF-26`. The selected
`CaseDefinition` supplies the semantic lead key, label, and kind. Malformed
input is a `400`, a valid but unknown case reference is a `404`, and an
already-current lead is a `409`.

Syntax is classified against all supported schemes before case lookup. For
example, `GF-26` is valid syntax even for a London-only case and therefore
returns `404` when unavailable, not `400`. Normalization accepts only the
documented compact, single-space, and single-hyphen aliases; misplaced or
repeated separators remain malformed.

Entering a historical lead reference is a side-effect-free selection of the
existing semantic lead. It never creates a visit. The user must invoke the
existing internal-`lead_id` revisit route explicitly, which appends a new
`LeadVisit` while retaining the same lead identity and visible reference.

Case-aware resources are resolved from the session's selected case and the
shared local resource catalogue. Resource groups cover maps, newspapers,
directory, informants, documents, and handouts. A case exposes only its
explicit ordered references. Multiple maps receive a simple selector; one map
is presented directly. Missing optional assets display a placeholder, while
resources marked unavailable are not disclosed. Completed sessions retain the
same readable resource set.

The application creates an active investigation with `create_session()` and
supports these provider-neutral operations:

- `visit_lead()` creates and visits a caller-described lead, or revisits an
  existing lead by stable ID. Every call creates a chronological visit.
- `reveal_information()` appends one or more explicit Game Master disclosures
  with service-owned IDs. Disclosures remain globally available afterward.
- `continue_lead_discussion()` creates one bounded `ConversationRun`, attaches
  it to the selected visit, and may run repeatedly without analysis, decision,
  or visit-completion prerequisites.
- `project_lead_conversation()` returns deterministic logical history without
  mutating or merging stored runs.
- `build_lead_discussion_context()` renders the case opening, current lead and
  visit, global disclosures, visit chronology, and prior same-lead conversation
  directly from the immutable session snapshot.

All operations that append activity require the latest visit. After B is
visited, Visit A is historical and remains readable, but adding more A activity
requires `visit_lead(lead_a)` to create a new visit. This applies uniformly to
information, discussion, analysis, hypothesis, and decision writes.

Thus a caller can visit A, visit B, and revisit A with a new visit ID while
retaining the original A lead ID, both leads' disclosed information, and A's
earlier conversation. Generation failures leave the caller's prior immutable
snapshot unchanged. Provider replies remain discussion messages and never
become disclosed case information automatically.

Optional visit-aware reasoning is recorded through `record_visit_analysis()`,
`record_hypothesis()`, and `record_group_decision()`. None changes navigation
permission. `finalize_lead_investigation()` completes an active Lead/Visit
session from its opening, leads, visits, global information, discussions, and
optional reasoning. It requires no analysis, decision, hypothesis, or round.

Deterministic mock discussion lookup uses semantic participant/visit/segment/
turn task names. Lead/Visit finalization has a separate versioned prompt and
fixture. Fixture coverage is not a maximum enforced by the domain.

The older clue/analysis/discussion/decision/finalization operations are absent
from authoritative public exports and the active web layer. Their private
implementation remains only for historical application compatibility tests.

## Purpose

This document describes what the system should do from the point of view of its users.

The system supports the creation, simulation, and blind recognizability
evaluation of persona-seeded fictional-character agents. It also implements a
deterministic mock, user-moderated investigation capability in which the
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
- act as investigation Game Master through the local web interface by
  supplying an introduction, revealing clues, and explicitly requesting each
  reasoning phase and finalization.

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

## F10 — Moderated investigation domain

### Description

The historical Sprint 6 round workflow is framework-independent, stateless,
deterministic, mock-only, and caller moderated. It remains a private
compatibility path and is not the active browser workflow.

### Historical compatibility workflow

| Operation | Accepted state | Result | Provider calls and boundary |
|---|---|---|---|
| `create_session()` | valid introduction, participants, and ID factory | empty `active` session | none; validates the whole initial aggregate |
| `reveal_clue()` | `active`, all earlier rounds completed | one clue and `awaiting_analyses` round | none; freezes the ordered clue prefix |
| `run_independent_analyses()` | newest round `awaiting_analyses` | ordered analyses and `awaiting_discussion` | one call per participant; prompts precede calls; atomic structured results |
| `run_group_discussion()` | newest round `awaiting_discussion` | completed `ConversationRun` and `awaiting_decision` | one call per turn through `simulate_chat()`; no partial run attaches |
| `create_group_decision()` | newest round `awaiting_decision` | one decision and completed round; session remains `active` | exactly one structured group-provider call; returns control |
| `finalize_investigation()` | `active`, every round completed | final theory and `completed` session together | exactly one structured final-provider call; explicit atomic completion |

Generated content traverses `GenerationResult`, strict payload parsing,
service-owned IDs, domain records, and aggregate revalidation. Failures return
no partial snapshot. Round completion and session completion are distinct.

### Implemented records and workflow inputs

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
`completed`, and `abandoned` remain representable. Operational services use
`active`; only explicit finalization creates `completed`, and final theory and
completed status require each other.

Investigation persistence, CLI delivery, live providers, automatic clues or
lead execution, scoring, and recognizability evaluation remain future work.
The local deterministic browser delivery described below is implemented.

## F11 — Local moderated investigation web interface

### Description

The existing main FastAPI/Jinja application exposes the authoritative
Lead/Visit workflow to a Game Master. `GET /investigations` lists process-local
sessions and provides catalogue-backed creation. Each session is rendered at
one canonical `/investigations/{session_id}` detail page whose controls reflect
the latest immutable snapshot.

### Explicit browser flow

```text
create → visit lead A → reveal information and discuss → visit lead B
→ revisit lead A → continue its persistent thread → explicit finalization
→ completed read-only archive and final theory
```

Every mutation requires its own POST and successful mutations redirect with
`303` to the canonical detail page. GET and refresh are side-effect free.
Historical visits are read-only; an explicit revisit creates a new visit for
the same semantic lead. Discussion segments are repeatable while matching mock
fixtures exist, and fixture inventory is not a domain limit.

### State and error behaviour

- The main app owns an in-memory registry; sessions survive navigation within
  one process but disappear on restart.
- Investigation actions create no investigation JSON, JSONL, Markdown,
  database, or browser-storage records. Existing conversation persistence is
  unchanged and separate.
- Session runtimes and generated references are independently scoped to their
  deterministic `session_NNN` namespace.
- Invalid input, unknown sessions, stale/wrong-phase actions, and unexpected
  local failures render readable `400`, `404`, `409`, and `500` responses.
  Failed operations retain the latest valid snapshot.
- The deterministic mock flow requires no network access or OpenAI API key.

### Acceptance criteria

- Sherlock Holmes and Hercule Poirot are selected through the validated
  catalogue and displayed in configured participant order.
- Leads, visits, disclosed information, ordered discussion messages, resources,
  and the final theory remain visible as history accumulates.
- No action executes automatically, and completed sessions expose no mutation
  controls.
- Two sessions can be advanced independently without record or identifier
  leakage.

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
- investigation-domain models and provider-neutral application orchestration.

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

Sprint 5 does not introduce real API calls or retries. Its successful
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

The main app also provides the Sprint 7 investigation interface. It presents
only the currently valid explicit Game Master action, retains earlier-round
reasoning on the canonical session page, and uses small loading/double-submit
feedback without making JavaScript necessary for correctness. This is a local
mock workflow, not an authentication, deployment, durable-history, or live-
provider interface.

## Security and ethics

The project should avoid private personal data unless explicit consent and course approval are obtained. The first version uses fictional characters to reduce privacy risk.

## Memory and scheduling

Agents use explicit complete per-run conversation history as working memory and
no persistent memory. Multi-agent simulation currently uses deterministic
round-robin turn taking behind a replaceable selector; the future dynamic
manager is not part of Sprint 5.
