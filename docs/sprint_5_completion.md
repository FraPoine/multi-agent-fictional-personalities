# Sprint 5 Completion

## 1. Status

**Completed**

## 2. Completion date

2026-08-06

## 3. Tested implementation commit

`701555f273083470a83a8766d5cb3ac9f017fe9c`

This is the implementation state tested before Task 15 documentation changes.
No closure commit SHA is claimed in advance.

## 4. Environment

| Field | Observed value |
|---|---|
| Platform | Linux |
| Python | 3.14.4 (`.venv/bin/python`) |
| Pytest | 9.1.1 |
| Provider | `mock` |
| API key required | No |
| Provider account required | No |
| External network required by tested flows | No |

The initial literal `python --version` probe exited 127 because the unactivated
shell had no global `python` command. The repository virtual environment was
then used for every Python command. Port 8015 was occupied; the web smoke used
the permitted alternate localhost port 18015.

## 5. Sprint objective

Complete a deterministic offline foundation for configurable participants,
replaceable speaker selection, participant-owned mock providers, structured
generation metadata, compatible artifacts, existing evaluation tooling, and
validated investigation-domain models without adding live execution or a
playable investigation.

## 6. Delivered functionality

- ordered, validated configuration for two or more participants;
- catalog-driven CLI and web conversation paths;
- `SpeakerSelector` with deterministic `RoundRobinSelector`;
- participant-owned file-backed mock providers;
- validated `GenerationResult`, metadata propagation, and legacy reads;
- atomic conversation artifacts with structured metadata;
- immutable `Clue`, `EvidenceReference`, `AgentAnalysis`, `Hypothesis`,
  `GroupDecision`, `FinalTheory`, and `InvestigationSession` models.

Sherlock Holmes and Hercule Poirot remain the only production runtime
characters. Mock remains the only executable provider.

## 7. Verified architecture

```text
CLI / web
→ configurable application service
→ simulate_chat()
→ SpeakerSelector / RoundRobinSelector
→ participant-owned mock provider
→ GenerationResult
→ Message / ConversationRun
→ run.json + messages.jsonl + transcript.md

separate immutable investigation aggregate and records (no workflow)
```

The selector chooses only a stable speaker ID. Generation, prompt creation,
history, and persistence remain outside it. Investigation models have no
FastAPI, provider, persistence, or clock dependency.

## 8. Tasks 1–15 summary

Tasks 1–10 established scope, catalog configuration, configurable participant
boundaries, data-driven UI, selector injection, participant-bound providers,
and structured generation results. Maintenance commit `706d13d` enforced
run/message metadata consistency. Tasks 11–14 persisted metadata and added the
investigation records and aggregate (`281529d`, `7329a6e`, `ca37389`,
`701555f`). Task 15 ran the integrated regression, smoke checks, cleanup, and
documentation reconciliation recorded here.

## 9. Acceptance-criteria evidence

| Boundary | Result |
|---|---|
| Configurable participants and catalog-driven UI | Passed focused service, catalog, CLI, and web tests |
| Selector isolation and deterministic order | Passed 15 selector and 39 simulation tests |
| Participant-owned providers and one generation per turn | Passed service, runtime, simulation, and CLI smoke checks |
| Generation schemas and metadata propagation | Passed generation, runtime, message, run, writer, and artifact checks |
| Legacy deserialization | Passed message and conversation focused suites |
| Investigation validation and partial states | Passed 54 model and 32 session tests |
| Offline evaluation pilot compatibility | Passed pilot commands, privacy checks, separation checks, and reproducibility comparison |
| Complete offline regression | 410 passed, 0 failed, 0 skipped, 0 warnings |

## 10. Exact commands and results

All commands were executed from the repository root on 2026-08-06.

| Command | Exit | Observed result |
|---|---:|---|
| `git status --short` | 0 | Clean baseline; no output |
| `git rev-parse HEAD` | 0 | `701555f273083470a83a8766d5cb3ac9f017fe9c` |
| `python --version` | 127 | Global command absent in unactivated shell |
| `.venv/bin/python --version` | 0 | Python 3.14.4 |
| `git diff --check` | 0 | No errors |
| `.venv/bin/python -m compileall -q src scripts` | 0 | No errors |
| `.venv/bin/python -m pytest tests/test_character_catalog.py -q` | 0 | 10 passed |
| `.venv/bin/python -m pytest tests/test_conversation_service.py -q` | 0 | 30 passed |
| `.venv/bin/python -m pytest tests/test_speaker_selector.py -q` | 0 | 15 passed |
| `.venv/bin/python -m pytest tests/test_simulation_engine.py -q` | 0 | 39 passed |
| `.venv/bin/python -m pytest tests/test_generation_models.py -q` | 0 | 27 passed |
| `.venv/bin/python -m pytest tests/test_agent_runtime.py -q` | 0 | 23 passed |
| `.venv/bin/python -m pytest tests/test_conversation_writer.py -q` | 0 | 13 passed |
| `.venv/bin/python -m pytest tests/test_investigation_models.py -q` | 0 | 54 passed |
| `.venv/bin/python -m pytest tests/test_investigation_session.py -q` | 0 | 32 passed |
| `.venv/bin/python -m pytest tests/test_conversation_cli.py -q` | 0 | 11 passed |
| `.venv/bin/python -m pytest tests/test_conversation_cli_e2e.py -q` | 0 | 1 passed |
| `.venv/bin/python -m pytest tests/test_web_app.py -q` | 0 | 29 passed |
| `.venv/bin/python -m pytest tests/test_web_startup.py -q` | 0 | 7 passed |
| `.venv/bin/python -m pytest tests/test_mock_pipeline_e2e.py -q` | 0 | 2 passed |
| `.venv/bin/python -m pytest tests/test_evaluation_trials.py -q` | 0 | 3 passed |
| `.venv/bin/python -m pytest tests/test_evaluation_persistence_analysis.py -q` | 0 | 11 passed |
| `.venv/bin/python -m pytest tests/test_evaluation_pilot_e2e.py -q` | 0 | 1 passed |
| `.venv/bin/python -m pytest tests/test_message.py -q` | 0 | 19 passed |
| `.venv/bin/python -m pytest tests/test_conversation.py -q` | 0 | 29 passed |
| `.venv/bin/python -m pytest` | 0 | 410 passed in 2.74s |

The full run collected 410 tests and reported 410 passed, 0 failed, 0 skipped,
and 0 warnings; therefore there are no warning types to list.

## 11. CLI smoke result

`run_conversation.py --help` was inspected. A four-turn Sherlock/Poirot run
used seed 42, provider `mock`, run ID `sprint5-smoke`, and a disposable `/tmp`
output root. It alternated Sherlock, Poirot, Sherlock, Poirot; retained four
ordered messages and complete prior history through the tested engine path;
and generated exactly one response per turn.

## 12. Web smoke result

With `PYTHONPATH` unset, `run_web.py --port 18015` started successfully.
`GET /health` returned 200 and `{"status":"ok","provider":"mock"}`;
`GET /` returned 200 and rendered both catalog characters. A valid four-turn
POST returned 200, `Completed`, ordered speakers, run ID, and artifact paths.
Invalid `turn_count=abc` returned HTML 400, `Failed`, and `Enter a whole number
between 2 and 12.` The server stopped cleanly. This is HTTP-level evidence; no
browser interaction is claimed.

## 13. Single-agent pipeline result

After inspecting `run_pipeline.py --help`, the mock pipeline passed for both
Sherlock and Poirot. Each produced exactly `persona.json`,
`system_prompt.txt`, `response.txt`, and `metadata.json`. Persona identity,
nonempty prompt/response, synthetic marker, provider `mock`, and model `mock`
were validated. The historical Sprint 2 contract was unchanged.

## 14. Evaluation-pilot result

The prepare, explicit development-only synthetic-response, and synthetic
analysis help and execution paths were exercised under `/tmp`. The pilot
created three source conversations and six balanced public trials. Public rows
contained no correct answer or source provenance. The genuine response file
remained empty; 12 development responses were separately stored with
`synthetic_data=true`. Repeated analysis was byte-identical and reported the
unchanged two-character chance baseline and synthetic accuracy of 0.5. The
analysis disclaimer states that this is not scientific evidence.

## 15. Artifact verification

Conversation `run.json` and every `messages.jsonl` row deserialized into the
current models and contained matching generation metadata. Message order and
count matched the complete run snapshot. `transcript.md` omitted technical
generation fields. Temporary smoke outputs were removed after inspection and
were not committed.

## 16. Known limitations

- no live provider or real provider telemetry;
- no third or fourth runtime character;
- no playable investigation, controller, persistence, prompts, or UI;
- no automatic clue disclosure, reasoning, hypothesis updates, or consensus;
- no final four-character recognizability experiment or genuine ratings.

Sprint 6 orchestration must record or enforce which clues were visible when an
analysis was produced; the immutable Sprint 5 models do not enforce temporal
visibility by themselves.

## 17. Risks and technical debt

Runtime mock assets still live under test fixtures. Deterministic fixtures
cannot demonstrate persona quality. The web smoke is HTTP-level rather than
browser-automated. The single-agent CLI has no configurable output root, so
closure had to remove its exact generated directories afterward. No CI result
is claimed; this record describes local verification.

## 18. Next Sprint 6 step

Implement a deterministic mock investigation workflow over the existing
aggregate while keeping clue disclosure user-controlled and preserving the
visibility context for each analysis. Do not add live-provider integration in
that increment.

## 19. Final verdict

Sprint 5 is complete. All required automated and smoke checks passed against
the tested implementation commit, active documentation is reconciled, no
substantive production defect remains, and generated evidence is excluded from
the closure changes.

### Issue #7 closure summary

Tasks 1–15 are complete against tested commit
`701555f273083470a83a8766d5cb3ac9f017fe9c`. The exact suite result is 410
passed, 0 failed, 0 skipped, and 0 warnings. Single-agent pipeline,
multi-agent CLI, localhost web, artifact, evaluation-pilot, and investigation-
model checks passed. Remaining limitations are the intentional absence of a
live provider, additional characters, a playable investigation workflow/UI,
and a final scientific evaluation. Sprint 6 begins the mock investigation
workflow. Issue #7 was inspected but not modified or closed.
