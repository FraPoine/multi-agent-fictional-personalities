# Multi-Agent Fictional Personalities

## Project summary

This project builds a multi-agent system that turns fictional characters into persona-seeded LLM agents, lets them interact in controlled group-chat simulations, and evaluates whether the generated messages preserve recognizable character identity and group-level dynamics.

The project is not about proving that an LLM "is" a character. It studies whether conditioning an LLM on structured persona profiles produces outputs that human raters can identify above chance.

## Project profile

**Profile:** Individual Track B, mixed project.

The project has both:
- a build component: an interactive system for persona extraction, chat simulation, logging, and evaluation;
- a study component: a controlled evaluation of persona recognizability and agent behavior.

## Scope and schedule

The final experiment uses Sherlock Holmes, Hercule Poirot, L, and Professor Layton. The initial Minimum Viable Build (MVB) uses only Sherlock and Poirot; L and Professor Layton are later extensions after the first end-to-end pipeline works.

The first interface is a CLI. OpenAI is the initial LLM provider, while the exact model is supplied through YAML configuration and an environment variable rather than hard-coded. Agents retain conversation history only within a run; there is no persistent memory. Multi-agent turns will use deterministic round-robin scheduling and runs will produce JSONL logs.

## Minimum Viable Build

The first working version will support:

1. selecting a small fixed set of fictional characters;
2. loading or writing small text corpora for each character;
3. extracting a structured persona profile for each character;
4. simulating a short multi-agent conversation;
5. saving transcripts and logs;
6. running a simple blind identification task;
7. computing accuracy against chance.

## Initial scope

The first vertical slice is intentionally narrow: Sherlock Holmes and Hercule Poirot, one configurable OpenAI model, versioned prompts, Pydantic validation, and a CLI command that saves one persona and one generated response. The four-persona experiment follows later.

## Repository structure

```txt
project-root/
├── README.md
├── AGENTS.md
├── docs/
│   ├── proposal.md
│   ├── functional_spec.md
│   ├── data_model.md
│   ├── evaluation_plan.md
│   ├── architecture.md
│   ├── sprint_1_plan.md
│   ├── sprint_2_plan.md
│   └── roadmap.md
├── notes/
│   ├── sprint-1-francesco.md
│   ├── sprint-2-francesco.md
│   └── github-sprint-setup.md
├── configs/
│   └── dev.yaml
├── prompts/
│   ├── extract_persona.md
│   ├── agent_reply.md
│   ├── agent_system_prompt.j2
│   └── style_neutralize.md
├── characters/
│   ├── sherlock/
│   ├── poirot/
│   ├── l/
│   └── layton/
├── outputs/
│   ├── sherlock/
│   └── poirot/
├── scripts/
│   ├── prepare_persona_prompt.py
│   ├── build_agent_prompt.py
│   ├── run_pipeline.py
│   ├── test_openai_connection.py
│   ├── load_corpus.py
│   └── split_corpus.py
├── src/
│   └── multi_agent_personalities/
│       ├── __init__.py
│       ├── models/
│       │   ├── __init__.py
│       │   └── persona.py
│       └── llm/
│           ├── __init__.py
│           └── base.py
├── tests/
│   └── test_persona.py
├── mockups/
│   └── ui_mockups.md
```

## Sprint status

- `docs/proposal.md`
- `docs/functional_spec.md`
- `docs/data_model.md`
- `docs/evaluation_plan.md`
- `docs/architecture.md`
- `docs/sprint_1_plan.md`
- `docs/sprint_2_plan.md`
- `docs/roadmap.md`
- `mockups/ui_mockups.md`
- initial repository structure
- `notes/sprint-1-francesco.md`
- initial Sherlock corpus download and cleaning, plus partial evidence extraction

Sprint 1 established the specification and architecture. Sprint 2 completed a
deterministic local pipeline for Sherlock Holmes and Hercule Poirot: it loads
processed corpora, builds versioned prompts, validates synthetic personas,
generates deterministic mock responses, and saves persona, prompt, response,
and metadata artifacts in isolated run directories. Unit and network-free
end-to-end tests cover this flow.

## Next step: Sprint 3

Sprint 3 extends the completed local vertical slice into:

```txt
Sherlock persona + Poirot persona
→ round-robin conversation
→ conversation history
→ transcript
→ structured JSONL logs
```

Sprint 3 will also implement the OpenAI provider and defer live verification
until credentials become available. OpenAI-backed execution does not currently
work. See the completed [Sprint 2 plan](docs/sprint_2_plan.md) and the
[roadmap](docs/roadmap.md).

## Development

Create and activate a virtual environment from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install the dependencies used by the current scripts and tests:

```bash
python -m pip install openai python-dotenv jinja2 pydantic pytest
```

Make the `src` layout importable in the current shell:

```bash
export PYTHONPATH="$PWD/src"
```

### Unified synthetic mock pipeline

The current Sprint 2 flow can be run end to end without an API key or network
access:

```bash
export PYTHONPATH="$PWD/src"

python scripts/run_pipeline.py \
    --character poirot \
    --provider mock \
    --message "How would you begin investigating this case?"

python scripts/run_pipeline.py \
    --character sherlock \
    --provider mock \
    --message "What should we examine first?"
```

Each invocation creates a new directory under
`outputs/<character>/runs/<run_id>/` containing:

- `persona.json`: the mock provider output validated with the `Persona` schema;
- `system_prompt.txt`: the Jinja-rendered character system prompt;
- `response.txt`: the configured mock agent response;
- `metadata.json`: run paths and provenance, including
  `"is_synthetic": true`.

**Warning:** for both Poirot and Sherlock, the persona and agent response come
from deterministic local synthetic development fixtures. They were not
generated by OpenAI and are not evidence that either persona or response
reflects real model behavior. No OpenAI-backed end-to-end execution has been
implemented or verified yet.

Configure the OpenAI credentials and model either in the shell:

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="your-model-name"
```

or in a repository-root `.env` file:

```dotenv
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=your-model-name
```

The `.env` file is ignored by Git. With the environment activated, the
currently available development scripts are:

```bash
# Load and count the processed Poirot corpus.
python scripts/load_corpus.py

# Deterministically split the processed Poirot corpus.
# This overwrites the existing persona/evaluation JSONL split files.
python scripts/split_corpus.py

# Send a small request to verify the OpenAI connection.
python scripts/test_openai_connection.py

# Prepare the Poirot persona-extraction prompt from the processed corpus.
python scripts/prepare_persona_prompt.py

# Validate the existing Poirot persona JSON and build its agent system prompt.
python scripts/build_agent_prompt.py

# Run the unit tests.
python -m pytest
```

These are separate development steps. A complete end-to-end CLI pipeline is
also available with local synthetic mock outputs as documented above. The
individual commands remain useful for inspecting and developing each stage.
The real OpenAI-backed end-to-end pipeline remains unimplemented and
unverified.

## Figma mockups 
[figma](https://www.figma.com/make/2dvBnDB3qcD9HVgimdZJm4/Multi-Agent-Personality-Simulator-Mockup?t=LYCAJGAbSbMaS37n-1&preview-route=%2Fevaluation)

## Canva presentation
[canva](https://canva.link/em2uvuw22kubcak)
