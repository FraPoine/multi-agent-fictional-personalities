# CLI Mockups

## Purpose

The initial interface is a CLI. These Sprint 1 wireframes describe planned interactions; they are not evidence that the commands already exist. A human-facing evaluation form may be added during the presentation sprint.

## Corpus status

```text
$ fictional-personas corpus status
Character          Stage       Status
Sherlock Holmes    initial MVB partial
Hercule Poirot     initial MVB sources selected; processing pending
L                  extension   deferred
Professor Layton   extension   deferred
```

## Persona extraction and one response

```text
$ fictional-personas generate-response \
    --character sherlock_holmes \
    --config configs/dev.yaml

Validated persona: data/personas/sherlock_holmes_persona_v1.json
Saved response:    logs/runs/<run_id>/response.json
Saved metadata:    logs/runs/<run_id>/steps.jsonl
```

The Sprint 2 command will load the extraction and reply templates from versioned files in `prompts/`. The OpenAI model comes from configuration; the CLI must not print the API key.

## Later multi-agent simulation

```text
$ fictional-personas simulate --config configs/dev.yaml --topic "..."

Turn policy: round_robin
Agents: Sherlock Holmes, Hercule Poirot
Transcript: logs/runs/<run_id>/transcript.md
Events: logs/runs/<run_id>/messages.jsonl
```

This command belongs to Sprint 3 and is not implemented in Sprint 1.

## Later blind evaluation

The final rater view presents one anonymized generated message and four choices: Sherlock Holmes, Hercule Poirot, L, and Professor Layton. Chance accuracy is 25%. A two-choice Sherlock/Poirot development pilot has a 50% chance baseline and is reported separately.

No results dashboard is shown here because no experiment has been run.
