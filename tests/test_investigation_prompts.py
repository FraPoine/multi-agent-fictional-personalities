"""Tests for versioned investigation prompts and deterministic context."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

import multi_agent_personalities.application.investigation_prompts as prompts
from multi_agent_personalities.application import (
    InvestigationPromptError,
    InvestigationPromptName,
    InvestigationPromptTemplate,
    load_investigation_prompt,
    render_analyses,
    render_decisions,
    render_discussion_messages,
    render_hypotheses,
    render_investigation_prompt,
    render_visible_clues,
)
from multi_agent_personalities.models import (
    AgentAnalysis,
    Clue,
    GroupDecision,
    GroupDecisionType,
    Hypothesis,
    HypothesisStatus,
    InvestigationSession,
    InvestigationStatus,
    Message,
)


EXPECTED_PLACEHOLDERS = {
    InvestigationPromptName.ANALYSIS: (
        "session_id", "round_id", "case_introduction", "participant_id",
        "persona_profile", "visible_clues", "completed_history",
    ),
    InvestigationPromptName.DISCUSSION: (
        "session_id", "round_id", "case_introduction", "participant_id",
        "persona_profile", "visible_clues", "analyses", "completed_history",
        "discussion_history",
    ),
    InvestigationPromptName.DECISION: (
        "session_id", "round_id", "case_introduction", "visible_clues",
        "analyses", "hypotheses", "discussion_transcript",
    ),
    InvestigationPromptName.FINAL_THEORY: (
        "session_id", "case_introduction", "visible_clues", "hypotheses",
        "decisions",
    ),
    InvestigationPromptName.LEAD_FINAL_THEORY: (
        "session_id", "case_introduction", "leads", "visits",
        "revealed_information", "discussion_history", "hypotheses",
        "decisions",
    ),
}


def session_with_clues() -> InvestigationSession:
    return InvestigationSession(
        session_id="session_001",
        case_introduction="A case.",
        participant_ids=("sherlock", "poirot"),
        status=InvestigationStatus.ACTIVE,
        clues=(
            Clue(clue_id="clue_z", text="Zebra clue.", reveal_order=0),
            Clue(clue_id="clue_a", text="Apple clue.", reveal_order=1),
            Clue(clue_id="clue_hidden", text="Hidden clue.", reveal_order=2),
        ),
    )


@pytest.mark.parametrize("name", list(InvestigationPromptName))
def test_loads_all_fixed_versioned_prompts(name: InvestigationPromptName) -> None:
    template = load_investigation_prompt(name)

    assert template.name is name
    assert template.version == 1
    assert template.required_placeholders == EXPECTED_PLACEHOLDERS[name]
    assert all(f"{{{{{item}}}}}" in template.body for item in EXPECTED_PLACEHOLDERS[name])


def test_prompt_mapping_is_fixed_and_unknown_names_are_rejected() -> None:
    assert set(prompts._PROMPT_FILES) == set(InvestigationPromptName)
    with pytest.raises(InvestigationPromptError, match="unknown"):
        load_investigation_prompt("../../secret")  # type: ignore[arg-type]


def _write_prompt(directory: Path, text: str) -> None:
    directory.mkdir(exist_ok=True)
    (directory / "investigation_analysis.md").write_text(text, encoding="utf-8")


def test_missing_prompt_file_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(prompts, "_PROMPT_DIRECTORY", tmp_path)
    with pytest.raises(FileNotFoundError, match="not found"):
        load_investigation_prompt(InvestigationPromptName.ANALYSIS)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("body only", "Prompt-Version"),
        ("Prompt-Version: one\nbody", "Prompt-Version"),
        ("Prompt-Version: 2\nbody", "unsupported"),
        ("Prompt-Version: 1\n\n  ", "body"),
    ],
)
def test_invalid_prompt_headers_and_body_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    text: str,
    message: str,
) -> None:
    _write_prompt(tmp_path, text)
    monkeypatch.setattr(prompts, "_PROMPT_DIRECTORY", tmp_path)
    with pytest.raises(InvestigationPromptError, match=message):
        load_investigation_prompt(InvestigationPromptName.ANALYSIS)


def test_loaded_template_is_immutable() -> None:
    template = load_investigation_prompt(InvestigationPromptName.ANALYSIS)
    with pytest.raises(ValidationError):
        template.version = 2


def test_loading_is_independent_of_current_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert load_investigation_prompt(InvestigationPromptName.FINAL_THEORY).version == 1


def test_complete_rendering_is_deterministic_and_replaces_repetitions() -> None:
    template = InvestigationPromptTemplate(
        name=InvestigationPromptName.ANALYSIS,
        version=1,
        body="{{session_id}}/{{session_id}} {{round_id}} {{case_introduction}} "
        "{{participant_id}} {{persona_profile}} {{visible_clues}} "
        "{{completed_history}}",
        required_placeholders=EXPECTED_PLACEHOLDERS[InvestigationPromptName.ANALYSIS],
    )
    values = {
        "session_id": "session_001",
        "round_id": "round_001",
        "case_introduction": "A case.",
        "participant_id": "sherlock",
        "persona_profile": "Sherlock persona.",
        "visible_clues": "[clue] Text.",
        "completed_history": "None.",
    }
    first = render_investigation_prompt(template, values)
    assert first == render_investigation_prompt(template, values)
    assert first.count("session_001") == 2


def test_rendered_value_braces_are_not_interpreted_again() -> None:
    template = load_investigation_prompt(InvestigationPromptName.ANALYSIS)
    values = {name: name for name in template.required_placeholders}
    values["case_introduction"] = "Literal {{not_a_placeholder}} remains."
    assert "{{not_a_placeholder}}" in render_investigation_prompt(template, values)


def test_known_placeholder_text_inside_values_remains_literal_in_single_pass() -> None:
    template = load_investigation_prompt(InvestigationPromptName.ANALYSIS)
    values = {name: name for name in template.required_placeholders}
    literal = "Literal {{participant_id}} and {{session_id}} remain."
    values["case_introduction"] = literal

    rendered = render_investigation_prompt(template, values)

    assert literal in rendered
    assert rendered == render_investigation_prompt(template, values)


@pytest.mark.parametrize("failure", ["missing_value", "empty_value", "wrong_type"])
def test_renderer_rejects_invalid_required_values(failure: str) -> None:
    template = load_investigation_prompt(InvestigationPromptName.ANALYSIS)
    values: dict[str, object] = {
        name: name for name in template.required_placeholders
    }
    if failure == "missing_value":
        del values["round_id"]
    elif failure == "empty_value":
        values["round_id"] = " "
    else:
        values["round_id"] = {"complex": "object"}
    with pytest.raises(InvestigationPromptError):
        render_investigation_prompt(template, values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "placeholder",
    ["missing_required", "{{unknown}}", "{{ malformed }}"],
)
def test_renderer_rejects_broken_template_contract(placeholder: str) -> None:
    required = EXPECTED_PLACEHOLDERS[InvestigationPromptName.ANALYSIS]
    body = " ".join(f"{{{{{item}}}}}" for item in required)
    body = body.replace("{{round_id}}", placeholder)
    template = InvestigationPromptTemplate(
        name=InvestigationPromptName.ANALYSIS,
        version=1,
        body=body,
        required_placeholders=required,
    )
    with pytest.raises(InvestigationPromptError):
        render_investigation_prompt(template, {item: item for item in required})


def test_visible_clues_follow_snapshot_order_not_id_or_text_order() -> None:
    rendered = render_visible_clues(session_with_clues(), ("clue_a", "clue_z"))
    assert rendered == "[clue_a] Apple clue.\n[clue_z] Zebra clue."


def test_visible_clue_renderer_does_not_render_hidden_session_clues() -> None:
    rendered = render_visible_clues(session_with_clues(), ("clue_z",))
    assert "Zebra clue." in rendered
    assert "Hidden clue." not in rendered
    assert "Apple clue." not in rendered


@pytest.mark.parametrize("ids", [("unknown",), ("clue_z", "clue_z")])
def test_visible_clue_renderer_rejects_unknown_or_duplicate_ids(
    ids: tuple[str, ...],
) -> None:
    with pytest.raises(ValueError):
        render_visible_clues(session_with_clues(), ids)


def test_other_record_renderers_preserve_order_and_stable_empty_value() -> None:
    analyses = (
        AgentAnalysis(analysis_id="a2", session_id="session_001", round_id="r1", agent_id="poirot", visible_clue_ids=(), facts=("Second",)),
        AgentAnalysis(analysis_id="a1", session_id="session_001", round_id="r1", agent_id="sherlock", visible_clue_ids=(), facts=("First",)),
    )
    hypotheses = (
        Hypothesis(hypothesis_id="h2", session_id="session_001", round_id="r1", statement="Second", status=HypothesisStatus.ACTIVE),
        Hypothesis(hypothesis_id="h1", session_id="session_001", round_id="r1", statement="First", status=HypothesisStatus.DISCARDED),
    )
    decisions = (
        GroupDecision(decision_id="d2", session_id="session_001", round_id="r1", decision_type=GroupDecisionType.REQUEST_INFORMATION, summary="Second"),
        GroupDecision(decision_id="d1", session_id="session_001", round_id="r1", decision_type=GroupDecisionType.PURSUE_LEAD, summary="First"),
    )
    assert render_analyses(analyses).index("[a2]") < render_analyses(analyses).index("[a1]")
    assert render_hypotheses(hypotheses).index("[h2]") < render_hypotheses(hypotheses).index("[h1]")
    assert render_decisions(decisions).index("[d2]") < render_decisions(decisions).index("[d1]")
    assert render_analyses(()) == render_hypotheses(()) == render_decisions(()) == "None."


def test_discussion_renderer_preserves_message_order() -> None:
    def message(message_id: str, turn: int, speaker: str) -> Message:
        return Message(message_id=message_id, run_id="run", turn_index=turn, speaker_character_id=speaker, speaker_name=speaker.title(), text=message_id, provider="mock", timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc))

    rendered = render_discussion_messages((message("m2", 2, "poirot"), message("m1", 1, "sherlock")))
    assert rendered.index("m2") < rendered.index("m1")
    assert render_discussion_messages(()) == "None."
