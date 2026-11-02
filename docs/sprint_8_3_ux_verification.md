# Sprint 8.3 — Layton Conversations UX verification

Date: 2026-11-02. Inspected baseline: `d83770d` (Layton runtime integration).
The working tree was clean at the start of this UX task.

## Outcome and existing behavior

No production changes were necessary. The existing catalog-driven Conversations
interface already satisfies the Layton selection and transcript requirements:

- Catalogue order is Sherlock Holmes, Hercule Poirot, Professor Layton.
- Display names and descriptions come from `configs/characters.yaml`.
- Generic first/last-word initials produce `SH`, `HP`, and `PL`.
- Catalogue positions assign the existing participant palette: Sherlock tone 1,
  Poirot tone 2, Layton tone 3 (green). Transcript presentation resolves identity
  by character ID against the complete catalogue, so omitting a participant
  does not shift the remaining speakers' colors.
- All catalogue entries are checked initially. Every two-character combination
  and the three-character selection can submit a conversation. Validation
  requires at least two distinct supported characters; it imposes no maximum
  of three. Existing synthetic-catalogue tests remain in place.
- Native labelled checkboxes retain keyboard focus and Space toggling. The
  visually hidden input's focus-visible rule draws an outline on its card.
  Field errors are associated with controls, and names identify participants
  without relying on color or decorative initials.
- Existing layouts stack character cards vertically, switch the workspace to
  one column at 900px, and reduce spacing at 560px. Message text wraps.
- Transcript messages retain chronological order, names, initials, identity
  colors, run metadata and the three saved artifacts.
- Loading JavaScript uses generic form/transcript hooks and has no character
  count or identity assumptions.

Inspected `AGENTS.md`, the character catalogue, `web/app.py`, `index.html`,
`styles.css`, `conversation.js`, and existing web tests before editing.
Backend integration was already available, so actual catalogue assets were used
for offline mock web tests. No live provider calls were made.

## Changed files

- `tests/test_web_app.py`: strengthen the default-selection test with Layton's
  initials and all catalogue descriptions/tones; add parametrized actual-web
  tests for all three pairs and the trio. Verify checked state after submission,
  speaker names/initials/colors, order, metadata, persisted JSON/JSONL/Markdown,
  and visible artifact paths. Add invalid Layton selections and static keyboard
  accessibility/responsive contracts using the existing ASGI test client.
- `docs/sprint_8_3_ux_verification.md`: record findings, scope and verification.

No app, template, stylesheet, JavaScript, catalogue, Persona, corpus, extraction,
generation, orchestration, Investigations, or human-evaluation code changed.
There was no UX defect requiring a design or implementation change.

## Automated verification

- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_web_app.py -q`:
  **62 passed in 4.94s**, exit 0; no failures.
- `PYTHONPATH=src .venv/bin/python -m pytest -q`:
  **1085 passed in 14.94s**, exit 0; no failures.
- `git diff --check`: passed.

The new web scenarios use the existing network-rejecting fixture and temporary
output directories. They generate deterministic mock conversations through the
real web route, rather than replacing conversation orchestration with a stub.
The Sherlock/Poirot pair is included explicitly to preserve existing behavior.

## Browser verification limitation

Static HTML/CSS checks cover semantic keyboard controls, associated errors,
visible focus styles, viewport declaration, stacking breakpoints and text wrap.
They do not prove actual keyboard events, computed layout, absence of overflow,
contrast, or screen-reader behavior in a browser.

An installed Chrome was attempted in headless mode but could not start inside
the sandbox: Crashpad reported `setsockopt: Operation not permitted` (exit 133).
No successful browser rendering or interactive accessibility audit is claimed.
No new browser dependency or frontend framework was added.

For a local browser check after restarting the app:

1. At desktop, tablet and narrow phone widths (for example 1280px, 768px, 375px),
   check all three cards are readable and the page has no horizontal overflow.
2. Tab through each checkbox and confirm a visible card outline. Toggle Layton
   with Space and confirm the selected mark changes.
3. Submit each pair and the trio with Mock; check Layton remains PL/green in
   selection and transcript, messages stay ordered and artifact paths appear.
4. Submit only Layton and confirm the readable minimum-selection error while
   preserving his checked state.

No commit was created. Live-model quality and persona validation remain outside
this UX verification task.
