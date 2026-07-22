# Manual GitHub Sprint 2 setup

GitHub CLI was installed but unauthenticated during Sprint 1 closure. Create the following milestone and issue manually after authentication is restored.

## Milestone

**Title:** Sprint 2 — Minimal persona-to-response pipeline

**Description:** Implement the first end-to-end vertical slice for Sherlock Holmes and Hercule Poirot. Do not include multi-agent simulation or evaluation implementation.

Do not set a milestone due date unless the Sprint 2 calendar is confirmed.

## Issue

**Title:** Implement minimal persona-to-response pipeline

**Body:**

Implement the first end-to-end vertical slice that converts a processed fictional-character corpus into a validated persona JSON and uses that persona to generate one saved agent response.

Use Sherlock Holmes and Hercule Poirot only.

### Checklist

- [ ] Define the persona JSON schema.
- [ ] Load processed character corpora.
- [ ] Load the persona-extraction prompt from a versioned file.
- [ ] Call the configured OpenAI model.
- [ ] Validate the model output.
- [ ] Save the persona JSON.
- [ ] Generate one response using the persona.
- [ ] Save basic execution metadata.
- [ ] Add a development command to the README.

### Definition of Done

A CLI command can generate a validated persona JSON from a processed character corpus and use that persona to produce one saved agent response.

Attach this issue to the `Sprint 2 — Minimal persona-to-response pipeline` milestone. Any incomplete Sprint 1 corpus work moved here should be noted in a comment rather than marking it complete.
