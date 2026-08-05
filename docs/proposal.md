# Project Proposal

## Title

Multi-Agent Fictional Personalities

## One-sentence pitch

We build fictional-detective agents, evaluate their blind recognizability, and
prepare them to collaborate in a user-moderated game of *Sherlock Holmes:
Consulting Detective*.

## Project profile

**Individual Track B, mixed project.**

The project combines:
- a **system-building contribution**, covering persona extraction, conversation
  simulation, logging, evaluation tooling, and a future investigation setting;
- a **behavior-study contribution**, with blind persona recognizability as its
  primary quantitative question and investigation behavior as secondary,
  qualitative or exploratory observation.

## Research question

Can persona-seeded LLM agents generate messages that blind raters can attribute
to the correct fictional character at above-chance accuracy?

## Primary hypothesis

Persona-seeded LLM agents will be identifiable above chance in a blind
multiple-choice attribution task. This tests observable recognizability, not
whether a model authentically is or understands a character.

The final experiment aims to use four characters. Its exact chance baseline and
rater methodology will be fixed and pre-registered with the final character and
candidate design. The two-character Sherlock/Poirot mock pilot uses a 50%
technical baseline and checks the pipeline only.

## Secondary questions

1. Do some fictional characters remain more recognizable than others?
2. Do agents collapse into a generic LLM voice during multi-agent chat?
3. Which characters are most often confused with each other?
4. Do persona profiles improve recognizability compared with a generic-agent baseline?
5. Do multi-agent conversations show measurable group dynamics, such as dominance, disagreement, or convergence?
6. In a moderated investigation, how do agents distinguish facts from
   deductions, revise hypotheses, identify contradictions, and reach group
   decisions?

## Motivation

LLM systems increasingly use personas, roles, simulated users, and multi-agent settings. However, it is not obvious whether these personas produce stable, distinguishable behavior, or whether they mostly produce superficial style imitation.

This project treats the LLM agents as the object of study. The goal is not to
make claims about fictional characters as real people or models as authentic
characters. The main measurable outcome is recognizable, distinguishable
output under controlled conditions. A moderated investigation is a connected
system capability and observational setting, not a replacement hypothesis.

## Character set and staged scope

The working runtime currently supports only Sherlock Holmes and Hercule
Poirot. The final evaluation aims to cover four characters, but the third and
fourth have not been finalized or implemented. L and Professor Layton were
previous candidates rather than irrevocable selections.

Sprint 5 prepares configuration and application boundaries for a configurable
participant sequence with a minimum of two, without adding persona data or a
new runtime character. Differences in source setting, corpus provenance, and
writing context remain potential confounds for whichever final set is chosen.

## Dataset strategy

For each character, we will collect a small corpus of text evidence, such as:
- dialogue excerpts;
- episode or scene transcripts;
- short character descriptions;
- manually curated example utterances.

The first version will not require a large dataset. The goal is to build the pipeline and validate the evaluation method before scaling.

The target for Sprint 2 is a processed corpus-to-persona-to-one-response pipeline for Sherlock and Poirot. Corpus size will be determined through documented curation rather than an unsupported quota.

The target for the full project is:

- 4 finalized characters;
- enough text evidence to extract a stable persona profile;
- multiple generated conversations;
- a small rater study.

## System overview

The system has six stages:

1. **Corpus preparation**
   - Store raw text examples for each character.
   - Track the source and character associated with each example.

2. **Persona extraction**
   - Use an LLM prompt to convert character text into a structured persona JSON.
   - The persona includes speaking style, motivations, typical phrases, values, and interaction rules.

3. **Agent runtime**
   - Instantiate one agent per persona.
   - Each agent receives the conversation history and replies in character.

4. **Chat simulation**
   - Simulate a controlled group conversation.
   - Log each turn, prompt version, model name, seed, and output.

5. **Evaluation**
   - Create anonymized message snippets.
   - Ask raters to identify which character produced each snippet.
   - Analyze accuracy, confidence intervals, and confusion patterns.

6. **Moderated investigation (future)**
   - The project user supplies the case introduction, reveals clues in order,
     and controls information access.
   - Agents analyze evidence, separate facts from deductions, revise
     hypotheses, propose leads, make group decisions, and formulate a final
     theory.

## Expected outputs

By the end of the project, the repository should contain:

- a runnable CLI system;
- persona JSON artifacts;
- generated transcripts;
- structured logs;
- rater responses;
- analysis scripts;
- a technical report;
- a final presentation.
- investigation-session artifacts from later real game sessions.

The implementation order is deliberately offline-first: complete conversation,
scheduling, metadata, persistence, evaluation, and investigation-domain
foundations with deterministic fixtures; integrate a real provider later; then
run the study and investigation sessions.

## Sprint 1 scope

Sprint 1 focuses on design and documentation, not full implementation.

Sprint 1 outputs:

- `docs/proposal.md`
- `docs/functional_spec.md`
- `docs/data_model.md`
- `docs/evaluation_plan.md`
- `docs/architecture.md`
- `docs/sprint_1_plan.md`
- `docs/sprint_2_plan.md`
- `docs/roadmap.md`
- `mockups/ui_mockups.md`
- repository structure
- Sprint planning and GitHub setup records

## Out of scope for the first version

The first version will not include:

- fine-tuning;
- large-scale data collection;
- complex memory systems;
- many LLM models;
- automatic web scraping without manual validation;
- advanced interface polish;
- open-ended public deployment;
- claims that the model understands or authentically represents the fictional character.
- autonomous access to case material or unrevealed clues.

## Risks and mitigations

### Risk 1: Generic LLM voice

All characters may sound too similar.

Mitigation:
- include a generic-agent baseline;
- include a style-neutralization control;
- report this as an important finding if it happens.

### Risk 2: Weak data

Some characters may have insufficient or noisy text examples.

Mitigation:
- start with a small, well-known character set;
- manually inspect corpus examples;
- document all data limitations.

### Risk 3: Raters do not know the characters

Raters may fail because they are unfamiliar with the character set.

Mitigation:
- use familiar fictional characters;
- include a familiarity question before the task;
- analyze results separately for familiar raters.

### Risk 4: Over-scoping

Trying to support too many characters, models, and interface features may prevent completion.

Mitigation:
- start the implementation with Sherlock and Poirot;
- keep mock providers as the default until the complete offline foundation is
  testable;
- use one extraction method;
- prioritize the end-to-end pipeline over polish.

Live-provider cost and reliability, bias in either human or LLM judging, and
information leakage during investigation are additional risks. The project
will keep provider choice configurable, pre-register the final rater design,
report judge-specific limitations, and make the user/game master authoritative
for clue disclosure.

## Definition of success

The project succeeds if it produces a working, reproducible pipeline and a defensible evaluation, even if the primary hypothesis is not supported.

A null result is still valuable if the project can show that:
- the pipeline ran correctly;
- the evaluation was pre-specified;
- uncertainty was reported;
- limitations were explained honestly.

## Implementation constraints and schedule

The current development provider is a deterministic local mock and requires no
secret or network access. A later real provider and exact model will be selected
through configuration. Configuration is YAML, structured data is validated with
Pydantic, prompts are versioned under `prompts/`, and future secrets must come
from environment variables. The system currently uses complete explicit
per-run history and deterministic round-robin simulation; a replaceable speaker
selector is planned before any future dynamic manager. The CLI and local web
interface reuse the same runtime and persistence boundaries.

The basic working-version target is August 7, 2026. The final course deadline is in September; no exact September date is currently documented.
