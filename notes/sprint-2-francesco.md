# Sprint 2 — Francesco

## Completed

- Prepared the Poirot persona-extraction prompt from the processed corpus and
  versioned prompt template.
- Added existing Sherlock and Poirot persona JSON files and a Jinja system
  prompt template.
- Added a reusable, strict Pydantic persona schema and unit tests.
- Made the OpenAI connection test use `OPENAI_MODEL`.
- Documented the current development setup and scripts.
- Added one unified Poirot CLI pipeline using deterministic local mock
  fixtures.
- Added validation and persistence for the mock persona, system prompt, mock
  reply, and synthetic execution metadata.
- Added end-to-end tests that prohibit network access and write only to
  temporary test directories.

## Currently working

- `scripts/prepare_persona_prompt.py` selects Poirot corpus examples and writes a
  compiled extraction prompt.
- `scripts/build_agent_prompt.py` validates the existing Poirot persona JSON and writes
  its system prompt.
- `scripts/run_pipeline.py` runs the complete synthetic Poirot development flow
  with the mock provider and creates an isolated run directory.
- `scripts/test_openai_connection.py` tests an OpenAI connection when the API key and model are
  configured.

## Incomplete

- The OpenAI persona-extraction call is not integrated.
- Real OpenAI persona generation and saving are not implemented or verified.
- Real OpenAI agent response generation is not implemented or verified.
- Sherlock support is not yet available in the unified CLI.

## Next main task

After credentials are available, design and verify the real OpenAI provider
path without treating the successful synthetic mock pipeline as evidence that
the external model path works.
