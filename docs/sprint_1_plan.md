# Sprint 1 — Architecture, planning, and initial corpus preparation

## Objective

Define a coherent foundation for an individual Track B project that builds and behaviorally evaluates fictional-character agents, without claiming that the runtime or experiment already works.

## Scope decisions

- Final personas: Sherlock Holmes, Hercule Poirot, L, and Professor Layton.
- Initial MVB: Sherlock Holmes and Hercule Poirot only.
- Later extensions: L and Professor Layton.
- Initial provider: OpenAI; exact model is configurable.
- Initial interface: CLI.
- Configuration and validation: YAML and Pydantic.
- Prompts and logs: versioned files under `prompts/` and JSONL execution logs.
- Memory and scheduling: per-run history only, no persistent memory, deterministic round robin.
- Basic working-version target: August 7, 2026.
- Final course deadline: September 2026, with no exact date currently documented.

## Deliverable audit

| Deliverable | Status at close | Evidence / remaining work |
|---|---|---|
| Project proposal | Complete for Sprint 1 | `docs/proposal.md` reflects the final scope and staged MVB. |
| Functional specification | Complete for Sprint 1 | `docs/functional_spec.md` describes planned behavior and constraints. |
| Architecture | Complete as an initial design | `docs/architecture.md`; implementation validation is deferred. |
| Data model | Complete as a draft | `docs/data_model.md`; Pydantic implementation is Sprint 2. |
| Evaluation plan | Complete as a pre-implementation plan | Final 25% and pilot 50% baselines are separated. |
| Prompt structure | Complete for Sprint 1 | Prompt templates exist under `prompts/`; runtime loading is deferred. |
| Configuration structure | Complete for Sprint 1 | `configs/dev.yaml` selects OpenAI and staged character sets without a hard-coded model. |
| Character selection | Complete | Four final characters and two-character MVB are fixed. |
| Character source definitions | Partial | Sherlock and Poirot sources exist; L and Layton are deferred and have metadata stubs. |
| Corpus preparation | Partial | Sherlock raw/clean texts and metadata exist; evidence extraction is unfinished/uncommitted. Poirot processing is not complete. |
| GitHub setup | Partial | CLI authentication is invalid; manual Sprint 2 content is in `notes/github-sprint-setup.md`. |
| Runtime / experiment | Deferred | No persona extraction runtime, response pipeline, simulator, rater interface, or results exist. |

## Definition of Done

- [x] Individual Track B and mixed-project status documented.
- [x] Final and initial character scopes documented consistently.
- [x] Architecture, functional specification, data model, and evaluation plan aligned.
- [x] Final four-way chance baseline fixed at 25%; two-way pilot baseline identified as 50%.
- [x] Prompt and YAML configuration structures established.
- [x] Sprint 1 note closed honestly and Sprint 2 planned.
- [x] Roadmap and manual GitHub setup instructions added.
- [x] Repository hygiene and internal documentation consistency checked.
- [ ] Complete Sherlock and Poirot processed corpora (moved to Sprint 2).
- [ ] Implement the minimal corpus-to-persona-to-response pipeline (moved to Sprint 2).

Sprint 1 is formally closed at the documentation and planning boundary. The unchecked implementation and corpus tasks are explicitly owned by Sprint 2 and are not represented as completed work.
