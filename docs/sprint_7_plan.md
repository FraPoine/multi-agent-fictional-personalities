# Sprint 7 Plan — Investigation Web UI Technical Contract

## 1. Sprint objective

Sprint 7 adds a local, server-rendered browser interface over the completed
Sprint 6 investigation application workflow. A Game Master must be able to
create and advance a deterministic mock investigation one explicit action at a
time, inspect every resulting immutable session snapshot, pause after each
group decision, and explicitly request finalization.

The web layer is a delivery and orchestration boundary. The existing
framework-independent operations remain the source of truth for phase
validation, clue visibility, analyses, discussion, decisions, and
finalization. Sprint 7 must remain fully usable offline with
`OPENAI_API_KEY` unset.

## 2. Current baseline

The repository currently provides:

- the stateless public operations `create_session()`, `reveal_clue()`,
  `run_independent_analyses()`, `run_group_discussion()`,
  `create_group_decision()`, and `finalize_investigation()`;
- immutable Pydantic investigation records and aggregate validation;
- deterministic, service-owned `session_NNN` and child identifiers;
- strict structured-output parsing with no repair or partial update;
- discussion through the existing `simulate_chat()` runtime and default
  `RoundRobinSelector`;
- a fixed two-participant, two-round mock fixture inventory; and
- one main FastAPI/Jinja conversation application in `web/app.py`, plus a
  separate blind-rater application with a different evaluation boundary.

The main web application currently exposes `/`, `POST /conversations`, static
assets, and `/health`. It has no investigation routes, registry, templates, or
persistence. The existing character catalogue contains Sherlock Holmes and
Hercule Poirot in canonical display order. The current investigation E2E uses
those characters, two discussion turns per round, and
`DeterministicInvestigationIdFactory(1)`.

Sprint 6's completion record reports a historical full-suite result of 757
passing tests. That result is baseline evidence, not a Sprint 7 result and must
not be presented as newly reproduced unless the suite is run again.

## 3. Scope

Sprint 7 includes:

- investigation routes mounted in the existing main FastAPI application;
- a create page and one state-driven canonical session page;
- catalogue-derived participant selection and presentation;
- explicit Game Master controls for every workflow transition;
- an application-owned, process-local in-memory session registry;
- session-scoped deterministic mock output assembly;
- explicit mock capability information for supported rounds and discussion
  turns;
- readable validation, conflict, fixture/provider, and internal errors;
- protection against repeated or concurrent execution of one session action;
- route, registry, foundation, full HTTP workflow, isolation, offline, and
  regression tests; and
- final documentation and manual smoke verification after implementation.

## 4. Non-goals

Sprint 7 does not include:

- disk or database persistence for investigations;
- restoring or resuming an investigation after process restart;
- an investigation CLI;
- live LLM/provider integration or an API-key workflow;
- third or fourth runtime character implementation;
- a dynamic conversation or speaker manager;
- investigation scoring or official-solution comparison;
- a real *Sherlock Holmes: Consulting Detective* case;
- a persona-recognizability study or scientifically interpretable evaluation;
- a major redesign of the conversation UI;
- a complex frontend framework;
- authentication, accounts, or multi-user isolation; or
- automatic clue revelation, analysis, discussion, decision, next-round
  creation, decision execution, or finalization.

## 5. Architectural decisions

### 5.1 One main application

The investigation UI must be added to the FastAPI application produced by
`create_app()` in `web/app.py`; Sprint 7 must not create a third independent
web application. Conversation and investigation delivery share that app and
its local navigation/static foundation. The rater app remains separate because
it preserves a blind evaluation boundary.

Investigation routes may live in a focused router/module, but that router must
be included by the main app factory and receive its dependencies explicitly.
Importing the web module must remain safe and must not execute an
investigation.

### 5.2 One state-driven detail page

`GET /investigations/{session_id}` is the canonical detail page. It renders the
latest immutable snapshot and derives the current workflow phase from session
status and the newest round status. It must expose only actions valid for that
snapshot and for the configured mock capability; it must not create separate
pages for each phase.

The page should present, in useful order:

- session ID, case introduction, status, participants, current round, and
  current phase;
- revealed clues in reveal order;
- participant analyses in participant order;
- optional hypotheses where they help interpret later actions;
- the ordered discussion transcript;
- the current round's group decision;
- a clear “waiting for the Game Master” state after a decision; and
- the final theory after explicit completion.

Provider metadata and low-value internal identifiers should not dominate the
primary UI. Stable IDs may appear where they clarify references or aid local
debugging.

### 5.3 Explicit transitions only

Every mutation corresponds to one submitted Game Master action and at most one
application operation. A successful group decision leaves the session
`active`, marks only its round `completed`, and returns control to the Game
Master. While the configured mock scenario still has supported rounds, the
page offers the next clue action. Once that mock scenario is exhausted, the
page instead offers explicit finalization. Neither transition happens
automatically. This browser flow reflects the mock runtime's capability and
does not impose a minimum-round invariant on the investigation domain.

Hiding invalid controls improves usability but is not authorization or phase
validation. POST handlers must still delegate to the application service and
handle stale, repeated, or manually constructed requests safely.

### 5.4 Application logic remains authoritative

Routes and templates must not reproduce or weaken:

- aggregate and workflow phase validation;
- immutable clue-prefix visibility;
- one-analysis-per-participant rules;
- prompt construction or structured-output validation;
- discussion generation or speaker selection;
- decision and hypothesis reference validation;
- final-theory requirements; or
- deterministic child-ID construction.

The web/runtime assembly layer resolves catalogue entries, participant
bindings, providers, ID namespaces, fixed mock capabilities, and presentation.
It then calls the public application operations and stores only a fully
validated returned snapshot.

### 5.5 Server-rendered and offline-first

Use FastAPI, Jinja, ordinary HTML forms, existing styling conventions, and
small progressive-enhancement JavaScript only where useful for loading and
double-submit feedback. Correctness must not depend on JavaScript. No route may
require a network call, provider account, or API key.

## 6. Browser and Game Master flow

The required flow is:

1. Open `GET /investigations`.
2. Submit a case introduction and a valid catalogue-backed participant set to
   `POST /investigations`.
3. Follow a `303` redirect to the new canonical session page and inspect its
   introduction, participants, status, and empty-round state.
4. Submit one clue explicitly; inspect the revealed clue and
   `awaiting_analyses` round.
5. Start independent analyses explicitly; inspect one analysis per
   participant.
6. Start discussion explicitly; inspect the ordered round-robin transcript.
7. Create the group decision explicitly; inspect the decision and the visible
   Game Master pause.
8. Reveal the next clue explicitly and repeat analyses, discussion, and
   decision for round two.
9. After the supported mock scenario is exhausted, do not offer a third clue;
   continue to show an explicit finalization action.
10. Finalize explicitly and inspect the completed status and final theory.

No GET request changes investigation state. Refreshing a canonical page is
side-effect free.

## 7. Route architecture

| Method and route | Responsibility | Success |
|---|---|---|
| `GET /investigations` | Render creation form and local-runtime explanation | `200` |
| `POST /investigations` | Validate input, allocate a session namespace, assemble the configured mock runtime, call `create_session()`, and register it | `303` to detail |
| `GET /investigations/{session_id}` | Render the latest snapshot and currently valid actions | `200` |
| `POST /investigations/{session_id}/clues` | Validate clue input and call `reveal_clue()` | `303` to detail |
| `POST /investigations/{session_id}/analyses` | Call `run_independent_analyses()` | `303` to detail |
| `POST /investigations/{session_id}/discussion` | Call `run_group_discussion()` with configured mock turn count and deterministic round robin | `303` to detail |
| `POST /investigations/{session_id}/decision` | Call `create_group_decision()` | `303` to detail |
| `POST /investigations/{session_id}/finalize` | Call `finalize_investigation()` | `303` to detail |

Successful mutations use POST/Redirect/GET with status `303` and one canonical
location. Session IDs are validated before lookup. Forms must have bounded
text and participant inputs, preserve safe values after a `400`, and render
readable field errors. The exact bounds should follow the existing web
validation style and be covered by tests.

Errors may render the list/detail page directly or redirect with app-owned
one-use feedback, provided failed POSTs never masquerade as success and never
change the stored snapshot.

## 8. Investigation state ownership

Sprint 7 introduces an app-owned registry/service, injected into the
investigation router by the main app factory. It owns process-local records
keyed by session ID. Each record contains the latest immutable
`InvestigationSession` plus the runtime dependencies/capabilities needed to
advance that session; provider objects and participant bindings remain runtime
objects and are not added to the domain aggregate.

Required registry behaviour:

- allocate unique monotonic session namespaces for the life of one app
  instance;
- retrieve a snapshot without mutation;
- isolate records for two or more sessions;
- reject unknown sessions;
- clear all sessions naturally when the application process restarts;
- perform no file or database writes; and
- expose controlled operations rather than an uncontrolled module-global
  dictionary.

Each mutation must be serialized per session. Under that guard, the registry
reads the latest snapshot, executes exactly one requested application action,
and replaces the record only after the action returns a fully valid snapshot.
If validation, fixture loading, generation, parsing, or runtime execution
fails, the previous snapshot remains registered. This prevents simultaneous
or double submissions from running the same provider-backed phase twice. A
stale second request is rejected as a state conflict after the first commits.
Locks for different sessions should not unnecessarily couple their state.

This is navigation continuity, not persistence, durable recovery, or a
multi-process consistency design. Multiple workers would have independent
registries and are outside the local Sprint 7 contract.

## 9. Mock runtime and session-scoping constraints

### 9.1 Session-scoped structured fixtures

The current structured fixtures contain literal references such as
`session_001_clue_0001`, `session_001_analysis_sherlock_holmes_0001`, and
`session_001_hypothesis_0001`. They validate for the original
`session_001` E2E, but unmodified output can leak that namespace into
`session_002` and fail aggregate/service validation.

Before web workflow routes are completed, the investigation mock
assembly/binding layer must scope deterministic structured output to the
target session namespace. The design must:

- keep the generic `MockProvider` generic;
- avoid silently repairing invalid generated references in the investigation
  application service;
- preserve strict structured parsing and service/domain validation;
- perform any deterministic fixture templating or binding in the mock
  investigation assembly boundary;
- preserve the original `session_001` scenario as far as practical; and
- prove that `session_001` and `session_002` outputs reference only their own
  clues, analyses, hypotheses, decisions, and final theory.

Task 1 freezes this requirement only; it does not implement the fix.

### 9.2 Catalogue-driven assembly

Routes and templates must not hard-code Sherlock Holmes or Hercule Poirot.
Creation choices, display names, IDs, personas, and participant order should
come from the existing character catalogue and validated persona fixtures.
Mock investigation assembly may report which catalogue participants the fixed
scenario can currently execute and must fail readably for unsupported
combinations. Adding a future fixture-backed character should primarily be a
data/configuration and assembly change, not a route rewrite.

### 9.3 Domain capability versus mock capability

The investigation domain and public operations have no artificial two-round
limit. The current deterministic fixture inventory does: it represents two
rounds with two discussion turns per round for the present participant set.
The mock runtime must expose capability data equivalent to:

```text
supported_rounds = 2
discussion_turns = 2
```

The browser uses that runtime capability to stop offering a third clue whose
later phases cannot be completed. This is a delivery/runtime guard, not a new
domain invariant. Exhausting mock rounds must never finalize automatically;
the Game Master still submits the finalization action.

## 10. Error-handling expectations

| Condition | HTTP status | Required behaviour |
|---|---:|---|
| Invalid or oversized form input, invalid participant selection | `400` | Show bounded field errors; do not call the workflow operation |
| Unknown or malformed session ID | `404` | Show a readable not-found page without leaking internals |
| Wrong phase, repeated/stale action, completed-session action, exhausted mock rounds | `409` | Explain the state conflict and retain the latest valid snapshot |
| Missing/empty fixture, malformed structured output, provider/runtime failure | `500` | Log diagnostic detail server-side, show a concise local-runtime error, retain the latest valid snapshot |

Unexpected exceptions must not expose tracebacks or raw prompt/provider data in
HTML. Known validation exceptions need an explicit delivery-layer mapping;
routes must not reinterpret them as successful transitions. The registry
commit rule is the final safeguard: failure never replaces the last valid
snapshot.

Client-side submit disabling and loading text should reduce accidental repeats,
but server-side per-session serialization and phase validation provide the
correctness guarantee.

## 11. Testing strategy

### 11.1 Foundation tests

Add focused tests for:

- session-scoped fixture transformation/binding, including strict failure on
  invalid references;
- catalogue-driven participant and provider assembly without route hard-coding;
- declared two-round/two-turn mock capability;
- registry creation, lookup, monotonic IDs, replacement-after-success,
  retention-after-failure, and process-instance isolation;
- serialized repeated/concurrent actions; and
- isolation between at least `session_001` and `session_002`.

### 11.2 Route tests

Cover every GET and POST route in its valid state and representative invalid
states. Assert status codes, `303` locations, visible phase/action controls,
escaped user content, ordered participants/transcripts, and absence of side
effects from GET requests. Verify wrong-phase, repeated, post-completion,
unknown-session, invalid-form, missing-fixture, malformed-output, and unexpected
runtime failures. Failure tests must compare the stored snapshot before and
after the request.

Existing conversation and rater route behaviour must remain unchanged.

### 11.3 Full HTTP end-to-end test

Drive this exact sequence through HTTP:

```text
create → clue 1 → analyses → discussion → decision → pause
→ clue 2 → analyses → discussion → decision → pause
→ explicit finalize → final theory
```

Assert that no transition occurs before its POST, each successful POST uses
PRG, clue-one visibility remains frozen in round one, the two-turn discussion
is round robin and ordered, decisions do not complete the session, a third
mock clue is unavailable, and only finalization produces `completed` with a
final theory.

### 11.4 Interleaved isolation and offline regression

Create two investigations, interleave all phases, and verify that an action on
one never mutates the other and all generated references remain within the
owning session namespace.

Run investigation web and E2E tests with `OPENAI_API_KEY` unset and socket
access blocked where appropriate. Preserve existing offline guards. Run the
existing conversation web, rater web, conversation CLI/evaluation, focused
investigation, and full regression suites. Do not predict or document a final
test count before execution.

## 12. Ordered implementation tasks

The dependency order is:

1. **Freeze Sprint 7 web contract** — complete this document; add no production
   implementation.
2. **Session-scope investigation mock outputs** — resolve structured fixture
   references in the mock assembly layer and test `session_001`/`session_002`.
3. **Add catalogue-driven mock runtime assembly** — build validated participant
   bindings and expose supported rounds/turns for the fixed scenario.
4. **Add the in-memory registry** — own session allocation, snapshots, runtime
   dependencies, per-session serialization, and atomic replacement.
5. **Add the investigation router and shell** — mount it in the existing main
   FastAPI app and add shared navigation/style support.
6. **Add creation and session rendering** — implement the list/create form,
   canonical detail page, participant presentation, and PRG.
7. **Add explicit clue revelation** — validate clue input and enforce mock
   round capability without changing the domain limit.
8. **Add independent analyses** — delegate once and render each participant's
   result.
9. **Add round-robin discussion** — delegate with configured turns and render
   the ordered transcript.
10. **Add group decision and Game Master pause** — delegate once, render the
    decision, and expose no automatic continuation.
11. **Add explicit finalization and final theory** — keep completion caller
    controlled and render the final result.
12. **Harden errors and submission behaviour** — complete status mapping,
    snapshot retention, loading feedback, and double-submit protection.
13. **Add complete HTTP E2E, isolation, and offline tests** — include two
    interleaved session namespaces and network/API-key guards.
14. **Run regression and smoke checks, then close Sprint 7 documentation** —
    record only commands and results actually observed.

Tasks 2–4 are foundations for stateful routes. Tasks 7–11 depend on the
registry transaction boundary and the preceding phase. Task 12 applies across
all routes and must be complete before the final E2E and closure work.

## 13. Definition of Done

Sprint 7 is complete only when:

- the investigation UI is part of the existing main FastAPI app and the rater
  app remains separate;
- catalogue-backed creation and a single state-driven session page work
  locally;
- every workflow transition requires its own Game Master POST and successful
  mutations use `303` PRG;
- routes delegate all investigation rules and generation to the existing
  application service;
- process-local app-owned state survives navigation, isolates sessions, writes
  nothing, and disappears on restart;
- concurrent/repeated actions cannot execute the same provider-backed phase
  twice or overwrite a newer snapshot;
- structured fixture references are session-scoped without specializing
  `MockProvider` or repairing them in the service;
- the UI respects the fixed two-round mock capability without adding a domain
  limit or automatic finalization;
- readable `400`, `404`, `409`, and `500` paths retain the last valid snapshot;
- the complete HTTP workflow and interleaved two-session isolation tests pass
  offline with the API key unset and network blocked;
- existing conversation UI, rater UI, CLI/evaluation, investigation, and full
  regression tests remain green; and
- completion documentation reports actual verification results and preserves
  the distinction between technical mock behaviour and persona quality.

## 14. Final manual smoke-test expectations

After automated tests pass, start the normal main web entry point with
`OPENAI_API_KEY` unset. In one browser process:

1. confirm the existing conversation page and `/health` still work;
2. open `/investigations`, create a catalogue-backed investigation, and note
   its session ID;
3. complete both mock rounds through separate clue, analyses, discussion, and
   decision submissions while checking the pause after each decision;
4. confirm no third-clue action is offered, explicitly finalize, and inspect
   the final theory;
5. create a second investigation and confirm its ID and displayed references
   are independent;
6. refresh and navigate between both detail pages without changing state;
7. submit a stale or repeated action and confirm a readable conflict with no
   snapshot loss; and
8. restart the server and confirm prior investigation URLs no longer resolve,
   demonstrating process-local, non-persistent state.

Record the exact startup/test commands and observed results during Sprint 7
closure. Do not claim live-provider, durable persistence, real-case, or
recognizability validation from this smoke test.
