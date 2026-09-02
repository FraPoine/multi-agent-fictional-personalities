"""Strict public/private catalogues for spoiler-safe case conclusions."""

from pathlib import Path
from typing import Annotated, Literal
import re

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, model_validator


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]
Key = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$", strict=True)]


class PublicQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    question_id: Key
    order: int = Field(strict=True, ge=1)
    series: int | None = Field(default=None, strict=True, ge=1)
    texts: dict[Literal["en"], NonEmptyStr]


class PublicConclusionDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1]
    case_id: Key
    conclusion_mode: Literal["official_questions", "authored_outcome"]
    questions: tuple[PublicQuestion, ...]

    @model_validator(mode="after")
    def validate_questions(self) -> "PublicConclusionDefinition":
        ids = [x.question_id for x in self.questions]
        if len(ids) != len(set(ids)): raise ValueError("duplicate question_id")
        if [x.order for x in self.questions] != list(range(1, len(self.questions) + 1)): raise ValueError("question order must be contiguous")
        if self.conclusion_mode == "official_questions" and not self.questions: raise ValueError("official conclusion requires questions")
        if self.conclusion_mode == "authored_outcome" and self.questions: raise ValueError("authored outcome cannot declare questions")
        return self


class PublicConclusionCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    cases: tuple[PublicConclusionDefinition, ...]

    @model_validator(mode="after")
    def unique_cases(self) -> "PublicConclusionCatalog":
        ids = [x.case_id for x in self.cases]
        if len(ids) != len(set(ids)): raise ValueError("duplicate conclusion case_id")
        return self

    def get(self, case_id: str) -> PublicConclusionDefinition | None:
        return next((x for x in self.cases if x.case_id == case_id), None)


class PrivateSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document: NonEmptyStr
    page: int = Field(strict=True, ge=1)
    region: NonEmptyStr


class OfficialAnswerElement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    element_id: Key
    question_id: Key
    answer_texts: dict[Literal["en"], NonEmptyStr]
    points: int = Field(strict=True, ge=0)


class LeadPenaltyRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    after_lead: int = Field(strict=True, ge=0)
    points_per_additional_lead: int = Field(strict=True, le=0)
    revisits_excluded: bool = False


class ScoreBand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    minimum: int | None = Field(default=None, strict=True)
    maximum: int | None = Field(default=None, strict=True)
    texts: dict[Literal["en"], NonEmptyStr]


class PrivateScoringDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1]
    case_id: Key
    printed_rule_texts: dict[Literal["en"], NonEmptyStr]
    holmes_lead_count: int = Field(strict=True, ge=0)
    printed_holmes_score: int = Field(strict=True)
    answer_elements: tuple[OfficialAnswerElement, ...]
    lead_penalty: LeadPenaltyRule
    score_bands: tuple[ScoreBand, ...] = ()
    needs_review: bool
    review_note: NonEmptyStr | None = None
    source: PrivateSource

    @model_validator(mode="after")
    def validate_elements(self) -> "PrivateScoringDefinition":
        ids = [x.element_id for x in self.answer_elements]
        if len(ids) != len(set(ids)): raise ValueError("duplicate answer element_id")
        if self.needs_review != (self.review_note is not None): raise ValueError("review_note must accompany needs_review")
        return self


class PrivateSolutionDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1]
    case_id: Key
    solution_texts: dict[Literal["en"], NonEmptyStr]
    holmes_route: tuple[NonEmptyStr, ...]
    source: PrivateSource


def default_public_conclusion_directory(project_root: Path) -> Path:
    return Path(project_root).resolve() / "configs" / "investigation" / "conclusions" / "public"


def default_private_scoring_directory(project_root: Path) -> Path:
    return Path(project_root).resolve() / "configs" / "investigation" / "conclusions" / "private" / "scoring"


def default_private_solution_directory(project_root: Path) -> Path:
    return Path(project_root).resolve() / "configs" / "investigation" / "conclusions" / "private" / "solutions"


def load_public_conclusion_catalog(directory: Path, case_catalog=None) -> PublicConclusionCatalog:
    """Eagerly load public questions without touching either private directory."""
    root = Path(directory).resolve()
    try:
        cases = tuple(PublicConclusionDefinition.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(root.glob("*.json")))
        catalog = PublicConclusionCatalog(cases=cases)
        if case_catalog is not None:
            known = {case.case_id for case in case_catalog.cases}
            unknown = [case.case_id for case in catalog.cases if case.case_id not in known]
            if unknown: raise ValueError(f"public conclusion references unknown case_id: {unknown[0]!r}")
        return catalog
    except (OSError, ValidationError) as error:
        raise ValueError(f"invalid public conclusion catalogue: {error}") from error


class PrivateScoringRepository:
    """Lazy repository: no private file is opened before ``load``."""
    def __init__(self, directory: Path) -> None: self.directory = Path(directory).resolve()
    def load(self, case_id: str) -> PrivateScoringDefinition:
        if not isinstance(case_id, str) or re.fullmatch(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", case_id) is None: raise ValueError("invalid private scoring case_id")
        path = self.directory / f"{case_id}.json"
        try: definition = PrivateScoringDefinition.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as error: raise ValueError(f"invalid private scoring definition for {case_id!r}: {error}") from error
        if definition.case_id != case_id: raise ValueError("private scoring cross-case mismatch")
        return definition


class PrivateSolutionRepository:
    """Separately lazy long-solution repository."""
    def __init__(self, directory: Path) -> None: self.directory = Path(directory).resolve()
    def load(self, case_id: str) -> PrivateSolutionDefinition:
        if not isinstance(case_id, str) or re.fullmatch(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", case_id) is None: raise ValueError("invalid private solution case_id")
        path = self.directory / f"{case_id}.json"
        try: definition = PrivateSolutionDefinition.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as error: raise ValueError(f"invalid private solution definition for {case_id!r}: {error}") from error
        if definition.case_id != case_id: raise ValueError("private solution cross-case mismatch")
        return definition
