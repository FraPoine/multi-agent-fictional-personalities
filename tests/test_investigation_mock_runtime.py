"""Tests for catalogue-driven deterministic investigation runtime assembly."""

import socket
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from multi_agent_personalities.application import (
    investigation_mock_runtime as runtime_module,
)
from multi_agent_personalities.application import (
    GeneratedAnalysisPayload,
    GeneratedDecisionPayload,
    GeneratedFinalTheoryPayload,
    InvestigationMockCapabilities,
    InvestigationMockRuntime,
    InvestigationMockTask,
    build_investigation_mock_runtime,
    parse_structured_generation,
)
from multi_agent_personalities.models import InvestigationSession, Persona
from multi_agent_personalities.pipeline import CharacterConfig, character_registry


ROOT = Path(__file__).resolve().parents[1]
PROMPT = "Assemble the deterministic investigation runtime."
EXPECTED_IDS = ("sherlock_holmes", "hercule_poirot")


@pytest.fixture(autouse=True)
def reject_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(socket.socket, "connect", fail)


def build_runtime(
    *,
    character_slugs: object = ("sherlock", "poirot"),
    session_sequence: object = 1,
    project_root: Path = ROOT,
) -> InvestigationMockRuntime:
    return build_investigation_mock_runtime(
        character_slugs=character_slugs,  # type: ignore[arg-type]
        session_sequence=session_sequence,  # type: ignore[arg-type]
        project_root=project_root,
    )


def test_builds_catalogue_driven_runtime_for_current_scenario() -> None:
    runtime = build_runtime()
    registry = character_registry(ROOT)

    assert isinstance(runtime, InvestigationMockRuntime)
    assert runtime.character_slugs == ("sherlock", "poirot")
    assert runtime.character_configs == (
        registry["sherlock"],
        registry["poirot"],
    )
    assert runtime.participant_ids == EXPECTED_IDS
    assert tuple(item.persona.character_id for item in runtime.participants) == (
        EXPECTED_IDS
    )
    assert tuple(item.display_name for item in runtime.participants) == (
        "Sherlock Holmes",
        "Hercule Poirot",
    )
    assert all(item.provider_name == "mock" for item in runtime.participants)
    assert all(item.model_name is None for item in runtime.participants)
    assert callable(runtime.decision_provider.generate)
    assert callable(runtime.final_theory_provider.generate)
    sherlock_generation = runtime.participants[0].provider.generate(
        PROMPT,
        task_name=InvestigationMockTask.SHERLOCK_ANALYSIS_ROUND_0001.value,
    )
    assert "SHERLOCK_R1" in sherlock_generation.text
    assert sherlock_generation.metadata.provider == "mock"


def test_session_two_factory_and_all_provider_levels_share_one_namespace() -> None:
    runtime = build_runtime(session_sequence=2)
    analysis = runtime.participants[0].provider.generate(
        PROMPT,
        task_name=InvestigationMockTask.SHERLOCK_ANALYSIS_ROUND_0001.value,
    )
    decision = runtime.decision_provider.generate(
        PROMPT,
        task_name=InvestigationMockTask.DECISION_ROUND_0002.value,
    )
    final = runtime.final_theory_provider.generate(
        PROMPT,
        task_name=InvestigationMockTask.FINAL_THEORY.value,
    )

    assert runtime.id_factory.session_id == "session_002"
    parse_structured_generation(analysis, GeneratedAnalysisPayload)
    parse_structured_generation(decision, GeneratedDecisionPayload)
    parse_structured_generation(final, GeneratedFinalTheoryPayload)
    for generation in (analysis, decision, final):
        assert "session_002_" in generation.text
        assert "session_001_" not in generation.text


def test_capabilities_are_explicit_runtime_limits_not_domain_fields() -> None:
    runtime = build_runtime()

    assert runtime.capabilities == InvestigationMockCapabilities(
        participant_ids=EXPECTED_IDS,
        supported_rounds=2,
        discussion_turns=2,
    )
    assert "supported_rounds" not in InvestigationSession.model_fields
    assert "discussion_turns" not in InvestigationSession.model_fields


def test_reverse_slug_input_normalizes_to_scenario_order() -> None:
    runtime = build_runtime(character_slugs=("poirot", "sherlock"))

    assert runtime.character_slugs == ("sherlock", "poirot")
    assert runtime.participant_ids == EXPECTED_IDS


@pytest.mark.parametrize(
    ("character_slugs", "message"),
    [
        ("sherlock", "sequence"),
        (b"sherlock", "sequence"),
        (("sherlock", 3), "only strings"),
        ((), "at least two"),
        (("sherlock",), "at least two"),
        (("sherlock", "sherlock"), "duplicates"),
    ],
)
def test_rejects_invalid_character_slug_collections(
    character_slugs: object,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_runtime(character_slugs=character_slugs)


def test_rejects_unknown_catalogue_slug_readably() -> None:
    with pytest.raises(
        ValueError,
        match="unknown catalogue character: 'unknown'.*sherlock, poirot",
    ):
        build_runtime(character_slugs=("sherlock", "unknown"))


def _catalog_entry(config: CharacterConfig) -> dict[str, str]:
    return {
        "slug": config.slug,
        "character_id": config.character_id,
        "display_name": config.display_name,
        "description": config.description,
        "corpus_path": str(config.corpus_paths[0]),
        "persona_fixture_path": str(config.persona_fixture),
        "mock_response_fixture_path": str(config.agent_response_fixture),
    }


def test_rejects_known_catalogue_character_without_scenario_provider(
    tmp_path: Path,
) -> None:
    registry = character_registry(ROOT)
    assets = tmp_path / "assets"
    assets.mkdir()
    corpus = assets / "corpus.jsonl"
    corpus.write_text('{"text":"Synthetic evidence."}\n', encoding="utf-8")
    persona_path = assets / "persona.json"
    persona_path.write_text(
        Persona(
            character_id="unsupported_detective",
            display_name="Unsupported Detective",
            description="Test-only catalogue character.",
            speaking_style=["Direct"],
            reasoning_style=["Methodical"],
            personality_traits=["Observant"],
            behavior_rules=["Use evidence"],
            example_messages=["A test response."],
        ).model_dump_json(),
        encoding="utf-8",
    )
    response = assets / "response.txt"
    response.write_text("Unsupported response.\n", encoding="utf-8")
    config_directory = tmp_path / "configs"
    config_directory.mkdir()
    entries = [
        _catalog_entry(registry["sherlock"]),
        _catalog_entry(registry["poirot"]),
        {
            "slug": "unsupported",
            "character_id": "unsupported_detective",
            "display_name": "Unsupported Detective",
            "description": "Test-only catalogue character.",
            "corpus_path": str(corpus),
            "persona_fixture_path": str(persona_path),
            "mock_response_fixture_path": str(response),
        },
    ]
    (config_directory / "characters.yaml").write_text(
        yaml.safe_dump({"characters": entries}, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="unsupported by the current investigation mock scenario: 'unsupported'",
    ):
        build_runtime(
            character_slugs=("sherlock", "unsupported"),
            project_root=tmp_path,
        )


def _replace_registry_persona(
    monkeypatch: pytest.MonkeyPatch,
    *,
    persona_fixture: Path,
) -> None:
    registry = character_registry(ROOT)
    registry["sherlock"] = replace(
        registry["sherlock"],
        persona_fixture=persona_fixture,
    )
    monkeypatch.setattr(runtime_module, "character_registry", lambda _: registry)


def test_rejects_missing_persona_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _replace_registry_persona(
        monkeypatch,
        persona_fixture=tmp_path / "missing.json",
    )

    with pytest.raises(ValueError, match="invalid investigation persona fixture"):
        build_runtime()


def test_rejects_malformed_persona_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "malformed.json"
    path.write_text("{", encoding="utf-8")
    _replace_registry_persona(monkeypatch, persona_fixture=path)

    with pytest.raises(ValueError, match="invalid investigation persona fixture"):
        build_runtime()


def test_rejects_persona_catalogue_identity_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "wrong-persona.json"
    poirot = character_registry(ROOT)["poirot"].persona_fixture.read_text(
        encoding="utf-8"
    )
    path.write_text(poirot, encoding="utf-8")
    _replace_registry_persona(monkeypatch, persona_fixture=path)

    with pytest.raises(ValueError, match="identity does not match 'sherlock'"):
        build_runtime()


@pytest.mark.parametrize("session_sequence", [0, -1, True, 1.0, "1"])
def test_invalid_session_sequence_uses_id_factory_validation(
    session_sequence: object,
) -> None:
    with pytest.raises(ValueError, match="session_sequence"):
        build_runtime(session_sequence=session_sequence)


def test_runtime_assembly_is_offline_and_api_key_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    runtime = build_runtime(session_sequence=2)
    result = runtime.final_theory_provider.generate(
        PROMPT,
        task_name=InvestigationMockTask.FINAL_THEORY.value,
    )

    assert result.metadata.provider == "mock"
    assert "session_002_" in result.text
