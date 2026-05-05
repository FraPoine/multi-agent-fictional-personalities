# Sprint 1 Plan — Setup, Design, and Documentation

# Sprint 1 Goal

For the solo-team version, Sprint 1 focuses on locking the experimental setup:

1. pick one corpus source;
2. select 4 personas;
3. collect initial text examples for each persona;
4. decide a feasible rater pool of around 10 people;
5. pre-register the primary hypothesis;
6. define the chance baseline and evaluation metric.

The project intentionally drops H2 and H3 from the main scope. The first study focuses only on whether persona-seeded agents are identifiable above chance by blind raters.

## Sprint outputs

Required outputs:

- `docs/proposal.md`
- `docs/functional_spec.md`
- `docs/data_model.md`
- `docs/evaluation_plan.md`
- `docs/architecture.md`
- `docs/sprint_plan.md`
- `mockups/ui_mockups.md`
- initial repository structure
- GitHub milestone for Sprint 1
- one issue per person
- one sprint-end note per person

## Scope decisions

## Project profile

Mixed project.

The system must be runnable and usable, but the main intellectual contribution is the study of whether persona-seeded LLM agents produce recognizable and measurable behavior.

## Character scope

Initial MVB:

- 4 fictional characters;
- one fictional universe if possible;
- manually curated corpus examples;
- no private personal data.

## Model scope

Initial MVB:

- one model;
- one persona extraction method;
- one chat simulation strategy;
- one evaluation protocol.

## Evaluation scope

Initial MVB:

- blind identification task;
- accuracy against chance;
- confusion matrix if enough responses are collected;
- confidence interval when sample size permits.

## Sprint tasks

## Task 1 — Define final project scope

### Output

`docs/proposal.md`

### Acceptance criteria

- One-sentence pitch is clear.
- Research question is stated.
- Primary hypothesis is stated.
- Project profile is declared.
- Scope and out-of-scope items are listed.

## Task 2 — Select characters and dataset strategy

### Output

Dataset section in `docs/proposal.md`

### Acceptance criteria

- Initial character set is listed.
- Corpus strategy is described.
- Data risks are documented.
- Backup plan is documented.

## Task 3 — Write functional specification

### Output

`docs/functional_spec.md`

### Acceptance criteria

- User types are defined.
- Core features are listed.
- Inputs and outputs are described.
- Non-functional requirements are included.

## Task 4 — Define data model

### Output

`docs/data_model.md`

### Acceptance criteria

- Main entities are defined.
- Each entity has fields.
- Entity relationships are explained.
- Storage locations are documented.

## Task 5 — Define architecture

### Output

`docs/architecture.md`

### Acceptance criteria

- Main components are named.
- Data flow is described.
- Public interfaces are drafted.
- Logging and prompt policies are stated.

## Task 6 — Define evaluation plan

### Output

`docs/evaluation_plan.md`

### Acceptance criteria

- Primary metric is defined.
- Chance baseline is defined.
- Conditions and controls are listed.
- Threats to validity are documented.
- Null-result interpretation is included.

## Task 7 — Prepare UI mockups

### Output

`mockups/ui_mockups.md`

### Acceptance criteria

- At least four screens are sketched:
  - character setup;
  - persona viewer;
  - chat simulator;
  - rater task.
- Main user actions are visible.

## Task 8 — Initialize repository structure

### Output

Initial directories and placeholder files.

### Acceptance criteria

- Repository has the planned folder structure.
- Prompts have their own directory.
- Docs are committed.
- Config directory exists.

## Suggested GitHub milestone

```txt
Sprint 1 — Setup, Design, and Documentation
```

## Suggested issues

```txt
#1 Define final project scope and proposal
#2 Select characters and dataset strategy
#3 Write functional specification
#4 Define data model
#5 Define architecture
#6 Write evaluation plan
#7 Prepare UI mockups
#8 Initialize repository structure
```

Each issue should be assigned to one person and attached to the Sprint 1 milestone.

## Daily plan

| Day | Focus | Output |
|---|---|---|
| 1 | Finalize idea | One-sentence pitch, scope, project profile |
| 1 | Dataset and characters | Initial character set and corpus plan |
| 1 | Functional spec | `docs/functional_spec.md` |
| 1 | Data model and architecture | `docs/data_model.md`, `docs/architecture.md` |
| 1 | Evaluation plan | `docs/evaluation_plan.md` |
| 2 | Mockups and repo | `mockups/ui_mockups.md`, folders |
| 3 | Cleanup | sprint note, issue updates, meeting slide |

## Definition of Done

Sprint 1 is complete when:

- [ ] Choose the corpus source
- [ ] Select 4 personas / characters
- [ ] Collect initial text for each of the 4 personas
- [ ] Document the corpus source and inclusion criteria
- [ ] Decide the rater pool, target N = 10
- [ ] Pre-register the primary hypothesis
- [ ] Define chance baseline: 1/4 = 25%
- [ ] Drop H2 and H3 from the main scope
- [ ] Keep only individual recognizability as the primary study

## Sprint 2 target

Sprint 2 should implement a toy end-to-end pipeline:

```txt
2 characters
↓
small corpus
↓
persona JSON files
↓
agent reply function
↓
short simulated chat
↓
basic transcript log
↓
simple evaluation sample
```
