# Sprint 8.3 — Professor Layton conversation integration

Date: 2026-11-02. Audited repository HEAD before edits:
`12b34cc6691cbfe1598037553dd7dc373ee6008a`. Initial working tree was clean.

## Scope and minimal plan

All 12 ZIP members were extracted and inspected, including the task, research
notes, corpus, Persona, source inventory, item provenance and checksums. The
pre-edit plan was recorded at `/tmp/layton-sprint83/implementation-plan.md`:
filter evidence conservatively, retain provenance, register a curated Persona
through existing catalogue paths, add a synthetic reply fixture, test runtime
loading/order/persistence and update related documentation. Inspection confirmed
that no schema, prompt, provider or runtime implementation changes were needed.

## Files and behavior

- `configs/characters.yaml`: register `layton` third, with stable ID
  `professor_layton` and display name Professor Layton.
- `characters/layton/layton_persona_curated_candidate.json`: unchanged supplied
  manually curated eight-field candidate. Both conversation loaders read it
  directly through the historical `persona_fixture_path` catalogue field.
- `characters/layton/corpus/persona_corpus.jsonl`: 35 original English editorial
  summaries only; all 13 unofficial transcript quote texts excluded.
- `characters/layton/metadata/`: unchanged source, entry and example provenance,
  original methodological notes and research checksums; integration manifest
  records archive hash, filtered IDs, exclusion rationale and artifact hashes.
- `characters/layton/README.md`: critical review, source/copyright limitations,
  exact loading behavior, fixture distinction and study-design caveats.
- `characters/layton/layton.yaml`: replace obsolete deferred status with
  conversation-candidate and editorial-summary status.
- `tests/fixtures/layton_agent_response.txt`: separate newly authored synthetic
  deterministic response; no canonical dialogue or genuine model output.
- `tests/test_layton_integration.py`: seven offline tests, including parametrized
  two/three-character persistence, corpus/provenance/hash consistency, Pydantic
  validation, catalogue paths, injected Copilot prompt inspection and investigation
  rejection.
- `tests/test_character_catalog.py`, `tests/test_conversation_cli.py`,
  `tests/test_web_app.py`: update obsolete catalogue expectations and replace
  Layton with `unknown` in an unsupported-character negative test.
- `README.md`, `AGENTS.md`, this report: document current conversation scope.

At Sprint 8.3 completion, the real-provider route still read Sherlock/Poirot's
synthetic catalog fixtures. The subsequent Persona-loading fix selects their
complete generated `outputs/` profiles through explicit `live_persona_path`
configuration. Mock fixtures and Layton's curated candidate remain unchanged.

The conversation web interface automatically displays/selects Layton through its
catalogue after app restart. No web template, static asset, or human-evaluation
interface changed. Investigation support remains exactly Sherlock/Poirot. Its
catalogue-driven lobby may show Layton as unsupported, but runtime capabilities
reject him. No investigation data, fixtures or implementation were changed.

## Evidence decision and limitations

All nine supplied research hashes passed. Copied sidecars and the renamed
Persona retain their original bytes; the corpus retains only original summary
lines. Quote text is not archived elsewhere in versioned files. Full source
references and IDs for excluded quotes remain in metadata. Source pages were
not independently authenticated against games or recordings, and redistribution
legitimacy was not established. This implementation makes no legal-clearance,
primary-source authentication, persona-quality or recognizability claim.

The candidate is plausible as a starting configuration but not an experimental
result. The corpus and illustrative examples do not establish actual lexical
style. Summary selection favors teaching, Luke and dramatic scenes; confidence
numbers are editorial judgments. Some rows are thematically overlapping even
though no exact normalized-text duplicates exist.

Sherlock/Poirot's literary-dialogue evidence and Layton's mixed-format research
(now imported as summaries only) are not methodologically equivalent. The current
extraction prompt/conventions expect representative speech lines and were not
changed or run. A separate documented study-design decision is required before
fair confirmatory comparison. No scientific validation or live-model quality
test has been conducted.

## Verification

Commands were run from the repository root unless otherwise stated.

1. `sha256sum -c SHA256SUMS`, in the extracted research directory:
   **9/9 OK**, exit 0. These are original-package checks, not a verification
   command for the deliberately filtered repository tree.
2. `PYTHONPATH=src .venv/bin/python -m pytest tests/test_layton_integration.py tests/test_character_catalog.py tests/test_conversation_cli.py tests/test_live_conversation_service.py -q`:
   initial run **43 passed, 2 failed** due to new test-harness assumptions
   (mock replies retain final newlines; providers return `GenerationResult`).
   Corrected only the new tests; final focused run **45 passed in 1.12s**.
3. `PYTHONPATH=src .venv/bin/python -m pytest -q`:
   **1075 passed in 13.90s**, exit 0, including investigation and web regressions.
4. CLI smoke test, exit 0:

   ```bash
   PYTHONPATH=src .venv/bin/python scripts/run_conversation.py \
     --characters sherlock poirot layton \
     --topic 'How can we distinguish a plausible explanation from an established fact?' \
     --turn-count 6 --provider mock --seed 42 \
     --output-root /tmp/layton-sprint83/smoke-output \
     --run-id sprint_8_3_layton_smoke
   ```

   Six turns persisted to
   `/tmp/layton-sprint83/smoke-output/conversations/runs/sprint_8_3_layton_smoke/`
   as `run.json`, `messages.jsonl`, and `transcript.md`. Automated tests also
   deserialize both structured formats, verify transcript contents, exact mock
   reply text and repeated Sherlock/Poirot/Layton round-robin ordering.
5. `git diff --check`: passed.

The injected offline Copilot-provider test verifies that all Layton description,
style, trait, rule and example strings reach his generation prompt. It makes no
network call and is not an actual Copilot SDK/live-model test. No real LLM run,
blind identification study, human-rating session, transcript authentication, or
legal review was run. No commit was created; changes remain reviewable in the
working tree.

## Narrow follow-up work

1. Run an explicitly authorized live Copilot conversation to assess generation
   quality; preserve model and generation metadata.
2. Resolve source authentication and permissible evidence use before adding any
   original dialogue excerpts.
3. Decide and document consistent evidence/extraction conditions before the
   recognizability study; evaluate the curated candidate empirically.
4. Review Sherlock/Poirot's preexisting real-provider fixture loading separately.
