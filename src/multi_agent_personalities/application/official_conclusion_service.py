"""Atomic, spoiler-safe application workflow for official case conclusions."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from multi_agent_personalities.conclusion_catalog import (
    PrivateScoringRepository, PrivateSolutionRepository, PublicConclusionDefinition,
)
from multi_agent_personalities.models import (
    ConclusionAnswer, ConclusionMode, ConclusionPhase, GenerationMetadata,
    GenerationResult, InvestigationConclusionState, InvestigationSession,
    InvestigationStatus, OfficialScoreResult, RevealedSolution,
)


class ConclusionConflictError(ValueError):
    """Raised when a conclusion action is unavailable in the current phase."""


class AnswerDraftProvider(Protocol):
    def generate(self, prompt: str, *, task_name: str) -> GenerationResult: ...


class DeterministicAnswerDraftProvider:
    """Offline answer provider keyed by public question ID."""
    def __init__(self, answers: Mapping[str, str]) -> None:
        self.answers = dict(answers); self.calls: list[tuple[str, str]] = []
    def generate(self, prompt: str, *, task_name: str) -> GenerationResult:
        self.calls.append((prompt, task_name))
        question_id = task_name.rsplit(".", 1)[-1]
        try: text = self.answers[question_id]
        except KeyError as error: raise ValueError(f"missing deterministic answer for {question_id!r}") from error
        return GenerationResult(text=text, metadata=GenerationMetadata(provider="mock"))


@dataclass(frozen=True)
class DraftGenerationResult:
    session: InvestigationSession
    prompts: tuple[str, ...]


def _snapshot(session: InvestigationSession) -> InvestigationSession:
    if not isinstance(session, InvestigationSession): raise ValueError("session must be validated")
    return InvestigationSession.model_validate(session.model_dump(mode="python"))


def _official(session: InvestigationSession, *phases: ConclusionPhase) -> InvestigationConclusionState:
    snapshot = _snapshot(session)
    if snapshot.status is not InvestigationStatus.READY_FOR_FINAL or snapshot.conclusion is None:
        raise ConclusionConflictError("official conclusion is not active")
    if phases and snapshot.conclusion.phase not in phases:
        raise ConclusionConflictError("official conclusion phase does not permit this action")
    return snapshot.conclusion


def _replace_conclusion(session: InvestigationSession, conclusion: InvestigationConclusionState, *, status: InvestigationStatus | None = None) -> InvestigationSession:
    payload = session.model_dump(mode="python"); payload["conclusion"] = conclusion
    if status is not None: payload["status"] = status
    return InvestigationSession.model_validate(payload)


def start_official_conclusion(session: InvestigationSession, *, public_definition: PublicConclusionDefinition) -> InvestigationSession:
    snapshot = _snapshot(session)
    if snapshot.status is not InvestigationStatus.ACTIVE or snapshot.final_theory is not None or snapshot.conclusion is not None:
        raise ConclusionConflictError("session cannot start an official conclusion")
    if snapshot.conclusion_mode is not ConclusionMode.OFFICIAL_QUESTIONS:
        raise ConclusionConflictError("session is not configured for official questions")
    if public_definition.case_id != snapshot.case_id or public_definition.conclusion_mode != "official_questions":
        raise ConclusionConflictError("public conclusion does not match this official-question case")
    conclusion = InvestigationConclusionState(mode=ConclusionMode.OFFICIAL_QUESTIONS, phase=ConclusionPhase.DRAFT, question_ids=tuple(x.question_id for x in public_definition.questions))
    return _replace_conclusion(snapshot, conclusion, status=InvestigationStatus.READY_FOR_FINAL)


def build_safe_answer_context(session: InvestigationSession, *, public_definition: PublicConclusionDefinition, safe_resource_context: Sequence[str] = ()) -> str:
    """Render only public and legitimately retained information."""
    if public_definition.case_id != session.case_id: raise ConclusionConflictError("public conclusion case mismatch")
    information = "\n".join(f"- {x.text}" for x in session.revealed_information) or "None."
    messages = "\n".join(f"- {m.speaker_name}: {m.text}" for run in session.conversation_runs for m in run.messages) or "None."
    questions = "\n".join(f"- [{q.question_id}] {q.texts['en']}" for q in public_definition.questions)
    resources = "\n".join(f"- {x}" for x in safe_resource_context) or "None."
    return f"Case opening:\n{session.case_introduction}\n\nRevealed information:\n{information}\n\nInvestigation conversations:\n{messages}\n\nPublic questions:\n{questions}\n\nConsulted resources:\n{resources}"


def generate_official_answer_drafts(session: InvestigationSession, *, public_definition: PublicConclusionDefinition, provider: AnswerDraftProvider, safe_resource_context: Sequence[str] = ()) -> DraftGenerationResult:
    snapshot = _snapshot(session); conclusion = _official(snapshot, ConclusionPhase.DRAFT)
    if conclusion.answers: raise ConclusionConflictError("answer drafts already exist")
    if public_definition.case_id != snapshot.case_id or tuple(x.question_id for x in public_definition.questions) != conclusion.question_ids:
        raise ConclusionConflictError("public questions do not match the session")
    base = build_safe_answer_context(snapshot, public_definition=public_definition, safe_resource_context=safe_resource_context)
    answers = []; prompts = []
    for question in public_definition.questions:
        prompt = f"{base}\n\nAnswer only this public question without inventing facts:\n[{question.question_id}] {question.texts['en']}"
        result = provider.generate(prompt, task_name=f"investigation.official_answer.{question.question_id}")
        answers.append(ConclusionAnswer(question_id=question.question_id, text=result.text)); prompts.append(prompt)
    updated = conclusion.model_copy(update={"answers": tuple(answers)})
    return DraftGenerationResult(_replace_conclusion(snapshot, InvestigationConclusionState.model_validate(updated.model_dump(mode="python"))), tuple(prompts))


def update_official_answer(session: InvestigationSession, *, question_id: str, text: str) -> InvestigationSession:
    snapshot = _snapshot(session); conclusion = _official(snapshot, ConclusionPhase.DRAFT)
    if question_id not in conclusion.question_ids: raise ConclusionConflictError("unknown public question")
    replacement = ConclusionAnswer(question_id=question_id, text=text)
    answers = tuple(replacement if x.question_id == question_id else x for x in conclusion.answers)
    if not any(x.question_id == question_id for x in conclusion.answers): answers = (*answers, replacement)
    ordered = tuple(next(x for x in answers if x.question_id == qid) for qid in conclusion.question_ids if any(x.question_id == qid for x in answers))
    return _replace_conclusion(snapshot, InvestigationConclusionState.model_validate({**conclusion.model_dump(mode="python"), "answers": ordered}))


def lock_official_answers(session: InvestigationSession) -> InvestigationSession:
    snapshot = _snapshot(session); conclusion = _official(snapshot, ConclusionPhase.DRAFT)
    if {x.question_id for x in conclusion.answers} != set(conclusion.question_ids) or len(conclusion.answers) != len(conclusion.question_ids):
        raise ConclusionConflictError("one complete answer per public question is required")
    locked = tuple(x.model_copy(update={"locked": True}) for x in conclusion.answers)
    updated = InvestigationConclusionState.model_validate({**conclusion.model_dump(mode="python"), "phase": ConclusionPhase.ANSWERS_LOCKED, "answers": locked})
    return _replace_conclusion(snapshot, updated)


def reveal_official_answer_elements(session: InvestigationSession, *, repository: PrivateScoringRepository) -> InvestigationSession:
    snapshot = _snapshot(session); conclusion = _official(snapshot, ConclusionPhase.ANSWERS_LOCKED)
    if conclusion.scoring_definition is not None: raise ConclusionConflictError("official answer elements already revealed")
    scoring = repository.load(snapshot.case_id)
    if scoring.case_id != snapshot.case_id or not {x.question_id for x in scoring.answer_elements} <= set(conclusion.question_ids):
        raise ConclusionConflictError("private scoring definition does not match the session")
    updated = InvestigationConclusionState.model_validate({**conclusion.model_dump(mode="python"), "answer_elements": scoring.answer_elements, "scoring_definition": scoring})
    return _replace_conclusion(snapshot, updated)


def confirm_official_score(session: InvestigationSession, *, awarded_elements: Mapping[str, Sequence[str]]) -> InvestigationSession:
    snapshot = _snapshot(session); conclusion = _official(snapshot, ConclusionPhase.ANSWERS_LOCKED)
    scoring = conclusion.scoring_definition
    if scoring is None: raise ConclusionConflictError("official answer elements have not been revealed")
    if set(awarded_elements) - set(conclusion.question_ids): raise ConclusionConflictError("unknown question in awarded elements")
    flat = [element_id for ids in awarded_elements.values() for element_id in ids]
    if len(flat) != len(set(flat)): raise ConclusionConflictError("awarded element IDs must be unique")
    by_id = {x.element_id: x for x in scoring.answer_elements}
    for question_id, ids in awarded_elements.items():
        for element_id in ids:
            if element_id not in by_id or by_id[element_id].question_id != question_id: raise ConclusionConflictError("unknown or cross-question answer element")
    answer_points = sum(by_id[x].points for x in flat)
    if scoring.lead_penalty.revisits_excluded:
        counted = len([x for x in snapshot.case_state.accounting_entries if x.source_kind == "first-visit"]) if snapshot.case_state else 0
    else:
        counted = sum(x.amount for x in snapshot.case_state.accounting_entries if x.source_kind in ("section-cost", "first-visit") and x.amount > 0) if snapshot.case_state else 0
    penalty = max(0, counted - scoring.lead_penalty.after_lead) * scoring.lead_penalty.points_per_additional_lead
    element_total = sum(x.points for x in scoring.answer_elements)
    result = OfficialScoreResult(awarded_element_ids=tuple(flat), answer_points=answer_points, counted_leads=counted, lead_penalty=penalty, total_score=answer_points + penalty, printed_holmes_score=scoring.printed_holmes_score, answer_element_total=element_total, provisional=scoring.needs_review, needs_review=scoring.needs_review, review_note=scoring.review_note)
    updated = InvestigationConclusionState.model_validate({**conclusion.model_dump(mode="python"), "phase": ConclusionPhase.SCORED, "score_result": result})
    return _replace_conclusion(snapshot, updated)


def reveal_official_solution(session: InvestigationSession, *, repository: PrivateSolutionRepository) -> InvestigationSession:
    snapshot = _snapshot(session); conclusion = _official(snapshot, ConclusionPhase.SCORED)
    solution = repository.load(snapshot.case_id)
    if solution.case_id != snapshot.case_id: raise ConclusionConflictError("private solution does not match the session")
    updated = InvestigationConclusionState.model_validate({**conclusion.model_dump(mode="python"), "phase": ConclusionPhase.SOLUTION_REVEALED, "revealed_solution": RevealedSolution(text=solution.solution_texts["en"])})
    return _replace_conclusion(snapshot, updated, status=InvestigationStatus.COMPLETED)
