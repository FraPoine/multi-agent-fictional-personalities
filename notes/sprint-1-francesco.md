# Sprint 1 — Francesco

## Sprint objective

Establish the architecture, specifications, evaluation design, repository structure, character scope, and initial corpus foundation for an individual Track B project.

## Work completed

- Defined the mixed system-building and behavioral-evaluation project.
- Selected Sherlock Holmes, Hercule Poirot, L, and Professor Layton as the final characters.
- Limited the initial MVB to Sherlock and Poirot.
- Produced the initial architecture, project proposal, functional specification, data model, and evaluation plan.
- Established versioned prompt and YAML configuration structures.
- Chose a CLI, OpenAI with a configurable model, Pydantic validation, JSONL logs, per-run history, and deterministic round robin.

## Work partially completed

- Sherlock corpus preparation: source texts were downloaded and cleaned, metadata was recorded, and an evidence-extraction script exists as uncommitted work; the processed corpus has not been finalized or validated.
- Poirot source metadata exists, but corpus download, cleaning, and processing are not complete.
- Character source definitions for L and Professor Layton are metadata stubs because their corpus work is deferred.

## Work deferred

- Completion and validation of processed Sherlock and Poirot corpora.
- Pydantic persona schema and all runtime code.
- OpenAI integration and the end-to-end persona-to-response pipeline.
- Multi-agent simulation, evaluation interface, trial generation, and analysis.
- L and Professor Layton corpus preparation and runtime support.

## Blockers

- GitHub CLI authentication is currently invalid, so Sprint 2 milestone and issue creation must be done manually or after re-authentication.
- Corpus excerpts require careful provenance, rights review, speaker attribution, and validation before use.
- The exact September course deadline is not documented.

## Decisions made

- This is an individual Track B, mixed project.
- The final four-persona blind task has a 25% chance baseline; the two-persona development pilot has a separate 50% baseline.
- The initial provider is OpenAI, but the model is configurable and secrets come from environment variables.
- The first interface is a CLI; no persistent agent memory is used.
- The working-version target is August 7, 2026, with the final deadline in September.

## Repository artifacts produced

- Documentation in `docs/` covering proposal, functional specification, architecture, data model, evaluation, sprint plans, and roadmap.
- Prompt templates in `prompts/`.
- Development configuration in `configs/dev.yaml`.
- Character source definitions under `characters/`.
- Partial Sherlock raw, cleaned, and metadata artifacts plus preparation scripts.
- CLI mockups and GitHub setup instructions.

## What I learned

Project scope, pilot scope, and experimental scope must be stated separately. Corpus preparation also needs explicit provenance and validation; downloaded or cleaned text alone is not a ready character corpus.

## Next sprint

Complete the processed Sherlock and Poirot corpora, then implement the minimal vertical slice that extracts and validates one persona JSON and generates one saved response from it. Do not begin the simulator or full evaluation until that path works.
