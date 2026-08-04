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

- Implemented only the mock technical foundation: balanced trial generation,
  leakage filtering, a separate rater-interface dry run, response persistence,
  synthetic development checks, and basic analysis.
- Sprint 5 is not complete. Live-provider generation, diverse real outputs,
  measured token/cost usage, genuine human responses, and the controlled
  Sherlock/Poirot pilot remain pending. See the [Sprint 5 plan](sprint_5_plan.md).

## Presentation sprint

Run and report the full four-character human evaluation, including confidence
intervals, limitations, and the final presentation.
