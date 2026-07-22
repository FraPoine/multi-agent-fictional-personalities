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
│   └── github-sprint-setup.md
├── prompts/
│   ├── extract_persona.md
│   ├── agent_reply.md
│   └── style_neutralize.md
├── characters/
│   ├── sherlock/
│   ├── poirot/
│   ├── l/
│   └── layton/
├── data/                         # created as implementation needs it
│   ├── raw/
│   ├── processed/
│   └── personas/
├── src/                          # planned for Sprint 2+
│   ├── persona_extraction/
│   ├── agent_runtime/
│   ├── simulation/
│   ├── evaluation/
│   └── logging/
├── scripts/                      # planned for Sprint 2+
│   └── smoke_test.sh
├── mockups/
│   └── ui_mockups.md
└── configs/
    └── dev.yaml
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

Sprint 1 established the specification and architecture but did not implement a working runtime. Corpus completion and the first end-to-end pipeline belong to Sprint 2.

## Next step: Sprint 2

Sprint 2 should implement the minimum end-to-end pipeline for Sherlock Holmes and Hercule Poirot:

```txt
processed Sherlock/Poirot corpus -> validated persona JSON -> one saved agent response
```

See the [Sprint 2 plan](docs/sprint_2_plan.md) and [roadmap](docs/roadmap.md).

## Figma mockups 
[figma](https://www.figma.com/make/2dvBnDB3qcD9HVgimdZJm4/Multi-Agent-Personality-Simulator-Mockup?t=LYCAJGAbSbMaS37n-1&preview-route=%2Fevaluation)

## Canva presentation
[canva](https://canva.link/em2uvuw22kubcak)
