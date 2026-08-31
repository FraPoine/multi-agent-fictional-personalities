"""Immutable building blocks for revealed investigation information."""

from collections.abc import Sequence
from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)

from multi_agent_personalities.models.conversation import ConversationRun


NonEmptyStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, strict=True),
]
NonNegativeStrictInt = Annotated[int, Field(strict=True, ge=0)]
PositiveStrictInt = Annotated[int, Field(strict=True, ge=1)]


class EvidenceRelation(str, Enum):
    """Allowed relationships between future reasoning and a revealed clue."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXT = "context"


class HypothesisStatus(str, Enum):
    """Lifecycle states for immutable hypothesis records."""

    ACTIVE = "active"
    DISCARDED = "discarded"


class GroupDecisionType(str, Enum):
    """Explicit actions that an investigation group may adopt."""

    PURSUE_LEAD = "pursue_lead"
    ADOPT_HYPOTHESIS = "adopt_hypothesis"
    DISCARD_HYPOTHESIS = "discard_hypothesis"
    REQUEST_INFORMATION = "request_information"


class InvestigationStatus(str, Enum):
    """Explicit lifecycle labels for investigation session snapshots."""

    SETUP = "setup"
    ACTIVE = "active"
    READY_FOR_FINAL = "ready_for_final"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class InvestigationRoundStatus(str, Enum):
    """Lifecycle states for one investigation clue-revelation cycle."""

    AWAITING_ANALYSES = "awaiting_analyses"
    AWAITING_DISCUSSION = "awaiting_discussion"
    AWAITING_DECISION = "awaiting_decision"
    COMPLETED = "completed"


class Clue(BaseModel):
    """Legacy round-workflow record for revealed information."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    clue_id: NonEmptyStr
    text: StrictStr
    reveal_order: NonNegativeStrictInt

    @field_validator("text")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        """Reject blank clue text while preserving its original form."""
        if not value.strip():
            raise ValueError("clue text must not be empty")
        return value


class EvidenceReference(BaseModel):
    """A stable reference to revealed information or a transitional clue."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    information_id: NonEmptyStr | None = None
    clue_id: NonEmptyStr | None = None
    relation: EvidenceRelation

    @model_validator(mode="after")
    def validate_exactly_one_target(self) -> "EvidenceReference":
        if (self.information_id is None) == (self.clue_id is None):
            raise ValueError(
                "evidence requires exactly one information_id or legacy clue_id"
            )
        return self

    @property
    def target_id(self) -> str:
        """Return the canonical referenced identifier."""
        return self.information_id or self.clue_id  # type: ignore[return-value]


class InvestigationLead(BaseModel):
    """A persistent semantic investigative track within one session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lead_id: NonEmptyStr
    session_id: NonEmptyStr
    label: NonEmptyStr
    kind: NonEmptyStr


class LeadVisit(BaseModel):
    """One chronological period of focus on an existing lead."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    visit_id: NonEmptyStr
    session_id: NonEmptyStr
    lead_id: NonEmptyStr
    visit_index: PositiveStrictInt
    revealed_information_ids: tuple[NonEmptyStr, ...] = ()
    conversation_run_ids: tuple[NonEmptyStr, ...] = ()

    @field_validator("revealed_information_ids", "conversation_run_ids")
    @classmethod
    def validate_unique_references(
        cls, value: tuple[str, ...], info: ValidationInfo
    ) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError(f"{info.field_name} must not contain duplicates")
        return value


class RevealedInformation(BaseModel):
    """Information explicitly disclosed and thereafter globally known."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    information_id: NonEmptyStr
    session_id: NonEmptyStr
    text: StrictStr
    reveal_index: NonNegativeStrictInt
    lead_id: NonEmptyStr | None = None
    visit_id: NonEmptyStr | None = None
    source_kind: NonEmptyStr | None = None
    source_id: NonEmptyStr | None = None

    @field_validator("text")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("revealed information text must not be empty")
        return value

    @model_validator(mode="after")
    def validate_source_pair(self) -> "RevealedInformation":
        if (self.source_kind is None) != (self.source_id is None):
            raise ValueError("source_kind and source_id must be supplied together")
        return self


def _reject_duplicate_strings(
    values: tuple[str, ...],
    field_name: str,
) -> tuple[str, ...]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must not contain duplicates")
    return values


def _reject_duplicate_evidence(
    values: tuple[EvidenceReference, ...],
) -> tuple[EvidenceReference, ...]:
    keys = [(item.target_id, item.relation) for item in values]
    if len(keys) != len(set(keys)):
        raise ValueError("evidence must not contain duplicate references")
    return values


class AgentAnalysis(BaseModel):
    """One agent's facts, deductions, evidence, and suggested leads."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_id: NonEmptyStr
    session_id: NonEmptyStr
    round_id: NonEmptyStr
    agent_id: NonEmptyStr
    visible_clue_ids: tuple[NonEmptyStr, ...]
    facts: tuple[NonEmptyStr, ...] = ()
    deductions: tuple[NonEmptyStr, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()
    proposed_leads: tuple[NonEmptyStr, ...] = ()

    @field_validator(
        "visible_clue_ids", "facts", "deductions", "proposed_leads"
    )
    @classmethod
    def validate_unique_text_entries(
        cls,
        value: tuple[str, ...],
        info: ValidationInfo,
    ) -> tuple[str, ...]:
        """Reject repeated entries while retaining their supplied order."""
        return _reject_duplicate_strings(value, info.field_name)

    @field_validator("evidence")
    @classmethod
    def validate_unique_evidence(
        cls,
        value: tuple[EvidenceReference, ...],
    ) -> tuple[EvidenceReference, ...]:
        return _reject_duplicate_evidence(value)

    @model_validator(mode="after")
    def validate_reasoning_content(self) -> "AgentAnalysis":
        """Require an observation, deduction, or proposed next step."""
        if not (self.facts or self.deductions or self.proposed_leads):
            raise ValueError(
                "analysis requires at least one fact, deduction, or proposed lead"
            )
        return self


class Hypothesis(BaseModel):
    """An immutable hypothesis, optionally revising an earlier record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hypothesis_id: NonEmptyStr
    session_id: NonEmptyStr
    round_id: NonEmptyStr
    statement: StrictStr
    status: HypothesisStatus
    evidence: tuple[EvidenceReference, ...] = ()
    previous_hypothesis_id: NonEmptyStr | None = None

    @field_validator("statement")
    @classmethod
    def validate_statement(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("hypothesis statement must not be empty")
        return value

    @field_validator("evidence")
    @classmethod
    def validate_unique_evidence(
        cls,
        value: tuple[EvidenceReference, ...],
    ) -> tuple[EvidenceReference, ...]:
        return _reject_duplicate_evidence(value)

    @model_validator(mode="after")
    def validate_revision_reference(self) -> "Hypothesis":
        if self.previous_hypothesis_id == self.hypothesis_id:
            raise ValueError("a hypothesis cannot reference itself as previous")
        return self


class GroupDecision(BaseModel):
    """A decision explicitly adopted by the investigation group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: NonEmptyStr
    session_id: NonEmptyStr
    round_id: NonEmptyStr
    decision_type: GroupDecisionType
    summary: StrictStr
    analysis_ids: tuple[NonEmptyStr, ...] = ()
    hypothesis_ids: tuple[NonEmptyStr, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("group decision summary must not be empty")
        return value

    @field_validator("analysis_ids", "hypothesis_ids")
    @classmethod
    def validate_unique_ids(
        cls,
        value: tuple[str, ...],
        info: ValidationInfo,
    ) -> tuple[str, ...]:
        return _reject_duplicate_strings(value, info.field_name)

    @field_validator("evidence")
    @classmethod
    def validate_unique_evidence(
        cls,
        value: tuple[EvidenceReference, ...],
    ) -> tuple[EvidenceReference, ...]:
        return _reject_duplicate_evidence(value)


class FinalTheory(BaseModel):
    """The group's immutable concluding theory, expressed through references."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    final_theory_id: NonEmptyStr
    summary: StrictStr
    hypothesis_ids: tuple[NonEmptyStr, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("final theory summary must not be empty")
        return value

    @field_validator("hypothesis_ids")
    @classmethod
    def validate_unique_hypothesis_ids(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _reject_duplicate_strings(value, "hypothesis_ids")

    @field_validator("evidence")
    @classmethod
    def validate_unique_evidence(
        cls,
        value: tuple[EvidenceReference, ...],
    ) -> tuple[EvidenceReference, ...]:
        return _reject_duplicate_evidence(value)


class InvestigationRound(BaseModel):
    """Immutable structural record for one investigation cycle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: NonEmptyStr
    round_id: NonEmptyStr
    round_index: PositiveStrictInt
    revealed_clue_id: NonEmptyStr
    visible_clue_ids: tuple[NonEmptyStr, ...]
    analysis_ids: tuple[NonEmptyStr, ...] = ()
    discussion_run: ConversationRun | None = None
    decision_id: NonEmptyStr | None = None
    status: InvestigationRoundStatus

    @field_validator("analysis_ids")
    @classmethod
    def validate_unique_analysis_ids(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _reject_duplicate_strings(value, "analysis_ids")


class InvestigationSession(BaseModel):
    """Validated immutable aggregate for one investigation snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: NonEmptyStr
    case_introduction: StrictStr
    participant_ids: tuple[NonEmptyStr, ...] = Field(min_length=2)
    status: InvestigationStatus
    leads: tuple[InvestigationLead, ...] = ()
    visits: tuple[LeadVisit, ...] = ()
    revealed_information: tuple[RevealedInformation, ...] = ()
    clues: tuple[Clue, ...] = ()
    rounds: tuple[InvestigationRound, ...] = ()
    analyses: tuple[AgentAnalysis, ...] = ()
    hypotheses: tuple[Hypothesis, ...] = ()
    decisions: tuple[GroupDecision, ...] = ()
    final_theory: FinalTheory | None = None

    @field_validator("case_introduction")
    @classmethod
    def validate_case_introduction(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("case introduction must not be empty")
        return value

    @field_validator("participant_ids")
    @classmethod
    def validate_unique_participants(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _reject_duplicate_strings(value, "participant_ids")

    def _validate_hypotheses(
        self,
        *,
        clue_ids: set[str],
        round_by_id: dict[str, InvestigationRound],
    ) -> dict[str, int]:
        hypothesis_positions = {
            item.hypothesis_id: index
            for index, item in enumerate(self.hypotheses)
        }
        for index, hypothesis in enumerate(self.hypotheses):
            if hypothesis.session_id != self.session_id:
                raise ValueError(
                    f"hypothesis {hypothesis.hypothesis_id!r} belongs to "
                    "another session"
                )
            if hypothesis.round_id not in round_by_id:
                raise ValueError(
                    f"hypothesis {hypothesis.hypothesis_id!r} references an "
                    "unknown round"
                )

            owning_round = round_by_id[hypothesis.round_id]
            for reference in hypothesis.evidence:
                if (
                    reference.clue_id is not None
                    and reference.clue_id not in clue_ids
                ):
                    raise ValueError(
                        f"hypothesis {hypothesis.hypothesis_id!r} references "
                        "an unknown clue"
                    )
                if (
                    reference.clue_id is not None
                    and reference.clue_id not in owning_round.visible_clue_ids
                ):
                    raise ValueError(
                        f"hypothesis {hypothesis.hypothesis_id!r} references "
                        "a clue outside its round visibility snapshot"
                    )

            previous_id = hypothesis.previous_hypothesis_id
            if previous_id is None:
                continue
            if previous_id not in hypothesis_positions:
                raise ValueError("previous hypothesis must exist in the session")
            previous_position = hypothesis_positions[previous_id]
            if previous_position >= index:
                raise ValueError("previous hypothesis must appear earlier")
            previous = self.hypotheses[previous_position]
            if previous.session_id != hypothesis.session_id:
                raise ValueError(
                    "previous hypothesis must belong to the same session"
                )
            if (
                round_by_id[previous.round_id].round_index
                > owning_round.round_index
            ):
                raise ValueError(
                    "previous hypothesis must not belong to a later round"
                )
        return hypothesis_positions

    def _validate_decisions(
        self,
        *,
        clue_ids: set[str],
        round_by_id: dict[str, InvestigationRound],
        analysis_by_id: dict[str, AgentAnalysis],
        hypothesis_positions: dict[str, int],
    ) -> None:
        decision_by_id = {
            item.decision_id: item for item in self.decisions
        }
        decision_round_ids: set[str] = set()
        for decision in self.decisions:
            if decision.session_id != self.session_id:
                raise ValueError(
                    f"decision {decision.decision_id!r} belongs to another session"
                )
            if decision.round_id not in round_by_id:
                raise ValueError(
                    f"decision {decision.decision_id!r} references an unknown round"
                )
            if decision.round_id in decision_round_ids:
                raise ValueError("each round may have at most one group decision")
            decision_round_ids.add(decision.round_id)

            owning_round = round_by_id[decision.round_id]
            for analysis_id in decision.analysis_ids:
                if analysis_id not in analysis_by_id:
                    raise ValueError("decision references an unknown analysis")
                analysis = analysis_by_id[analysis_id]
                if analysis.round_id != decision.round_id:
                    raise ValueError(
                        "decision analyses must belong to the decision round"
                    )
                if analysis_id not in owning_round.analysis_ids:
                    raise ValueError(
                        "decision analysis must be listed by the owning round"
                    )

            for hypothesis_id in decision.hypothesis_ids:
                if hypothesis_id not in hypothesis_positions:
                    raise ValueError("decision references an unknown hypothesis")
                hypothesis = self.hypotheses[
                    hypothesis_positions[hypothesis_id]
                ]
                hypothesis_round = round_by_id[hypothesis.round_id]
                if hypothesis_round.round_index > owning_round.round_index:
                    raise ValueError(
                        "decision must not reference a future-round hypothesis"
                    )

            for reference in decision.evidence:
                if (
                    reference.clue_id is not None
                    and reference.clue_id not in clue_ids
                ):
                    raise ValueError(
                        f"decision {decision.decision_id!r} references an "
                        "unknown clue"
                    )
                if (
                    reference.clue_id is not None
                    and reference.clue_id not in owning_round.visible_clue_ids
                ):
                    raise ValueError(
                        f"decision {decision.decision_id!r} references a clue "
                        "outside its round visibility snapshot"
                    )

        for investigation_round in self.rounds:
            decision_id = investigation_round.decision_id
            if investigation_round.status is InvestigationRoundStatus.COMPLETED:
                if decision_id is None:
                    raise ValueError("completed rounds require a group decision")
            elif decision_id is not None:
                raise ValueError(
                    "non-completed rounds must not reference a group decision"
                )

            if decision_id is not None:
                if decision_id not in decision_by_id:
                    raise ValueError("round references an unknown decision")
                if (
                    decision_by_id[decision_id].round_id
                    != investigation_round.round_id
                ):
                    raise ValueError(
                        "round references a decision belonging to another round"
                    )

        for decision in self.decisions:
            if (
                round_by_id[decision.round_id].decision_id
                != decision.decision_id
            ):
                raise ValueError(
                    f"decision {decision.decision_id!r} must be referenced by "
                    "its owning round"
                )

    @model_validator(mode="after")
    def validate_investigation_graph(self) -> "InvestigationSession":
        """Validate ordering and references across the aggregate snapshot."""
        collection_ids = (
            ("lead_id", [item.lead_id for item in self.leads]),
            ("visit_id", [item.visit_id for item in self.visits]),
            (
                "information_id",
                [item.information_id for item in self.revealed_information],
            ),
            ("clue_id", [clue.clue_id for clue in self.clues]),
            ("round_id", [item.round_id for item in self.rounds]),
            ("analysis_id", [item.analysis_id for item in self.analyses]),
            ("hypothesis_id", [item.hypothesis_id for item in self.hypotheses]),
            ("decision_id", [item.decision_id for item in self.decisions]),
        )
        for field_name, values in collection_ids:
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} values must be unique")

        if any(item.session_id != self.session_id for item in self.leads):
            raise ValueError("all leads must belong to the investigation session")
        lead_by_id = {item.lead_id: item for item in self.leads}

        visit_indexes = [item.visit_index for item in self.visits]
        if visit_indexes != list(range(1, len(self.visits) + 1)):
            raise ValueError(
                "visits must be ordered contiguously by visit_index from one"
            )
        visit_by_id = {item.visit_id: item for item in self.visits}
        for visit in self.visits:
            if visit.session_id != self.session_id:
                raise ValueError("all visits must belong to the investigation session")
            if visit.lead_id not in lead_by_id:
                raise ValueError(f"visit {visit.visit_id!r} references an unknown lead")

        reveal_indexes = [
            item.reveal_index for item in self.revealed_information
        ]
        if reveal_indexes != list(range(len(self.revealed_information))):
            raise ValueError(
                "revealed information must be ordered contiguously by "
                "reveal_index from zero"
            )
        information_by_id = {
            item.information_id: item for item in self.revealed_information
        }
        for item in self.revealed_information:
            if item.session_id != self.session_id:
                raise ValueError(
                    "all revealed information must belong to the investigation session"
                )
            if item.lead_id is not None and item.lead_id not in lead_by_id:
                raise ValueError(
                    f"revealed information {item.information_id!r} references "
                    "an unknown lead"
                )
            if item.visit_id is not None:
                if item.visit_id not in visit_by_id:
                    raise ValueError(
                        f"revealed information {item.information_id!r} references "
                        "an unknown visit"
                    )
                visit = visit_by_id[item.visit_id]
                if item.lead_id is not None and item.lead_id != visit.lead_id:
                    raise ValueError(
                        f"revealed information {item.information_id!r} lead_id "
                        "does not match its visit lead"
                    )

        listed_information_ids: list[str] = []
        conversation_run_ids: list[str] = []
        for visit in self.visits:
            conversation_run_ids.extend(visit.conversation_run_ids)
            for information_id in visit.revealed_information_ids:
                if information_id not in information_by_id:
                    raise ValueError(
                        f"visit {visit.visit_id!r} references unknown revealed information"
                    )
                information = information_by_id[information_id]
                if information.visit_id != visit.visit_id:
                    raise ValueError(
                        "visit revealed_information_ids must match information visit_id"
                    )
                listed_information_ids.append(information_id)
        if len(listed_information_ids) != len(set(listed_information_ids)):
            raise ValueError("revealed information may be listed by only one visit")
        if len(conversation_run_ids) != len(set(conversation_run_ids)):
            raise ValueError("conversation_run_ids must be unique across visits")
        for information in self.revealed_information:
            if (
                information.visit_id is not None
                and information.information_id not in listed_information_ids
            ):
                raise ValueError(
                    "visit-linked revealed information must be listed by its visit"
                )

        reveal_orders = [clue.reveal_order for clue in self.clues]
        if reveal_orders != list(range(len(self.clues))):
            raise ValueError(
                "clues must be ordered contiguously by reveal_order from zero"
            )

        round_indexes = [item.round_index for item in self.rounds]
        if len(round_indexes) != len(set(round_indexes)):
            raise ValueError("round_index values must be unique")
        if round_indexes != list(range(1, len(self.rounds) + 1)):
            raise ValueError(
                "rounds must be ordered contiguously by round_index from one"
            )
        if any(item.session_id != self.session_id for item in self.rounds):
            raise ValueError(
                "all rounds must belong to the investigation session"
            )
        if len(self.rounds) > len(self.clues):
            raise ValueError("round history must not contain more rounds than clues")
        for position, investigation_round in enumerate(self.rounds):
            expected_clue_id = self.clues[position].clue_id
            expected_visible_clue_ids = tuple(
                clue.clue_id for clue in self.clues[: position + 1]
            )
            if investigation_round.revealed_clue_id != expected_clue_id:
                raise ValueError(
                    "round history revealed_clue_id must match its clue position"
                )
            if investigation_round.visible_clue_ids != expected_visible_clue_ids:
                raise ValueError(
                    "round history visibility must exactly match its clue prefix"
                )

        clue_ids = {clue.clue_id for clue in self.clues}
        participant_ids = set(self.participant_ids)
        round_by_id = {item.round_id: item for item in self.rounds}
        analysis_by_id = {item.analysis_id: item for item in self.analyses}
        analysis_owners: set[tuple[str, str]] = set()
        for analysis in self.analyses:
            if analysis.session_id != self.session_id:
                raise ValueError(
                    f"analysis {analysis.analysis_id!r} belongs to another session"
                )
            if analysis.agent_id not in participant_ids:
                raise ValueError(
                    f"analysis {analysis.analysis_id!r} must belong to a "
                    "session participants collection"
                )
            if analysis.round_id not in round_by_id:
                raise ValueError(
                    f"analysis {analysis.analysis_id!r} references an unknown round"
                )

            investigation_round = round_by_id[analysis.round_id]
            if analysis.visible_clue_ids != investigation_round.visible_clue_ids:
                raise ValueError(
                    f"analysis {analysis.analysis_id!r} visibility snapshot must "
                    "exactly match its round"
                )

            owner = (analysis.round_id, analysis.agent_id)
            if owner in analysis_owners:
                raise ValueError(
                    "each agent may have at most one analysis per round"
                )
            analysis_owners.add(owner)

            for reference in analysis.evidence:
                if (
                    reference.clue_id is not None
                    and reference.clue_id not in clue_ids
                ):
                    raise ValueError(
                        f"analysis {analysis.analysis_id!r} references an "
                        "unknown clue"
                    )
                if (
                    reference.clue_id is not None
                    and reference.clue_id not in analysis.visible_clue_ids
                ):
                    raise ValueError(
                        f"analysis {analysis.analysis_id!r} references a clue "
                        "outside its visibility snapshot"
                    )

        for investigation_round in self.rounds:
            for analysis_id in investigation_round.analysis_ids:
                if analysis_id not in analysis_by_id:
                    raise ValueError(
                        f"round {investigation_round.round_id!r} references an "
                        "unknown analysis"
                    )
                if (
                    analysis_by_id[analysis_id].round_id
                    != investigation_round.round_id
                ):
                    raise ValueError(
                        f"round {investigation_round.round_id!r} lists an analysis "
                        "belonging to another round"
                    )

        hypothesis_positions = self._validate_hypotheses(
            clue_ids=clue_ids,
            round_by_id=round_by_id,
        )
        self._validate_decisions(
            clue_ids=clue_ids,
            round_by_id=round_by_id,
            analysis_by_id=analysis_by_id,
            hypothesis_positions=hypothesis_positions,
        )

        for investigation_round in self.rounds:
            expected_analysis_ids = tuple(
                item.analysis_id
                for item in self.analyses
                if item.round_id == investigation_round.round_id
            )
            if investigation_round.analysis_ids != expected_analysis_ids:
                raise ValueError(
                    f"round {investigation_round.round_id!r} analysis_ids must "
                    "match session analysis order"
                )

            round_analyses = tuple(
                item
                for item in self.analyses
                if item.round_id == investigation_round.round_id
            )
            complete_analyses = (
                tuple(item.agent_id for item in round_analyses)
                == self.participant_ids
            )
            discussion = investigation_round.discussion_run
            complete_discussion = (
                discussion is not None
                and discussion.status == "completed"
                and discussion.character_ids == self.participant_ids
            )

            if investigation_round.status is InvestigationRoundStatus.AWAITING_ANALYSES:
                if round_analyses or investigation_round.analysis_ids:
                    raise ValueError("rounds awaiting analyses must not contain analyses")
                if discussion is not None:
                    raise ValueError("rounds awaiting analyses must not contain a discussion")
                if investigation_round.decision_id is not None:
                    raise ValueError("rounds awaiting analyses must not contain a decision")
            elif investigation_round.status is InvestigationRoundStatus.AWAITING_DISCUSSION:
                if not complete_analyses:
                    raise ValueError(
                        "rounds awaiting discussion require one ordered analysis per participant"
                    )
                if discussion is not None:
                    raise ValueError("rounds awaiting discussion must not contain a discussion")
                if investigation_round.decision_id is not None:
                    raise ValueError("rounds awaiting discussion must not contain a decision")
            elif investigation_round.status is InvestigationRoundStatus.AWAITING_DECISION:
                if not complete_analyses:
                    raise ValueError(
                        "rounds awaiting decision require one ordered analysis per participant"
                    )
                if not complete_discussion:
                    raise ValueError(
                        "rounds awaiting decision require a completed discussion with exact participants"
                    )
                if investigation_round.decision_id is not None:
                    raise ValueError("rounds awaiting decision must not contain a decision")
            elif investigation_round.status is InvestigationRoundStatus.COMPLETED:
                if not complete_analyses:
                    raise ValueError(
                        "completed rounds require one ordered analysis per participant"
                    )
                if not complete_discussion:
                    raise ValueError(
                        "completed rounds require a completed discussion with exact participants"
                    )

        discussion_run_ids = [
            item.discussion_run.run_id
            for item in self.rounds
            if item.discussion_run is not None
        ]
        if len(discussion_run_ids) != len(set(discussion_run_ids)):
            raise ValueError("discussion run_id values must be unique across rounds")

        evidence_groups = []
        evidence_groups.extend(item.evidence for item in self.analyses)
        evidence_groups.extend(item.evidence for item in self.hypotheses)
        evidence_groups.extend(item.evidence for item in self.decisions)
        if self.final_theory is not None:
            evidence_groups.append(self.final_theory.evidence)
        if any(
            reference.information_id is not None
            and reference.information_id not in information_by_id
            for evidence in evidence_groups
            for reference in evidence
        ):
            raise ValueError(
                "all information evidence must reference revealed information "
                "in the session"
            )
        if any(
            reference.clue_id is not None and reference.clue_id not in clue_ids
            for evidence in evidence_groups
            for reference in evidence
        ):
            raise ValueError("all evidence must reference session clues")

        hypothesis_ids = set(hypothesis_positions)
        if self.final_theory is not None and any(
            item not in hypothesis_ids
            for item in self.final_theory.hypothesis_ids
        ):
            raise ValueError("final theory references an unknown hypothesis")

        if (
            self.status is InvestigationStatus.COMPLETED
            and self.final_theory is None
        ):
            raise ValueError("completed sessions require a final theory")
        if (
            self.final_theory is not None
            and self.status is not InvestigationStatus.COMPLETED
        ):
            raise ValueError("non-completed sessions must not contain a final theory")
        return self


def validate_unique_clue_ids(clues: Sequence[Clue]) -> tuple[Clue, ...]:
    """Return clues in input order after rejecting duplicate identifiers."""
    validated = tuple(clues)
    clue_ids = [clue.clue_id for clue in validated]
    if len(clue_ids) != len(set(clue_ids)):
        raise ValueError("clue_id values must be unique")
    return validated
