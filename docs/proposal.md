# Project Proposal

## Title

Multi-Agent Fictional Personalities

## One-sentence pitch

We build a system that extracts structured persona profiles from fictional character text corpora, instantiates those profiles as LLM agents, lets the agents interact in controlled group chats, and evaluates whether their generated messages are recognizable as the intended characters.

## Project profile

**Mixed project.**

The project combines:
- a **system-building contribution**, because we implement persona extraction, agent simulation, logging, and an evaluation interface;
- a **behavior-study contribution**, because we evaluate whether persona-seeded agents preserve recognizable individual identity and group behavior.

## Research question

Can persona-seeded LLM agents generate messages that human raters can attribute to the correct fictional character at above-chance accuracy?

## Primary hypothesis

Persona-seeded LLM agents will be identifiable above chance in a blind multiple-choice attribution task.

For example:
- with 4 characters, chance accuracy is 25%;
- with 6 characters, chance accuracy is 16.7%;
- with 8 characters, chance accuracy is 12.5%.

The first version will use 4 characters to reduce scope and make the evaluation feasible.

## Secondary questions

1. Do some fictional characters remain more recognizable than others?
2. Do agents collapse into a generic LLM voice during multi-agent chat?
3. Which characters are most often confused with each other?
4. Do persona profiles improve recognizability compared with a generic-agent baseline?
5. Do multi-agent conversations show measurable group dynamics, such as dominance, disagreement, or convergence?

## Motivation

LLM systems increasingly use personas, roles, simulated users, and multi-agent settings. However, it is not obvious whether these personas produce stable, distinguishable behavior, or whether they mostly produce superficial style imitation.

This project treats the LLM agents as the object of study. The goal is not to make claims about fictional characters as real people. The goal is to measure whether the model, when conditioned on a persona profile, behaves in a way that is distinguishable and reproducible.

## Initial character set

The Minimum Viable Build will start with 4 characters from the same fictional universe.

Candidate set:

1. Naruto Uzumaki
2. Sasuke Uchiha
3. Sakura Haruno
4. Kakashi Hatake

This set is useful because the characters share a narrative world but have different speech styles, motivations, and interaction patterns.

If data collection becomes difficult, the team may replace this set with another compact group of fictional characters with easily available dialogue examples.

## Dataset strategy

For each character, we will collect a small corpus of text evidence, such as:
- dialogue excerpts;
- episode or scene transcripts;
- short character descriptions;
- manually curated example utterances.

The first version will not require a large dataset. The goal is to build the pipeline and validate the evaluation method before scaling.

The target for Sprint 2 is:

- 2 characters;
- 5–10 example passages per character;
- one toy conversation;
- one dry-run evaluation sample.

The target for the full project is:

- 4–6 characters;
- enough text evidence to extract a stable persona profile;
- multiple generated conversations;
- a small rater study.

## System overview

The system has five stages:

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

## Expected outputs

By the end of the project, the repository should contain:

- a runnable system with UI or CLI;
- persona JSON artifacts;
- generated transcripts;
- structured logs;
- rater responses;
- analysis scripts;
- a technical report;
- a final presentation.

## Sprint 1 scope

Sprint 1 focuses on design and documentation, not full implementation.

Sprint 1 outputs:

- `docs/proposal.md`
- `docs/functional_spec.md`
- `docs/data_model.md`
- `docs/evaluation_plan.md`
- `docs/architecture.md`
- `docs/sprint_plan.md`
- `mockups/ui_mockups.md`
- repository structure
- GitHub milestone and issues

## Out of scope for the first version

The first version will not include:

- fine-tuning;
- large-scale data collection;
- complex memory systems;
- many LLM models;
- automatic web scraping without manual validation;
- advanced UI polish;
- open-ended public deployment;
- claims that the model understands or authentically represents the fictional character.

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

Trying to support too many characters, models, and UI features may prevent completion.

Mitigation:
- start with 4 characters;
- use one model;
- use one extraction method;
- prioritize the end-to-end pipeline over polish.

## Definition of success

The project succeeds if it produces a working, reproducible pipeline and a defensible evaluation, even if the primary hypothesis is not supported.

A null result is still valuable if the team can show that:
- the pipeline ran correctly;
- the evaluation was pre-specified;
- uncertainty was reported;
- limitations were explained honestly.
