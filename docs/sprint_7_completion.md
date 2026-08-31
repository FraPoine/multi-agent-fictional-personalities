# Sprint 7 Completion Record

> Historical notice: this record verifies web delivery over the original
> round-based Sprint 6 contract. The screen is now a compatibility interface;
> registry and locking infrastructure remain for a future Lead/Visit UX.

## Status

Automated verification and terminal HTTP smoke verification completed locally
on 2026-08-27. **Manual interactive browser smoke remains pending.** Sprint 7
implementation is complete, but final closure must not be declared until the
browser checklist below is confirmed by a human with an interactive browser.

## Delivered scope

Sprint 7 adds the deterministic investigation workflow to the existing main
FastAPI/Jinja application. It delivers catalogue-backed creation, one
state-driven canonical session page, explicit Game Master POST actions for
clues, analyses, discussion, decisions, and finalization, `303` PRG,
progressive loading feedback, process-local app-owned state, per-session
serialized mutations, atomic snapshot replacement, session-scoped fixture
references, readable error paths, and complete HTTP E2E and interleaved-session
tests.

The current browser runtime uses two Sherlock Holmes/Hercule Poirot fixture
rounds with two discussion turns. Exhaustion offers explicit finalization; it
does not create a two-round domain invariant or finalize automatically.

## Tested implementation commit

The implementation verified before documentation changes is commit
`524bc84d5b4607fab61f207aa8363e5694c32d46` (`524bc84`,
`test(web): add investigation HTTP e2e and isolation`) on branch `main`.
The documentation verification commit follows this frozen implementation and
contains no production Python changes.

## Verification environment

| Field | Observed value |
|---|---|
| Date | 2026-08-27 (`2026-08-27T12:14:51+02:00`) |
| Execution | Local, not CI |
| Platform | Linux 7.0.0-29-generic, x86_64 |
| Python | 3.14.4 (`.venv/bin/python`) |
| Pytest | 9.1.1; pluggy 1.6.0; anyio 4.14.2 |
| Pip | 26.2.1 in the local Python 3.14 virtual environment |
| Dependency declaration | `requirements.txt`; local `.venv` |
| Project import mode | `PYTHONPATH=src`, not an editable-install command |
| Investigation provider | committed local deterministic `mock` fixtures |
| Branch | `main` |
| Frozen implementation SHA | `524bc84d5b4607fab61f207aa8363e5694c32d46` |

The repository has no configured `pyproject.toml`, `setup.cfg`, `tox.ini`,
`Makefile`, Ruff, Black, mypy, or Pyright command. No formatter, linter, type
checker, or build tool was invented or installed for closure.

## Frozen-implementation verification commands and results

All successful commands below ran from the repository root and exited with
status 0.

| Purpose | Exact command | Observed result |
|---|---|---|
| Date | `date --iso-8601=seconds` | `2026-08-27T12:14:51+02:00` |
| Platform | `uname -a` | Linux 7.0.0-29-generic, x86_64 |
| Python | `.venv/bin/python --version` | Python 3.14.4 |
| Pytest | `PYTHONPATH=src .venv/bin/python -m pytest --version` | pytest 9.1.1 |
| Pip | `.venv/bin/python -m pip --version` | pip 26.2.1, Python 3.14 |
| Compilation | `PYTHONPATH=src .venv/bin/python -m compileall -q src tests scripts` | success; no output |
| Task 13 HTTP E2E first | `PYTHONPATH=src .venv/bin/python -m pytest tests/test_investigation_web_e2e.py` | 2 passed in 0.60s |
| Investigation web | `PYTHONPATH=src .venv/bin/python -m pytest tests/test_investigation_web.py tests/test_investigation_web_e2e.py` | 99 passed in 2.80s |
| Focused investigation | `PYTHONPATH=src .venv/bin/python -m pytest tests/test_investigation_prompts.py tests/test_investigation_structured_output.py tests/test_investigation_ids.py tests/test_investigation_mock_fixtures.py tests/test_investigation_mock_runtime.py tests/test_investigation_models.py tests/test_investigation_session.py tests/test_investigation_service.py tests/test_investigation_independent_analyses.py tests/test_investigation_group_discussion.py tests/test_investigation_group_decision.py tests/test_investigation_finalization.py tests/test_investigation_workflow_e2e.py tests/test_investigation_store.py tests/test_investigation_web.py tests/test_investigation_web_e2e.py` | 571 passed in 3.92s |
| Simulation and selection | `PYTHONPATH=src .venv/bin/python -m pytest tests/test_simulation_engine.py tests/test_speaker_selector.py tests/test_conversation_participant.py tests/test_message.py tests/test_generation_models.py` | 119 passed in 0.52s |
| Conversation, artifacts, CLI, and web | `PYTHONPATH=src .venv/bin/python -m pytest tests/test_conversation.py tests/test_conversation_service.py tests/test_conversation_writer.py tests/test_run_writer.py tests/test_conversation_cli.py tests/test_conversation_cli_e2e.py tests/test_web_app.py tests/test_web_startup.py` | 129 passed in 1.75s |
| Rater and evaluation | `PYTHONPATH=src .venv/bin/python -m pytest tests/test_rater_web.py tests/test_evaluation_models.py tests/test_evaluation_persistence_analysis.py tests/test_evaluation_pilot_e2e.py tests/test_evaluation_preparation_failures.py tests/test_evaluation_trials.py` | 24 passed in 0.80s |
| Persona and mock pipeline | `PYTHONPATH=src .venv/bin/python -m pytest tests/test_character_catalog.py tests/test_mock_pipeline_e2e.py tests/test_pipeline.py tests/test_agent_runtime.py tests/test_persona.py tests/test_persona_extraction.py tests/test_persona_io.py tests/test_system_prompt.py tests/test_mock_provider.py` | 67 passed in 0.55s |
| Explicit API-key-unset HTTP E2E | `PYTHONPATH=src env -u OPENAI_API_KEY .venv/bin/python -m pytest tests/test_investigation_web_e2e.py` | 2 passed in 0.49s |
| Full suite | `PYTHONPATH=src .venv/bin/python -m pytest` | 911 passed in 6.35s |

## Full-suite result

Pytest collected 911 tests and reported exactly:

```text
============================= 911 passed in 6.35s ==============================
```

Failures: 0. Skips: 0. Xfails: 0. Xpasses: 0. Reported warnings: 0. Exit
status: 0.

## HTTP E2E and interleaved isolation evidence

The Task 13 tests drive all state changes through the real investigation router
mounted in the normal main app:

```text
create → clue 1 → analyses → discussion → decision → explicit pause
→ clue 2 → analyses → discussion → decision → exhausted pause
→ rejected third clue → explicit finalization → final theory → completed
```

They assert a `303` canonical redirect after every successful mutation, no GET
side effects, frozen Round 1 clue visibility, deterministic participant and
discussion order, retained history, no automatic Round 2 or finalization, a
server-enforced `409` third-clue conflict, and no controls after completion.

A second E2E creates `session_001` and `session_002` through HTTP and
substantially interleaves both workflows. At representative checkpoints the
untargeted record retains exact object identity. Structural checks cover clue,
round, analysis, hypothesis, evidence, discussion run/message, decision, and
final-theory namespaces; neither aggregate contains the other's namespace.

## Offline evidence

The explicit E2E command removed `OPENAI_API_KEY` with `env -u`. The Task 13
fixture also removes it internally and replaces `socket.create_connection` and
`socket.socket.connect` with immediate test failures. Both complete workflows
passed through real committed local providers. This establishes that the
tested deterministic investigation workflow requires no OpenAI API key or
network access; it does not claim every repository script is network-incapable.

## Investigation state and persistence boundary

The E2E snapshots the temporary output directory and proves that complete
single- and two-session investigation workflows create no files. The terminal
smoke found no investigation/session artifact under the existing `outputs/`
tree and observed no output-file inventory change during second-session
actions. Existing conversation JSON, JSONL, and Markdown persistence remains
implemented and separate.

The normal application was stopped and restarted. Before restart,
`session_001` was completed and `session_002` was active. After restart, GETs
for both canonical URLs returned `404`, while `/investigations` returned `200`.
This directly verifies intentional process-local, non-durable registry state.

## Error and atomicity evidence

Focused route and registry tests cover bounded `400` validation, malformed or
unknown-session `404`, wrong-phase/repeated/completed/exhausted `409`, and safe
unexpected `500` responses. They verify that failures do not invoke later
providers where preclassified, do not expose internal details, and retain the
exact latest valid registry record. The terminal smoke additionally submitted
a valid third clue after mock exhaustion, observed a readable `409`, and then
retrieved a byte-identical pre-finalization detail page.

## Terminal HTTP smoke evidence

No interactive browser capability was available. Terminal smoke used the
normal startup path with the API key removed:

```text
env -u OPENAI_API_KEY .venv/bin/python scripts/run_web.py \
  --host 127.0.0.1 --port 18765
```

The socket-restricted execution sandbox initially prevented binding; the same
normal command was then run with localhost socket permission. Uvicorn reported
successful startup. Actual `curl` requests observed:

- `GET /health`, `GET /`, and `GET /investigations`: `200`;
- first creation: `303` to `/investigations/session_001`;
- all nine explicit Round 1/Round 2/finalization mutations: `303`;
- canonical GETs between phases: `200`;
- manual third-clue POST after exhaustion: `409`;
- second creation: `303` to `/investigations/session_002`;
- second-session clue POST: `303`; both detail pages remained independent;
- completed-page refresh was byte-identical; and
- after server restart, both prior detail URLs returned `404` and the index
  returned `200`.

HTML checks found the Round 1 Game Master pause, ordered discussion and decision
history, mock-exhaustion message, explicit finalization control, completed
message, both round histories, final theory, readable conflict message, and
distinct case/clue content for each session. These are terminal HTTP/template
checks, not interactive visual browser validation.

## Manual browser smoke evidence

**Pending.** This environment provided no interactive browser capability, so
no claim is made about human visual inspection or actual click interaction.
Before Sprint 7 is declared fully closed, a human should start the normal main
app with `OPENAI_API_KEY` unset and confirm:

1. `/`, `/health`, and investigation navigation load visibly.
2. Creation yields a canonical session page with readable participants.
3. Every Round 1 phase requires a separate click and decision pauses for the
   next clue.
4. Every Round 2 phase requires a separate click; both histories remain
   readable, no third clue is offered, and finalization remains explicit.
5. Finalization shows completed status and final theory and removes controls.
6. A second session remains visually independent during navigation/refresh.
7. A stale direct action presents the readable conflict page without losing
   the latest snapshot.
8. Restart removes the earlier process-local session URLs.

## Architecture boundaries

- Domain models and framework-independent application operations remain
  authoritative for phase and reference validation.
- The web layer owns delivery, presentation, PRG, and process-local registry
  orchestration; it does not add domain rules.
- Registry records pair immutable snapshots with runtime dependencies outside
  the aggregate. Per-session locks commit only complete validated replacements.
- The two-round/two-turn limit belongs only to the current fixture-backed mock
  runtime capability.
- The blind-rater app remains separate from the main conversation and
  investigation application.

## Scientific claim boundary and explicit limitations

Sprint 7 verifies technical workflow correctness, deterministic local
execution, browser delivery at the HTTP/template boundary, session isolation,
and reproducible mock fixtures. It does **not** establish that Sherlock or
Poirot is recognizable, that personas improve or harm game performance, that
the agents solve *Sherlock Holmes: Consulting Detective*, or any scientifically
meaningful persona-quality result.

Additional limitations are:

- deterministic mock only; no live-provider investigation verification;
- no investigation persistence or investigation CLI;
- no real or commercial investigation case, official solution, or scoring;
- two fixture-backed runtime characters only;
- two-round browser mock capability only, without a domain round limit; and
- no final human/LLM-judge recognizability study.

## Post-documentation verification

After the documentation edits, both required checks were repeated:

| Exact command | Observed result |
|---|---|
| `PYTHONPATH=src env -u OPENAI_API_KEY .venv/bin/python -m pytest tests/test_investigation_web_e2e.py` | 2 passed in 0.56s |
| `PYTHONPATH=src .venv/bin/python -m pytest` | 911 passed in 6.26s |

Both exited with status 0. This evidence is separate from the frozen
implementation verification above; the tested implementation SHA remains the
pre-documentation commit.

## Temporary-output cleanup

Compilation- and pytest-generated `.pyc` files and empty `__pycache__`
directories under `src`, `tests`, and `scripts` were removed after the final
test run. Terminal-smoke response files under `/tmp` were removed. No
conversation run, investigation artifact, API key, environment file, browser
profile, virtual-environment content, or machine-specific report is included
in the documentation changes.

## Remaining risks and future work

The only Sprint 7 closure item is the pending interactive browser smoke above.
Sprint 8 remains future work and has not started. Durable investigation state,
live providers, additional characters, real observability, scoring design, and
scientifically interpretable evaluation require later separately scoped work.
