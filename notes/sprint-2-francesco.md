# Sprint 2 — Francesco

## Completed

- Prepared the Poirot persona-extraction prompt from the processed corpus and
  versioned prompt template.
- Added existing Sherlock and Poirot persona JSON files and a Jinja system
  prompt template.
- Added a reusable, strict Pydantic persona schema and unit tests.
- Made the OpenAI connection test use `OPENAI_MODEL`.
- Documented the current development setup and scripts.
- Added one unified Poirot and Sherlock CLI pipeline using deterministic local
  mock fixtures.
- Added validation and persistence for the mock persona, system prompt, mock
  reply, and synthetic execution metadata.
- Added end-to-end tests that prohibit network access and write only to
  temporary test directories.

## What the sprint produced

- A shared pipeline for Sherlock Holmes and Hercule Poirot.
- Strict persona validation with Pydantic.
- Versioned extraction, reply, and system-prompt templates.
- Deterministic mock persona and response providers.
- An isolated run directory for every pipeline invocation.
- Saved `persona.json`, `system_prompt.txt`, `response.txt`, and
  `metadata.json` artifacts.
- Unit tests and network-free end-to-end tests.

## Limitations

The saved personas and replies are synthetic development fixtures. No claim
about real character fidelity or OpenAI behavior can yet be made. The external
provider path remains unimplemented and unverified until credentials are
available.

## Moved to Sprint 3

- Implementation of `OpenAIProvider`.
- Live persona extraction.
- Live agent responses.
- Live end-to-end verification when credentials are available.
- Multi-agent round-robin conversation.
- Transcript and structured JSONL logging.
