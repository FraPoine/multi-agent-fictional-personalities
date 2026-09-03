"""Atomic explicit consultation of verified local public resource text."""

from multi_agent_personalities.case_catalog import CaseCatalog
from multi_agent_personalities.models import InvestigationSession, InvestigationStatus, ResourceConsultation
from multi_agent_personalities.resource_text_catalog import ResourceTextCatalog


class ResourceConsultationError(ValueError):
    """Base error for unavailable resource consultation mutations."""


class UnknownConsultationResourceError(ResourceConsultationError):
    """Raised for an unknown or cross-case resource identifier."""


class PlayerOnlyResourceError(ResourceConsultationError):
    """Raised when a human-mediated image is requested as agent knowledge."""


class ConsultationClosedError(ResourceConsultationError):
    """Raised when a completed session rejects a consultation mutation."""


class ConsultationConflictError(ResourceConsultationError):
    """Raised when consultation is unavailable in the current lifecycle."""


def consult_case_resource(
    session: InvestigationSession,
    *,
    resource_id: str,
    case_catalog: CaseCatalog,
    resource_text_catalog: ResourceTextCatalog,
) -> InvestigationSession:
    """Record one explicit consultation without copying text into session state."""
    snapshot = InvestigationSession.model_validate(session.model_dump(mode="python"))
    if snapshot.status is InvestigationStatus.COMPLETED:
        raise ConsultationClosedError("completed investigations reject resource consultation")
    if (
        snapshot.status is not InvestigationStatus.ACTIVE
        or snapshot.conclusion is not None
        or (snapshot.case_state is not None and snapshot.case_state.outcome is not None)
    ):
        raise ConsultationConflictError("resource consultation requires an active investigation before conclusion")
    try:
        case_resources = {resource.resource_id for resource in case_catalog.resources_for_case(snapshot.case_id)}
    except KeyError as error:
        raise UnknownConsultationResourceError(str(error)) from error
    if resource_id not in case_resources:
        raise UnknownConsultationResourceError("resource is unknown or belongs to another case")
    try:
        definition = resource_text_catalog.get(snapshot.case_id, resource_id)
    except (LookupError, ValueError) as error:
        raise UnknownConsultationResourceError(str(error)) from error
    if not definition.agent_readable:
        raise PlayerOnlyResourceError("player-only images cannot be consulted by agents")
    if any(item.resource_id == resource_id for item in snapshot.resource_consultations):
        return snapshot
    consultation = ResourceConsultation(
        session_id=snapshot.session_id,
        resource_id=resource_id,
        consultation_index=len(snapshot.resource_consultations),
    )
    return InvestigationSession.model_validate({
        **snapshot.model_dump(mode="python"),
        "resource_consultations": (*snapshot.resource_consultations, consultation),
    })


def render_consulted_resource_context(session: InvestigationSession, *, resource_text_catalog: ResourceTextCatalog) -> str:
    """Resolve only explicitly retained IDs through same-case public definitions."""
    blocks = []
    for consultation in session.resource_consultations:
        definition = resource_text_catalog.get(session.case_id, consultation.resource_id)
        if not definition.agent_readable:
            raise PlayerOnlyResourceError("session references a player-only resource")
        blocks.append(f"[{definition.resource_id}]\n{definition.render()}")
    return "\n\n".join(blocks) or "None."


def resolved_resource_context(
    session: InvestigationSession,
    resource_text_catalog: ResourceTextCatalog | None,
) -> str:
    """Require the validating catalogue whenever consultation state exists."""
    if resource_text_catalog is None:
        if session.resource_consultations:
            raise ResourceConsultationError("consulted resources require a resource-text catalogue")
        return "None."
    return render_consulted_resource_context(session, resource_text_catalog=resource_text_catalog)
