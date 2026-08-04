# Sprint 4 Smoke Test

## Purpose

This report records the Task 17 reproducibility check for the local Sprint 4
web interface. It verifies the documented installation-independent startup
boundary, HTTP routes, deterministic Sherlock/Poirot conversation, persisted
artifacts, invalid-input response, and custom-port option. It is not a Sprint 4
completion or closure note.

## Environment used

```text
Date: 2026-08-04
Platform: Ubuntu 26.04
Python: 3.14.4
Commit: 7b96df3600298bab424f32f01da11a8966ef34e4
Provider: mock
PYTHONPATH during web startup: unset
OpenAI API key present: no
API key required: no
Network required by conversation flow: no
```

The commit is the Task 16 repository state tested before the Task 17
documentation changes.

## Preconditions

The repository root, an activated `.venv`, and dependencies installed from
`requirements.txt` were used. The required web application, templates, static
assets, startup script, and web tests were present. Existing output runs were
listed before the manual test so that only the new smoke-test run could be
removed afterward.

## Automated pre-check

Command executed:

```bash
export PYTHONPATH="$PWD/src"
python -m pytest
```

Observed result: exit status `0`; all `189` tests passed in `2.60s`. Pytest
reported one existing `StarletteDeprecationWarning` from FastAPI's TestClient
compatibility layer. No test failed, and the warning did not indicate a smoke
test failure.

## Default startup and route checks

Commands executed from the repository root with the virtual environment's
Python interpreter:

```bash
unset PYTHONPATH
python scripts/run_web.py
```

The server started at `http://127.0.0.1:8000` without a
`ModuleNotFoundError`. The following requests were made and observed:

| Request | Status | Content type / result |
|---|---:|---|
| `GET /` | 200 | `text/html; charset=utf-8` |
| `GET /health` | 200 | `application/json`; `{"status":"ok","provider":"mock"}` |
| `GET /static/styles.css` | 200 | `text/css; charset=utf-8` |
| `GET /static/conversation.js` | 200 | `text/javascript; charset=utf-8` |

A real Chrome render of `/` also loaded the styled page, both detective cards,
the default topic and turn count, the fixed local mock provider, and the
`Awaiting case` state. No API-key field or provider selector was exposed.

## Valid-conversation check

The submitted values were:

```text
Characters: Sherlock Holmes and Hercule Poirot
Topic: A valuable document disappeared from a locked room.
Turns: 6
```

The response was HTTP `200` HTML and displayed `Completed`, six ordered turns,
both detective names, the run ID, repository-relative artifact directory, and
exactly the three expected artifact entries. The recorded run ID was:

```text
9c83fa7c0df0434ebda24d0f52785814
```

The six persisted speakers alternated in this order:

```text
sherlock_holmes
hercule_poirot
sherlock_holmes
hercule_poirot
sherlock_holmes
hercule_poirot
```

The normal form includes Task 13's JavaScript loading hooks, and the automated
web suite covers their presence. The original non-interactive headless smoke
session could not directly observe the transient visual state because the
local mock response completed almost immediately.

### Interactive loading-state verification

A subsequent interactive browser check was performed manually by the user.
Browser network throttling was enabled solely to make the short-lived state
visible during a valid Sherlock Holmes and Hercule Poirot submission. The user
directly observed that:

- the transcript status changed to `Running`;
- the submit-button label changed to `Generating conversation…`;
- the submit button became disabled;
- the loading indicator and loading message appeared;
- the previous transcript or placeholder content was replaced;
- the returned server-rendered state changed to `Completed`;
- the submit button returned to its normal state on the returned page.

No production code, artificial server delay, polling, AJAX behavior, or
browser automation was introduced for this verification. This interactive
user observation supplements rather than replaces the automated and headless
smoke-test evidence above.

## Artifact verification

The generated directory was:

```text
outputs/conversations/runs/9c83fa7c0df0434ebda24d0f52785814/
```

It contained exactly:

```text
messages.jsonl
run.json
transcript.md
```

`run.json` parsed as valid JSON. Its status was `completed`, provider was
`mock`, topic matched the submitted topic, turn count was `6`, and it contained
six messages. `messages.jsonl` contained six non-empty records.
`transcript.md` contained both Sherlock Holmes and Hercule Poirot.

## Invalid-input check

A crafted form request used both supported characters, the topic
`A locked-room mystery.`, and `turn_count=abc`:

```bash
curl -i \
  -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "characters=sherlock" \
  --data-urlencode "characters=poirot" \
  --data-urlencode "topic=A locked-room mystery." \
  --data-urlencode "turn_count=abc" \
  http://127.0.0.1:8000/conversations
```

Observed result: HTTP `400 Bad Request` with `text/html; charset=utf-8`, a
`Failed` state, and the readable message `Enter a whole number between 2 and
12.` It did not return FastAPI JSON `422`, did not display a completed state,
and did not create another run directory.

## Custom-port check

After stopping the default server, this command was executed:

```bash
unset PYTHONPATH
python scripts/run_web.py --port 8080
```

Uvicorn started at `http://127.0.0.1:8080`. `GET /` returned HTTP `200` HTML
containing the application title and `New investigation`. The server was then
stopped with `Ctrl+C`.

## Cleanup

The default-port server and custom-port server were both stopped. Only the
smoke-test run directory
`outputs/conversations/runs/9c83fa7c0df0434ebda24d0f52785814/`
was removed. Pre-existing runs and the parent `outputs/` directory were left
untouched. The temporary browser screenshot and HTTP response files were kept
outside the repository under the system temporary directory and are not part
of the working tree.

## Final outcome

The automated suite, documented no-`PYTHONPATH` startup command, default HTTP
routes, deterministic six-turn conversation, artifact persistence,
server-rendered invalid-input path, custom-port startup, and user-observed
interactive loading state all passed. No API key, OpenAI call, or
network-backed conversation provider was used.

## Limitations

- The deterministic synthetic fixtures do not assess real LLM persona quality
  or human recognizability.
- OpenAI-backed conversation execution was not tested because it is not
  implemented and no API key was present or required.
- L, Professor Layton, and evaluation functionality remain future work.
- This Task 17 report does not perform Task 18 or formally close Sprint 4.
