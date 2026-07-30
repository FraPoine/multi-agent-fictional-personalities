# Sprint 2 — Minimal persona-to-response pipeline

## Objective

> Implement and verify a deterministic local end-to-end pipeline that converts
> the processed Sherlock Holmes and Hercule Poirot corpora into validated
> persona artifacts and saved synthetic agent responses.

Sprint 2 uses Sherlock Holmes and Hercule Poirot only. L and Professor Layton remain deferred.

## Checklist

- [x] Define the persona JSON schema.
- [x] Load the processed Poirot and Sherlock character corpora.
- [x] Load the persona-extraction prompt from a versioned file.
- [x] Generate deterministic persona output with the local mock provider.
- [x] Strictly validate the mock provider output.
- [x] Save the validated mock persona JSON.
- [x] Render and save the character system prompt.
- [x] Generate one synthetic response using the mock provider and persona.
- [x] Save basic execution metadata for the mock run.
- [x] Provide one unified mock CLI command.
- [x] Add development commands to the README.
- [x] Add unit tests and network-free end-to-end tests.

The unified character-independent command now supports Poirot and Sherlock. It
prepares the extraction prompt, validates a deterministic mock persona, renders
the system prompt, obtains the configured mock agent reply, and saves all four
run artifacts. This completes the deterministic local development pipeline.

## Definition of Done

> A unified CLI command deterministically converts either processed Sherlock
> Holmes or Hercule Poirot corpus into a strictly validated persona JSON,
> renders and saves its system prompt, produces one saved synthetic agent
> response, and records execution metadata in an isolated run directory, with
> unit and network-free end-to-end tests passing.

## OpenAI deferral

OpenAI integration has been intentionally deferred to Sprint 3. The mock
outputs are synthetic development fixtures and must not be presented as
evidence of real LLM behavior or character fidelity. The external provider
path remains unimplemented and unverified until an API key is available.

## Boundaries

The exact future OpenAI model remains configurable, secrets come from
environment variables, and prompts stay under `prompts/`. Sprint 2 does not
include multi-agent conversation, evaluation trials, or the full
four-character experiment.
