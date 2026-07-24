# Sprint 2 — Minimal persona-to-response pipeline

## Objective

> Implement the first end-to-end vertical slice that converts a processed fictional-character corpus into a validated persona JSON and uses that persona to generate one saved agent response.

Sprint 2 uses Sherlock Holmes and Hercule Poirot only. L and Professor Layton remain deferred.

## Checklist

- [x] Define the persona JSON schema.
- [x] Load the processed Poirot character corpus.
- [x] Load the persona-extraction prompt from a versioned file.
- [ ] Call the configured OpenAI model.
- [ ] Validate the model output.
- [ ] Save the persona JSON.
- [ ] Generate one response using the persona.
- [ ] Save basic execution metadata.
- [x] Add development commands to the README.

The current scripts can prepare a Poirot extraction prompt and validate an
existing Sherlock or Poirot persona before rendering a system prompt. The
generated persona files currently in the repository are not evidence of an
automated extraction pipeline: the OpenAI extraction call and complete CLI
pipeline remain unimplemented.

## Definition of Done

> A CLI command can generate a validated persona JSON from a processed character corpus and use that persona to produce one saved agent response.

## Boundaries

The exact OpenAI model remains configurable, secrets come from environment variables, and prompts stay under `prompts/`. Sprint 2 does not include multi-agent conversation, evaluation trials, fabricated outputs, or the full four-character experiment.
