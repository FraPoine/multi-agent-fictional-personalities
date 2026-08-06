# Sprint 6 Retrospective

Sprint 6 completed the deterministic mock investigation application workflow:
caller-controlled clues, immutable per-round visibility, independent Sherlock
and Poirot analyses, round-robin discussion through `simulate_chat()`, explicit
group decisions and pauses, and explicit finalization.

Verification on 2026-08-06 against
`9d2906c0c3edab911a0f8a9e268a5dcc37885723` produced 757 passed, 0 failed, 0
skipped, and 0 warnings on Python 3.14.4. The synthetic two-round E2E passed
twice deterministically, round 1 never saw clue 2, two decisions did not
finalize implicitly, and the completed aggregate round-tripped through JSON.

The workflow remains deliberately offline, mock-only, stateless, and separate
from delivery and persistence. There is no investigation CLI/web UI,
investigation persistence, live provider, automatic clue/action/finalization,
official-solution scoring, or recognizability evaluation of investigation
outputs.

Next: follow the existing Sprint 7 plan for an investigation web UI without
weakening application/domain boundaries; design persistence and live-provider
work separately.
