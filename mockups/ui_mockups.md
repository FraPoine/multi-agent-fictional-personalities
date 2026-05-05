# UI Mockups

## Purpose

This document describes the planned user interface screens for the first version of the system.

The Sprint 1 mockups are textual wireframes. They can later be converted into Figma, Streamlit, or a web interface.

---

# Screen 1 — Character and Dataset Setup

## Goal

Let the project user select characters and inspect corpus readiness.

## Wireframe

```txt
+------------------------------------------------------+
| Multi-Agent Fictional Personalities                  |
+------------------------------------------------------+
| Characters                                           |
|                                                      |
| [x] Naruto Uzumaki      Corpus: Ready                |
| [x] Sasuke Uchiha       Corpus: Partial              |
| [x] Sakura Haruno       Corpus: Ready                |
| [x] Kakashi Hatake      Corpus: Missing metadata     |
|                                                      |
| Selected characters: 4                               |
|                                                      |
| [Upload corpus] [Validate corpus] [Generate personas]|
+------------------------------------------------------+

Right panel:
+------------------------------------------------------+
| Character preview                                    |
| Name: Naruto Uzumaki                                 |
| Tags: energetic, loyal, stubborn                     |
| Corpus examples: 8                                   |
| Warnings: none                                       |
+------------------------------------------------------+
```

## Main actions

- select or deselect characters;
- upload or edit corpus text;
- validate corpus completeness;
- generate persona profiles.

---

# Screen 2 — Persona Profile Viewer

## Goal

Let the user inspect the generated persona profile before running simulations.

## Wireframe

```txt
+------------------------------------------------------+
| Persona Profile Viewer                               |
+------------------------------------------------------+
| Character: Naruto Uzumaki                            |
| Persona version: v1                                  |
| Prompt: extract_persona_v1                           |
| Model: placeholder-model                             |
+------------------------------------------------------+

Style:
- energetic and direct
- informal
- emotionally expressive

Values:
- friendship
- persistence
- recognition

Speech patterns:
- short emotional statements
- direct challenges
- optimism under pressure

Interaction rules:
- encourage others not to give up
- respond strongly to betrayal
- avoid formal language

Example utterances:
1. "We can still do this."
2. "I won't back down."
3. "No one gets left behind."

[Regenerate] [Edit manually] [Save profile]
```

## Main actions

- inspect persona dimensions;
- regenerate profile;
- manually edit profile;
- save versioned profile.

---

# Screen 3 — Chat Simulator

## Goal

Let the user run and inspect a controlled multi-agent conversation.

## Wireframe

```txt
+------------------------------------------------------+
| Chat Simulator                                       |
+------------------------------------------------------+
| Topic: [The team must decide who leads a mission.]   |
| Turn count: [12]                                     |
| Turn policy: [round_robin]                           |
| Seed: [42]                                           |
|                                                      |
| Agents:                                              |
| [x] Naruto    [x] Sasuke    [x] Sakura    [x] Kakashi|
|                                                      |
| [Run simulation] [Save config]                       |
+------------------------------------------------------+

Transcript:
+------------------------------------------------------+
| Naruto: We cannot just wait. Someone has to go.      |
| Sasuke: Rushing in without a plan is pointless.      |
| Sakura: Both of you need to think clearly.           |
| Kakashi: Then we decide based on information.        |
+------------------------------------------------------+

Run metadata:
- run_id: run_001
- model: placeholder-model
- prompt: agent_reply_v1
- status: completed

[Download transcript] [Download JSONL logs] [Create eval trials]
```

## Main actions

- choose topic;
- choose agents;
- set turn count;
- run simulation;
- inspect transcript;
- export transcript and logs;
- create evaluation trials.

---

# Screen 4 — Rater Evaluation Interface

## Goal

Collect blind character-identification responses from human raters.

## Wireframe

```txt
+------------------------------------------------------+
| Character Identification Task                        |
+------------------------------------------------------+
| Read the message below and choose which character    |
| most likely produced it.                             |
+------------------------------------------------------+

Message:
"We cannot just wait around. If someone needs to step up,
I will do it."

Who wrote this?

( ) Naruto Uzumaki
( ) Sasuke Uchiha
( ) Sakura Haruno
( ) Kakashi Hatake

Confidence:
[1] [2] [3] [4] [5]

[Submit answer]
```

## Main actions

- read message;
- choose character;
- report confidence;
- submit response.

---

# Screen 5 — Analysis Dashboard

## Goal

Show the project user the current evaluation results.

## Wireframe

```txt
+------------------------------------------------------+
| Evaluation Results                                   |
+------------------------------------------------------+
| Total responses: 120                                 |
| Overall accuracy: 43%                                |
| Chance baseline: 25%                                 |
| 95% CI: [34%, 52%]                                   |
+------------------------------------------------------+

Per-character accuracy:
Naruto: 55%
Sasuke: 48%
Sakura: 31%
Kakashi: 38%

Confusion matrix:
              selected
true      Naruto  Sasuke  Sakura  Kakashi
Naruto      18      5       3       4
Sasuke       4     16       2       8
Sakura       7      6       9       8
Kakashi      5      8       4      13

[Export CSV] [Export figure] [Open examples]
```

## Main actions

- inspect primary result;
- inspect per-character breakdown;
- inspect confusion matrix;
- export analysis outputs.
