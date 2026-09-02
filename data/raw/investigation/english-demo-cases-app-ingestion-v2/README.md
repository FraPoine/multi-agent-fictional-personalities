# English demo cases — application ingestion v2

This package restructures the three user-supplied official English demos into two complementary layers. It does not modify the application repository and does not include the future long case.

## Layer A: strict current-app subset

`current_app/cases/*.yaml` deliberately contains only fields accepted by the current strict `CaseDefinition`: identity, spoiler-free description, opening, static lead coordinates and resource references. `current_app/resources.yaml.fragment` contains only fields accepted by `CaseResourceDefinition`. Merge the fragment’s `resources` list into the repository catalogue when implementing integration; the included `current_app/assets/` paths already match the fragment.

Demo 1 and Demo 2 expose all London references with the supported `london-address` scheme. Demo 3 validates as a case shell with its opening and resource but an empty `leads` list: its printed four-digit `time-code` scheme is unsupported by the current application and has not been coerced.

## Layer B: complete playable content

Each `cases/<case-id>/` directory contains the official English opening, state model, one JSON file per physical reference, resource provenance/assets, player-facing questions, isolated spoiler files and a validation report. Ordered `sections` preserve conditional disclosure. Demo 3 minimally extends a lead with ordered `variants`, because the same time code can have distinct Interview, Investigation and Intervention text.

The rich schema uses `texts.en`, `source_language: en` and `play_language: en`. No Italian text was invented. Deterministic lead keys are derived only from printed references (`wc-68`, `nw-32`, `time-1921`) and contain no ground-truth labels.

## Spoiler firewall

Answers, Holmes’s route and scoring criteria exist only below `spoilers/`. They are not duplicated in case YAML, openings, normal manifests, lead labels, resource descriptions or question files. Demo 3 has no separate printed question, solution or scoring section; this absence is recorded instead of inventing one. Its Investigation and Intervention outcomes remain inside their gated playable variants, because those entries are the source’s playable endgame content.

## Mechanics preserved

- Demo 1: `london-address`; 18 physical references; 32 NW contains player choices and paragraph-level lead costs, including the printed top-floor closure.
- Demo 2: `london-address`; 26 physical references; global flags A/B/C; revisitable gates; explicit break-in confirmation; irreversible closure; one uniform choice.
- Demo 3: provisional `time-code`; 18 codes and 32 mode variants; ten-lead budget; +3 lead effect; Rose’s brooch and add-5 derived references; exactly one final Intervention.

## Source/layout decisions

Rendered page layout was treated as authoritative. In Demo 2, the uniform-burning prompt is visually the continuation of 68 WC before the 90 WC heading; although the worker prompt cites 86 SW as an example, the structured interaction is therefore attached to 68 WC. Demo 1’s printed answer allocations total 140 while its text says Holmes scored 100; both facts are preserved and the scoring file is marked `needs_review`.

All included visual assets are faithful crops from the user-supplied PDFs. They were not redrawn, regenerated or sourced from the web.

## Validation

`validation_summary.md` records schema and cross-file checks against the current repository. Per-case reports record physical lead counts, state mechanics, resources and source issues.
