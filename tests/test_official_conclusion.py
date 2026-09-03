"""Official conclusion lifecycle and structural spoiler-firewall tests."""

import json
from pathlib import Path

import pytest

from multi_agent_personalities.application import (
    ConclusionConflictError, DeterministicAnswerDraftProvider,
    DeterministicInvestigationIdFactory, build_safe_answer_context,
    confirm_official_score, create_session, generate_official_answer_drafts,
    lock_official_answers, reveal_official_answer_elements,
    reveal_official_solution, start_official_conclusion,
    update_official_answer, visit_lead,
)
from multi_agent_personalities.case_catalog import default_case_catalog_directory, load_case_catalog
from multi_agent_personalities.case_content_catalog import default_case_content_directory, load_case_content_catalog
from multi_agent_personalities.conclusion_catalog import (
    PrivateScoringRepository, PrivateSolutionRepository,
    default_private_scoring_directory, default_private_solution_directory,
    default_public_conclusion_directory, load_public_conclusion_catalog,
)
from multi_agent_personalities.models import (
    ConclusionMode, FinalTheory, InvestigationSession, InvestigationStatus,
    LeadAccountingEntry,
)

ROOT = Path(__file__).resolve().parents[1]
CASES = load_case_catalog(default_case_catalog_directory(ROOT))
CONTENT = load_case_content_catalog(default_case_content_directory(ROOT), CASES)
PUBLIC = load_public_conclusion_catalog(default_public_conclusion_directory(ROOT))
SCORING_DIR = default_private_scoring_directory(ROOT)
SOLUTION_DIR = default_private_solution_directory(ROOT)


def official_session(case_id: str, sequence: int = 1):
    case = CASES.get(case_id); content = CONTENT.get(case_id); factory = DeterministicInvestigationIdFactory(sequence)
    public = PUBLIC.get(case_id)
    session = create_session(id_factory=factory, introduction=case.opening, participant_ids=("sherlock_holmes", "hercule_poirot"), case_id=case_id, case_content=content, conclusion_mode=ConclusionMode(public.conclusion_mode) if public else ConclusionMode.GENERATED_FINAL_THEORY)
    return session, factory, public


def draft_answers(session, public, answers=None):
    started = start_official_conclusion(session, public_definition=public)
    provider = DeterministicAnswerDraftProvider(answers or {q.question_id: f"Draft for {q.question_id}" for q in public.questions})
    return generate_official_answer_drafts(started, public_definition=public, provider=provider), provider


def scored_session(case_id="demo-1-vanishing-from-hyde-park"):
    session, factory, public = official_session(case_id)
    drafts, _ = draft_answers(session, public)
    locked = lock_official_answers(drafts.session)
    unlocked = reveal_official_answer_elements(locked, repository=PrivateScoringRepository(SCORING_DIR))
    awards = {q.question_id: tuple(x.element_id for x in unlocked.conclusion.answer_elements if x.question_id == q.question_id) for q in public.questions}
    return confirm_official_score(unlocked, awarded_elements=awards), factory


def test_public_catalogue_loads_modes_and_never_opens_private_files(monkeypatch: pytest.MonkeyPatch) -> None:
    original = Path.read_text; opened = []
    def spy(path: Path, *args, **kwargs):
        opened.append(path); return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", spy)
    catalog = load_public_conclusion_catalog(default_public_conclusion_directory(ROOT))
    assert [(x.conclusion_mode, len(x.questions)) for x in catalog.cases] == [("official_questions", 4), ("official_questions", 4), ("authored_outcome", 0)]
    assert opened and all("/private/" not in str(path) for path in opened)


def test_public_and_private_models_are_strict_and_repositories_reject_traversal(tmp_path: Path) -> None:
    bad = tmp_path / "public"; bad.mkdir(); data = json.loads((default_public_conclusion_directory(ROOT) / "demo-1-vanishing-from-hyde-park.json").read_text()); data["unknown"] = True; (bad / "bad.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="extra_forbidden"): load_public_conclusion_catalog(bad)
    with pytest.raises(ValueError, match="case_id"): PrivateScoringRepository(SCORING_DIR).load("../../escape")
    with pytest.raises(ValueError, match="case_id"): PrivateSolutionRepository(SOLUTION_DIR).load("../escape")


def test_safe_context_and_deterministic_drafts_contain_no_private_material() -> None:
    session, _factory, public = official_session("demo-1-vanishing-from-hyde-park")
    started = start_official_conclusion(session, public_definition=public)
    context = build_safe_answer_context(started, public_definition=public)
    for spoiler in ("Howard Parker", "crystal clear", "scored 100 points", "Grosvenor Investments (40 points)"):
        assert spoiler not in context
    result, provider = draft_answers(session, public)
    assert [x.question_id for x in result.session.conclusion.answers] == ["q1", "q2", "q3", "q4"]
    assert len(provider.calls) == 4
    assert all("Howard Parker" not in prompt and "/private/" not in prompt for prompt, _ in provider.calls)


def test_provider_failure_is_atomic() -> None:
    session, _factory, public = official_session("demo-1-vanishing-from-hyde-park")
    started = start_official_conclusion(session, public_definition=public); before = started.model_dump_json()
    provider = DeterministicAnswerDraftProvider({"q1": "only one"})
    with pytest.raises(ValueError): generate_official_answer_drafts(started, public_definition=public, provider=provider)
    assert started.model_dump_json() == before and started.conclusion.answers == ()


def test_drafts_edit_and_lock_irreversibly_with_complete_set_required() -> None:
    session, _factory, public = official_session("demo-1-vanishing-from-hyde-park")
    started = start_official_conclusion(session, public_definition=public)
    partial = update_official_answer(started, question_id="q1", text="Reviewed answer")
    with pytest.raises(ConclusionConflictError): lock_official_answers(partial)
    assert partial.conclusion.phase.value == "draft"
    drafts, _ = draft_answers(session, public); edited = update_official_answer(drafts.session, question_id="q1", text="Edited answer")
    locked = lock_official_answers(edited)
    assert locked.status is InvestigationStatus.READY_FOR_FINAL and all(x.locked for x in locked.conclusion.answers)
    with pytest.raises(ConclusionConflictError): update_official_answer(locked, question_id="q1", text="too late")
    with pytest.raises(ConclusionConflictError): lock_official_answers(locked)


def test_private_loaders_are_phase_gated_and_separate() -> None:
    session, _factory, public = official_session("demo-1-vanishing-from-hyde-park")
    drafts, _ = draft_answers(session, public)
    class ScoringSpy(PrivateScoringRepository):
        calls = 0
        def load(self, case_id): self.calls += 1; return super().load(case_id)
    class SolutionSpy(PrivateSolutionRepository):
        calls = 0
        def load(self, case_id): self.calls += 1; return super().load(case_id)
    scoring, solution = ScoringSpy(SCORING_DIR), SolutionSpy(SOLUTION_DIR)
    with pytest.raises(ConclusionConflictError): reveal_official_answer_elements(drafts.session, repository=scoring)
    assert scoring.calls == 0 and solution.calls == 0
    locked = lock_official_answers(drafts.session); unlocked = reveal_official_answer_elements(locked, repository=scoring)
    assert scoring.calls == 1 and solution.calls == 0 and unlocked.conclusion.answer_elements
    with pytest.raises(ConclusionConflictError): reveal_official_solution(unlocked, repository=solution)
    assert solution.calls == 0


def test_demo1_scoring_preserves_140_100_discrepancy_and_invalid_awards_are_atomic() -> None:
    session, _factory, public = official_session("demo-1-vanishing-from-hyde-park")
    drafts, _ = draft_answers(session, public); locked = lock_official_answers(drafts.session); unlocked = reveal_official_answer_elements(locked, repository=PrivateScoringRepository(SCORING_DIR)); before = unlocked.model_dump_json()
    with pytest.raises(ConclusionConflictError): confirm_official_score(unlocked, awarded_elements={"q1": ("q2-e1",)})
    assert unlocked.model_dump_json() == before
    scored = confirm_official_score(unlocked, awarded_elements={"q1": ("q1-e1",), "q2": ("q2-e1",), "q3": ("q3-e1",), "q4": ("q4-e1",)})
    result = scored.conclusion.score_result
    assert (result.answer_points, result.answer_element_total, result.printed_holmes_score) == (140, 140, 100)
    assert result.provisional is result.needs_review is True
    assert result.review_note == "The printed answer elements total 140 while the source says Holmes scored 100. Both are preserved without reconciliation."
    assert unlocked.conclusion.scoring_definition.holmes_route == ("32 NW", "68 EC")
    assert result.score_band_text is None


def test_scoring_uses_accounting_and_demo2_excludes_revisits() -> None:
    session, _factory, public = official_session("demo-2-an-irregular-meeting")
    state = session.case_state.model_copy(update={"accounting_entries": (
        LeadAccountingEntry(source_kind="first-visit", source_id="a", lead_id="la", visit_id="v1", amount=1, uniqueness="once-per-lead"),
        LeadAccountingEntry(source_kind="first-visit", source_id="b", lead_id="lb", visit_id="v2", amount=1, uniqueness="once-per-lead"),
    )})
    session = InvestigationSession.model_validate({**session.model_dump(mode="python"), "case_state": state})
    drafts, _ = draft_answers(session, public); unlocked = reveal_official_answer_elements(lock_official_answers(drafts.session), repository=PrivateScoringRepository(SCORING_DIR))
    scored = confirm_official_score(unlocked, awarded_elements={})
    assert scored.conclusion.score_result.counted_leads == 2
    assert scored.conclusion.score_result.lead_penalty == 0
    assert scored.conclusion.score_result.score_band_text == "At least you tried."
    scoring = unlocked.conclusion.scoring_definition
    assert scoring.holmes_route == ("33 WC", "68 WC", "28 WC", "4 SW", "86 SW")


def test_private_scoring_requires_exact_question_coverage(tmp_path: Path) -> None:
    session, _factory, public = official_session("demo-1-vanishing-from-hyde-park")
    drafts, _ = draft_answers(session, public); locked = lock_official_answers(drafts.session)
    data = json.loads((SCORING_DIR / f"{session.case_id}.json").read_text())
    data["answer_elements"] = [element for element in data["answer_elements"] if element["question_id"] != "q4"]
    (tmp_path / f"{session.case_id}.json").write_text(json.dumps(data))
    before = locked.model_dump_json()
    with pytest.raises(ConclusionConflictError, match="does not match"):
        reveal_official_answer_elements(locked, repository=PrivateScoringRepository(tmp_path))
    assert locked.model_dump_json() == before


def test_score_bands_reject_overlap_but_preserve_printed_gaps(tmp_path: Path) -> None:
    case_id = "demo-2-an-irregular-meeting"
    data = json.loads((SCORING_DIR / f"{case_id}.json").read_text())
    assert [(band.get("minimum"), band.get("maximum")) for band in data["score_bands"]] == [
        (None, 0), (5, 30), (35, 70), (75, 100), (105, None),
    ]
    data["score_bands"][2]["minimum"] = 30
    (tmp_path / f"{case_id}.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="ordered and non-overlapping"):
        PrivateScoringRepository(tmp_path).load(case_id)


def test_solution_reveal_completes_and_all_terminal_modes_remain_exclusive() -> None:
    scored, _factory = scored_session(); ended = reveal_official_solution(scored, repository=PrivateSolutionRepository(SOLUTION_DIR))
    assert ended.status is InvestigationStatus.COMPLETED
    assert ended.conclusion.phase.value == "solution_revealed" and "An easy case to solve" in ended.conclusion.revealed_solution.text
    with pytest.raises(ConclusionConflictError): reveal_official_solution(ended, repository=PrivateSolutionRepository(SOLUTION_DIR))
    payload = ended.model_dump(mode="python"); payload["final_theory"] = FinalTheory(final_theory_id="conflict", summary="Conflict")
    with pytest.raises(ValueError): InvestigationSession.model_validate(payload)


def test_long_solution_has_no_structured_holmes_route_owner() -> None:
    for path in SOLUTION_DIR.glob("*.json"):
        assert "holmes_route" not in json.loads(path.read_text())


def test_ready_for_final_freezes_gameplay_and_sessions_are_isolated() -> None:
    first, factory, public = official_session("demo-1-vanishing-from-hyde-park", 1); second, _factory2, _public2 = official_session("demo-1-vanishing-from-hyde-park", 2)
    ready = start_official_conclusion(first, public_definition=public)
    with pytest.raises(ValueError, match="active session"): visit_lead(ready, id_factory=factory, label="Late", kind="place")
    assert second.status is InvestigationStatus.ACTIVE and second.conclusion is None
