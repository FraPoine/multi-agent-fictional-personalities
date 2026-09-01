"""Process-local state ownership for future investigation web delivery."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Lock
from typing import Generic, TypeVar

from multi_agent_personalities.case_catalog import CaseCatalog, CaseDefinition
from multi_agent_personalities.application.investigation_ids import (
    DeterministicInvestigationIdFactory,
)
from multi_agent_personalities.application.investigation_mock_runtime import (
    InvestigationMockRuntime,
    build_investigation_mock_runtime,
)
from multi_agent_personalities.application.investigation_visit_service import (
    create_session,
)
from multi_agent_personalities.models import InvestigationSession


T = TypeVar("T")


class InvestigationSessionNotFoundError(KeyError):
    """Raised when a process-local investigation session is unknown."""


class InvestigationSessionCollisionError(ValueError):
    """Raised when registration would overwrite an existing session."""


class InvestigationRegistryInvariantError(ValueError):
    """Raised when record, runtime, and session identities disagree."""


@dataclass(frozen=True)
class InvestigationSessionRecord:
    """One immutable snapshot and its session-scoped runtime dependencies."""

    session_sequence: int
    session: InvestigationSession
    runtime: InvestigationMockRuntime

    @property
    def session_id(self) -> str:
        return self.session.session_id


@dataclass(frozen=True)
class InvestigationSessionMutation(Generic[T]):
    """A proposed replacement snapshot plus an operation-specific result."""

    session: InvestigationSession
    result: T


class InMemoryInvestigationRegistry:
    """Own process-local investigation records with per-session serialization."""

    def __init__(self, *, case_catalog: CaseCatalog | None = None) -> None:
        self._registry_lock = Lock()
        self._creation_lock = Lock()
        self._records: dict[str, InvestigationSessionRecord] = {}
        self._session_locks: dict[str, Lock] = {}
        self._next_session_sequence = 1
        self._case_catalog = case_catalog

    @property
    def session_ids(self) -> tuple[str, ...]:
        """Return registered IDs in insertion order without exposing storage."""
        with self._registry_lock:
            return tuple(self._records)

    @property
    def case_catalog(self) -> CaseCatalog | None:
        """Expose the immutable catalogue configured for session creation."""
        return self._case_catalog

    def create(
        self,
        *,
        character_slugs: Sequence[str],
        introduction: str | None = None,
        case_id: str | None = None,
        case_definition: CaseDefinition | None = None,
        project_root: Path | None = None,
    ) -> InvestigationSessionRecord:
        """Build and atomically register one complete investigation record."""
        with self._creation_lock:
            if case_definition is not None:
                if case_id is not None and case_id != case_definition.case_id:
                    raise ValueError("case_id must match case_definition")
                resolved_case_id = case_definition.case_id
                resolved_introduction = case_definition.opening
            elif case_id is not None:
                if self._case_catalog is None:
                    raise ValueError(
                        "case_id requires a configured local case catalogue"
                    )
                try:
                    case = self._case_catalog.get(case_id)
                except KeyError as error:
                    raise ValueError(str(error)) from error
                resolved_case_id = case.case_id
                resolved_introduction = case.opening
            else:
                if introduction is None:
                    raise ValueError("introduction is required without case_id")
                resolved_case_id = "legacy-local-demo"
                resolved_introduction = introduction
            with self._registry_lock:
                session_sequence = self._next_session_sequence
            runtime = build_investigation_mock_runtime(
                character_slugs=character_slugs,
                session_sequence=session_sequence,
                project_root=project_root,
            )
            session = create_session(
                id_factory=runtime.id_factory,
                introduction=resolved_introduction,
                participant_ids=runtime.participant_ids,
                case_id=resolved_case_id,
            )
            record = InvestigationSessionRecord(
                session_sequence=session_sequence,
                session=session,
                runtime=runtime,
            )
            self._validate_record(record)
            with self._registry_lock:
                if record.session_id in self._records:
                    raise InvestigationSessionCollisionError(
                        "investigation session already registered: "
                        f"{record.session_id}"
                    )
                self._records[record.session_id] = record
                self._session_locks[record.session_id] = Lock()
                self._next_session_sequence += 1
            return record

    def register(
        self,
        record: InvestigationSessionRecord,
    ) -> InvestigationSessionRecord:
        """Register one complete externally assembled record without overwrite."""
        self._validate_record(record)
        with self._creation_lock:
            with self._registry_lock:
                if record.session_id in self._records:
                    raise InvestigationSessionCollisionError(
                        "investigation session already registered: "
                        f"{record.session_id}"
                    )
                self._records[record.session_id] = record
                self._session_locks[record.session_id] = Lock()
                self._next_session_sequence = max(
                    self._next_session_sequence,
                    record.session_sequence + 1,
                )
        return record

    def get(self, session_id: str) -> InvestigationSessionRecord:
        """Return the latest immutable record for one known session."""
        session_lock = self._get_session_lock(session_id)
        with session_lock:
            with self._registry_lock:
                return self._records[session_id]

    def snapshot(self, session_id: str) -> InvestigationSession:
        """Return the latest immutable investigation aggregate."""
        return self.get(session_id).session

    def mutate(
        self,
        session_id: str,
        operation: Callable[
            [InvestigationSessionRecord],
            InvestigationSessionMutation[T],
        ],
    ) -> tuple[InvestigationSessionRecord, T]:
        """Execute and commit one operation while holding its session lock."""
        if not callable(operation):
            raise ValueError("operation must be callable")
        session_lock = self._get_session_lock(session_id)
        with session_lock:
            with self._registry_lock:
                current = self._records[session_id]
            mutation = operation(current)
            if not isinstance(mutation, InvestigationSessionMutation):
                raise InvestigationRegistryInvariantError(
                    "operation must return an InvestigationSessionMutation"
                )
            updated = replace(current, session=mutation.session)
            self._validate_record(updated)
            if updated.session_id != session_id:
                raise InvestigationRegistryInvariantError(
                    "replacement session_id must match the registered session"
                )
            with self._registry_lock:
                self._records[session_id] = updated
            return updated, mutation.result

    def _get_session_lock(self, session_id: str) -> Lock:
        with self._registry_lock:
            try:
                return self._session_locks[session_id]
            except KeyError as error:
                raise InvestigationSessionNotFoundError(session_id) from error

    @staticmethod
    def _validate_record(record: InvestigationSessionRecord) -> None:
        if not isinstance(record, InvestigationSessionRecord):
            raise InvestigationRegistryInvariantError(
                "record must be an InvestigationSessionRecord"
            )
        if not isinstance(record.session, InvestigationSession):
            raise InvestigationRegistryInvariantError(
                "record session must be a validated InvestigationSession"
            )
        if not isinstance(record.runtime, InvestigationMockRuntime):
            raise InvestigationRegistryInvariantError(
                "record runtime must be an InvestigationMockRuntime"
            )
        try:
            expected_id = DeterministicInvestigationIdFactory(
                record.session_sequence
            ).session_id
        except ValueError as error:
            raise InvestigationRegistryInvariantError(
                "record session_sequence is invalid"
            ) from error
        runtime_factory = record.runtime.id_factory
        if runtime_factory.session_sequence != record.session_sequence:
            raise InvestigationRegistryInvariantError(
                "runtime session sequence must match the record"
            )
        if runtime_factory.session_id != expected_id:
            raise InvestigationRegistryInvariantError(
                "runtime session ID must match the record sequence"
            )
        if record.session.session_id != expected_id:
            raise InvestigationRegistryInvariantError(
                "session ID must match the record sequence"
            )
        if record.session.participant_ids != record.runtime.participant_ids:
            raise InvestigationRegistryInvariantError(
                "session participants must match the registered runtime"
            )
