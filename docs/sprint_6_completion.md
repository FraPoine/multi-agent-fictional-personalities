# Sprint 6 Completion Record

## Status

Completed and locally verified on 2026-08-06.

## Delivered scope

Sprint 6 delivers a deterministic, provider-neutral investigation application
workflow over local mock fixtures: session creation, caller-controlled clue
revelation, one independent analysis per participant, round-robin discussion,
structured group decisions with a pause after each round, and explicit final
theory generation. The two-round E2E exercises every public operation without
bypassing prompt, provider, structured-output, domain, or aggregate boundaries.

## Tested implementation commit

The implementation verified by this record is commit
`9d2906c0c3edab911a0f8a9e268a5dcc37885723` (`9d2906c`,
`test(investigation): cover two-round workflow end to end`) on branch `main`.
The documentation closure commit was created afterward and contains no
production workflow changes.

## Verification environment

| Field | Observed value |
|---|---|
| Date | 2026-08-06 |
| Execution | Local, not CI |
| Platform | Linux 7.0.0-28-generic, x86_64 |
| Python | 3.14.4 (`.venv/bin/python`) |
| Pytest | 9.1.1; pluggy 1.6.0; anyio 4.14.2 |
| Dependency declaration | `requirements.txt`; local virtual environment |
| Project import mode | `PYTHONPATH=src`, not an editable-install command |
| Investigation provider | committed local `mock` fixtures |

The repository has no `pyproject.toml`, `Makefile`, `tox.ini`, or `setup.cfg`.
No Ruff, Black, mypy, Pyright, or other formatter/linter/type-check command is
configured, so none was invented or installed for closure.

## Verification commands and results

All commands below ran from the repository root against the tested commit and
exited with status 0.

| Purpose | Exact command | Result |
|---|---|---|
| Environment | `.venv/bin/python --version` | Python 3.14.4 |
| Test runner | `PYTHONPATH=src .venv/bin/python -m pytest --version` | pytest 9.1.1 |
| Compilation | `PYTHONPATH=src .venv/bin/python -m compileall -q src tests scripts` | success; no output |
| Focused investigation | `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_investigation_prompts.py tests/test_investigation_structured_output.py tests/test_investigation_ids.py tests/test_investigation_mock_fixtures.py tests/test_investigation_session.py tests/test_investigation_independent_analyses.py tests/test_investigation_group_discussion.py tests/test_investigation_group_decision.py tests/test_investigation_finalization.py tests/test_investigation_workflow_e2e.py` | 302 passed in 1.21s |
| Simulation and selection | `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_simulation_engine.py tests/test_speaker_selector.py tests/test_conversation_participant.py` | 73 passed in 0.38s |
| Conversation service/artifacts | `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_conversation_service.py tests/test_conversation.py tests/test_conversation_writer.py tests/test_run_writer.py` | 81 passed in 0.43s |
| Conversation CLI | `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_conversation_cli.py tests/test_conversation_cli_e2e.py` | 12 passed in 0.63s |
| Conversation web | `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_web_app.py tests/test_web_startup.py tests/test_rater_web.py` | 38 passed in 0.64s |
| Evaluation pilot | `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_evaluation_models.py tests/test_evaluation_persistence_analysis.py tests/test_evaluation_pilot_e2e.py tests/test_evaluation_preparation_failures.py tests/test_evaluation_trials.py` | 22 passed in 0.41s |
| Single-agent pipeline | `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_mock_pipeline_e2e.py tests/test_pipeline.py tests/test_agent_runtime.py tests/test_persona.py tests/test_persona_extraction.py tests/test_persona_io.py tests/test_system_prompt.py tests/test_mock_provider.py` | 57 passed in 0.31s |
| API-key-unset investigation E2E | `PYTHONPATH=src env -u OPENAI_API_KEY .venv/bin/python -m pytest -q tests/test_investigation_workflow_e2e.py` | 1 passed in 0.17s |
| Full suite | `PYTHONPATH=src .venv/bin/python -m pytest` | 757 passed in 3.74s |

No investigation smoke script exists; Task 13 intentionally delivered the E2E
test only. No separate configured formatter, linter, or type checker was
available to execute.

## Full-suite result

Pytest collected 757 tests and reported exactly:

```text
============================= 757 passed in 3.74s ==============================
```

Failures: 0. Skips: 0. Xfails: 0. Xpasses: 0. Reported warnings: 0. Exit
status: 0.

## Post-documentation verification

After the closure documentation edits, the required checks were repeated:

| Command | Result |
|---|---|
| `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_investigation_workflow_e2e.py` | 1 passed in 0.23s |
| `PYTHONPATH=src .venv/bin/python -m pytest` | 757 passed in 4.25s |

Both exited with status 0. This post-edit result is separate from the frozen
implementation verification result above; the tested implementation SHA
remains the pre-documentation commit.

## Two-round E2E evidence

The explicit sequence passed:

```text
create session → reveal clue 1 → independent analyses
→ round-robin discussion → decision 1 → pause
→ reveal clue 2 → independent analyses → round-robin discussion
→ decision 2 → active session → explicit finalization
→ completed session with final theory
```

The test asserts that round 1 and its analyses retain clue 1 only; round 2 and
its analyses see the ordered clue 1 + clue 2 prefix; two completed rounds leave
the session active; only finalization completes it. It also validates metadata,
serializes and restores the aggregate, and runs the entire timestamp-injected
workflow twice with equal traces and JSON.

## Regression evidence

- Default and injected simulation, complete history, round robin, messages,
  metadata, and failure paths passed.
- Framework-independent conversation services and conversation artifact
  writers passed; this is conversation persistence, not investigation
  persistence.
- The supported conversation CLI and its E2E passed. No investigation CLI
  exists.
- FastAPI/Jinja conversation and rater web tests passed. The existing web
  interface supports conversation/evaluation tooling only; no investigation
  UI exists.
- Technical evaluation schemas, preparation, persisted responses, and analysis
  passed. This is not recognizability evaluation of investigation output.
- Persona loading, prompt construction, mock generation, validation, and
  single-agent artifact behavior passed.

## Offline and secret-free evidence

The E2E passed with `OPENAI_API_KEY` removed from its environment. Investigation
tests install socket guards that fail any attempted connection. Providers read
only committed fixtures; no live client, external download, provider account,
OpenAI dependency at runtime, or API key is required for the tested Sprint 6
mock workflow. This is a narrow claim about the tested workflow, not a claim
that every repository script is incapable of network access.

## Architecture boundaries

The application service is stateless and framework-independent. Deterministic
IDs and provider-neutral task names remain service-controlled; generated JSON
passes through `GenerationResult` and strict structured schemas before domain
records and aggregate reconstruction. Discussion alone reuses `simulate_chat()`
and `RoundRobinSelector`. Every decision pauses, while finalization is explicit.

## Explicit limitations

- no investigation persistence, CLI, or web UI;
- no live-provider investigation verification or required API key;
- no automatic clue generation/revelation, decision execution, or finalization;
- no scoring or comparison with an official/commercial solution;
- no persona-recognizability evaluation of investigation output; and
- mock fixtures establish technical reproducibility, not persona quality or a
  scientifically interpretable study.

## Temporary-output cleanup

Compilation-generated `.pyc` files and empty `__pycache__` directories under
`src`, `tests`, and `scripts` were removed. No coverage database, smoke log,
investigation output, conversation run, API key, virtual environment, or
machine-specific report was added. The implementation worktree was clean
before documentation editing.

## Remaining risks and future work

Sprint 7 is the existing planned investigation web increment. Investigation
persistence, live providers, additional characters, real observability,
official-case-independent scoring design, and scientifically interpretable
recognizability work remain future scope and require separate design and
verification.
