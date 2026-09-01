# Sprint 7 Lead/Visit UX redesign completion

## Outcome

Sprint 7 is complete for the offline Lead/Visit web scope. The main
FastAPI/Jinja application now exposes only the authoritative Lead/Visit
investigation contract. The obsolete round mutation routes, web-only round
presentation helpers, dead round-screen styles, and round-oriented HTTP tests
were removed.

The retained private round model and application services are historical
compatibility code. They are excluded from public exports and are not imported
by the web router, presentation layer, templates, or browser scripts.

## Final HTTP contract

- `GET /investigations`
- `POST /investigations`
- `GET /investigations/{session_id}` with optional read-only `lead` selection
- `POST /investigations/{session_id}/leads`
- `POST /investigations/{session_id}/leads/{lead_id}/visit`
- `POST /investigations/{session_id}/visits/{visit_id}/information`
- `POST /investigations/{session_id}/visits/{visit_id}/discussion`
- `POST /investigations/{session_id}/finalize`

The browser covers Case Opening, semantic lead creation and selection,
chronological visits and revisits, current-visit information disclosure,
repeatable bounded discussion, persistent same-lead thread projection,
resource states, explicit finalization, and a completed read-only archive.

## Verification

All commands ran offline with `OPENAI_API_KEY` removed from the environment.
The HTTP E2E module additionally blocks socket connection attempts.

| Check | Result |
|---|---:|
| Final Sprint 7 HTTP cutover set | 21 passed |
| Complete investigation suite | 534 passed |
| Conversation and main-web regression | 202 passed |
| Persona, catalogue, and runtime regression | 65 passed |
| Evaluation and rater regression | 24 passed |
| Web startup regression | 36 passed |
| Complete repository suite | 874 passed |
| Python compilation and `git diff --check` | passed |

The E2E tests cover the complete A → B → A revisit flow, persistent semantic
threads, stale historical-write rejection, explicit finalization, completed
archive immutability, process-local no-artifact behavior, interleaved session
isolation, and provider-failure atomicity.

## Design fidelity review

The final templates retain the Figma Make information architecture: a
catalogue-driven lobby, three-region game shell, lead rail, central persistent
thread, resource rail/drawer, explicit conclusion action, and completed case
archive. The supplied Make reference exposed its generated source manifest to
the design-context integration but did not provide a renderable node screenshot
for pixel-level comparison. Fidelity was therefore reviewed structurally
against the available source context and the implemented responsive states.

## Boundaries and deferred work

Investigation state remains process-local and is discarded on restart. The
demo uses committed deterministic fixtures and has no network, API-key,
database, browser-storage, or investigation-artifact dependency. Live
providers, durable investigation persistence, real case content, enabled map
and reference resources, human participation, scoring, and investigation-output
recognizability evaluation remain future work.

