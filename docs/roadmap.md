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

- Realign the two final goals and active documentation.
- Generalize configuration and application boundaries for a configurable
  participant sequence of at least two, without adding a character.
- Isolate deterministic round-robin speaker choice behind `SpeakerSelector`
  and `RoundRobinSelector`; leave a dynamic manager for later.
- Introduce `GenerationResult` and deterministic offline generation metadata.
- Model investigation sessions, clues, analyses, evidence, hypotheses,
  decisions, final theories, and partial session states without orchestration.
- Finish with a complete offline regression. See the
  [Sprint 5 plan](sprint_5_plan.md).

The previously implemented two-character mock pilot remains technical
foundation. Sprint 5 requires no API key, network access, live provider, real
token/cost collection, genuine human response, LLM-judge panel, real pilot, or
real investigation game.

## Later provider and experimental work

- Integrate and verify a real configurable LLM provider.
- Collect real provider metadata and add cost calculation where supported.
- Finalize and implement characters three and four.
- Pre-register the final human-versus-LLM-judge methodology, sample size,
  candidate design, chance baseline, and analysis.
- Generate real experimental material, collect the chosen ratings, and report
  scientifically interpretable recognizability results.
- Implement investigation orchestration and persistence, then run moderated
  real investigation sessions.

## Presentation sprint

Run and report the pre-registered four-character evaluation using the selected
rater methodology, including confidence intervals, limitations, and the final
presentation.
