# Sprint 5 Plan

## Context

Sprint 4 delivered a local mock conversation CLI and FastAPI/Jinja interface.
Subsequent work added a two-character, mock-only technical blind-evaluation
pilot. Neither synthetic conversation fixtures nor technical pilot responses
are scientific evidence. Sprint 5 therefore completes the offline technical
foundation before any live-provider integration, experiment, or real game.

The development order is:

```text
complete the technical offline foundation
→ integrate a real LLM provider later
→ run experiments and investigation sessions afterward
```

## Final project goals

1. **Persona recognizability:** build four fictional-detective agents and test
   whether blind raters attribute generated messages correctly above chance.
   This remains the primary quantitative experiment and measures observable
   recognizability, not authentic identity or understanding.
2. **Multi-agent investigative interaction:** let the agents participate in a
   user-moderated game of *Sherlock Holmes: Consulting Detective*. The user is
   game master, supplies the introduction, reveals clues progressively, and
   controls access to unrevealed information. The game is a second system
   capability and a setting for qualitative or exploratory observations, not a
   replacement hypothesis.

## Sprint objective

Realign the project and create an end-to-end, deterministic, offline foundation
for configurable participants, replaceable speaker selection, structured
generation results, existing evaluation tooling, and investigation-domain
models. Sprint 5 adds no live provider, character, experiment, or playable
investigation.

## Current implementation baseline

- Sherlock Holmes and Hercule Poirot are the only supported runtime characters.
- Persona and response fixtures are deterministic and local.
- `Message` and `ConversationRun` are immutable validated models.
- Each complete run contains explicit, ordered per-run history.
- `simulate_chat()` supports an ordered sequence of at least two unique
  personas and directly schedules deterministic round-robin turns.
- The CLI and local conversation UI reuse application/runtime logic.
- Conversation persistence atomically writes `run.json`, `messages.jsonl`, and
  `transcript.md`.
- The two-character blind-evaluation pilot is technical, mock-only, and
  offline; it cannot establish recognizability.
- Tests require no API key or network access.
- Providers currently return plain text, and the conversation mock associates
  fixture order with one provider-wide call counter.
- No live provider, dynamic manager, investigation domain or workflow, third
  or fourth runtime character, real game, or final experiment exists.

## In-scope objectives

1. Realign goals and current high-level documentation.
2. Generalize configuration and application boundaries for a configurable
   participant sequence with a minimum of two.
3. Isolate speaker choice behind `SpeakerSelector` while preserving round-robin
   behavior through `RoundRobinSelector`.
4. Introduce `GenerationResult`, validation, deterministic mock metadata, and
   basic offline observability propagation.
5. Model investigation sessions and related entities, including valid partial
   states, without building the investigation cycle.
6. Run a final complete offline regression across conversation, scheduling,
   metadata, persistence, evaluation, and investigation models.

## Target architecture

```text
CLI / conversation web
          │
          ▼
application boundary with configurable participants
          │
          ▼
`simulate_chat()` conversation-engine boundary
          │
          ▼
SpeakerSelector
    ├── RoundRobinSelector
    └── future ConversationManager
          │
          ▼
participant-owned provider configuration
          │
          ▼
GenerationResult → Message → ConversationRun → atomic artifacts

separate Sprint 5 domain: investigation models with partial session states
```

`simulate_chat()` may remain the practical engine boundary. A concrete
`ConversationEngine` class is neither currently implemented nor mandatory.

## Architectural decisions

### Speaker selection

- `SpeakerSelector` chooses only the next speaker.
- `RoundRobinSelector` preserves current deterministic behavior for two or more
  configured participants.
- The selector does not own generation, prompt construction, conversation
  history, investigation reasoning, or persistence.
- A future `ConversationManager` may implement dynamic selection, but
  rule-based, LLM-based, content-dependent, priority-based, and investigation-
  specific scheduling are outside Sprint 5.

### Generation result

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

`GenerationResult` represents success. It has no nullable `error`; provider
failures continue to fail loudly through exceptions. A separate failure entity
may be introduced later if failures need persistent records. Existing top-level
`Message.provider` and `Message.model` fields may remain for compatibility when
optional structured metadata is added, but duplicated values must be validated
for consistency.

Mock metadata must be deterministic. Sprint 5 does not collect real token
counts, latency, request IDs, retry observations, or monetary cost. Cost
calculation is future work.

### Participant-bound mock responses

Mock responses must be associated with their owning participant instead of a
global provider call counter. Speaker order and fixture order are separate:
changing the selector must not give Sherlock's response to Poirot or vice
versa. A runtime participant may conceptually bind persona, provider, provider
name, and model name, but the exact entity and class name remain implementation
decisions.

### Investigation domain

Sprint 5 will model concepts such as `InvestigationSession`, `Clue`,
`EvidenceReference`, `AgentAnalysis`, `Hypothesis`, `GroupDecision`, and
`FinalTheory`. Together they must support the case introduction, progressively
revealed clues and their order, individual facts and deductions, evidence
references, supporting and contradicting evidence, active and discarded
hypotheses, proposed leads, group decisions, final theory, and session status.

Partial sessions must be valid. Statuses may be conceptually similar to
`setup`, `active`, `ready_for_final`, `completed`, and `abandoned`. Only a
completed session requires a final theory.

## Ordered task plan

1. Realign active goals, scope, roadmap, and Sprint 5 documentation.
2. Generalize configuration and application inputs for configurable
   participants while preserving the two working characters.
3. Add and test the speaker-selection contract and deterministic selector.
4. Separate mock fixture ownership from speaker order.
5. Add and propagate structured successful generation results and deterministic
   mock metadata.
6. Add and validate investigation-domain models and partial session states.
7. Run focused checks throughout, then the complete offline regression and
   reconcile active documentation.

Each later task should remain independently reviewable and must validate its
design against the implementation present at that time.

## Compatibility requirements

- Existing Sherlock/Poirot CLI and web commands remain valid.
- Existing deterministic speaker order and complete history remain stable.
- Existing run and message serialization remains readable; any schema change
  requires an explicit compatibility path.
- `run.json`, `messages.jsonl`, and `transcript.md` remain the canonical
  conversation artifacts and retain atomic persistence guarantees.
- Provider failures continue to propagate rather than becoming successful
  results with error fields.
- Mock execution remains the default and requires no secret or network.
- Sprint 5 adds no character fixture, UI option, or evaluation candidate.

## Test strategy

All Sprint 5 behavior is exercised offline with deterministic fixtures. Tests
will cover configurable participant sequences (minimum two), round-robin
selection, selector responsibility boundaries, participant-owned mock
responses, generation-result validation and metadata propagation, artifact
compatibility, evaluation regressions, and investigation models including
partial and completed states. The final task runs the complete offline suite.

## Explicitly out of scope

- OpenAI or any live-provider adapter and real provider calls;
- API keys, network access, real token/cost collection, and cost calculation;
- a dynamic conversation manager or non-round-robin policy;
- new persona data or a third/fourth runtime character;
- real pilot material, genuine human responses, or an LLM-judge panel;
- the final recognizability experiment or scientific claims;
- investigation orchestration, persistence, prompts, scheduling, UI, or a real
  *Consulting Detective* session.

The final rater methodology remains unresolved. Human blind evaluation is the
preferred direct interpretation; an LLM-judge panel is a possible course-
aligned or feasibility alternative with shared-model and training-data biases.
The choice, sample size, character/candidate design, chance baseline, and
analysis will be pre-registered before data collection. Pilot, human, and LLM-
judge results will not be pooled without a predefined design.

## Definition of Done

Sprint 5 is complete when:

- active documentation consistently records both final goals and the offline-
  first sequence;
- configuration and application boundaries support a configurable participant
  sequence of at least two while runtime character support remains Sherlock and
  Poirot;
- `SpeakerSelector` and `RoundRobinSelector` preserve deterministic behavior;
- provider results use validated structured success data with deterministic
  mock metadata and loud exception failures;
- mock responses belong to their participants independently of speaker order;
- investigation models represent required information and valid partial states,
  with a final theory required only for completed sessions;
- existing conversation artifacts and technical evaluation tooling remain
  compatible; and
- the full test suite passes offline without an API key or network access.

Completion does not depend on a live provider, real metadata or cost, human or
LLM-judge responses, a real pilot, or a playable investigation.

## Future work

After Sprint 5, integrate and verify a real configurable provider; finalize and
implement characters three and four; pre-register and run the chosen
recognizability evaluation; implement investigation orchestration and
persistence; and run user-moderated investigation sessions. Scientific and
exploratory results must be reported separately according to the predefined
design.
