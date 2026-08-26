"""Tests for explicit deterministic investigation workflow fixtures."""

import socket
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from multi_agent_personalities.application import (
    HERCULE_POIROT_ID,
    INVESTIGATION_FIXTURE_FILES,
    SHERLOCK_HOLMES_ID,
    DeterministicInvestigationIdFactory,
    GeneratedAnalysisPayload,
    GeneratedDecisionPayload,
    GeneratedFinalTheoryPayload,
    InvestigationMockBindings,
    InvestigationMockTask,
    StructuredOutputError,
    build_investigation_mock_bindings,
    investigation_analysis_task_name,
    investigation_decision_task_name,
    investigation_discussion_task_name,
    investigation_final_theory_task_name,
    parse_structured_generation,
)
from multi_agent_personalities.models import GenerationResult


FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures" / "investigation"
PROMPT = "Deterministic investigation fixture test."


@pytest.fixture(autouse=True)
def reject_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(socket.socket, "connect", fail)


def generate_from_bindings(
    bindings: InvestigationMockBindings,
    task: InvestigationMockTask,
) -> GenerationResult:
    if "sherlock_holmes" in task.value:
        provider = bindings.participant_providers[SHERLOCK_HOLMES_ID]
    elif "hercule_poirot" in task.value:
        provider = bindings.participant_providers[HERCULE_POIROT_ID]
    elif ".decision." in task.value:
        provider = bindings.decision_provider
    else:
        provider = bindings.final_theory_provider
    return provider.generate(PROMPT, task_name=task.value)


def generate(
    task: InvestigationMockTask,
    *,
    session_sequence: int = 1,
) -> GenerationResult:
    return generate_from_bindings(
        build_investigation_mock_bindings(session_sequence=session_sequence),
        task,
    )


def test_fixture_inventory_is_complete_unique_and_explicit() -> None:
    assert set(INVESTIGATION_FIXTURE_FILES) == set(InvestigationMockTask)
    assert len(INVESTIGATION_FIXTURE_FILES) == 11
    assert len(set(task.value for task in InvestigationMockTask)) == 11
    assert len(set(INVESTIGATION_FIXTURE_FILES.values())) == 11

    names = tuple(task.value for task in InvestigationMockTask)
    for round_id in ("round_0001", "round_0002"):
        assert sum(f"analysis.sherlock_holmes.{round_id}" in item for item in names) == 1
        assert sum(f"analysis.hercule_poirot.{round_id}" in item for item in names) == 1
        assert sum(f"discussion.sherlock_holmes.{round_id}" in item for item in names) == 1
        assert sum(f"discussion.hercule_poirot.{round_id}" in item for item in names) == 1
        assert sum(f"decision.{round_id}" in item for item in names) == 1
    assert names.count("investigation.final_theory") == 1


def test_provider_neutral_task_names_remain_backward_compatible() -> None:
    assert investigation_analysis_task_name("sherlock_holmes", 1) == (
        "investigation.analysis.sherlock_holmes.round_0001"
    )
    assert investigation_discussion_task_name("hercule_poirot", 2, 0) == (
        "investigation.discussion.hercule_poirot.round_0002.turn_0001"
    )
    assert investigation_decision_task_name(1) == (
        "investigation.decision.round_0001"
    )
    assert investigation_final_theory_task_name() == "investigation.final_theory"


@pytest.mark.parametrize("value", [0, -1, True, 1.0, "1"])
def test_decision_task_name_rejects_invalid_round(value: object) -> None:
    with pytest.raises(ValueError, match="round_index"):
        investigation_decision_task_name(value)  # type: ignore[arg-type]


def test_provider_neutral_service_does_not_import_mock_module() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src" / "multi_agent_personalities" / "application"
    for filename in ("investigation_service.py", "investigation_discussion.py"):
        assert "investigation_mock" not in (source_root / filename).read_text(
            encoding="utf-8"
        )


def test_all_mapped_fixture_files_exist_and_are_nonempty() -> None:
    for filename in INVESTIGATION_FIXTURE_FILES.values():
        path = FIXTURES_ROOT / filename
        assert path.is_file()
        assert path.read_bytes().strip()


@pytest.mark.parametrize(
    ("task", "marker"),
    [
        (InvestigationMockTask.SHERLOCK_ANALYSIS_ROUND_0001, "SHERLOCK_R1"),
        (InvestigationMockTask.POIROT_ANALYSIS_ROUND_0001, "POIROT_R1"),
        (
            InvestigationMockTask.SHERLOCK_DISCUSSION_ROUND_0001_TURN_0001,
            "SHERLOCK_DISCUSSION_R1",
        ),
        (
            InvestigationMockTask.POIROT_DISCUSSION_ROUND_0001_TURN_0002,
            "POIROT_DISCUSSION_R1",
        ),
    ],
)
def test_participant_tasks_return_the_bound_fixture(
    task: InvestigationMockTask,
    marker: str,
) -> None:
    assert marker in generate(task).text


def test_participant_cannot_select_the_other_participants_task() -> None:
    bindings = build_investigation_mock_bindings()
    with pytest.raises(ValueError, match="No mock response configured"):
        bindings.participant_providers[SHERLOCK_HOLMES_ID].generate(
            PROMPT,
            task_name=InvestigationMockTask.POIROT_ANALYSIS_ROUND_0001.value,
        )


def test_group_tasks_are_explicit_and_call_order_independent() -> None:
    bindings = build_investigation_mock_bindings()
    round_two = bindings.decision_provider.generate(
        PROMPT,
        task_name=InvestigationMockTask.DECISION_ROUND_0002.value,
    )
    round_one = bindings.decision_provider.generate(
        PROMPT,
        task_name=InvestigationMockTask.DECISION_ROUND_0001.value,
    )
    final = bindings.final_theory_provider.generate(
        PROMPT,
        task_name=InvestigationMockTask.FINAL_THEORY.value,
    )

    assert "interior corridor" in round_two.text
    assert "ground below the window" in round_one.text
    assert "false exit" in final.text
    assert set(bindings.participant_providers) == {
        SHERLOCK_HOLMES_ID,
        HERCULE_POIROT_ID,
    }


def test_group_provider_does_not_fall_back_between_phase_types() -> None:
    bindings = build_investigation_mock_bindings()
    with pytest.raises(ValueError, match="No mock response configured"):
        bindings.decision_provider.generate(
            PROMPT,
            task_name=InvestigationMockTask.FINAL_THEORY.value,
        )


@pytest.mark.parametrize(
    ("task", "model"),
    [
        (InvestigationMockTask.SHERLOCK_ANALYSIS_ROUND_0001, GeneratedAnalysisPayload),
        (InvestigationMockTask.POIROT_ANALYSIS_ROUND_0001, GeneratedAnalysisPayload),
        (InvestigationMockTask.DECISION_ROUND_0001, GeneratedDecisionPayload),
        (InvestigationMockTask.DECISION_ROUND_0002, GeneratedDecisionPayload),
        (InvestigationMockTask.FINAL_THEORY, GeneratedFinalTheoryPayload),
    ],
)
def test_structured_fixture_traverses_generation_and_adapter_boundaries(
    task: InvestigationMockTask,
    model: type[BaseModel],
) -> None:
    generation = generate(task)
    result = parse_structured_generation(generation, model)

    assert isinstance(generation, GenerationResult)
    assert isinstance(result.value, model)
    assert result.generation is generation
    assert result.generation.metadata is generation.metadata
    assert generation.metadata.provider == "mock"
    assert generation.metadata.model is None
    assert generation.metadata.finish_reason == "completed"


def test_discussion_fixture_is_plain_text_inside_generation_result() -> None:
    result = generate(
        InvestigationMockTask.SHERLOCK_DISCUSSION_ROUND_0002_TURN_0001
    )
    assert isinstance(result, GenerationResult)
    assert result.text.startswith("SHERLOCK_DISCUSSION_R2")


def test_unknown_and_missing_fixtures_fail_explicitly(tmp_path: Path) -> None:
    bindings = build_investigation_mock_bindings(tmp_path)
    with pytest.raises(ValueError, match="No mock response configured"):
        bindings.decision_provider.generate(PROMPT, task_name="unknown.task")
    with pytest.raises(FileNotFoundError, match="not found"):
        bindings.decision_provider.generate(
            PROMPT,
            task_name=InvestigationMockTask.DECISION_ROUND_0001.value,
        )


@pytest.mark.parametrize("content", ["", " \n\t"])
def test_empty_fixture_fails_at_generation_boundary(
    tmp_path: Path,
    content: str,
) -> None:
    filename = INVESTIGATION_FIXTURE_FILES[
        InvestigationMockTask.DECISION_ROUND_0001
    ]
    (tmp_path / filename).write_text(content, encoding="utf-8")
    provider = build_investigation_mock_bindings(tmp_path).decision_provider
    with pytest.raises(ValidationError, match="text must not be empty"):
        provider.generate(
            PROMPT,
            task_name=InvestigationMockTask.DECISION_ROUND_0001.value,
        )


@pytest.mark.parametrize(
    ("content", "message"),
    [("{", "malformed JSON"), ('{"summary":"only"}', "invalid schema")],
)
def test_invalid_structured_fixture_reaches_adapter_failure(
    tmp_path: Path,
    content: str,
    message: str,
) -> None:
    filename = INVESTIGATION_FIXTURE_FILES[
        InvestigationMockTask.DECISION_ROUND_0001
    ]
    (tmp_path / filename).write_text(content, encoding="utf-8")
    generation = build_investigation_mock_bindings(tmp_path).decision_provider.generate(
        PROMPT,
        task_name=InvestigationMockTask.DECISION_ROUND_0001.value,
    )
    with pytest.raises(StructuredOutputError, match=message):
        parse_structured_generation(generation, GeneratedDecisionPayload)


def test_extra_structured_field_is_rejected_by_existing_schema(
    tmp_path: Path,
) -> None:
    filename = INVESTIGATION_FIXTURE_FILES[
        InvestigationMockTask.DECISION_ROUND_0001
    ]
    (tmp_path / filename).write_text(
        '{"decision_type":"pursue_lead","summary":"x",'
        '"analysis_ids":[],"hypothesis_ids":[],"evidence":[],"extra":1}',
        encoding="utf-8",
    )
    generation = build_investigation_mock_bindings(tmp_path).decision_provider.generate(
        PROMPT,
        task_name=InvestigationMockTask.DECISION_ROUND_0001.value,
    )
    with pytest.raises(StructuredOutputError, match="invalid schema"):
        parse_structured_generation(generation, GeneratedDecisionPayload)


@pytest.mark.parametrize("session_sequence", [1, 2])
def test_two_round_references_follow_deterministic_chronology(
    session_sequence: int,
) -> None:
    factory = DeterministicInvestigationIdFactory(session_sequence)
    clue_one = factory.clue_id(0)
    clue_two = factory.clue_id(1)
    round_one_analyses = (
        parse_structured_generation(
            generate(
                InvestigationMockTask.SHERLOCK_ANALYSIS_ROUND_0001,
                session_sequence=session_sequence,
            ),
            GeneratedAnalysisPayload,
        ).value,
        parse_structured_generation(
            generate(
                InvestigationMockTask.POIROT_ANALYSIS_ROUND_0001,
                session_sequence=session_sequence,
            ),
            GeneratedAnalysisPayload,
        ).value,
    )
    round_two_analyses = (
        parse_structured_generation(
            generate(
                InvestigationMockTask.SHERLOCK_ANALYSIS_ROUND_0002,
                session_sequence=session_sequence,
            ),
            GeneratedAnalysisPayload,
        ).value,
        parse_structured_generation(
            generate(
                InvestigationMockTask.POIROT_ANALYSIS_ROUND_0002,
                session_sequence=session_sequence,
            ),
            GeneratedAnalysisPayload,
        ).value,
    )
    decision_one = parse_structured_generation(
        generate(
            InvestigationMockTask.DECISION_ROUND_0001,
            session_sequence=session_sequence,
        ),
        GeneratedDecisionPayload,
    ).value
    decision_two = parse_structured_generation(
        generate(
            InvestigationMockTask.DECISION_ROUND_0002,
            session_sequence=session_sequence,
        ),
        GeneratedDecisionPayload,
    ).value
    final = parse_structured_generation(
        generate(
            InvestigationMockTask.FINAL_THEORY,
            session_sequence=session_sequence,
        ),
        GeneratedFinalTheoryPayload,
    ).value

    assert {
        reference.clue_id
        for analysis in round_one_analyses
        for reference in analysis.evidence
    } <= {clue_one}
    assert {
        reference.clue_id
        for analysis in round_two_analyses
        for reference in analysis.evidence
    } <= {clue_one, clue_two}
    assert decision_one.analysis_ids == (
        factory.analysis_id("sherlock_holmes", 1),
        factory.analysis_id("hercule_poirot", 1),
    )
    assert sum(len(item.hypotheses) for item in round_one_analyses) == 1
    assert decision_one.hypothesis_ids == (factory.hypothesis_id(1),)
    assert decision_two.analysis_ids == (
        factory.analysis_id("sherlock_holmes", 2),
        factory.analysis_id("hercule_poirot", 2),
    )
    assert sum(len(item.hypotheses) for item in round_two_analyses) == 1
    assert round_two_analyses[0].hypotheses[0].previous_hypothesis_id == (
        factory.hypothesis_id(1)
    )
    assert decision_two.hypothesis_ids == (factory.hypothesis_id(2),)
    assert final.hypothesis_ids == (factory.hypothesis_id(2),)
    assert {item.clue_id for item in final.evidence} <= {clue_one, clue_two}


def test_explicit_session_one_matches_default_fixture_bytes() -> None:
    default_bindings = build_investigation_mock_bindings()
    explicit_bindings = build_investigation_mock_bindings(session_sequence=1)

    for task in InvestigationMockTask:
        default = generate_from_bindings(default_bindings, task)
        explicit = generate_from_bindings(explicit_bindings, task)
        assert explicit == default
        assert explicit.text.encode("utf-8") == (
            FIXTURES_ROOT / INVESTIGATION_FIXTURE_FILES[task]
        ).read_bytes()


@pytest.mark.parametrize(
    ("task", "model"),
    [
        (InvestigationMockTask.SHERLOCK_ANALYSIS_ROUND_0001, GeneratedAnalysisPayload),
        (InvestigationMockTask.POIROT_ANALYSIS_ROUND_0001, GeneratedAnalysisPayload),
        (InvestigationMockTask.SHERLOCK_ANALYSIS_ROUND_0002, GeneratedAnalysisPayload),
        (InvestigationMockTask.POIROT_ANALYSIS_ROUND_0002, GeneratedAnalysisPayload),
        (InvestigationMockTask.DECISION_ROUND_0001, GeneratedDecisionPayload),
        (InvestigationMockTask.DECISION_ROUND_0002, GeneratedDecisionPayload),
        (InvestigationMockTask.FINAL_THEORY, GeneratedFinalTheoryPayload),
    ],
)
def test_all_structured_outputs_are_scoped_to_session_two(
    task: InvestigationMockTask,
    model: type[BaseModel],
) -> None:
    generation = generate(task, session_sequence=2)
    parsed = parse_structured_generation(generation, model)

    assert isinstance(parsed.value, model)
    assert "session_001" not in generation.text
    assert "session_002" in generation.text
    assert generation.metadata.provider == "mock"
    assert generation.metadata.finish_reason == "completed"


def test_session_scoped_bindings_are_independent_and_byte_deterministic() -> None:
    session_one = build_investigation_mock_bindings(session_sequence=1)
    session_two = build_investigation_mock_bindings(session_sequence=2)
    tasks = (
        InvestigationMockTask.SHERLOCK_ANALYSIS_ROUND_0001,
        InvestigationMockTask.SHERLOCK_ANALYSIS_ROUND_0002,
        InvestigationMockTask.DECISION_ROUND_0001,
        InvestigationMockTask.DECISION_ROUND_0002,
        InvestigationMockTask.FINAL_THEORY,
    )

    session_one_before = tuple(
        generate_from_bindings(session_one, task) for task in tasks
    )
    session_two_reordered = tuple(
        generate_from_bindings(session_two, task) for task in reversed(tasks)
    )
    session_one_after = tuple(
        generate_from_bindings(session_one, task) for task in tasks
    )
    session_two_again = tuple(
        generate_from_bindings(session_two, task) for task in reversed(tasks)
    )

    assert session_one_after == session_one_before
    assert session_two_again == session_two_reordered
    assert all("session_002" not in item.text for item in session_one_after)
    assert all("session_001" not in item.text for item in session_two_again)


@pytest.mark.parametrize("value", [0, -1, True, 1.0, "1"])
def test_bindings_reject_invalid_session_sequences(value: object) -> None:
    with pytest.raises(ValueError, match="session_sequence"):
        build_investigation_mock_bindings(
            session_sequence=value  # type: ignore[arg-type]
        )


def test_repeated_and_reordered_calls_are_byte_deterministic() -> None:
    first_bindings = build_investigation_mock_bindings()
    second_bindings = build_investigation_mock_bindings()
    task = InvestigationMockTask.SHERLOCK_ANALYSIS_ROUND_0002
    first = first_bindings.participant_providers[SHERLOCK_HOLMES_ID].generate(
        PROMPT, task_name=task.value
    )
    generate(InvestigationMockTask.POIROT_ANALYSIS_ROUND_0001)
    second = second_bindings.participant_providers[SHERLOCK_HOLMES_ID].generate(
        PROMPT, task_name=task.value
    )

    assert first == second
    assert first.text.encode("utf-8") == (
        FIXTURES_ROOT / INVESTIGATION_FIXTURE_FILES[task]
    ).read_bytes()


def test_bindings_are_offline_and_independent_of_api_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = generate(InvestigationMockTask.FINAL_THEORY)
    assert result.metadata.provider == "mock"


def test_default_fixture_resolution_is_independent_of_working_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    result = build_investigation_mock_bindings().final_theory_provider.generate(
        PROMPT,
        task_name=InvestigationMockTask.FINAL_THEORY.value,
    )
    assert "false exit" in result.text
