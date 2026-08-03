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

- Add a minimal local web interface over the existing mock conversation
  pipeline without replacing the CLI.
- Allow Sherlock Holmes and Hercule Poirot selection, topic and turn-count
  configuration, and local mock conversation submission.
- Display the ordered transcript, visible validation or runtime errors, run ID,
  saved artifact path, and generated artifact filenames.
- Add critical-path tests plus local startup and reproducibility documentation.

## Sprint 5

- Generate blind evaluation trials and introduce the separate rater interface.
- Add basic analysis and prepare the first controlled evaluation.
- Complete smoke-test or reproducibility work not finished during Sprint 4.

This phase is future work and has not started.

## Presentation sprint

Run and report the full four-character human evaluation, including confidence
intervals, limitations, and the final presentation.
