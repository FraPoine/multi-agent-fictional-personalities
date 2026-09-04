# Architecture

## Playable demo content boundary

`CaseCatalog` owns lobby and structural metadata. `CaseContentCatalog`
independently loads validated lead sections, gates, interactions, and initial
state from `configs/investigation/content/`; it never opens spoiler files.
Static definitions remain outside sessions. `CasePlayState` stores only flags,
items, choices, interaction completion, closures, budgets, applied section IDs,
outcomes, and an immutable accounting ledger. Section effects alone perform
transitions, and text enters agent context only through `RevealedInformation`.
Authored operations preflight modes, gates, closures, and budget before a visit
exists. Authored terminal effects complete the session without generating a
`FinalTheory`; those terminal representations are mutually exclusive.

`CaseDefinition` is the trusted source for selectable identity, opening, lead
references, and resource references. Session creation resolves the submitted
`case_id` server-side and snapshots the opening into `InvestigationSession`.
Players navigate with physical references; the service assigns the persistent
semantic `lead_id` and chronological `visit_id`. Demo 1 accounts narrative
paragraphs, Demo 2 accounts first visits, and Demo 3 accounts configured
variant visits plus authored budget adjustments.

## Resource consultation boundary

`configs/investigation/resources.yaml` owns visible resource metadata and safe
asset paths. `ResourceTextCatalog` separately owns verified public text and
provenance. Image GETs never mutate knowledge. Maps and floor plans are
player-only; agent-readable directory, newspaper, and informant text enters
later discussion or draft context only after `consult_case_resource()` records
an immutable same-case consultation. Consultation is allowed only during
active gameplay before any conclusion or authored outcome.

## Official conclusion spoiler firewall

Public definitions in `configs/investigation/conclusions/public/` may load at
startup. Private scoring and long solutions have separate directories and lazy
repositories. Scoring is opened only after answer lock; the solution is opened
only by explicit solution reveal. Private definitions are never placed in the
mock runtime or answer-draft prompts.

Official conclusions use `READY_FOR_FINAL` through draft, lock, and
player-confirmed deterministic scoring, which freezes gameplay. Explicit
solution reveal transitions to `COMPLETED`. Official conclusion, authored
outcome, and generated `FinalTheory` are mutually exclusive terminal paths.
Demo 1 retains the supplied 140-point answer-element total and printed Holmes
score of 100 with an explicit review note. Demo 3 supplies no conclusion data;
its exact revealed authored ending is the only terminal artifact.

## Lead/Visit web presentation

Sprint 7 adds a server-side presentation boundary in
`web/investigation_presentation.py`. It projects catalogue identities and an
immutable `InvestigationSessionRecord` into lobby, participant, resource, and
session view data; Jinja does not traverse legacy round state to decide the
new shell. Creation still runs through the existing registry, deterministic
runtime assembly, and application-level `create_session()` operation.

The detail shell reserves separate regions for chronological leads, central
case content, and resources. It presents Case Opening, active and historical
lead threads, final theory, and the completed archive. Legacy round mutation
routes and presentation helpers have been removed from the web layer.

Task 2 extends that presentation boundary with one sidebar item per semantic
`InvestigationLead`, visit counts/current state, and a selected-lead detail
projection. Query-string lead selection is read-only. Mutation routes use the
existing registry lock and immutable replacement protocol, delegating to
`visit_lead()`, `reveal_information()`, and `continue_lead_discussion()`.

The web projection groups information and messages beneath their originating
visit marker while `project_lead_conversation()` supplies the authoritative
semantic-thread ordering. Runtime participants provide catalogue identities;
run IDs, visit IDs, provider metadata, and task names are not displayed.

## Purpose

This document describes the conceptual architecture, main components, data flow, and public interfaces of the project.

This document distinguishes the completed offline conversation and
investigation application workflows, plus the implemented Sprint 7 local web
delivery, from later live-provider, durable-persistence, and experiment work.

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
                                      replaceable `SpeakerSelector`
                                        (`RoundRobinSelector` preserves order)
                              future: dynamic `ConversationManager` outside Sprint 5
                                                               │
                                                               ▼
                                                        Agent runtime
                                                               │
                                                               ▼
                                             Deterministic mock provider
                                      participant-owned responses
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
experiment. Selector abstractions, engine injection, participant-bound mocks,
structured generation results, investigation models, the deterministic Sprint
6 investigation application workflow, and its Sprint 7 browser delivery are
implemented. A dynamic manager, investigation persistence, and live provider
remain later work.

The implemented investigation dependency flow is:

```text
Main FastAPI investigation router / other caller
        ↓
Investigation application service
        ├── deterministic ID factory
        ├── versioned prompt loader and renderer
        ├── provider-neutral task names
        ├── participant/group mock providers
        ├── structured-output adapter
        └── simulate_chat() for discussion
                ├── RoundRobinSelector
                └── injected investigation turn generator
        ↓
Immutable InvestigationSession aggregate
```

Each operation reconstructs and validates one complete immutable snapshot or
raises without returning a partial update. A decision ends its round and pauses
the workflow; finalization is separate and explicit. No investigation
persistence or CLI is implemented. The web layer stores the latest snapshots
and their runtime dependencies only in an app-owned process-local registry.

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

`simulate_chat()` also accepts an optional generic `TurnReplyGenerator` callable.
When omitted, the engine continues to use `generate_participant_reply()` with
the standard conversation prompt and task exactly as before. An injected
generator receives the engine-selected participant, topic, run ID, timestamp,
zero-based turn index, and the complete immutable history tuple. It may choose
the prompt and provider task and generate that turn's `Message`; it cannot
select speakers, alter turn order, truncate stored history, stop the loop, or
construct the final run.

The engine revalidates every returned message and requires its run ID, turn
index, speaker, provider, and configured model to match the current selected
turn before appending it. Generator, provider, selector, and validation errors
propagate without retry or fallback. The investigation discussion operation
now uses this extension to reuse the conversation loop.

The application service owns the normal default policy: it constructs
`RoundRobinSelector` when callers do not inject a selector. CLI and web callers
therefore retain deterministic round-robin behavior without exposing selector
controls.

A future `ConversationManager` may implement dynamic selection. Rule-based,
LLM-based, content-dependent, priority-based, and investigation-specific
selection are all outside Sprint 5.

## Sprint 5 generation-result implementation

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

## Investigation prompt and structured-output infrastructure

Four UTF-8 prompt files now define the analysis, discussion, decision, and
final-theory context boundaries. Each begins with `Prompt-Version: 1` and has a
fixed, closed `{{placeholder_name}}` contract. The application-layer loader
resolves those files from the repository rather than the process working
directory. Rendering validates the complete contract, accepts string values
only, and performs one regex substitution pass over the original body, so
placeholder-like text inserted by a value remains literal. Separate helpers render
visible clues, analyses, hypotheses, decisions, and discussion messages in
their supplied order. In particular, visible-clue rendering resolves only the
explicit visibility tuple and fails on duplicates or unknown IDs, so later
session clues are not disclosed accidentally.

Provider-produced investigation content uses one application-layer adapter:

```text
GenerationResult
    ├── text ── model_validate_json(output payload schema)
    └── metadata ───────────────────────────────┐
                                                ▼
                              StructuredGenerationResult
                                  ├── validated value
                                  └── original GenerationResult
```

The payload schemas contain provider-authored content only. Authoritative
session, round, analysis, hypothesis, decision, and final-theory IDs remain
service-owned. The adapter retains the original immutable `GenerationResult`
and all its metadata without reconstructing it. It does not call providers,
retry, repair malformed JSON, remove Markdown fences, or extract JSON
substrings. Analysis, discussion, decision, and final-theory generation all use
this infrastructure.

## Deterministic investigation workflow fixtures

The focused `tests/fixtures/investigation/` directory contains eleven offline
outputs covering two rounds: one analysis and one discussion reply for each of
Sherlock Holmes and Hercule Poirot per round, one group decision per round, and
one final theory. Stable task names identify phase, participant, round, and
discussion turn; fixture selection never depends on invocation order or a
counter.

`build_investigation_mock_bindings()` creates participant-specific
`MockProvider` instances, plus explicitly injected decision and final-theory
providers. The participant mapping contains only the two existing character
IDs; group phases do not introduce a manager persona. All mappings use fixed
known filenames resolved from the repository independently of the working
directory.

Structured fixtures traverse the same planned production boundary:

```text
UTF-8 fixture → MockProvider → GenerationResult
             → parse_structured_generation() → provider payload schema
```

The files contain no service-owned record IDs beyond permitted references to
deterministic existing records. Round-one evidence uses only clue one;
round-two and final evidence may use clues one and two. Mock metadata and file
bytes are deterministic, and execution requires neither network access nor an
API key. These fixtures and the two-round E2E verify deterministic workflow
plumbing; they do not establish persona quality or scientific validity.

## Independent investigation analyses

`run_independent_analyses()` now implements the first generated investigation
phase. It accepts a fully validated active session, the existing ordered
persona/provider bindings, and the session's deterministic ID factory. Before
calling any provider, it revalidates one immutable pre-analysis snapshot and
renders every participant prompt from that same snapshot. Each prompt contains
the participant's own validated persona, the current round's exact visible-
clue tuple, and only completed history from earlier rounds. Current-round peer
outputs, discussion, decisions, and later clues are excluded.

Providers are then called once per `session.participant_ids` order with the
explicit participant-and-round analysis task name constructed by the
provider-neutral `investigation_tasks` module. Every `GenerationResult`
passes through `parse_structured_generation()` before the service assigns the
canonical analysis ID, session, round, participant, and visibility fields.
Analysis-phase hypotheses already permitted by the payload contract receive
service-owned deterministic IDs in the same atomic operation. Revision links
may target only hypotheses present in the pre-analysis snapshot, not hypotheses
created during the operation. The immutable
result returns the updated session plus the ordered structured generations, so
original text and metadata remain available.

Only after all prompts, generations, payloads, domain records, and IDs validate
does the service reconstruct the aggregate once and move the round to
`awaiting_discussion`. Any participant failure raises without returning a
partially updated session. Decision and finalization remain separate explicit
operations.

## Investigation group discussion

`run_group_discussion()` now implements the shared discussion phase for a
round whose complete ordered participant analyses are present. It revalidates
the immutable session, applies a strict 1–100 turn bound, and reuses
`simulate_chat()` with its Task 9 reply-generation extension. The default
selector is `RoundRobinSelector` in session participant order; callers may
inject another valid `SpeakerSelector` without transferring history or loop
ownership out of the engine.

The application-layer `InvestigationDiscussionReplyGenerator` renders the
versioned investigation discussion prompt on every selected turn. Its fixed
round context contains the case introduction, exact visible-clue snapshot,
all current-round analyses, permitted earlier completed history, and the
selected participant's persona. Its changing context is the complete ordered
message history supplied by the simulation engine. Each provider call uses an
explicit participant, round, and one-based discussion-turn task name, while
the conversation run uses the deterministic
`session_001_round_0001_discussion` namespace and a short round topic.

The complete validated `ConversationRun`, including per-message generation
metadata, is attached only after every turn succeeds. The service then moves
that round from `awaiting_discussion` to `awaiting_decision` in one aggregate
reconstruction. A failure attaches no partial run. Dynamic consensus behavior
and investigation persistence remain unimplemented; finalization is explicit
and separate from discussion.

## Investigation group decision

`create_group_decision()` implements the structured decision phase after a
completed, participant-consistent current-round discussion. It renders the
versioned decision prompt from the round's visible clues, ordered analyses,
temporally available hypotheses, and complete discussion transcript, then
calls one explicitly supplied provider with a provider-neutral deterministic
round task name. The shared structured-output adapter preserves the exact
generation result while the service assigns authoritative decision and any
optional hypothesis IDs and ownership.

References and append-only proposed hypotheses are validated against the
immutable pre-decision snapshot. A successful operation attaches exactly one
decision, marks only the round `completed`, leaves the session `active`, and
returns control. It does not execute the decision, reveal a clue, open another
round, persist records, or finalize the investigation; those actions remain
caller-controlled.

## Explicit investigation finalization

`finalize_investigation()` is the sole workflow operation that creates a
`FinalTheory` and changes a session from `active` directly to `completed`. The
caller must invoke it explicitly after every round is completed and at least
one valid decision and hypothesis exist. `ready_for_final` remains a compatible
domain label but is neither generated nor accepted as an operational trigger.

The service renders the versioned final-theory prompt from the last completed
round's maximum clue visibility, all session hypotheses in stored order, and
completed decisions in round order. It calls one explicitly supplied provider
with the stable provider-neutral `investigation.final_theory` task, parses the
result through the shared structured adapter, validates nonempty hypothesis and
evidence references, and assigns the service-owned deterministic final-theory
ID. The theory and completed status are inserted in one aggregate rebuild.
This historical round operation has no automatic finalization or official
scoring, and investigation sessions are not persisted. The active authored
Lead/Visit path has a separate official-conclusion service for Demos 1–2.
The main web application exposes this operation only through an explicit
finalization POST when the configured mock scenario is exhausted.

## Synthetic two-round workflow test

The offline end-to-end test uses an original case in which a researcher
disappears from a locked archive room. The caller reveals an open archive-room
window in round one, pauses after the first decision, then explicitly reveals
that wet soil below the window has no footprints for round two. The workflow
again pauses after its decision and completes only when the caller invokes
finalization. Committed mock fixtures drive every provider boundary with no
network or secrets. The service-level test verifies deterministic
orchestration, temporal clue visibility, metadata propagation, and aggregate
serialization. Separate HTTP E2E tests verify browser delivery; neither layer
provides persistence, live-provider support, scoring, or compatibility with
any commercial case.

Participant declarations provide the expected provider and optional configured
model; generation metadata provides the reported values. Agent runtime resolves
the effective message model, using configuration only when the provider omits
a model. The engine derives one effective run-level provider/model from the
generated messages and validates every message against it. Custom replies must
also match the selected participant's display name, and message IDs are unique
during simulation and in the `ConversationRun` aggregate. Heterogeneous
provider or model runs remain unsupported. Error-bearing legacy messages cannot
carry successful generation metadata.

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

## Lead/Visit investigation architecture (redesign complete)

The six-task local case-catalogue integration is complete; its current
verification boundary is recorded in
[`sprint_7_case_catalogue_completion.md`](sprint_7_case_catalogue_completion.md).

### Local case catalogue foundation

Static case configuration and runtime investigation state are separate:

```text
configs/investigation/cases/*.yaml
→ CaseDefinition
→ InMemoryInvestigationRegistry.create(case_id=...)
→ InvestigationSession(case_id, case_introduction snapshot)
```

`load_case_catalog()` reads local YAML files in deterministic filename order
and validates immutable `CaseDefinition` and `CaseLeadDefinition` models. Case
IDs are unique across the catalogue; lead keys and references are unique only
within their owning case. Definitions contain synthetic configuration, not
runtime visits, discussions, or conclusions.

Catalogue-backed creation resolves the selected `case_id` and copies the
definition's opening into `case_introduction`. The complete definition is not
stored in the aggregate. Consequently two sessions may independently reference
the same case, and later configuration changes cannot rewrite either session's
opening. The browser lobby renders one selectable card per local case and posts
only `case_id` plus the investigator selection. The server resolves the trusted
title and opening from the configured catalogue; browser-supplied opening text
is neither required nor used.

### Case lead reference resolution

Player-facing case references are configuration identities, not runtime IDs.
`CaseLeadDefinition.reference` is canonicalized according to its explicit
scheme, while `InvestigationLead.lead_id` remains the immutable session-scoped
identifier used in URLs and aggregate references. A created runtime lead copies
only `case_lead_key`, canonical `reference`, `label`, and `kind` from its case
definition.

`parse_supported_case_lead_reference()` first checks input against every
globally supported scheme using explicit conservative alternatives; validity
does not depend on which schemes the selected case happens to use. It never
deletes arbitrary separators. `resolve_case_lead()` then searches the selected
case for the parsed scheme and canonical reference. Thus malformed syntax is a
`400`, while structurally valid syntax absent from the case is a `404`.
`visit_case_lead()` creates a semantic lead and its
first visit only when that definition has not been visited. Resolving a
historical lead returns its existing identity without mutation; resolving the
current lead is a conflict. A revisit remains an explicit `visit_lead(lead_id=)`
operation, preserving A → B → A chronology without duplicating Lead A.

The normal lead-entry form accepts only the player-facing reference. An
unvisited reference creates the semantic lead and first visit, a historical
reference opens existing history without mutation, and revisit remains an
explicit action. URLs continue to carry internal `lead_id` values rather than
physical-game references.

### Case-aware resource catalogue

Shared local resource definitions live in
`configs/investigation/resources.yaml`. A `CaseResourceDefinition` has a stable
resource ID, structural type, title, optional safe relative asset path, optional
date, description, and `initially_available` flag. Case definitions reference
these reusable IDs explicitly and in display order; the catalogue rejects
unknown references before a session starts.

The supported types are map, newspaper, directory, informants, document, and
handout. Cases may reference zero, one, or multiple maps, and do not inherit all
configured newspapers automatically. Shared directory and informant resources
may be referenced by several cases without copying their definitions.

Presentation resolves resources from `InvestigationSession.case_id`. Hidden
resources are omitted, so configuring a handout asset does not disclose it.
One map renders directly; multiple maps preserve case order and use a small
drawer selector. Missing optional assets produce an honest local placeholder.
Case Opening and Rules remain application-level resources. No network access,
asset ingestion, or automatic unlock engine is involved.

The shipped catalogue is deliberately content-neutral: it contains only
synthetic openings, lead labels, and placeholder resource metadata. The
repository includes no copyrighted Sherlock case text, maps, newspapers, or
handouts. User-provided owned material can be integrated later by adding a
validated case YAML, declaring explicit shared resource IDs, and placing any
owned files under the catalogue's local asset root. Safe relative-path
validation and `initially_available` remain the boundaries; content ingestion,
OCR, and unlock automation are separate future work.

The FastAPI application loads one immutable `CaseCatalog` during
`create_app()`. That same object configures the default process-local registry
and is passed to the investigation router for creation, lead resolution, and
resource presentation. Injected registries remain supported, but the router
does not independently reload catalogue configuration.

The authoritative investigation-domain direction is now a persistent semantic
lead graph with a chronological visit history:

```text
InvestigationSession
├── case_id
├── case_introduction (immutable opening snapshot)
├── InvestigationLead[]
├── LeadVisit[]
└── RevealedInformation[]
```

An `InvestigationLead` is a session-owned semantic track such as a person,
place, informant, or topic. It persists independently of visits and has no
completed state. A `LeadVisit` is one globally ordered period of focus on an
existing lead. Consequently `A → B → A` creates three visits referencing two
leads; returning to A does not duplicate or reopen the lead. Visits have
contiguous one-based indexes and may reference zero or more bounded
conversation-run IDs. Task 2 stores and executes those bounded segments
through the existing conversation engine.

Only the latest visit accepts new chronological activity. Once a later visit
exists, earlier visits are immutable historical activity records: information,
discussion segments, analyses, hypotheses, and decisions cannot be appended to
them. Historical reads and same-lead projections remain available. Returning
to an earlier lead always creates a new `LeadVisit` before further activity.

`RevealedInformation` is the authoritative disclosure record. It has a stable
session-scoped ID and contiguous zero-based reveal index, remains globally
known, and may identify a source lead, source visit, or generic external source
pair. A visit can disclose any number of information records. When both a lead
and visit are supplied they must agree, and visit/information links are checked
in both directions. `EvidenceReference.information_id` targets these records.

Task 2 exposes stateless application operations over the graph. `visit_lead()`
either creates and visits a caller-described semantic lead or creates a new
visit referencing an existing lead ID. `reveal_information()` explicitly
appends one or more caller-controlled disclosures to a visit; provider output
never becomes authoritative information implicitly. Neither operation invokes
a provider or requires analysis, discussion, decision, or completion.

`continue_lead_discussion()` uses `simulate_chat()` and creates a new bounded
immutable `ConversationRun` each time. The aggregate stores runs in
`conversation_runs`, while each visit stores their ordered IDs. Segment IDs
are deterministic and visit-scoped, for example
`session_001_visit_0003_discussion_0002`. Existing segments are never extended
or concatenated. `project_lead_conversation()` returns logical same-lead
history in visit, run, and message-turn order.

Discussion context is rebuilt explicitly from each input snapshot. Its stable
sections contain the case opening, current lead and visit, all globally
revealed information, global visit chronology, and previous conversation from
the same semantic lead. Persona context remains supplied by the existing
participant runtime, and current-segment messages remain normal
`simulate_chat()` history. There is no hidden persistent LLM memory.

The immutable `InvestigationSession` aggregate owns and validates this graph:
unique IDs, session ownership, existing lead/visit targets, chronological
ordering, source consistency, and resolvable information evidence. It encodes
no fixed lead or visit maximum and imposes no analysis, discussion, decision,
or visit-completion phase.

Sprint 6 reasoning, deterministic mock execution, and explicit finalization now
have an authoritative Lead/Visit path. Analyses, hypotheses, and decisions are
optional visit-originated artifacts and never transition or complete a visit.
Their legacy round fields remain mutually exclusive compatibility alternatives.

`finalize_lead_investigation()` requires an active session with a visit and
explicitly revealed information. It does not require analyses, hypotheses,
decisions, or completed rounds. Its versioned prompt receives leads, visits,
global information, bounded discussions, and optional reasoning. The service
owns the final ID and strictly validates information and hypothesis references.

The deterministic mock exposes lead fixture references and available segments.
Semantic task names include participant, visit, segment, and turn. Fixture
coverage is not a domain maximum; additional leads and visits remain valid.
The committed coverage includes Visit 1 segments 1 and 2 plus segment 1 for
Visits 2 and 3; `available_discussion_segments` counts these four supported
visit/segment combinations rather than imposing a session-wide run limit.

The Sprint 7 web workflow uses only the Lead/Visit graph. `Clue`,
`InvestigationRound`, and `InvestigationRoundStatus` remain isolated private
compatibility fields so historical offline behavior and tests remain readable.
`EvidenceReference.clue_id` is accepted only for that legacy graph, with
exactly one of `information_id` or `clue_id` required. Round symbols and
services are excluded from authoritative public exports and are not imported
by the web layer.

## Sprint 5 investigation domain (historical foundation)

Sprint 5 models, but does not orchestrate, `InvestigationSession`, `Clue`,
`EvidenceReference`, `AgentAnalysis`, `Hypothesis`, `GroupDecision`, and
`FinalTheory`. The domain must represent a manually supplied case introduction,
progressively revealed clues and clue order, individual facts and deductions,
evidence references, supporting and contradicting evidence, active and
discarded hypotheses, proposed leads, group decisions, and a final theory.

`InvestigationSession` is the aggregate root: it validates collection IDs,
participant ownership, contiguous clue order, stable-ID references, and
append-only hypothesis history without executing agents. Clues contain only
game-master-revealed information, and complete nested entities are not copied
into references.

Sessions allow partial state. Statuses are `setup`, `active`,
`ready_for_final`, `completed`, and `abandoned`; only `completed` requires a
final theory. Investigation orchestration, persistence, prompts, UI, scheduling,
automatic disclosure, controllers, game loops, and a real game are future work.

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

## Investigation web delivery and process-local state

Sprint 7 mounts an investigation router in the same main FastAPI application
as the conversation UI. The blind-rater application remains separate. The
router provides the list/create page, one canonical state-driven detail page,
and explicit POST routes for lead visits, information disclosure, bounded
discussion, and finalization. Successful mutations use `303`
POST/Redirect/GET; GET routes only render the latest snapshot.

`InMemoryInvestigationRegistry` is injected by the application factory and
owns monotonic session allocation plus one record per process-local session.
Each `InvestigationSessionRecord` pairs the latest immutable domain aggregate
with its `InvestigationMockRuntime`; providers, participant bindings,
capabilities, and locks therefore remain outside the domain model. A
per-session lock reads the latest record, runs one application operation, and
atomically replaces the record only after a complete validated result. Locks
for distinct sessions are independent.

Runtime assembly resolves participants and presentation from the character
catalogue, constructs participant-specific fixture providers, and scopes mock
references to the owning `session_NNN` namespace. Semantic task names select
the committed visit/segment fixtures; fixture exhaustion is reported as a
local failure and is not interpreted as a domain visit or discussion limit.

The registry writes no investigation JSON, JSONL, Markdown, database, or
browser storage. Navigation works only while one application process remains
alive; restart discards all investigation sessions. This boundary is separate
from the unchanged conversation artifact persistence described elsewhere.
Validation, lookup, workflow conflicts, and unexpected local failures render
readable `400`, `404`, `409`, and `500` responses while retaining the last
valid registered snapshot.

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

`run.json` is the canonical complete run snapshot. `messages.jsonl` is the
canonical ordered per-turn generation trace, with one complete `Message` per
line. For new messages, both structured artifacts contain the same nested
generation metadata; legacy artifacts that omit it remain readable.
`transcript.md` intentionally excludes technical metadata. Mock metadata is
deterministic and mostly `null`; real token, latency, and request values depend
on future providers. There is no cost calculation or broader event-logging
system.

## Verified smoke-test path

The Sprint 5 closure verification exercised the current critical path:

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

Task 3 adds presentation-only resource definitions and a minimal JavaScript
drawer; no resource state enters the investigation aggregate. Only Case Opening
and Rules have content. Unsupported resources remain disabled metadata.

The existing `/finalize` route now uses the authoritative Lead/Visit
`finalize_lead_investigation()` service inside `registry.mutate()`. The service
generates and validates the immutable `FinalTheory` before replacement, so
provider or structured-output failures leave the prior snapshot registered.
Completed snapshots remain on the same detail route. Presentation suppresses
all mutation forms while routes independently reject stale direct POSTs.
