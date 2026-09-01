# Roadmap

The target for the first usable release is August 7, 2026. The final course deadline is in September; no exact date is currently documented.

## Sprint 1

Architecture, specification, evaluation design, repository structure, and initial corpus work.

## Sprint 2

Completed deterministic mock pipeline from processed corpus to validated
persona to one saved synthetic response for Sherlock Holmes and Hercule
Poirot.

## Sprint 3

- Completed multi-agent round-robin simulation with explicit per-run history.
- Completed atomic conversation persistence with a Markdown transcript,
  canonical JSON, and structured JSONL messages.
- Completed local CLI for saved, deterministic synthetic mock conversations.
- OpenAI provider implementation and live verification remain pending.

## Sprint 4

- Completed the minimal local web interface over the existing mock
  conversation pipeline without replacing the CLI.
- Added Sherlock Holmes and Hercule Poirot configuration, deterministic local
  mock execution, ordered transcript display, and run and artifact details.
- Added visible validation and safe error states, loading feedback, responsive
  styling, route tests, and startup-command tests.
- Documented and smoke-tested dependency installation, local startup,
  conversation execution, and artifact inspection. See the
  [Sprint 4 completion record](sprint_4_completion.md).
- OpenAI-backed conversation execution remains pending, and persona evaluation
  remains future work.

## Sprint 5

- Completed realignment of the two final goals and active documentation.
- Generalized configuration and application boundaries for a configurable
  participant sequence of at least two, without adding a character.
- Isolated deterministic round-robin speaker choice behind `SpeakerSelector`
  and `RoundRobinSelector`; leave a dynamic manager for later.
- Introduced `GenerationResult` and deterministic offline generation metadata.
- Modeled investigation sessions, clues, analyses, evidence, hypotheses,
  decisions, final theories, and partial session states without orchestration.
- Completed the offline regression with 410 passing tests. See the
  [Sprint 5 completion record](sprint_5_completion.md).

The previously implemented two-character mock pilot remains technical
foundation. Sprint 5 requires no API key, network access, live provider, real
token/cost collection, genuine human response, LLM-judge panel, real pilot, or
real investigation game.

## Sprint 6 — Mock investigation workflow

- Completed and verified deterministic offline orchestration over the Sprint 5
  models, including two rounds, immutable clue visibility, structured analyses,
  round-robin discussions, decisions, pauses, and explicit finalization.
- Delivered no investigation persistence, UI, live provider, automatic clue or
  action execution, scoring, or investigation-output recognizability study.
- See the [Sprint 6 completion record](sprint_6_completion.md).

### Sprint 6 Lead/Visit redesign

- Replaced the authoritative round state machine with persistent semantic
  leads, chronological visits, global explicit information disclosure, and
  repeatable bounded conversation segments.
- Made analyses, hypotheses, and decisions optional and non-gating.
- Added explicit Lead/Visit finalization and deterministic semantic mock tasks.
- Isolated remaining round implementation as private historical compatibility
  code. See the [redesign completion record](sprint_6_redesign_completion.md).

## Sprint 7 — Investigation web UI

- The catalogue-backed deterministic mock UI now uses the authoritative
  Lead/Visit model end to end: lobby, Case Opening, semantic leads, new visits
  and revisits, information disclosure, repeatable discussions, resources,
  explicit finalization, and a completed read-only archive.
- Task 4 removed the original round routes, presentation helpers, dead styles,
  and obsolete HTTP tests. Private round application/model compatibility code
  remains deliberately outside the web contract.
- Full HTTP workflow, interleaved-session isolation, investigation, and
  repository regressions pass offline. The investigation path writes no
  artifacts and process restart discards state. See the historical
  [original verification record](sprint_7_completion.md) and final
  [redesign completion record](sprint_7_redesign_completion.md).

## Sprint 8 — Generic recognizability evaluation

- Generalize the evaluation design after the runtime character set expands.

## Sprint 9 — Complete offline system

- Integrate and regress the complete offline conversation, investigation, and
  evaluation system.

## Later live-provider and experimental work

- Integrate and verify a real configurable LLM provider.
- Collect real provider metadata and add cost calculation where supported.
- Finalize and implement characters three and four.
- Pre-register the final human-versus-LLM-judge methodology, sample size,
  candidate design, chance baseline, and analysis.
- Generate real experimental material, collect the chosen ratings, and report
  scientifically interpretable recognizability results.
- Integrate a live provider only after the complete offline system.
- Add investigation persistence and run moderated real investigation sessions.

## Presentation sprint

Run and report the pre-registered four-character evaluation using the selected
rater methodology, including confidence intervals, limitations, and the final
presentation.
