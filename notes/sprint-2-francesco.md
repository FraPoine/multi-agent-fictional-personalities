# Sprint 2 — Francesco

## Completed

- Prepared the Poirot persona-extraction prompt from the processed corpus and
  versioned prompt template.
- Added existing Sherlock and Poirot persona JSON files and a Jinja system
  prompt template.
- Added a reusable, strict Pydantic persona schema and unit tests.
- Made the OpenAI connection test use `OPENAI_MODEL`.
- Documented the current development setup and scripts.

## Currently working

- `scripts/prepare_persona_prompt.py` selects Poirot corpus examples and writes a
  compiled extraction prompt.
- `scripts/build_agent_prompt.py` validates the existing Poirot persona JSON and writes
  its system prompt.
- `scripts/test_openai_connection.py` tests an OpenAI connection when the API key and model are
  configured.

## Incomplete

- The OpenAI persona-extraction call is not integrated.
- Persona generation and saving are not automated.
- Agent response generation and execution metadata are not implemented.
- There is no complete end-to-end CLI pipeline.

## Next main task

Integrate the configured OpenAI persona-extraction call, validate its response
with the persona schema, and save the validated persona JSON.
