# Sprint 6 Plan — Deterministic Investigation Workflow Contract

> Historical notice: this document records the original round-based plan. The
> later Lead/Visit redesign is documented in
> `docs/sprint_6_redesign_completion.md`.

> **Status:** Completed and verified on 2026-08-06. Implementation evidence is
> recorded in the [Sprint 6 completion record](sprint_6_completion.md). The
> requirements below remain the historical technical contract.

## 1. Sprint objective

Sprint 6 defined a deterministic, offline, mock-driven investigation
workflow over the immutable investigation records delivered in Sprint 5. The
workflow must support at least two complete clue-revelation cycles, stop after
each completed round, and complete a session only when its caller explicitly
requests finalization.

This document was a technical contract for planned work, not a description of
the current implementation. At the time of writing, the repository had validated
investigation records and partial `InvestigationSession` snapshots, but no
`InvestigationRound`, investigation application service, structured-output
adapter, investigation prompts, fixtures, orchestration, persistence, or UI.
See the [architecture](architecture.md), [data model](data_model.md),
[functional specification](functional_spec.md), and
[Sprint 5 completion record](sprint_5_completion.md) for the current baseline.

## 2. Scope

Sprint 6 includes:

- investigation session creation;
- clue revelation controlled by the game master or calling orchestration layer;
- one independent analysis per participant in each round;
- deterministic shared discussion using round-robin speaker selection;
- explicit group-decision creation;
- a pause that returns control to the caller after every completed round;
- explicit investigation finalization;
- provider-generated JSON text parsed by an application-layer adapter;
- deterministic, offline execution through local mock fixtures; and
- automated model, unit, integration, regression, and two-round end-to-end
  tests.

The service boundary will be framework-independent, stateless, and independent
of persistence. Except for `create_session`, which has no prior session, every
operation receives an immutable session snapshot and returns a new, fully
validated snapshot. `create_session` returns the first validated snapshot.
Dependencies such as participant bindings, providers, the selector,
deterministic ID factory, and prompt loader are passed explicitly where needed.

## 3. Explicitly out of scope

Sprint 6 does not include:

- web UI development;
- investigation-workflow persistence;
- live LLM providers, network access, or API keys;
- dynamic manager-agent orchestration or content-dependent speaker choice;
- automatic clue generation or disclosure;
- automatic investigation finalization;
- additional fictional characters; or
- recognizability evaluation experiments.

None of these capabilities should be described as implemented by Sprint 6
work. Sprint 7 is the planned investigation UI increment. Persistence and
live-provider integration remain later work.

## 4. Public workflow operations

All public operations are pure with respect to the supplied aggregate: they do
not mutate it, retain hidden session state, write artifacts, or depend on a web
framework. They may call injected providers only where stated. Each operation
first validates its complete input snapshot and preconditions. It then builds
and validates all proposed records before reconstructing and validating the
whole aggregate.

### `create_session`

- **Required input:** nonblank case introduction; an ordered sequence of at
  least two unique participant IDs and their runtime bindings; and a
  deterministic ID factory initialized with an explicit session sequence or
  key.
- **Preconditions:** participant IDs and bindings agree exactly; all IDs are
  valid and unique; the ID factory can allocate a new session namespace.
- **Success:** returns a new `InvestigationSession` with a generated session ID,
  the supplied ordered participants, status `active`, and empty clues, rounds,
  analyses, hypotheses, decisions, and final theory.
- **Resulting state:** active session; no round exists.
- **Expected errors:** invalid or duplicate participants, fewer than two
  participants, mismatched bindings, invalid introduction, invalid or
  colliding session ID.
- **Provider calls:** none.
- **Atomicity:** either the complete initial aggregate validates and is
  returned, or no session is returned.

### `reveal_clue`

- **Required input:** an immutable session, nonblank game-master-supplied clue
  text, and the deterministic ID factory for that session.
- **Preconditions:** session is `active`; no incomplete round exists; the clue
  ID, round ID, zero-based clue `reveal_order`, and one-based `round_index` can
  be allocated without collision.
- **Success:** appends exactly one `Clue` and one `InvestigationRound`. The new
  round freezes all clue IDs in reveal order through the new clue.
- **Resulting state:** active session; newest round is `awaiting_analyses`;
  earlier rounds remain completed.
- **Expected errors:** completed or otherwise non-operational session, blank
  clue, incomplete previous round, invalid/duplicate generated IDs, invalid
  reveal order, or aggregate validation failure.
- **Provider calls:** none. The clue is never generated by a provider.
- **Atomicity:** clue and round are inserted together or neither is returned.

### `run_independent_analyses`

- **Required input:** immutable session; participant bindings/providers;
  analysis prompt renderer; structured-output adapter; and session ID factory.
- **Preconditions:** session is `active`; newest round is
  `awaiting_analyses`; exactly one round clue exists; participant bindings
  match the session; no current-round analysis exists; and the round's visible
  clue snapshot is valid.
- **Success:** obtains one structured result per participant, validates all
  analysis envelopes and any proposed hypotheses, appends exactly one
  `AgentAnalysis` per participant in participant order, and records their IDs
  on the round.
- **Resulting state:** active session; current round becomes
  `awaiting_discussion`.
- **Expected errors:** no revealed clue/round, wrong round status, unknown or
  missing participant, duplicate analysis, malformed or schema-invalid output,
  invalid evidence or IDs, future-clue reference, cross-session record,
  provider failure, or final aggregate validation failure.
- **Provider calls:** exactly one per participant, using the same immutable
  pre-analysis session snapshot. Calls are logically independent even if the
  first implementation executes them sequentially for determinism.
- **Atomicity:** operation-level all-or-nothing. A failure for any participant
  returns no updated session and exposes no session containing a subset of the
  analyses or hypotheses.

### `run_group_discussion`

- **Required input:** immutable session; ordered participant bindings;
  positive configured discussion turn count; `RoundRobinSelector`; injectable
  investigation reply-generation strategy; seed and deterministic run inputs.
- **Preconditions:** session is `active`; current round is
  `awaiting_discussion`; exactly one valid current-round analysis exists for
  every participant; and the round has no `discussion_run`.
- **Success:** returns a completed `ConversationRun` containing the configured
  number of messages, all generated from the discussion context and existing
  runtime metadata contracts.
- **Resulting state:** active session; discussion run is attached to the round,
  whose status becomes `awaiting_decision`.
- **Expected errors:** missing/duplicate/foreign analysis, wrong round status,
  invalid discussion configuration, selector error, participant mismatch,
  provider/generation failure, incomplete or invalid `ConversationRun`, or
  aggregate validation failure.
- **Provider calls:** one per configured discussion turn through the selected
  participant's provider and injected reply strategy.
- **Atomicity:** no partial discussion is attached. The complete run and new
  aggregate validate before return.

### `create_group_decision`

- **Required input:** immutable session; decision prompt renderer; decision
  provider; structured-output adapter; and session ID factory.
- **Preconditions:** session is `active`; current round is
  `awaiting_decision`; its discussion is completed; all participant analyses
  are present and valid; and the round has no decision.
- **Success:** parses and validates one `GroupDecision` envelope and any new or
  revised hypotheses, appends them, attaches the decision ID to the round, and
  completes the round.
- **Resulting state:** active session with current round `completed`. The
  operation stops and returns control; it does not reveal a clue or finalize.
- **Expected errors:** wrong round/session state, missing or incomplete
  discussion, missing participant analysis, second decision, malformed or
  invalid structured output, unknown/cross-round analysis, unknown or
  cross-session hypothesis, invisible evidence, invalid revision link,
  provider failure, or aggregate validation failure.
- **Provider calls:** exactly one.
- **Atomicity:** decision, associated hypotheses, round completion, and the
  rebuilt session are committed to the returned snapshot together or not at
  all.

### `finalize_investigation`

- **Required input:** immutable session; final-theory prompt renderer;
  finalization provider; structured-output adapter; and session ID factory.
- **Preconditions:** session is `active`; at least one round exists; every
  round is completed; no operation is pending; no final theory exists; and
  the session contains at least one valid hypothesis and visible evidence that
  can support a final theory.
- **Success:** parses and validates exactly one `FinalTheory`, attaches it, and
  changes status to `completed`.
- **Resulting state:** completed and terminal session; all rounds remain
  completed.
- **Expected errors:** already completed or non-operational session, no rounds,
  incomplete round, pending discussion/decision, existing final theory,
  malformed/invalid output, missing or foreign hypothesis/evidence reference,
  provider failure, or aggregate validation failure.
- **Provider calls:** exactly one.
- **Atomicity:** final theory and completed status appear together only after
  record and aggregate validation; failure returns no updated session.

## 5. Session state machine

The implemented `InvestigationStatus` enum currently contains `setup`,
`active`, `ready_for_final`, `completed`, and `abandoned`. Sprint 5 did not
define transition operations, and its model accepts partial snapshots in the
first four non-completed statuses.

Sprint 6's public workflow has this narrower operational state machine:

```text
create_session → active
active --finalize_investigation--> completed
completed → terminal
```

- `create_session` produces `active`, not `setup`.
- Completing one or many rounds leaves the session `active`.
- Only explicit `finalize_investigation` produces `completed`.
- A completed session rejects clue, analysis, discussion, decision, and
  finalization operations.
- A fixed round count never implies completion.

For compatibility, Sprint 6 may retain the existing enum members, but the
workflow service must reject `setup`, `ready_for_final`, and `abandoned`
snapshots as non-operational inputs. No Sprint 6 operation produces them. This
is a proposed service-level restriction, not current behavior. If later model
work removes or deprecates those unused values, that schema change must include
compatibility tests and documentation; it is not part of this planning task.

## 6. `InvestigationRound` model

`InvestigationRound` is the planned aggregate section that binds exactly one
clue-revelation cycle to its independently generated analyses, shared
discussion, and group decision. It prevents session-wide collections from
losing temporal and round ownership.

Proposed minimum fields are:

```text
InvestigationRound
├── session_id
├── round_id
├── round_index
├── revealed_clue_id
├── visible_clue_ids
├── analysis_ids
├── discussion_run: ConversationRun | None
├── decision_id: str | None
└── status: InvestigationRoundStatus
```

`round_index` is one-based and contiguous in session order. Clue
`reveal_order` remains the existing zero-based contiguous field. The two are
related by `round_index == reveal_order + 1`. `visible_clue_ids` and
`analysis_ids` are ordered immutable tuples. Discussion reuses the existing
`ConversationRun`, `Message`, and generation metadata models; no second
message-history abstraction is introduced.

Proposed statuses and legal transitions are:

| From | Operation and preconditions | To and result |
|---|---|---|
| no round | `reveal_clue`; active session and all prior rounds complete | `awaiting_analyses`; new clue and frozen visibility snapshot exist |
| `awaiting_analyses` | `run_independent_analyses`; exactly one valid result for every participant | `awaiting_discussion`; ordered `analysis_ids` is complete |
| `awaiting_discussion` | `run_group_discussion`; all analyses valid and no run attached | `awaiting_decision`; one completed `ConversationRun` is attached |
| `awaiting_decision` | `create_group_decision`; completed run and one valid decision | `completed`; one `decision_id` is attached |
| `completed` | no round mutation is allowed | remains terminal |

Status invariants must make impossible states invalid: later-stage fields are
absent before their stage, `analysis_ids` is empty or complete rather than
partial, discussion exists only from `awaiting_decision` onward, and a decision
exists exactly when the round is completed.

## 7. Round lifecycle and stopping points

Each cycle is exactly:

1. Reveal exactly one new clue.
2. Create one new round.
3. Freeze the ordered visible-clue snapshot for that round.
4. Generate one independent analysis per participant.
5. Run the shared group discussion.
6. Create one group decision.
7. Mark the round completed.
8. Stop and return control to the caller.

The workflow never automatically reveals another clue or finalizes the
investigation. `reveal_clue` is legal only when every earlier round is
completed. The caller may then reveal another clue or explicitly finalize.

## 8. Visibility rules

For round `N`, `visible_clue_ids` contains exactly the IDs of clues revealed in
rounds 1 through `N`, in clue reveal order. It is frozen when the round is
created and cannot be extended when later clues are revealed. Every participant
in that round receives the same tuple and corresponding clue content.

All current-round analyses are generated from the same immutable pre-analysis
session snapshot. No analysis prompt includes any current-round peer analysis,
and provider calls do not incrementally update the snapshot. An analysis may
use results of earlier completed rounds only when that history is explicitly
included in its prompt context. Its evidence references are restricted to its
own `visible_clue_ids`; consequently, an earlier analysis can never reference a
later clue.

`AgentAnalysis` is proposed to add:

- `session_id`;
- `round_id`; and
- `visible_clue_ids`.

This deliberate duplication makes an analysis independently auditable without
reconstructing visibility from the latest session. Aggregate validation must
also prove that the tuple exactly matches its owning round, rather than merely
being a subset of current session clues.

## 9. Session isolation

Every round-bound generated record carries its owning `session_id`.
`InvestigationRound`, `AgentAnalysis`, `Hypothesis`, and `GroupDecision` must
have session ownership; analyses and decisions additionally carry `round_id`.
Hypotheses may be created or revised in a round and should also record their
originating `round_id` so temporal evidence can be checked. A final theory is
owned by its containing session and has a deterministic session-scoped ID; an
additional `session_id` field is optional if aggregate containment and its
namespace provide equivalent validation.

Aggregate validation rejects a record whose `session_id` differs from the
containing session, whose `round_id` is absent or belongs to another session,
or whose referenced records are outside that ownership boundary. Tiny
`EvidenceReference` objects remain only `(clue_id, relation)`; redundant
session IDs are not added because the owning record and aggregate validate the
reference.

## 10. ID ownership and namespace

An injected, stateless `DeterministicInvestigationIdFactory` owns ID creation.
The service asks it for IDs; providers never invent authoritative IDs, and
callers do not supply IDs for generated nested records. `create_session`
receives an explicit deterministic session sequence/key, allowing the factory
to create the session namespace without randomness. Services overwrite or
reject any provider-supplied identity fields according to the adapter schema;
the preferred structured payload omits authoritative IDs entirely.

The canonical human-readable format is:

```text
session_001
session_001_clue_0001
session_001_round_0001
session_001_analysis_sherlock_holmes_0001
session_001_hypothesis_0001
session_001_decision_0001
session_001_final_theory
```

Discussion run/message IDs use the same namespace, for example
`session_001_round_0001_discussion` and
`session_001_round_0001_discussion_msg_0001`. Character IDs are normalized only
through the already validated catalog identity; two normalized participant
tokens must not collide.

IDs must be deterministic, human-readable, valid under the repository's safe
identifier rules where reused by conversation models, unique within their
session/type namespace, and stable across identical mock runs. Allocation uses
collection order and the one-based round index, never `uuid4`, wall-clock time,
provider text, or mutable process-global counters. The factory must detect a
collision against the supplied snapshot and fail before insertion.

## 11. Structured provider outputs

The provider contract remains unchanged:

```text
LLMProvider.generate(prompt, task_name) → GenerationResult
GenerationResult.text                → JSON text
application structured-output adapter → parsed object
Pydantic output model                 → validated structured data
domain service                        → validated aggregate insertion
```

Investigation parsing belongs in an application-layer adapter, not
`MockProvider`. Domain schemas and aggregate validation remain provider-neutral.
The adapter should expose task-specific payload models for analysis (and
optional hypotheses), decision (and optional hypotheses), and final theory.
Those payloads omit service-owned IDs and ownership fields.

Behavior is explicit:

| Failure | Required behavior |
|---|---|
| malformed JSON | raise a structured-output parse error; no fallback to plain text |
| valid JSON, invalid schema | raise an output-schema validation error |
| unknown fields | reject them (`extra="forbid"`) |
| missing required fields | reject through Pydantic validation |
| invalid IDs/evidence references | reject during service enrichment or aggregate validation |
| provider exception | propagate or wrap with operation, task, and participant context while preserving the cause |

The adapter returns both validated domain payload and the exact
`GenerationMetadata`. The proposed record extensions place that metadata on
the record created by the call: `AgentAnalysis.generation_metadata`,
`GroupDecision.generation_metadata`, and
`FinalTheory.generation_metadata`. Hypotheses produced in an analysis or
decision envelope are auditable through the owning analysis/decision call and
do not duplicate its metadata. Discussion metadata remains on each existing
`Message`. Metadata must not be discarded merely because `text` is parsed as
JSON. If an operation later fails, its successful intermediate metadata may be
diagnostic exception context but must not appear in an updated session.

## 12. Prompt boundaries

Later Sprint 6 tasks will create, version, and hash these files:

- `prompts/investigation_analysis.md`;
- `prompts/investigation_discussion.md`;
- `prompts/investigation_decision.md`; and
- `prompts/investigation_final_theory.md`.

This task does not create them. Their context boundaries are:

- **Analysis:** persona, case introduction, current round identity, identical
  ordered visible clues, and explicitly selected outcomes from previous
  completed rounds. It never contains current-round peer analyses.
- **Discussion:** persona, case introduction, current round visible clues, all
  validated current-round analyses in session participant order, relevant
  prior completed-round outcomes, and the discussion history accumulated so
  far.
- **Decision:** case introduction, current visible clues, every validated
  current-round analysis, and the completed current-round discussion. Prior
  valid hypotheses may be included for revision/reference.
- **Final theory:** case introduction, all completed rounds and decisions, all
  valid hypotheses, and all evidence visible by the final completed round.

No prompt receives unrevealed clue content. Prompt construction is separate
from provider I/O and records a stable prompt identifier/hash wherever the
planned generation trace stores metadata.

## 13. Conversation runtime reuse

Group discussion reuses the existing ordered participants,
`SpeakerSelector`, deterministic `RoundRobinSelector`, `ConversationRun`,
`Message`, and generation metadata. It should preserve the current rule that a
selector chooses only a participant ID and owns no prompts, generation,
history, investigation reasoning, or persistence.

The existing `simulate_chat()` currently constructs generic agent-reply
prompts through `generate_participant_reply`. It will likely need an injected
reply-generation strategy so the same engine can construct investigation
discussion replies without hardcoding investigation behavior into the generic
conversation engine. The default strategy must preserve all existing
conversation behavior and tests. This refactoring is planned for a later
Sprint 6 task and is not implemented here.

## 14. Hypothesis and decision rules

- Every hypothesis belongs to one session and originates in one round.
- A hypothesis is created or revised using only that round's visible evidence.
- Revisions are append-only: `previous_hypothesis_id` points to an earlier
  hypothesis in the same session and an earlier record position; it never
  points forward or to itself.
- A revised hypothesis receives a new deterministic ID; the old record is not
  mutated.
- Every decision belongs to exactly one session and round.
- A decision references only analyses whose `round_id` equals its round and
  includes no duplicate analysis ID.
- Referenced hypotheses exist in the same session and are temporally available
  by that round.
- Decision evidence belongs to the round's `visible_clue_ids`.
- Each round has zero decisions before its decision stage and exactly one when
  completed; a second decision is invalid.
- Round completion requires that decision and all of its references to validate
  in the rebuilt session aggregate.

## 15. Finalization rules

Finalization is always caller-triggered. It is permitted only when:

- the session is `active`;
- at least one round exists;
- every existing round is `completed`;
- no analysis, discussion, or decision operation is pending;
- no final theory already exists;
- at least one same-session hypothesis exists; and
- the generated theory contains at least one evidence reference and references
  only valid hypotheses and evidence from the same session.

On success the operation creates exactly one deterministic `FinalTheory`,
validates all references against the final visible-clue set and hypothesis
collection, attaches it, and changes the session to `completed` in the same
aggregate reconstruction. The completed snapshot rejects every later mutation,
including a second finalization attempt. The workflow never infers completion
from executing a fixed number of rounds.

## 16. Error catalogue

Errors should use stable application/domain exception categories with precise
messages and preserve underlying provider/Pydantic causes. No listed condition
may be silently ignored.

| Condition | Rejecting operation(s) |
|---|---|
| duplicate/invalid session or generated ID | `create_session`; any operation allocating a record |
| duplicate participants | `create_session` |
| unknown participant or binding mismatch | `create_session`, `run_independent_analyses`, `run_group_discussion` |
| clue revealed while previous round incomplete | `reveal_clue` |
| analysis before any clue/round | `run_independent_analyses` |
| duplicate analysis for participant and round | `run_independent_analyses`; aggregate validation |
| missing participant analysis | `run_independent_analyses`, `run_group_discussion`, `create_group_decision` |
| future-clue reference | analyses, decision, hypothesis, and finalization operations |
| unknown clue reference | analyses, decision, hypothesis, and finalization operations |
| cross-session record/reference | every operation accepting or creating nested records |
| discussion before all analyses exist | `run_group_discussion` |
| decision before completed discussion | `create_group_decision` |
| multiple decisions for one round | `create_group_decision`; aggregate validation |
| finalization with incomplete round | `finalize_investigation` |
| finalization without valid evidence or hypotheses | `finalize_investigation` |
| operation on completed session | all six operations except initial `create_session`, as applicable; finalization also rejects repeat |
| malformed structured output | `run_independent_analyses`, `create_group_decision`, `finalize_investigation` |
| valid JSON with invalid/extra/missing fields | same structured-generation operations |
| provider failure | every operation documented as making provider calls |

Wrong round status, invalid transition, duplicate clue, inconsistent visible
snapshot, foreign round, invalid hypothesis revision, and invalid/incomplete
discussion run are distinct validation failures even where they share an
operation above.

## 17. Atomicity and immutability

- Existing session and nested snapshots are never mutated.
- Each successful operation constructs and returns a new, fully validated
  aggregate.
- A failed operation returns no updated aggregate.
- Every generated record is JSON-parsed, payload-validated, enriched with
  service-owned IDs/ownership/metadata, domain-validated, and aggregate-
  validated before insertion.
- Multi-agent analysis generation is atomic at service-operation level. If one
  participant fails, no snapshot containing only other participants' analyses
  is returned.
- Clue plus round creation, discussion plus round transition, decision plus
  hypotheses plus completion, and final theory plus completed status are each
  indivisible in their returned snapshots.

Implementation should reconstruct models through normal validated constructors
or `model_validate`. It must not rely on unchecked
`model_copy(update=...)`, which can bypass aggregate validators.

## 18. Testing strategy for later tasks

Later tasks will add:

- model unit tests for new fields, enums, immutable collections, and aggregate
  invariants;
- state-transition tests for every legal and illegal session/round edge;
- temporal-visibility and cross-session isolation tests;
- structured-output parsing tests for malformed JSON, strict schemas,
  references, and metadata preservation;
- service orchestration and atomic-failure tests, including one failed member
  of multi-agent analysis generation;
- conversation-engine regression tests for the injectable reply strategy and
  unchanged default behavior;
- a deterministic two-round end-to-end test; and
- the complete existing offline regression suite.

The main end-to-end scenario is:

1. Create an active session with Sherlock Holmes and Hercule Poirot.
2. Reveal clue 1.
3. Generate both independent analyses from the same snapshot.
4. Run deterministic round-robin discussion.
5. Create group decision 1 and verify round 1 completes.
6. Confirm the workflow pauses and the session remains active.
7. Reveal clue 2.
8. Repeat analyses, discussion, and decision for round 2.
9. Confirm both rounds are complete but the session is still active.
10. Explicitly finalize the investigation.
11. Confirm exactly one final theory and a completed, terminal session.

The test must prove round 1's round and analysis snapshots exclude clue 2,
both participants had identical round-specific visibility, analysis prompts
excluded peer current-round output, speaker order followed configured
round-robin selection, and two runs with identical inputs/fixtures produce
equivalent domain outputs, conversation outputs, IDs, and metadata. Any
explicit creation timestamp should be fixed in the fixture or excluded only
from a clearly documented equivalence comparison.

## 19. Sprint 6 Definition of Done

Sprint 6 is complete only when:

- the framework-independent workflow runs deterministically and offline;
- one session completes at least two full rounds;
- temporal visibility is exact and earlier records cannot see future clues;
- session and round ownership prevent cross-session record movement;
- each participant produces an independent current-round analysis;
- discussion reuses deterministic `RoundRobinSelector` and conversation models;
- each completed round has exactly one valid group decision;
- finalization is explicit and is the only path to `completed`;
- all generated JSON is strictly parsed and schema/domain validated;
- successful generation metadata is preserved at the correct record boundary;
- generation, parsing, transition, and aggregate failures are atomic;
- mock critical paths perform no network access and require no API key;
- all new model, unit, integration, orchestration, regression, and deterministic
  two-round end-to-end tests pass;
- the full pre-existing suite still passes; and
- documentation is updated only after implementation to distinguish newly
  implemented behavior from remaining plans.

Completion does not depend on persistence, a web UI, a live provider, a
dynamic manager, more characters, or recognizability experiments.

## 20. Implementation sequence

The remaining Sprint 6 work follows these dependency-ordered tasks:

1. **Workflow contract** — this document.
2. **Round model** — add `InvestigationRound`, its status enum, aggregate
   containment, and invariants.
3. **Temporal visibility** — add analysis round/session ownership and frozen
   clue snapshots with validation.
4. **Round-aware hypotheses and decisions** — add ownership, temporal
   reference, revision, and one-decision-per-round rules.
5. **Service skeleton and state transitions** — add the stateless application
   boundary, deterministic ID factory, non-generating operations, and atomic
   aggregate rebuilding.
6. **Structured-output adapter** — strictly parse `GenerationResult.text`,
   validate task payloads, and preserve metadata outside providers.
7. **Deterministic mock fixtures** — add local JSON fixtures for each task and
   failure case without network dependencies.
8. **Independent analysis generation** — generate all participant analyses
   from one snapshot with operation-level atomicity.
9. **Injectable conversation reply generation** — generalize the engine while
   preserving its current default path and regression behavior.
10. **Group discussion** — reuse participants, `RoundRobinSelector`,
    `ConversationRun`, `Message`, and metadata with investigation context.
11. **Group decision and pause** — validate one decision, complete its round,
    and return control without advancing.
12. **Explicit finalization** — validate one final theory and perform the sole
    active-to-completed transition.
13. **Deterministic two-round end-to-end test** — execute and compare the
    complete Sherlock/Poirot mock scenario.
14. **Regression and documentation closure** — run the full offline suite and
    update active documentation only for behavior actually delivered.
