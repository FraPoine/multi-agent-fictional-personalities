# What Codex must implement next

The next application change should consume this package without weakening the spoiler boundary.

Minimum capabilities:

1. Load rich case manifests, openings, state definitions, lead files, questions and resource manifests separately from `spoilers/`.
2. Resolve a visited physical reference to its persistent semantic lead and automatically reveal only the next eligible ordered section.
3. Persist case flags, lead-local choices, confirmed interactions, granted items, lead-budget changes and chronological revisits.
4. Evaluate section gates without exposing gated text; permit the source-defined revisit behavior after state changes.
5. Present explicit confirmation and single-choice interactions before disclosure, and enforce lead/scope closure after irreversible actions.
6. Support paragraph-level lead costs for Demo 1 and mode-aware `time-code` variants, derived add-5 references, lead budgets and final Intervention selection for Demo 3.
7. Present player questions and finalization separately, loading solution/scoring files only in an explicitly authorized post-investigation evaluation path.
8. Add tests for flag transitions, gated disclosure, revisit behavior, irreversible locking, choice persistence, budget accounting, time-code mode selection, asset resolution and spoiler non-loading.

No unrelated catalogue redesign, provider integration or long-case ingestion is required for this step.
