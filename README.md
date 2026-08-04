# Multi-Agent Fictional Personalities

## Project summary

This project builds a multi-agent system that turns fictional characters into
persona-seeded LLM agents, lets them interact in controlled group-chat
simulations, and evaluates whether generated messages preserve recognizable
character identity and group-level dynamics.

The project does not try to prove that an LLM "is" a character. It studies
whether conditioning an LLM on structured persona profiles produces outputs
that human raters can identify above chance.

**Profile:** Individual Track B, mixed project.

The project has two distinct parts:

- a build component for persona extraction, conversation simulation, logging,
  web and CLI interaction, and evaluation tooling;
- a study component for controlled human evaluation of persona recognizability
  and agent behavior.

The currently implemented work mostly covers the build and local
reproducibility components. The human study has not been completed.

## Current implementation status

The repository currently provides structured synthetic persona fixtures for
Sherlock Holmes and Hercule Poirot, deterministic local mock responses,
round-robin multi-agent simulation, and explicit per-run message history.
Immutable `Message` and `ConversationRun` models validate results, and atomic
persistence safely publishes each completed run.

Both delivery interfaces remain available:

- a command-line conversation interface;
- a server-rendered FastAPI/Jinja web interface with validation, safe error
  states, loading feedback, ordered transcript rendering, and visible run and
  artifact paths.

Route and startup tests cover the web boundary. The current conversation
provider is fixed to `mock`, needs no API key, and makes no network request.
These deterministic fixtures support local development and reproducibility;
they do not demonstrate real LLM persona quality or validate character
recognizability. OpenAI-backed conversation execution is not implemented or
verified. A two-character technical mock pilot now exercises blind trial
generation, local rating, response persistence, and analysis. It verifies the
pipeline only; L, Professor Layton, and a scientifically interpretable human
evaluation remain future work.

## Technical blind-evaluation pilot

Prepare the fixed pilot (three neutral topics, three six-turn conversations,
six balanced trials, seed 42), then start its separate local rater interface:

```bash
python scripts/prepare_evaluation_pilot.py
python scripts/run_rater_web.py --pilot-id <pilot-id>
```

The first command prints the generated pilot ID and directory. The rater app
defaults to <http://127.0.0.1:8001/>. Recompute analysis after responses with:

```bash
python scripts/analyze_evaluation_pilot.py --pilot-id <pilot-id>
```

Pilots are atomically published under `outputs/evaluation/pilots/<pilot-id>/`
with `pilot_manifest.json`, provenance-free and answer-free
`trials_public.jsonl`, private `answer_key.jsonl`, genuine `responses.jsonl`,
development-only `synthetic_responses.jsonl`, reproducible `analysis.json`,
and `report.md`. Existing IDs are not overwritten. Normal analysis uses only
genuine responses, a 50% chance baseline, and a 95% Wilson score interval.

For automated development only, synthetic responses require the explicit
command `python scripts/create_synthetic_responses.py --pilot-id <pilot-id>
--confirm-development-only`. They carry `synthetic_data=true`, are never made
by pilot preparation, and must not be represented as human data.
Analyze that separate development file only with `--response-source synthetic`.

## Quick start

From a fresh clone:

```bash
git clone https://github.com/FraPoine/multi-agent-fictional-personalities.git
cd multi-agent-fictional-personalities

python -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python scripts/run_web.py
```

Open <http://127.0.0.1:8000/> and stop the server with `Ctrl+C`. The startup
command resolves the repository's `src/` layout itself; it does not require an
editable install or a manually configured `PYTHONPATH`.

## Local web interface

The implemented web flow is:

```text
open page
→ select Sherlock Holmes and Hercule Poirot
→ enter an investigation topic
→ choose 2–12 turns
→ submit
→ run a deterministic local mock conversation
→ view the ordered transcript
→ inspect the run ID and artifact paths
```

Both `sherlock` and `poirot` are required by the Sprint 4 web form. The topic
must not be blank, and the turn count must be a whole number from `2` through
`12`. The provider is fixed to `mock`, the seed is fixed to `42`, and output is
written beneath the repository's `outputs/` directory. There is no provider
dropdown or API-key input.

Start the interface with:

```bash
python scripts/run_web.py
```

The optional arguments are `--host`, `--port`, and `--reload`. Defaults are
host `127.0.0.1`, port `8000`, and reload disabled. For example:

```bash
python scripts/run_web.py --port 8080
python scripts/run_web.py --reload
```

## Conversation CLI

The Sprint 3 CLI remains supported alongside the web interface. Run a six-turn
synthetic conversation from the repository root with:

```bash
export PYTHONPATH="$PWD/src"

python scripts/run_conversation.py \
    --characters sherlock poirot \
    --topic "A valuable document disappeared from a locked room." \
    --turn-count 6 \
    --provider mock \
    --seed 42 \
    --output-root outputs
```

The required options are `--characters` (two or more unique supported slugs)
and `--topic`. Optional arguments are `--turn-count` (default `6`),
`--provider` (default and currently only `mock`), `--seed` (default `42`),
`--output-root` (default `outputs`), and `--run-id` (otherwise generated). The
supported MVB character slugs are `sherlock` and `poirot`.

## Generated artifacts

Web and conversation CLI runs are saved under:

```text
outputs/conversations/runs/<run-id>/
├── run.json
├── messages.jsonl
└── transcript.md
```

- `run.json` is the complete validated conversation run.
- `messages.jsonl` stores one serialized message per line.
- `transcript.md` is the human-readable Markdown transcript.

Persistence atomically reserves each run ID with a per-run lock file, writes
through a temporary sibling directory, and publishes only after all files are
written. Existing run IDs are never intentionally overwritten. After a
successful web submission, the page displays the run ID, repository-relative
artifact directory, and each of the three artifact names and paths. It does not
provide download links.

## Testing

Because the project uses a `src/` layout, run the complete suite with:

```bash
export PYTHONPATH="$PWD/src"
python -m pytest
```

Focused web checks are also available:

```bash
python -m pytest tests/test_web_app.py -q
python -m pytest tests/test_web_startup.py -q
```

Web route tests use temporary output directories and do not write conversation
runs into the repository. Tests require no OpenAI API key, and mock
critical-path tests reject attempted network access.

## Current limitations

- Conversation execution currently supports only the local `mock` provider.
- Synthetic fixtures do not establish persona quality or recognizability.
- OpenAI-backed conversation execution is not implemented or verified.
- L and Professor Layton are not yet supported by the working conversation
  interfaces.
- The technical mock pilot cannot establish persona recognizability or support
  scientific conclusions; a real provider and genuine human responses are
  required before making persona-quality claims.
- The web interface is local and has no authentication, deployment, or run
  history browser.

## Repository structure

```text
project-root/
├── characters/
├── configs/
├── docs/
├── outputs/
├── prompts/
├── scripts/
├── src/multi_agent_personalities/
│   ├── agent_runtime/
│   ├── application/
│   ├── artifacts/
│   ├── cli/
│   ├── llm/
│   ├── models/
│   ├── persona_extraction/
│   ├── pipeline/
│   ├── simulation/
│   └── web/
└── tests/
```

Generated files beneath `outputs/` are local run products and are not
guaranteed to be committed.

## Repository documentation

- [Proposal](docs/proposal.md)
- [Functional specification](docs/functional_spec.md)
- [Architecture](docs/architecture.md)
- [Data model](docs/data_model.md)
- [Evaluation plan](docs/evaluation_plan.md)
- [Roadmap](docs/roadmap.md)
- [Sprint 4 plan](docs/sprint_4_plan.md)
- [Sprint 4 smoke test](docs/sprint_4_smoke_test.md)
- [Sprint 5 plan](docs/sprint_5_plan.md)

## Historical development details

Sprint 1 established the specification and architecture. Sprint 2 completed a
deterministic local pipeline for Sherlock Holmes and Hercule Poirot: it loads
processed corpora, builds versioned prompts, validates synthetic personas,
generates deterministic mock responses, and saves persona, prompt, response,
and metadata artifacts in isolated run directories. Unit and network-free
end-to-end tests cover this flow.

The Sprint 2 pipeline remains available:

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

Each invocation creates `persona.json`, `system_prompt.txt`, `response.txt`,
and `metadata.json` under `outputs/<character>/runs/<run-id>/`. These older
single-agent artifacts are distinct from the Sprint 3 and Sprint 4
conversation-run structure documented above.

The individual corpus, prompt, and provider diagnostic scripts under
`scripts/` remain useful for development. The persona and response fixtures
are synthetic and were not generated by OpenAI. The OpenAI-backed end-to-end
pipeline remains unimplemented and unverified.

## Figma and presentation links

- [Figma mockups](https://marker-oculus-50834570.figma.site/)
- [Canva presentation](https://canva.link/em2uvuw22kubcak)
