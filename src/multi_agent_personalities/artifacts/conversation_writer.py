"""Persistence for complete multi-agent conversation runs."""

import os
import shutil
import sys
import tempfile
from pathlib import Path

from multi_agent_personalities.models.conversation import ConversationRun
from multi_agent_personalities.models.identifiers import validate_run_id


def _render_transcript(run: ConversationRun) -> str:
    """Render a stable human-readable view without changing message content."""
    metadata = [
        "# Conversation Transcript",
        "",
        f"**Run ID:** {run.run_id}  ",
        f"**Topic:** {run.topic}  ",
        f"**Status:** {run.status}  ",
        f"**Provider:** {run.provider}  ",
    ]
    if run.model is not None:
        metadata.append(f"**Model:** {run.model}  ")
    metadata.extend(
        [
            f"**Seed:** {run.seed}  ",
            f"**Created at:** {run.created_at.isoformat()}",
            "",
        ]
    )

    sections = metadata
    for message in run.messages:
        sections.extend(
            [
                f"## Turn {message.turn_index} — {message.speaker_name}",
                "",
            ]
        )
        if message.text:
            sections.extend([message.text, ""])
        else:
            sections.extend(
                [f"_Generation error: {message.error}_", ""]
            )

    return "\n".join(sections).rstrip("\n") + "\n"


def save_conversation_run(
    *,
    output_root: Path,
    run: ConversationRun,
) -> Path:
    """Atomically save a conversation without overwriting an existing run."""
    run_id = validate_run_id(run.run_id)
    runs_directory = Path(output_root) / "conversations" / "runs"
    runs_directory.mkdir(parents=True, exist_ok=True)
    run_directory = runs_directory / run_id
    lock_path = runs_directory / f".{run_id}.lock"
    lock_acquired = False
    temporary_directory: Path | None = None

    try:
        try:
            lock_fd = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            lock_acquired = True
        except FileExistsError as error:
            raise FileExistsError(
                f"conversation run is already reserved: {run_directory}"
            ) from error
        os.close(lock_fd)

        if run_directory.exists():
            raise FileExistsError(
                f"conversation run already exists: {run_directory}"
            )

        temporary_directory = Path(
            tempfile.mkdtemp(prefix=f".{run_id}.", dir=runs_directory)
        )
        (temporary_directory / "run.json").write_text(
            run.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )

        messages_jsonl = "".join(
            message.model_dump_json() + "\n" for message in run.messages
        )
        (temporary_directory / "messages.jsonl").write_text(
            messages_jsonl,
            encoding="utf-8",
        )

        (temporary_directory / "transcript.md").write_text(
            _render_transcript(run),
            encoding="utf-8",
        )

        # The lock prevents another repository writer from publishing the
        # same run ID while this atomic sibling rename is in progress.
        temporary_directory.rename(run_directory)
    except BaseException:
        if temporary_directory is not None:
            shutil.rmtree(temporary_directory, ignore_errors=True)
        raise
    finally:
        # Missing locks are harmless during cleanup. Other cleanup failures
        # are reported only when they would not mask an active failure.
        if lock_acquired:
            operation_failed = sys.exc_info()[0] is not None
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                if not operation_failed:
                    raise

    return run_directory
