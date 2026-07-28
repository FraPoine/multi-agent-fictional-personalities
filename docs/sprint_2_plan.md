# Sprint 2 — Minimal persona-to-response pipeline

## Objective

> Implement the first end-to-end vertical slice that converts a processed fictional-character corpus into a validated persona JSON and uses that persona to generate one saved agent response.

Sprint 2 uses Sherlock Holmes and Hercule Poirot only. L and Professor Layton remain deferred.

## Checklist

- [x] Define the persona JSON schema.
- [x] Load the processed Poirot character corpus.
- [x] Load the persona-extraction prompt from a versioned file.
- [ ] Call the configured OpenAI model.
- [x] Validate mock provider output.
- [x] Save the validated mock persona JSON.
- [x] Generate one synthetic response using the mock provider and persona.
- [x] Save basic execution metadata for the mock run.
- [x] Provide one unified mock CLI command.
- [x] Add development commands to the README.

The unified Poirot command now prepares the extraction prompt, validates a
deterministic mock persona, renders the system prompt, obtains the configured
mock agent reply, and saves all four run artifacts. This completes the local
synthetic development pipeline only. The fixtures are not evidence of real
model behavior, and the OpenAI extraction and reply calls remain unimplemented
and unverified.

## Definition of Done

> A CLI command can generate a validated persona JSON from a processed
> character corpus and use that persona to produce one saved agent response.

This definition is currently demonstrated using the mock provider. Completion
with a real configured OpenAI model remains pending.

## Boundaries

The exact future OpenAI model remains configurable, secrets come from
environment variables, and prompts stay under `prompts/`. The current mock
artifacts are explicitly marked synthetic. Sprint 2 does not include
multi-agent conversation, evaluation trials, or the full four-character
experiment.
