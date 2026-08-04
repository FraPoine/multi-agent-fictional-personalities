# Sprint 4 Completion

## Status

**Completed**

| Field | Verified value |
|---|---|
| Completion date | 2026-08-04 |
| Tested commit | `1a2f694f4ca51bc4a1f46aca5fb6a5b6ca6befec` |
| Project track | Individual Track B, mixed project |
| Conversation provider | `mock` |
| Python | 3.14.4 |
| Full test result | 189 passed, 0 skipped, 0 failed, 1 warning |

## Sprint objective

Sprint 4 added a minimal local web interface over the existing deterministic
mock conversation pipeline. It improves local usability and verifies
integration across delivery, application, simulation, and persistence layers
without replacing the Sprint 3 CLI or making claims about real LLM persona
quality or recognizability.

## Delivered functionality

The verified delivery includes:

- a framework-independent conversation application service;
- a FastAPI application and server-rendered Jinja page;
- a form for Sherlock Holmes and Hercule Poirot, topic, and 2–12 turns;
- a fixed local `mock` provider and deterministic seed;
- server-side validation plus safe `400`, `409`, and `500` failure states;
- browser loading feedback with disabled submission and `Running` status;
- ordered transcript rendering;
- run ID, artifact-directory, artifact-name, and artifact-path rendering;
- atomic creation of `run.json`, `messages.jsonl`, and `transcript.md`;
- responsive visual styling;
- application-service, route, and startup-command tests;
- a no-`PYTHONPATH` local startup command;
- README quick-start instructions and an executed smoke-test record.

## Verified architecture

```text
Browser
→ FastAPI route
→ conversation application service
→ deterministic round-robin simulation
→ local mock provider
→ atomic persistence
→ server-rendered transcript and artifact details
```

The web route delegates conversation work to the framework-independent
application service. The service reuses the simulation runtime, mock provider,
and conversation writer. The CLI remains a separate delivery interface and
reuses the same application/runtime logic rather than depending on FastAPI.

## Task summary

1. Planning and architecture documentation established the web scope and kept
   evaluation and live providers deferred.
2. Existing dependencies were used to introduce and test a
   framework-independent conversation service boundary.
3. A minimal FastAPI skeleton, Jinja template, accessible form, and static
   assets established the local interface.
4. Form submission was connected to the service, with ordered messages, run
   metadata, and artifact details rendered in the returned page.
5. Bounded validation, safe error mapping, and transient loading feedback made
   empty, running, completed, and failed states explicit.
6. Responsive styling refined the interface while preserving the functional
   contract.
7. Route and startup tests covered successful, invalid, and failure paths
   without external network access or real repository output.
8. The startup command, README workflow, and Task 17 reproducibility smoke test
   documented and demonstrated the complete local path.
9. Final closure verification audited all acceptance criteria, reran focused
   and full tests, and repeated the public startup check.

## Acceptance-criteria evidence

| Criterion | Status | Evidence | Notes |
|---|---|---|---|
| 1. Documented local startup | Passed | [`scripts/run_web.py`](../scripts/run_web.py), [`tests/test_web_startup.py`](../tests/test_web_startup.py), [`README.md`](../README.md), [smoke test](sprint_4_smoke_test.md) | `python scripts/run_web.py` starts without exposing `src/` through `PYTHONPATH`. |
| 2. Main page loads | Passed | `GET /` in [`web/app.py`](../src/multi_agent_personalities/web/app.py); `test_main_page_renders_without_creating_output` in [`test_web_app.py`](../tests/test_web_app.py) | Returns HTML 200 and creates no run. |
| 3. Sherlock and Poirot are selectable | Passed | [`index.html`](../src/multi_agent_personalities/web/templates/index.html), `_SUPPORTED_CHARACTERS` in [`web/app.py`](../src/multi_agent_personalities/web/app.py) | Supported web slugs are exactly `sherlock` and `poirot`; L and Professor Layton are not claimed. |
| 4. Topic and turn configuration | Passed | Form in [`index.html`](../src/multi_agent_personalities/web/templates/index.html); `_validate_conversation_form()` in [`web/app.py`](../src/multi_agent_personalities/web/app.py) | Both characters are required, topic is nonblank, turn range is 2–12, and provider is fixed to `mock`. |
| 5. Valid deterministic execution | Passed | `POST /conversations` in [`web/app.py`](../src/multi_agent_personalities/web/app.py); [`conversation_service.py`](../src/multi_agent_personalities/application/conversation_service.py); valid-submission web tests | A valid POST calls the real local mock service with seed 42. |
| 6. Existing runtime and persistence reused | Passed | [`conversation_service.py`](../src/multi_agent_personalities/application/conversation_service.py) calls `simulate_chat()` and `save_conversation_run()` | Routes do not reimplement scheduling, reply generation, or persistence. |
| 7. Ordered transcript displayed | Passed | Message loop in [`index.html`](../src/multi_agent_personalities/web/templates/index.html); `test_valid_submission_renders_completed_conversation`; simulation-order tests | Six-turn evidence preserves turn order and alternates Sherlock and Poirot. |
| 8. Run information displayed | Passed | Run summary in [`index.html`](../src/multi_agent_personalities/web/templates/index.html); valid-submission web test; [smoke test](sprint_4_smoke_test.md) | Completed page shows run ID and repository-relative artifact directory. |
| 9. Three artifacts created and identified | Passed | `ConversationResult.artifact_paths`; conversation-writer and web artifact tests; [smoke artifact verification](sprint_4_smoke_test.md#artifact-verification) | Exactly `run.json`, `messages.jsonl`, and `transcript.md` are saved beneath `outputs/conversations/runs/<run-id>/`. |
| 10. Understandable failure handling | Passed | Error mapping in [`web/app.py`](../src/multi_agent_personalities/web/app.py); invalid and service-error cases in [`test_web_app.py`](../tests/test_web_app.py) | Invalid form input returns HTML 400, collision returns 409, expected generation/persistence failures return safe 500 responses, and failures never render completed state. |
| 11. No network or API-key requirement | Passed | Fixed `mock` service and route; network-rejection fixtures in service, simulation, persistence, CLI, and web tests; [smoke test](sprint_4_smoke_test.md) | Critical path passed without an API key or external conversation request. |
| 12. Existing CLI remains functional | Passed | [`scripts/run_conversation.py`](../scripts/run_conversation.py), [`test_conversation_cli.py`](../tests/test_conversation_cli.py), [`test_conversation_cli_e2e.py`](../tests/test_conversation_cli_e2e.py) | Sprint 3 CLI remains documented and tested. |
| 13. Regression suite passes | Passed | Final `python -m pytest` run | 189 passed, 0 skipped, 0 failed. |
| 14. Sprint 4 tests cover the critical path | Passed | [`test_conversation_service.py`](../tests/test_conversation_service.py), [`test_web_app.py`](../tests/test_web_app.py), [`test_web_startup.py`](../tests/test_web_startup.py) | Covers main page, health, assets, valid execution and rendering, artifacts, validation, safe errors, escaping, network rejection, and startup arguments/path resolution. |

## Definition of Done

The documented path is:

```text
python -m pip install -r requirements.txt
→ python scripts/run_web.py
→ configure Sherlock Holmes and Hercule Poirot
→ run the local mock conversation
→ read the ordered transcript
→ locate outputs/conversations/runs/<run-id>/ and its three artifacts
```

This path is supported by the [README](../README.md), exercised through the
automated service, route, startup, CLI, simulation, and persistence tests, and
demonstrated by the executed [Sprint 4 smoke test](sprint_4_smoke_test.md),
including the subsequent user-observed interactive loading-state check. The
implementation is mock-only and the critical-path tests reject network
access. The Sprint 4 Definition of Done is therefore **Passed**.

## Validation results

All commands were run from the repository root against commit
`1a2f694f4ca51bc4a1f46aca5fb6a5b6ca6befec` with
`PYTHONPATH="$PWD/src"` for pytest:

| Command | Exit code | Result |
|---|---:|---|
| `python -m pytest` | 0 | 189 passed, 0 skipped, 0 failed, 1 warning |
| `python -m pytest tests/test_conversation_service.py -q` | 0 | 21 passed |
| `python -m pytest tests/test_web_app.py -q` | 0 | 21 passed, 1 warning |
| `python -m pytest tests/test_web_startup.py -q` | 0 | 7 passed |

The warning was the existing `StarletteDeprecationWarning` emitted by
FastAPI's TestClient compatibility layer. It did not cause a failure.

The public startup command was also run with `PYTHONPATH` unset. Uvicorn
started successfully on `127.0.0.1:8000`, `/health` returned
`{"status":"ok","provider":"mock"}`, and the server was stopped cleanly.
The detailed browser, conversation, invalid-input, artifact, and cleanup
observations are recorded in the [Sprint 4 smoke test](sprint_4_smoke_test.md).

## Deliverables

- [`src/multi_agent_personalities/application/conversation_service.py`](../src/multi_agent_personalities/application/conversation_service.py)
- [`src/multi_agent_personalities/web/app.py`](../src/multi_agent_personalities/web/app.py)
- [`src/multi_agent_personalities/web/templates/index.html`](../src/multi_agent_personalities/web/templates/index.html)
- [`src/multi_agent_personalities/web/static/styles.css`](../src/multi_agent_personalities/web/static/styles.css)
- [`src/multi_agent_personalities/web/static/conversation.js`](../src/multi_agent_personalities/web/static/conversation.js)
- [`scripts/run_web.py`](../scripts/run_web.py)
- [`tests/test_conversation_service.py`](../tests/test_conversation_service.py)
- [`tests/test_web_app.py`](../tests/test_web_app.py)
- [`tests/test_web_startup.py`](../tests/test_web_startup.py)
- [`README.md`](../README.md)
- [`docs/sprint_4_plan.md`](sprint_4_plan.md)
- [`docs/sprint_4_smoke_test.md`](sprint_4_smoke_test.md)

## Known limitations

The following are intentional Sprint 4 scope boundaries, not unresolved
Sprint 4 defects:

- no OpenAI-backed conversation execution or real LLM persona validation;
- no support for L or Professor Layton in the working conversation interfaces;
- no human rating workflow, blind evaluation trials, or statistical
  evaluation;
- no persistent conversation-history browser;
- no authentication, public deployment, or database storage;
- no streaming responses or background jobs.

No unresolved defect was found in the required Sprint 4 workflow during final
verification.

## Risks and technical debt

- Deterministic synthetic fixtures cannot establish real model persona quality
  or human recognizability.
- Synchronous server-rendered execution is appropriate for the current fast
  local mock but may not suit a future slow live provider without a separately
  designed execution model.
- Only the two MVB personas are integrated into the conversation interfaces.
- Interactive browser behavior has manual smoke-test evidence rather than a
  browser-automation suite.
- No GitHub Actions workflow is present, so this completion record documents
  local verification rather than CI status.
- Reproducibility depends on the documented Python environment and dependency
  installation.

## Next steps

Sprint 5 remains future work and has not started. Its roadmap direction is
limited to blind evaluation-trial generation, a separate rater interface,
basic evaluation analysis, and an initial controlled persona-recognizability
study.

## Final verdict

Sprint 4 is complete because the documented local web workflow,
critical-path tests, startup command, persistence artifacts, and
reproducibility smoke test satisfy the Sprint 4 acceptance criteria and
Definition of Done.
