"""Persistence for complete multi-agent conversation runs."""

from pathlib import Path

from multi_agent_personalities.models.conversation import ConversationRun


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
    """Save one validated conversation without overwriting an existing run."""
    run_directory = (
        Path(output_root) / "conversations" / "runs" / run.run_id
    )
    run_directory.mkdir(parents=True, exist_ok=False)

    (run_directory / "run.json").write_text(
        run.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )

    messages_jsonl = "".join(
        message.model_dump_json() + "\n" for message in run.messages
    )
    (run_directory / "messages.jsonl").write_text(
        messages_jsonl,
        encoding="utf-8",
    )

    (run_directory / "transcript.md").write_text(
        _render_transcript(run),
        encoding="utf-8",
    )

    return run_directory
