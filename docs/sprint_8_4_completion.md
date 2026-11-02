# Sprint 8.4 — Kogoro Mori conversation integration

Date: 2026-11-02. Pre-edit HEAD:
`c96cfdb8a1c326c79358c0c58e75b9c6ded74b45`; working tree was clean.
All 12 archive members were extracted and reviewed. Explicit user authorization
superseded historical conditional approval wording in the attached documents.

## Changes and decisions

- `characters/kogoro/`: unchanged 36-entry editorial corpus, manually curated
  Persona, research provenance and methodological notes; added character status,
  README and integration manifest with archive hash, file mappings and hashes.
  All 10 external research checksum entries passed. Stale internal manifest
  hashes and the two broadcaster/publisher context mismatches are documented
  without silently changing research files. The actual repository Pydantic
  `Persona` validates the supplied candidate.
- `configs/characters.yaml`: append `kogoro` / `kogoro_mouri` fourth. The existing
  mock and Copilot conversation paths load the same curated Persona directly.
- `tests/fixtures/kogoro_agent_response.txt`: separate original synthetic reply,
  neither canonical dialogue nor live generation.
- `tests/test_kogoro_integration.py`: integrity, schema, provenance, all six pairs,
  all four trios, four-agent round-robin, persistence, injected offline Copilot
  prompt inspection and investigation runtime rejection.
- `tests/test_character_catalog.py`, `tests/test_web_app.py`: update catalog
  expectations; exercise all selections, Kogoro's KM initials and fourth color,
  attribution, accessible selection, artifacts and disabled/rejected
  investigation participation.
- `AGENTS.md`, `README.md`, this report: update current conversation scope.

No UI, runtime, provider, prompt, schema, investigation or evaluation implementation
changes were needed. Existing Personas, corpora and fixtures were not modified.
No live LLM call or extraction was performed. No commit was created.

## Verification

Commands run from repository root except the archive checksum check:

```bash
# Inside the extracted kogoro_mori_sprint_8_4 research directory:
sha256sum -c SHA256SUMS
# 10/10 OK

PYTHONPATH=src .venv/bin/python -m pytest tests/test_kogoro_integration.py tests/test_layton_integration.py tests/test_character_catalog.py tests/test_web_app.py tests/test_conversation_cli.py tests/test_conversation_cli_e2e.py tests/test_conversation_service.py tests/test_live_conversation_service.py -q
# 176 passed

PYTHONPATH=src .venv/bin/python -m pytest -q
# 1123 passed

git diff --check
# Passed

PYTHONPATH=src .venv/bin/python scripts/run_conversation.py \
  --characters sherlock poirot layton kogoro \
  --topic 'How should we verify an uncertain witness timeline?' \
  --turn-count 8 --provider mock --seed 42 \
  --output-root outputs/sprint_8_4_smoke --run-id kogoro_four_agent_smoke
# Exit 0; eight turns, two per agent
```

The initial added investigation web test expected the wrong existing rejection
message. Correcting that test alone resolved the failure; no product behavior
needed correction. Final focused and full suites both passed.

Smoke artifacts remain available locally for review in
`outputs/sprint_8_4_smoke/conversations/runs/kogoro_four_agent_smoke/`:
`run.json`, `messages.jsonl`, `transcript.md`. A separate offline check parsed
the run with `ConversationRun`, compared every JSONL `Message` to the run,
verified the exact four-agent order repeated twice, checked each message/name
in the transcript and confirmed exactly the three expected files.

## Remaining limitations

These are technical integration results, not scientific recognizability or
character-fidelity evidence. The summaries are not canonical dialogue; English
voice choices and confidence values are editorial. Original manga panels and
source authenticity were not independently verified. Evidence modality and
manual curation differ from Sherlock/Poirot's literary-dialogue approach.
Sherlock/Poirot's pre-existing real-provider synthetic Persona loading remains
unchanged. Live behavior and aligned human evaluation remain future work.

Suggested commit message for review:
`feat(characters): integrate Kogoro Mori as fourth conversation agent`
