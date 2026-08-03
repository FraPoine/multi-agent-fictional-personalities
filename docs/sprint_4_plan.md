# Sprint 4 Plan — Minimal Web UI

## Sprint objective

Sprint 4 adds a minimal human-facing web interface over the existing local
mock conversation pipeline. The objective is to improve usability and verify
integration with the completed conversation flow, not to introduce new agent
behavior, assess persona quality, or replace the CLI.

## Starting point

Sprint 3 provides the functionality that the web interface will reuse:

- immutable, validated `Message` and `ConversationRun` models;
- one-message generation through `generate_reply()` with explicit complete
  per-run history;
- deterministic round-robin simulation for Sherlock Holmes and Hercule Poirot;
- a local, network-free mock provider;
- atomic conversation persistence with safe run ID validation and per-run
  locking;
- `run.json`, `messages.jsonl`, and `transcript.md` artifacts beneath
  `outputs/conversations/runs/<run-id>/`;
- an importable CLI implementation, a local command-line entry point, and an
  end-to-end subprocess test.

OpenAI conversation execution is not implemented. The existing deterministic
mock replies are synthetic development fixtures and are not evidence of
persona quality.

## User flow

```text
Open local web page
→ configure Sherlock and Poirot
→ enter topic and turn count
→ submit conversation
→ validate inputs
→ call existing application/runtime logic
→ persist the completed run
→ show transcript
→ show artifact path or a readable error
```

The completed view identifies the saved run and its three generated artifact
files. An invalid request or runtime failure remains visibly unsuccessful.

## In-scope functionality

- One local web page.
- Selection of Sherlock Holmes and Hercule Poirot.
- Investigation-topic input.
- Turn-count input.
- A fixed local `mock` provider with no live-provider option.
- Conversation submission through the existing application logic.
- Transcript display in speaker and turn order.
- Run ID, artifact directory, and generated-filename display.
- Explicit empty, loading, completed, and error states.
- Basic responsive styling based on the existing Figma design.
- Tests covering the UI critical path.
- A documented local startup command.

## Out-of-scope functionality

- OpenAI or other live providers and API-key management.
- L and Professor Layton.
- Persona editing and corpus management.
- Evaluation trial generation, a rater interface, statistics, or analysis.
- Authentication or database storage.
- A conversation history browser.
- Public deployment.
- Complex frontend frameworks unless an existing documented decision later
  requires one.

## Proposed architecture

```text
Browser / HTML form
→ web route or controller
→ application service
→ existing simulation runtime
→ existing persistence layer
→ structured result rendered by the UI
```

Web-specific request parsing and rendering should remain separate from
simulation logic. The UI should call importable Python functions instead of
duplicating CLI orchestration. A framework-independent application service
should validate and translate application inputs, load the supported local
fixtures, invoke the existing simulation and persistence boundaries, and
return a structured result suitable for either interface.

The CLI must continue to work. It may share the application service, but the
service must not depend on the selected web framework. The mock provider
remains the only enabled provider. The simulation runtime and persistence
layer remain authoritative for run construction, message ordering, run ID
safety, and artifact generation. Exact web modules and function signatures are
provisional implementation decisions.

## Suggested implementation stages

Each stage is intended to be a narrow, independently reviewable Codex task.

1. Update Sprint 4 documentation and reconcile related documentation as an
   explicit task.
2. Introduce only the dependencies required by the selected minimal UI stack.
3. Add a framework-independent conversation application service.
4. Test the application service in isolation with the local mock fixtures.
5. Create the minimal local web application skeleton and startup entry point.
6. Create the HTML form and static page structure.
7. Connect valid form submission to the mock conversation service.
8. Render the ordered transcript, run ID, artifact directory, and artifact
   filenames.
9. Add input validation, readable error handling, and loading feedback.
10. Apply minimal responsive styling based on the existing Figma design.
11. Add web integration tests for the critical path and failure cases.
12. Document local startup and write the Sprint 4 completion note.

## Validation rules

- The topic must not be empty or whitespace-only.
- At least two supported, unique characters must be selected.
- Only the supported `sherlock` and `poirot` slugs may be accepted.
- The turn count must be an integer within a small documented range.
- The provider must remain `mock`; it should be fixed by the application rather
  than accepted as an unrestricted browser value.
- Filesystem and persistence failures must be presented as readable errors.
- Failed validation or execution must not render a completed state or silently
  appear successful.

The existing runtime requires a positive turn count but does not impose an
upper bound. Selecting and documenting a small UI range is therefore a Sprint
4 implementation decision that must be applied consistently in the form,
application service, and tests.

## Acceptance criteria

1. The web application starts through a documented local command.
2. The main page loads successfully.
3. Sherlock Holmes and Hercule Poirot are available for selection.
4. The user can enter an investigation topic and turn count.
5. A valid request runs a deterministic local mock conversation.
6. The existing simulation runtime and persistence code are reused rather than
   reimplemented in the web layer.
7. The transcript is displayed in speaker and turn order.
8. The completed view displays the run ID and artifact directory.
9. The run produces `run.json`, `messages.jsonl`, and `transcript.md`, and the
   UI identifies those files.
10. Invalid inputs and runtime or persistence failures produce understandable
    feedback and do not appear successful.
11. The complete flow requires neither network access nor an OpenAI API key.
12. The existing conversation CLI remains functional.
13. All previous tests continue to pass.
14. New tests cover the main-page response, valid submission, displayed
    result, artifact creation, and representative invalid submission.

## Definition of Done

Sprint 4 is complete only when a user starting from a clean clone can follow
the documented path:

```text
install the documented dependencies
→ start the local UI
→ run a Sherlock/Poirot mock conversation
→ read the transcript
→ locate the saved artifacts
```

The relevant documentation must be updated, all tests must pass, and the
implementation must contain no hidden network dependency. Evaluation work,
live-provider work, and additional characters must not be mixed into this
sprint.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| CLI orchestration is duplicated in a route | Extract a small framework-independent application service and use importable functions from both interfaces where appropriate. |
| Application logic becomes coupled to FastAPI or another framework | Keep web request and response objects at the controller boundary; use plain Python inputs and structured results in the service. |
| Stable Sprint 3 behavior changes | Treat the existing simulation and persistence APIs as authoritative and run the previous test suite after each integration stage. |
| Unnecessary frontend complexity is introduced | Use one server-rendered page and minimal HTML, CSS, and browser scripting needed for the four UI states. |
| Errors are hidden or too technical | Map validation and expected filesystem failures to concise visible messages while preserving failed status. |
| The UI accidentally invokes a network provider | Fix the service configuration to `mock` and test the critical path without credentials or network access. |
| Evaluation features enter the UI early | Limit page content and tests to conversation configuration, execution, transcript viewing, and artifact discovery. |

## Expected sprint deliverables

- Sprint 4 planning documentation.
- A minimal local web application.
- A framework-independent application service boundary.
- HTML and CSS assets.
- Critical-path service and web integration tests.
- README startup instructions.
- A Sprint 4 completion note.

These are deliverable categories; their exact filenames and framework-specific
layout will be selected and documented during implementation.

## Deferred work

Evaluation trial generation, rater UX, statistical analysis, live providers,
and the additional L and Professor Layton characters remain future work. The
web UI created in this sprint does not claim to validate character
recognizability or persona quality.
