# Sprint 7 demo-case integration completion

The three supplied English demos are available in the existing investigation
lobby. `data/raw/investigation/` remains provenance; application-ready YAML,
rich JSON, and image assets live under `configs/investigation/`.

The static/runtime and Lead/Visit boundaries remain intact. Eligible sections
are disclosed through `RevealedInformation` without duplication. Session state
contains only changing values plus an auditable accounting ledger. Lead-section
effects are authoritative, so redundant Demo 3 trigger metadata is absent from
runtime configuration and cannot double-apply. Authored actions are preflighted
before visits or charges, and authored outcomes complete without `FinalTheory`.

Demo 1 supports floor/approach choices and the corrected canonical scope
`nw-32-top-floor`. Demo 2 supports A/B/C gates, revisit unlocks, explicit
break-in/uniform selection, and lead closure. Demo 3 supports time codes,
modes, budget changes, item-gated entries, and terminal outcomes. Demo 3 charges
each successful configured variant visit, including a revisit in another
available variant; failed preflight actions create no visit and no charge.

The later web closure exposes only the three authored demos in the normal
lobby. Actual local assets remain player-visible and human-mediated; verified
directory, newspaper, and informant text reaches agents only after explicit
consultation. Case-specific operational guidance replaces generic rules.

Demos 1 and 2 now implement public questions, deterministic drafts and edits,
irreversible lock, lazy answer-element reveal, deterministic scoring, Holmes
benchmarks, and separately lazy long-solution reveal. Demo 1 intentionally
retains the supplied 140-point answer-element total and printed Holmes score
of 100. Demo 3 has no official conclusion package and terminates only through
its exact authored outcome. These statements supersede this document's earlier
“later UI/scoring work” status; that wording was historical at initial content
integration.

Only the three supplied English demos are integrated. Raw provenance remains
under `data/raw/investigation/`; application-owned normalized files live under
`configs/investigation/`. `The Demise of a Teetotaller` is not integrated.
There is no live provider, investigation database or persistence, human chat,
or automatic map interpretation. Later lawful user-provided material must be
added as a new validated case/content/resource/conclusion package with retained
provenance and the complete offline regression rerun. No network or API key is
required for the current demos.

## Targeted correction verification — 2026-09-04

The authoritative normalized runtime paths are
`configs/investigation/cases/`, `configs/investigation/content/`,
`configs/investigation/resources.yaml`,
`configs/investigation/resources_text/`, and
`configs/investigation/conclusions/`; retained provenance remains under
`data/raw/investigation/`. Demos 1 and 2 use the official public-question,
private-scoring, and private-solution lifecycle. Demo 3 is
`authored_outcome` and has no questions, private scoring, or private solution.

The case-creation correction is commit `eedad92` (`fix(web): enforce authored
case creation boundary`). Verification was rerun after that correction:

- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_investigation_web.py tests/test_investigation_web_e2e.py -q`
  — 10 passed in 1.53s.
- `env -u OPENAI_API_KEY -u OPENAI_ORG_ID PYTHONPATH=src .venv/bin/python -m pytest -q`
  — 984 passed in 9.46s.
- `PYTHONPATH=src .venv/bin/python -m compileall -q src tests` — passed.
- `git diff --check` — passed.

The tested mock path is offline and API-key-free; the full suite includes the
configured startup coverage. No repository-configured lint, type, or format
command was found, so none was invented or installed. `scripts/smoke_test.sh`
is absent. Interactive browser and screenshot verification remains pending
because no such facility was available in this execution.
