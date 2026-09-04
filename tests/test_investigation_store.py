"""Tests for process-local investigation session state ownership."""

import socket
from dataclasses import replace
from pathlib import Path
from threading import Event, Thread

import pytest

from multi_agent_personalities.application import (
    build_investigation_mock_runtime,
    create_session,
    reveal_clue,
    run_independent_analyses,
)
from multi_agent_personalities.web.investigation_store import (
    InMemoryInvestigationRegistry,
    InvestigationRegistryInvariantError,
    InvestigationSessionCollisionError,
    InvestigationSessionDeletionForbiddenError,
    InvestigationSessionMutation,
    InvestigationSessionNotFoundError,
    InvestigationSessionRecord,
)
from multi_agent_personalities.models import InvestigationSession, InvestigationStatus


ROOT = Path(__file__).resolve().parents[1]
CHARACTERS = ("sherlock", "poirot")
INTRODUCTION = "A researcher disappears from a locked archive room."
CLUE_ONE = "The archive-room window was found open."


@pytest.fixture(autouse=True)
def reject_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(socket.socket, "connect", fail)


def create_record(
    registry: InMemoryInvestigationRegistry,
) -> InvestigationSessionRecord:
    return registry.create(
        character_slugs=CHARACTERS,
        introduction=INTRODUCTION,
        project_root=ROOT,
    )


def reveal(record: InvestigationSessionRecord, clue: str = CLUE_ONE):
    return reveal_clue(
        record.session,
        clue_text=clue,
        id_factory=record.runtime.id_factory,
    )


def test_fresh_registries_are_empty_and_allocate_independently() -> None:
    first = InMemoryInvestigationRegistry()
    second = InMemoryInvestigationRegistry()

    assert first.session_ids == second.session_ids == ()
    assert create_record(first).session_id == "session_001"
    assert create_record(second).session_id == "session_001"


def test_creation_allocates_monotonic_session_namespaces() -> None:
    registry = InMemoryInvestigationRegistry()
    records = tuple(create_record(registry) for _ in range(3))

    assert tuple(item.session_id for item in records) == (
        "session_001",
        "session_002",
        "session_003",
    )
    assert tuple(item.session_sequence for item in records) == (1, 2, 3)
    assert tuple(item.runtime.id_factory.session_id for item in records) == (
        "session_001",
        "session_002",
        "session_003",
    )
    assert registry.session_ids == (
        "session_001",
        "session_002",
        "session_003",
    )


def test_failed_creation_registers_nothing_and_does_not_consume_sequence() -> None:
    registry = InMemoryInvestigationRegistry()

    with pytest.raises(ValueError, match="introduction"):
        registry.create(
            character_slugs=CHARACTERS,
            introduction=" ",
            project_root=ROOT,
        )

    assert registry.session_ids == ()
    assert create_record(registry).session_id == "session_001"


def test_retrieval_returns_latest_record_without_mutation() -> None:
    registry = InMemoryInvestigationRegistry()
    created = create_record(registry)

    assert registry.get(created.session_id) is created
    assert registry.snapshot(created.session_id) is created.session
    assert registry.session_ids == (created.session_id,)
    assert created.runtime.id_factory.session_id == created.session.session_id


@pytest.mark.parametrize("action", ["get", "snapshot", "mutate"])
def test_unknown_session_raises_dedicated_error(action: str) -> None:
    registry = InMemoryInvestigationRegistry()

    with pytest.raises(InvestigationSessionNotFoundError):
        if action == "get":
            registry.get("session_999")
        elif action == "snapshot":
            registry.snapshot("session_999")
        else:
            registry.mutate(
                "session_999",
                lambda record: InvestigationSessionMutation(
                    session=record.session,
                    result=None,
                ),
            )


def test_delete_missing_session_preserves_registry() -> None:
    registry = InMemoryInvestigationRegistry()
    created = create_record(registry)

    with pytest.raises(InvestigationSessionNotFoundError):
        registry.delete("session_999")

    assert registry.session_ids == (created.session_id,)
    assert registry.get(created.session_id) is created


def test_delete_removes_only_the_target_active_record_and_lock() -> None:
    registry = InMemoryInvestigationRegistry()
    first = create_record(registry)
    second = create_record(registry)

    deleted = registry.delete(first.session_id)

    assert deleted is first
    assert registry.session_ids == (second.session_id,)
    assert first.session_id not in registry._session_locks
    with pytest.raises(InvestigationSessionNotFoundError):
        registry.get(first.session_id)
    with pytest.raises(InvestigationSessionNotFoundError):
        registry.snapshot(first.session_id)
    with pytest.raises(InvestigationSessionNotFoundError):
        registry.mutate(
            first.session_id,
            lambda record: InvestigationSessionMutation(
                session=record.session,
                result=None,
            ),
        )
    with pytest.raises(InvestigationSessionNotFoundError):
        registry.delete(first.session_id)
    assert registry.get(second.session_id) is second


def test_delete_rejects_non_active_session_without_changing_record_or_lock() -> None:
    registry = InMemoryInvestigationRegistry()
    created = create_record(registry)
    payload = created.session.model_dump(mode="python")
    payload["status"] = InvestigationStatus.READY_FOR_FINAL
    ready_session = InvestigationSession.model_validate(payload)
    ready, _ = registry.mutate(
        created.session_id,
        lambda _record: InvestigationSessionMutation(
            session=ready_session,
            result=None,
        ),
    )
    session_lock = registry._session_locks[created.session_id]

    with pytest.raises(InvestigationSessionDeletionForbiddenError):
        registry.delete(created.session_id)

    assert registry.get(created.session_id) is ready
    assert registry._session_locks[created.session_id] is session_lock


def test_sessions_remain_isolated_across_independent_mutations() -> None:
    registry = InMemoryInvestigationRegistry()
    first = create_record(registry)
    second = create_record(registry)
    second_before = second.session

    first_updated, _ = registry.mutate(
        first.session_id,
        lambda record: InvestigationSessionMutation(
            session=reveal(record),
            result="first",
        ),
    )
    assert registry.get(second.session_id).session is second_before

    second_updated, _ = registry.mutate(
        second.session_id,
        lambda record: InvestigationSessionMutation(
            session=reveal(record, "A ledger page is missing."),
            result="second",
        ),
    )

    assert registry.get(first.session_id) is first_updated
    assert first_updated.session.clues[0].text == CLUE_ONE
    assert second_updated.session.clues[0].text == "A ledger page is missing."


def test_successful_mutation_replaces_only_the_immutable_snapshot() -> None:
    registry = InMemoryInvestigationRegistry()
    created = create_record(registry)
    received: list[object] = []

    updated, result = registry.mutate(
        created.session_id,
        lambda record: (
            received.append(record)
            or InvestigationSessionMutation(
                session=reveal(record),
                result={"phase": "awaiting_analyses"},
            )
        ),
    )

    assert received == [created]
    assert result == {"phase": "awaiting_analyses"}
    assert updated.session is not created.session
    assert created.session.clues == created.session.rounds == ()
    assert updated.session.clues[0].text == CLUE_ONE
    assert updated.runtime is created.runtime
    assert registry.get(created.session_id) is updated


def test_failed_mutation_propagates_and_preserves_exact_record() -> None:
    registry = InMemoryInvestigationRegistry()
    created = create_record(registry)

    def fail(record: InvestigationSessionRecord):
        assert record is created
        raise RuntimeError("operation failed")

    with pytest.raises(RuntimeError, match="operation failed"):
        registry.mutate(created.session_id, fail)

    assert registry.get(created.session_id) is created


def test_application_validation_failure_preserves_latest_snapshot() -> None:
    registry = InMemoryInvestigationRegistry()
    created = create_record(registry)
    revealed, _ = registry.mutate(
        created.session_id,
        lambda record: InvestigationSessionMutation(
            session=reveal(record),
            result=None,
        ),
    )

    with pytest.raises(ValueError, match="existing round is incomplete"):
        registry.mutate(
            created.session_id,
            lambda record: InvestigationSessionMutation(
                session=reveal(record, "A second clue."),
                result=None,
            ),
        )

    assert registry.get(created.session_id) is revealed


def test_wrong_session_replacement_is_rejected_without_commit() -> None:
    registry = InMemoryInvestigationRegistry()
    first = create_record(registry)
    second = create_record(registry)

    with pytest.raises(InvestigationRegistryInvariantError, match="session ID"):
        registry.mutate(
            first.session_id,
            lambda _: InvestigationSessionMutation(
                session=second.session,
                result=None,
            ),
        )

    assert registry.get(first.session_id) is first


def test_register_rejects_runtime_session_namespace_mismatch() -> None:
    runtime_one = build_investigation_mock_runtime(
        character_slugs=CHARACTERS,
        session_sequence=1,
        project_root=ROOT,
    )
    runtime_two = build_investigation_mock_runtime(
        character_slugs=CHARACTERS,
        session_sequence=2,
        project_root=ROOT,
    )
    session_one = create_session(
        id_factory=runtime_one.id_factory,
        introduction=INTRODUCTION,
        participant_ids=runtime_one.participant_ids,
    )
    mismatched = InvestigationSessionRecord(
        session_sequence=1,
        session=session_one,
        runtime=runtime_two,
    )

    with pytest.raises(
        InvestigationRegistryInvariantError,
        match="runtime session sequence",
    ):
        InMemoryInvestigationRegistry().register(mismatched)


def test_register_rejects_duplicate_session_without_overwrite() -> None:
    registry = InMemoryInvestigationRegistry()
    created = create_record(registry)

    with pytest.raises(InvestigationSessionCollisionError, match="already"):
        registry.register(created)

    assert registry.get(created.session_id) is created


def test_same_session_mutations_are_serialized_across_callbacks() -> None:
    registry = InMemoryInvestigationRegistry()
    created = create_record(registry)
    first_entered = Event()
    release_first = Event()
    second_started = Event()
    second_entered = Event()
    errors: list[BaseException] = []
    second_round_counts: list[int] = []

    def first_operation(record: InvestigationSessionRecord):
        first_entered.set()
        if not release_first.wait(timeout=5):
            raise AssertionError("first mutation was not released")
        return InvestigationSessionMutation(
            session=reveal(record),
            result=None,
        )

    def second_operation(record: InvestigationSessionRecord):
        second_entered.set()
        second_round_counts.append(len(record.session.rounds))
        return InvestigationSessionMutation(
            session=reveal(record, "A duplicate concurrent clue."),
            result=None,
        )

    def run_first() -> None:
        try:
            registry.mutate(created.session_id, first_operation)
        except BaseException as error:  # pragma: no cover - assertion transport
            errors.append(error)

    def run_second() -> None:
        second_started.set()
        try:
            registry.mutate(created.session_id, second_operation)
        except BaseException as error:
            errors.append(error)

    first_thread = Thread(target=run_first)
    second_thread = Thread(target=run_second)
    first_thread.start()
    assert first_entered.wait(timeout=5)
    second_thread.start()
    assert second_started.wait(timeout=5)
    assert not second_entered.is_set()
    release_first.set()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert second_entered.is_set()
    assert second_round_counts == [1]
    assert len(errors) == 1
    assert isinstance(errors[0], ValueError)
    assert len(registry.snapshot(created.session_id).rounds) == 1


def test_same_session_mutation_and_delete_share_serialization_lock() -> None:
    registry = InMemoryInvestigationRegistry()
    created = create_record(registry)
    mutation_entered = Event()
    release_mutation = Event()
    deletion_started = Event()
    deletion_completed = Event()
    deleted_records: list[InvestigationSessionRecord] = []
    errors: list[BaseException] = []

    def hold_mutation(record: InvestigationSessionRecord):
        mutation_entered.set()
        if not release_mutation.wait(timeout=5):
            raise AssertionError("mutation was not released")
        return InvestigationSessionMutation(session=reveal(record), result=None)

    def run_mutation() -> None:
        try:
            registry.mutate(created.session_id, hold_mutation)
        except BaseException as error:  # pragma: no cover - assertion transport
            errors.append(error)

    def run_delete() -> None:
        deletion_started.set()
        try:
            deleted_records.append(registry.delete(created.session_id))
            deletion_completed.set()
        except BaseException as error:  # pragma: no cover - assertion transport
            errors.append(error)

    mutation_thread = Thread(target=run_mutation)
    deletion_thread = Thread(target=run_delete)
    mutation_thread.start()
    assert mutation_entered.wait(timeout=5)
    deletion_thread.start()
    assert deletion_started.wait(timeout=5)
    assert not deletion_completed.is_set()
    release_mutation.set()
    mutation_thread.join(timeout=5)
    deletion_thread.join(timeout=5)

    assert not mutation_thread.is_alive()
    assert not deletion_thread.is_alive()
    assert errors == []
    assert len(deleted_records) == 1
    assert len(deleted_records[0].session.rounds) == 1
    assert created.session_id not in registry.session_ids


def test_different_session_mutations_do_not_share_operation_lock() -> None:
    registry = InMemoryInvestigationRegistry()
    first = create_record(registry)
    second = create_record(registry)
    first_entered = Event()
    release_first = Event()
    second_completed = Event()
    errors: list[BaseException] = []

    def hold_first(record: InvestigationSessionRecord):
        first_entered.set()
        if not release_first.wait(timeout=5):
            raise AssertionError("first mutation was not released")
        return InvestigationSessionMutation(session=reveal(record), result=None)

    def run_first() -> None:
        try:
            registry.mutate(first.session_id, hold_first)
        except BaseException as error:  # pragma: no cover - assertion transport
            errors.append(error)

    def run_second() -> None:
        try:
            registry.mutate(
                second.session_id,
                lambda record: InvestigationSessionMutation(
                    session=reveal(record, "An independent clue."),
                    result=None,
                ),
            )
            second_completed.set()
        except BaseException as error:  # pragma: no cover - assertion transport
            errors.append(error)

    first_thread = Thread(target=run_first)
    second_thread = Thread(target=run_second)
    first_thread.start()
    assert first_entered.wait(timeout=5)
    second_thread.start()
    assert second_completed.wait(timeout=5)
    assert first_thread.is_alive()
    release_first.set()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)

    assert errors == []
    assert len(registry.snapshot(first.session_id).rounds) == 1
    assert len(registry.snapshot(second.session_id).rounds) == 1


def test_real_create_reveal_analyse_workflow_reuses_runtime() -> None:
    registry = InMemoryInvestigationRegistry()
    created = create_record(registry)
    initial_session = created.session

    revealed, revealed_result = registry.mutate(
        created.session_id,
        lambda record: InvestigationSessionMutation(
            session=reveal(record),
            result="clue revealed",
        ),
    )
    analysed, analysis_result = registry.mutate(
        created.session_id,
        lambda record: (
            lambda result: InvestigationSessionMutation(
                session=result.session,
                result=result,
            )
        )(
            run_independent_analyses(
                record.session,
                participant_bindings=record.runtime.participants,
                id_factory=record.runtime.id_factory,
            )
        ),
    )

    assert revealed_result == "clue revealed"
    assert analysis_result.session is analysed.session
    assert registry.get(created.session_id) is analysed
    assert created.runtime is revealed.runtime is analysed.runtime
    assert initial_session.clues == initial_session.analyses == ()
    assert len(revealed.session.clues) == 1
    assert revealed.session.analyses == ()
    assert len(analysed.session.analyses) == 2
    assert analysed.session.session_id == created.session_id


def test_registry_creates_no_files_and_remains_api_key_independent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    before = tuple(tmp_path.iterdir())
    registry = InMemoryInvestigationRegistry()

    created = create_record(registry)
    registry.mutate(
        created.session_id,
        lambda record: InvestigationSessionMutation(
            session=reveal(record),
            result=None,
        ),
    )

    assert tuple(tmp_path.iterdir()) == before
