# Sprint 6 Lead/Visit Redesign Completion Record

## Status

The four-task Lead/Visit migration was implemented and locally verified on
2026-08-31. This is an engineering architecture result, not evidence of persona
recognizability, fidelity, investigation quality, or mystery-solving ability.

## Architectural result

The authoritative immutable aggregate contains persistent
`InvestigationLead` records, chronological `LeadVisit` records, globally
retained `RevealedInformation`, bounded `ConversationRun` segments, optional
visit-aware reasoning artifacts, and an explicitly generated `FinalTheory`.
Revisiting a lead creates a new visit with the original lead ID. Analyses,
discussion, decisions, and visit completion do not gate navigation.

A corrective follow-up makes the chronological append boundary explicit:
only the latest visit accepts new information, discussions, or reasoning.
Earlier visits remain readable historical records. Visit-originated hypothesis
revisions additionally require the previous hypothesis to originate at the
same or an earlier visit index. The deterministic mock supports two bounded
segments on Visit 1 and one segment on Visits 2 and 3.

The application exposes deterministic creation, lead navigation, explicit
information disclosure, repeatable discussion, same-lead conversation
projection, optional reasoning, and explicit finalization. Context is rebuilt
from the immutable snapshot and contains no hidden persistent provider memory.
Fixture capability is runtime metadata and does not constrain domain lead or
visit counts.

## Original Sprint 6 and Sprint 7 boundary

The original Sprint 6 round workflow remains historically documented. Its
`Clue`, `InvestigationRound`, `InvestigationRoundStatus`, and phase services are
excluded from authoritative public exports. They remain directly importable
only to keep the original Sprint 7 compatibility screen and its verified
registry/locking infrastructure operational until a separate Lead/Visit UX
rewrite. The compatibility screen displays this status explicitly.

The FastAPI application, conversation/evaluation pages, process-local registry,
per-session locks, session allocation, immutable replacement, PRG behavior,
error handling, and session isolation remain intact. No future visual
investigation UX was implemented during this migration.

## Verification environment

- Execution: local, not CI
- Python: 3.14.4
- Pytest: 9.1.1
- Import mode: `PYTHONPATH=src`
- Provider: committed deterministic mock fixtures

## Commands and observed results

Focused investigation, explicitly without `OPENAI_API_KEY`:

```bash
PYTHONPATH=src env -u OPENAI_API_KEY .venv/bin/python -m pytest tests/test_investigation_lead_visit_models.py tests/test_investigation_visit_service.py tests/test_investigation_lead_finalization.py tests/test_investigation_cutover.py tests/test_investigation_ids.py tests/test_investigation_structured_output.py tests/test_investigation_prompts.py tests/test_investigation_mock_fixtures.py tests/test_investigation_mock_runtime.py
```

Result: `179 passed in 0.84s`.

Conversation and simulation regression:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_message.py tests/test_conversation.py tests/test_simulation_engine.py tests/test_speaker_selector.py tests/test_conversation_participant.py tests/test_conversation_service.py tests/test_conversation_writer.py tests/test_run_writer.py tests/test_conversation_cli.py tests/test_conversation_cli_e2e.py
```

Result: `185 passed in 1.27s`.

Persona and catalogue regression:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_persona.py tests/test_character_catalog.py tests/test_agent_runtime.py tests/test_persona_extraction.py tests/test_persona_io.py tests/test_pipeline.py tests/test_mock_pipeline_e2e.py tests/test_system_prompt.py tests/test_mock_provider.py
```

Result: `67 passed in 0.40s`.

Evaluation and rater regression:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_evaluation_models.py tests/test_evaluation_persistence_analysis.py tests/test_evaluation_pilot_e2e.py tests/test_evaluation_preparation_failures.py tests/test_evaluation_trials.py tests/test_rater_web.py
```

Result: `24 passed in 1.19s`.

Web and registry regression:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_web_app.py tests/test_web_startup.py tests/test_investigation_store.py tests/test_investigation_web.py tests/test_investigation_web_e2e.py
```

Result: `153 passed in 3.63s`.

Compilation and complete regression:

```bash
PYTHONPATH=src .venv/bin/python -m compileall -q src tests scripts
PYTHONPATH=src .venv/bin/python -m pytest
```

Compilation succeeded with no output. The full suite reported
`949 passed in 7.32s` with no failures, skips, or reported warnings.

The headline deterministic E2E removes `OPENAI_API_KEY`, replaces socket
connection functions with immediate failures, executes A → B → A plus further
leads, and explicitly finalizes. This verifies that tested path as offline; it
does not claim every repository command is incapable of networking.

## Deferred work

- Lead/Visit-specific Sprint 7 visual and interaction design
- Removal of the private original Sprint 7 round compatibility implementation
- Human participation and messaging
- Real case resources, ingestion, OCR, or parsing
- Durable investigation persistence
- Live providers and API-key workflows
- Scoring or official-solution comparison
- Persona recognizability or game-performance experiments

## Corrective chronology verification

The 2026-08-31 corrective follow-up was verified after adding the latest-visit
write invariant, visit-index hypothesis revision validation, and deterministic
Visit 1 segment 2 fixture mapping.

```bash
PYTHONPATH=src env -u OPENAI_API_KEY .venv/bin/python -m pytest tests/test_investigation_lead_visit_models.py tests/test_investigation_visit_service.py tests/test_investigation_lead_finalization.py tests/test_investigation_cutover.py tests/test_investigation_mock_runtime.py tests/test_investigation_mock_fixtures.py
```

Result: `101 passed in 0.70s`. The repeat-segment test also replaces socket
connection functions with immediate failures.

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_investigation_*.py
```

Result: `612 passed in 4.40s`.

```bash
PYTHONPATH=src .venv/bin/python -m compileall -q src tests scripts
PYTHONPATH=src .venv/bin/python -m pytest
```

Compilation succeeded with no output. The full suite reported
`952 passed in 6.60s`.
