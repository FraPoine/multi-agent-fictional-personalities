# Sprint 7 case-catalogue integration completion

## Scope and outcome

The six-task Sprint 7 catalogue integration is complete for synthetic,
offline, process-local use. The FastAPI/Jinja investigation path now selects a
local `CaseDefinition`, resolves physical lead references into persistent
semantic leads, presents case-aware resources including multiple maps, and
retains chronological visits through explicit finalization and a read-only
archive. This closure adds no commercial content and makes no scientific claim.

The verified integration range begins at `3cf030d` (local case catalogue
foundation). Closure verification started from `181016a` on Python 3.14.4.

## Final architecture

```text
configs/investigation/resources.yaml
configs/investigation/cases/*.yaml
             │
             ▼
         CaseCatalog
             │ resolve case_id server-side
             ▼
CaseDefinition ──opening snapshot──▶ InvestigationSession
                                      ├── InvestigationLead[]
                                      ├── LeadVisit[]
                                      ├── RevealedInformation[]
                                      ├── ConversationRun[]
                                      └── optional FinalTheory
```

The application loads one immutable catalogue. `InvestigationSession.case_id`
records provenance, while `case_introduction` snapshots the selected opening;
the complete case definition is not embedded in the aggregate. The registry is
process-local, uses per-session locking, and replaces immutable snapshots only
after successful application operations.

## Lead references and chronology

`InvestigationLead.lead_id` is an internal, service-owned, session-scoped ID
used in URLs and relationships. `InvestigationLead.reference` is the canonical
player-facing physical notation copied from `CaseLeadDefinition`; it is not a
resource ID. The same visible reference may resolve to different lead keys and
labels in different cases.

Supported schemes are:

- London address: number plus `NW`, `WC`, `SW`, `EC`, or `SE`, displayed as
  `42 NW`; compact, reversed, spaced, and single-hyphen aliases are accepted,
  and the number has no two-digit maximum.
- Carlton interior: `GF`, `FF`, or `BF` plus a number, displayed as `GF-26`;
  compact or single-hyphen aliases are accepted.

Malformed syntax returns HTTP `400`; supported syntax absent from the selected
case returns `404`. First entry creates one semantic lead and one visit.
Entering the current lead is a conflict. Entering a historical reference opens
history without mutation; only the explicit internal-`lead_id` revisit route
appends a new `LeadVisit`. Thus A → B → A retains one Lead A and three visits.

## Resource model

`CaseResourceDefinition` provides a stable resource ID, structural type, title,
optional safe relative asset path, optional date and description, and
`initially_available`. Types are map, newspaper, directory, informants,
document, and handout. Each case owns an explicit ordered `resource_refs`
collection; resources may be shared without being duplicated. Zero, one, or
multiple maps are valid, and multiple maps retain order in the drawer selector.
Hidden resources are omitted and missing optional assets are labelled honestly.

## Route and UX flow

The normal browser path is catalogue card and investigator selection → `303`
creation redirect → trusted Case Opening → physical reference entry → current
or historical semantic thread → explicit revisit → resource toolbar/drawer →
explicit Final Theory → completed read-only archive. GET selection and resource
views are side-effect free. Task 5 aligned the lobby proportions, lead rail,
editorial message stream, resource toolbar/drawer, opening, final state, and
responsive lead overlay with the supplied Figma Make structure while retaining
semantic forms, keyboard dismissal, focus restoration, and accessible labels.

Figma fidelity was verified structurally against the Make source context and
specified proportions; the published target could not be rendered through the
available connector, so pixel-perfect fidelity is not claimed. Repository
fonts were retained and compact text glyphs were used where durable exported
icons were unavailable.

## Cross-case, atomicity, and offline evidence

The real HTTP router is tested with an injected synthetic catalogue in which
both Case A and Case B define `42 NW`. Simultaneous sessions resolve it to
different case-specific keys and labels while retaining separate case IDs,
opening snapshots, disclosures, conversation-run IDs, leads, and resources.
The shipped-case E2E also verifies both lobby cards, the exact selected opening,
42 NW → 95 NW → 42 NW chronology, multiple-map markup, newspaper/directory
visibility, finalization, and archive readability.

Focused tests explicitly preserve the prior snapshot after malformed and
unknown lead entry, stale information and discussion writes, provider
discussion failure, premature finalization, finalization-provider failure, and
all completed-session mutations.

The offline path was run with `OPENAI_API_KEY` removed. The HTTP E2E's autouse
fixture rejects both `socket.create_connection` and `socket.socket.connect`,
and the selected catalogue/resource/reference/E2E command passed 40 tests.
Investigation sessions created no output directory. This evidence applies to
the commands below; it is not a claim about unexecuted external tooling.

## Verification

Environment: Python 3.14.4. No configured Ruff, Black, mypy, Pyright, tox, or
equivalent repository lint/type/format gate was found, so no tooling was
installed.

Focused integration and adjacent regressions:

```bash
PYTHONPATH=src env -u OPENAI_API_KEY .venv/bin/python -m pytest \
  tests/test_case_catalog.py tests/test_case_resources.py \
  tests/test_investigation_case_leads.py tests/test_investigation_visit_service.py \
  tests/test_investigation_lead_visit_models.py \
  tests/test_investigation_lead_finalization.py \
  tests/test_investigation_mock_runtime.py tests/test_investigation_mock_fixtures.py \
  tests/test_investigation_store.py tests/test_investigation_web.py \
  tests/test_investigation_web_task1.py tests/test_investigation_web_task2.py \
  tests/test_investigation_web_task3.py tests/test_investigation_web_e2e.py \
  tests/test_conversation.py tests/test_conversation_service.py \
  tests/test_simulation_engine.py tests/test_web_app.py \
  tests/test_character_catalog.py tests/test_persona.py \
  tests/test_persona_extraction.py tests/test_persona_io.py tests/test_pipeline.py \
  tests/test_evaluation_models.py tests/test_evaluation_persistence_analysis.py \
  tests/test_evaluation_pilot_e2e.py tests/test_evaluation_preparation_failures.py \
  tests/test_evaluation_trials.py tests/test_rater_web.py tests/test_web_startup.py -q
```

Result: **385 passed in 3.67s**.

Explicit socket-blocked catalogue/resource/reference/HTTP path:

```bash
PYTHONPATH=src env -u OPENAI_API_KEY .venv/bin/python -m pytest \
  tests/test_case_catalog.py tests/test_case_resources.py \
  tests/test_investigation_case_leads.py tests/test_investigation_web_e2e.py -q
```

Result: **40 passed in 0.75s**.

Complete repository regression:

```bash
PYTHONPATH=src env -u OPENAI_API_KEY .venv/bin/python -m pytest
```

Result: **917 passed in 5.86s**, with no failures, skips, or warnings reported.

Compilation and whitespace checks:

```bash
PYTHONPATH=src .venv/bin/python -m compileall -q src tests
git diff --check
```

Result: **passed** (both commands produced no error output).

## Obsolete-occurrence classification

- No active product occurrence of `DEMO_CASE_TITLE`, manual lobby opening,
  Lead name/type inputs, one-map enforcement, case-unaware web creation, or a
  hardcoded case resource list remains.
- `legacy-local-demo` and application-level free-form creation defaults are
  intentional compatibility for older domain callers and snapshots.
- `DEMO_CASE` in a Task 1 test is test-only naming for the first synthetic
  catalogue fixture.
- “Case Opening” is current valid presentation and prompt terminology.
- Resource-type display labels are presentation metadata, not case resources.
- Sprint 5, Sprint 6, and earlier Sprint 7 plans/completion records are
  historical evidence and may accurately describe their former manual or
  round-oriented workflows.
- Legacy free-form lead provenance documented in the data model is intentional
  compatibility, not the normal browser flow.

## Boundaries and adding owned material later

Investigation state remains process-local: there is no database, persistence,
authentication, live provider, human chat, scoring, OCR/PDF ingestion, or
automatic unlock engine. Private round-workflow code remains covered only for
historical compatibility. The current Figma review is structural rather than a
pixel screenshot comparison.

The repository ships **no copyrighted Sherlock case text, maps, newspapers,
scans, or handouts**. Carlton House, Queen's Park, Blue Edition, and other
user-owned material are not integrated. When the user supplies material they
own or may lawfully use, add a validated case YAML, declare explicit resource
IDs in `resources.yaml`, place owned files beneath the local catalogue asset
root using safe relative paths, set availability deliberately, and rerun the
offline focused and full regressions. No domain redesign is required.

This work establishes system structure and reproducibility only. It does not
demonstrate better persona fidelity, recognizability, reasoning, or case-solving
performance.
