# Multi-Agent Fictional Personalities

## Project summary

This project builds a multi-agent system that turns fictional characters into persona-seeded LLM agents, lets them interact in controlled group-chat simulations, and evaluates whether the generated messages preserve recognizable character identity and group-level dynamics.

The project is not about proving that an LLM "is" a character. It studies whether conditioning an LLM on structured persona profiles produces outputs that human raters can identify above chance.

## Project profile

**Profile:** Mixed project.

The project has both:
- a build component: an interactive system for persona extraction, chat simulation, logging, and evaluation;
- a study component: a controlled evaluation of persona recognizability and agent behavior.

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

The Sprint 1 scope is intentionally narrow:

- 4 characters for the first end-to-end version;
- one LLM model;
- one persona extraction method;
- one simulation mode;
- one evaluation protocol;
- one simple UI or CLI-first prototype.

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
│   └── sprint_plan.md
├── notes/
│   └── sprint-1-yourname.md
├── prompts/
│   ├── extract_persona.md
│   ├── agent_reply.md
│   └── style_neutralize.md
├── data/
│   ├── raw/
│   ├── processed/
│   └── personas/
├── src/
│   ├── persona_extraction/
│   ├── agent_runtime/
│   ├── simulation/
│   ├── evaluation/
│   └── logging/
├── scripts/
│   └── smoke_test.sh
├── mockups/
│   └── ui_mockups.md
└── configs/
    └── dev.yaml
```

## Expected Sprint 1 outputs

- `docs/proposal.md`
- `docs/functional_spec.md`
- `docs/data_model.md`
- `docs/evaluation_plan.md`
- `docs/architecture.md`
- `docs/sprint_plan.md`
- `mockups/ui_mockups.md`
- initial repository structure
- Sprint 1 GitHub milestone and issues
- one sprint-end markdown note per team member

## Next step after Sprint 1

Sprint 2 should implement the minimum end-to-end pipeline on 2 characters:

```txt
raw text -> persona JSON -> agent reply -> short transcript -> evaluation sample -> simple metric
```
