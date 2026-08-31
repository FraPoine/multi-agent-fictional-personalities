"""Server-side presentation models for the Lead/Visit investigation UI."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from multi_agent_personalities.pipeline import CharacterConfig
from multi_agent_personalities.web.investigation_store import InvestigationSessionRecord

DEMO_CASE_TITLE = "The Local Demonstration Case"


def _initials(display_name: str) -> str:
    words = display_name.split()
    if not words:
        return "?"
    return "".join(word[0].upper() for word in (words[0], words[-1]))


@dataclass(frozen=True)
class InvestigationParticipantPresentation:
    slug: str
    display_name: str
    description: str
    initials: str
    selected: bool
    supported: bool


@dataclass(frozen=True)
class InvestigationResourcePresentation:
    label: str
    description: str
    available: bool


@dataclass(frozen=True)
class InvestigationSessionPresentation:
    session_id: str
    case_title: str
    introduction: str
    status: str
    participants: tuple[InvestigationParticipantPresentation, ...]
    lead_count: int
    visit_count: int
    is_case_opening: bool
    resources: tuple[InvestigationResourcePresentation, ...]


def catalogue_participants(
    catalogue: Mapping[str, CharacterConfig],
    *,
    supported_character_ids: Sequence[str],
    selected_slugs: Sequence[str],
) -> tuple[InvestigationParticipantPresentation, ...]:
    """Present every catalogue entry without making fixture support a rule."""
    supported = set(supported_character_ids)
    selected = set(selected_slugs)
    return tuple(
        InvestigationParticipantPresentation(
            slug=config.slug,
            display_name=config.display_name,
            description=config.description,
            initials=_initials(config.display_name),
            selected=config.slug in selected,
            supported=config.character_id in supported,
        )
        for config in catalogue.values()
    )


def present_session(record: InvestigationSessionRecord) -> InvestigationSessionPresentation:
    """Project an immutable Lead/Visit snapshot for the web shell."""
    participants = tuple(
        InvestigationParticipantPresentation(
            slug=config.slug,
            display_name=config.display_name,
            description=config.description,
            initials=_initials(config.display_name),
            selected=True,
            supported=True,
        )
        for config in record.runtime.character_configs
    )
    session = record.session
    return InvestigationSessionPresentation(
        session_id=session.session_id,
        case_title=DEMO_CASE_TITLE,
        introduction=session.case_introduction,
        status=session.status.value.replace("_", " ").title(),
        participants=participants,
        lead_count=len(session.leads),
        visit_count=len(session.visits),
        is_case_opening=not session.visits,
        resources=(
            InvestigationResourcePresentation("Case notes", "Review retained case information.", False),
            InvestigationResourcePresentation("Rules", "Read the local investigation guide.", True),
        ),
    )
