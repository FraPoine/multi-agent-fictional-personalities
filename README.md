# Multi-Agent Fictional Personalities

## Project summary

This project builds fictional-detective agents for two connected goals. The
primary quantitative goal is to test whether blind raters can attribute their
generated messages to the intended character above chance. The second goal is
to let the agents participate in a user-moderated game of *Sherlock Holmes:
Consulting Detective*, providing a structured setting for individual behavior
and qualitative or exploratory group-dynamics observations.

The project does not try to prove that an LLM "is" a character. It studies
whether conditioning an LLM on structured persona profiles produces outputs
that blind raters can identify above chance. It does not claim that a model
authentically is, understands, or reproduces a fictional character's identity.

**Profile:** Individual Track B, mixed project.

The project has two distinct parts:

- a build component for persona extraction, conversation simulation, logging,
  web and CLI interaction, and evaluation tooling;
- a study component for controlled blind evaluation of persona recognizability
  and secondary investigation-session observations.

The currently implemented work mostly covers the build and local
reproducibility components. The final study has not been completed.

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

Sprint 4 formally completed this local web workflow in commit
`b48636ae6fffbb73f9cf65adaf848dd4792e5633`; its
[completion record](docs/sprint_4_completion.md) documents the historical
verification result of 189 passing tests. The web and CLI delivery layers
reuse the framework-independent conversation application/runtime logic rather
than duplicating simulation or persistence behavior.

Route and startup tests cover the web boundary. The current conversation
provider is fixed to `mock`, needs no API key, and makes no network request.
These deterministic fixtures support local development and reproducibility;
they do not demonstrate real LLM persona quality or validate character
recognizability. OpenAI-backed conversation execution is not implemented or
verified. A two-character technical mock pilot now exercises blind trial
generation, local rating, response persistence, and analysis. It verifies the
pipeline only. The final study targets four characters, but characters three
and four are not finalized or implemented; L and Professor Layton are previous
candidates. A scientifically interpretable evaluation remains future work.

Sprint 5 completed the generic offline foundation. It remains network-free and
requires no API key, genuine rater responses, or live-provider measurements.
The verified closure result is 410 passed, 0 failed, 0 skipped, and 0 warnings
on Python 3.14.4. See the
[Sprint 5 completion record](docs/sprint_5_completion.md).

Supported runtime characters are declared in `configs/characters.yaml`. The
validated loader preserves declaration order and resolves every asset path
relative to that catalog file, independently of the current working directory.
The existing mock persona and response assets remain under `tests/fixtures/`
temporarily; moving runtime assets into a production-owned directory is future
cleanup rather than part of the catalog refactor.

The completed foundation includes the validated catalog, configurable
participant application boundaries, a data-driven conversation UI, the
standalone speaker-selector contract, and participant-bound deterministic mock
providers. The
application service supplies `RoundRobinSelector` by default, while the engine
requires a `SpeakerSelector` and resolves its validated character ID to the
participant-owned provider. The provider boundary now returns validated
`GenerationResult` values with deterministic mock metadata. Persona extraction
consumes `result.text`; agent runtime now stores both `result.text` and the
complete metadata in each new `Message`. Legacy messages without nested metadata
remain readable, and no metadata is shown in transcripts, CLI output, or web UI.
Sprint 6 adds a framework-independent deterministic investigation application
workflow over those immutable models. Its public operations create active
sessions, reveal caller-supplied clues, generate independent analyses, reuse
round-robin conversation simulation for discussion, record structured group
decisions, pause after every round, and finalize only on an explicit caller
request. Local fixture-backed two-round execution is covered end to end. It
does not provide investigation persistence, CLI or web delivery, live-provider
execution, automatic clues/actions/finalization, scoring, or recognizability
evaluation of investigation output. See the
[Sprint 6 completion record](docs/sprint_6_completion.md).

Sprint 7 exposes that workflow in the existing main FastAPI/Jinja application.
The browser delivery uses catalogue-backed mock participants, a process-local
in-memory registry, one canonical state-driven detail page, and an explicit
Game Master POST for each transition. The current mock browser scenario
supports two rounds and then offers explicit finalization; this is a runtime
capability, not a two-round domain invariant. Investigation state is not
persisted and vanishes when the application process restarts. See the
[Sprint 7 verification record](docs/sprint_7_completion.md).

### Implemented workflows

- validated persona loading and deterministic local single-agent generation;
- deterministic multi-agent conversations through application, CLI, and web;
- atomic persistence for conversation runs;
- technical evaluation-pilot preparation, rating, and analysis tooling; and
- deterministic two-round mock investigation orchestration with explicit clue
  revelation, analysis, discussion, decisions, pauses, and finalization,
  available through the main local web application.

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

The conversation page is at `/`. The investigation list and creation page is
at <http://127.0.0.1:8000/investigations>. Investigation execution uses the
committed deterministic mock fixtures, requires no OpenAI API key, and writes
no investigation session artifacts. Its process-local sessions are lost on
server restart; conversation runs continue to use the persistence described
below.

## Local web interface

The implemented web flow is:

```text
open page
→ select at least two available characters
→ enter an investigation topic
→ choose 2–12 turns
→ submit
→ run a deterministic local mock conversation
→ view the ordered transcript
→ inspect the run ID and artifact paths
```

The form renders every character in the validated catalog and selects all
currently available characters by default. A submission must contain at least
two unique supported character slugs. Because the production catalog currently
contains only Sherlock and Poirot, both are initially selected. The topic must
not be blank, and the turn count must be a whole number from `2` through `12`.
The provider is fixed to `mock`, the seed is fixed to `42`, and output is
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

- `run.json` is the canonical complete validated run snapshot, including
  nested generation metadata on new messages.
- `messages.jsonl` is the canonical ordered per-turn generation trace. Each
  line contains one complete serialized message with the same nested metadata.
- `transcript.md` is the human-readable Markdown transcript and deliberately
  omits technical generation metadata.

Artifacts created before generation metadata was introduced remain readable.
Current mock metadata is deterministic and mostly contains `null` values. Real
token counts, latency, request IDs, and retry observations require a future
provider; no cost calculation or broader logging system exists yet.

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
python -m pytest tests/test_investigation_web.py -q
python -m pytest tests/test_investigation_web_e2e.py -q
```

The complete investigation workflow check is:

```bash
python -m pytest tests/test_investigation_workflow_e2e.py
```

Web route tests use temporary output directories and do not write conversation
runs into the repository. Tests require no OpenAI API key, and mock
critical-path tests reject attempted network access.

## Current limitations

- Conversation execution currently supports only the local `mock` provider.
- Synthetic fixtures do not establish persona quality or recognizability.
- OpenAI-backed conversation execution is not implemented or verified.
- Only Sherlock Holmes and Hercule Poirot are supported by the working runtime;
  the third and fourth final characters remain undecided.
- The technical mock pilot cannot establish persona recognizability or support
  scientific conclusions; real-provider outputs and responses from the
  pre-registered rater methodology are required before making persona-quality
  claims.
- The web interface is local and has no authentication, deployment, or run
  history browser.
- Normal application scheduling uses deterministic round-robin. There is no
  dynamic conversation manager or content-dependent speaker priority.
- Investigation has no persistence, CLI, live provider, automatic clue
  generation, automatic lead execution, automatic finalization, official-case
  scoring, or recognizability evaluation. Its implemented web UI is local,
  deterministic, mock-only, and process-local.
- Real token usage, latency, request IDs, retries, and monetary costs are not
  collected.

## Future work

Sprint 6's offline mock investigation workflow and Sprint 7's local browser
delivery are implemented. Sprint 7 automated and terminal HTTP verification is
recorded, while final interactive browser smoke confirmation remains pending.
Sprint 8 generalizes the recognizability evaluation, and Sprint 9 completes
the offline system. Live-
provider integration, real observability, characters three and four,
pre-registration, and real experimental data remain later work.

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
│   ├── character_catalog.py
│   ├── pipeline.py
│   ├── simulation/
│   │   ├── participant.py
│   │   └── speaker_selector.py
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
- [Sprint 5 completion record](docs/sprint_5_completion.md)
- [Sprint 6 completion record](docs/sprint_6_completion.md)
- [Sprint 7 plan](docs/sprint_7_plan.md)
- [Sprint 7 verification record](docs/sprint_7_completion.md)

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
