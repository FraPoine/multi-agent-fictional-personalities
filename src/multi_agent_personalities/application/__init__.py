"""Framework-independent application services."""

from multi_agent_personalities.application.conversation_service import (
    ConversationResult,
    run_mock_conversation,
)

from multi_agent_personalities.application.evaluation_service import (
    PilotPreparationResult,
    prepare_technical_pilot,
)
from multi_agent_personalities.application.investigation_service import (
    IndependentAnalysesResult,
    create_session,
    reveal_clue,
    run_independent_analyses,
)
from multi_agent_personalities.application.investigation_ids import (
    DeterministicInvestigationIdFactory,
)
from multi_agent_personalities.application.investigation_mock import (
    HERCULE_POIROT_ID,
    INVESTIGATION_FIXTURE_FILES,
    SHERLOCK_HOLMES_ID,
    InvestigationMockBindings,
    InvestigationMockTask,
    build_investigation_mock_bindings,
    investigation_analysis_task_name,
)
from multi_agent_personalities.application.investigation_prompts import (
    InvestigationPromptError,
    InvestigationPromptName,
    InvestigationPromptTemplate,
    load_investigation_prompt,
    render_analyses,
    render_decisions,
    render_discussion_messages,
    render_hypotheses,
    render_investigation_prompt,
    render_persona_context,
    render_visible_clues,
)
from multi_agent_personalities.application.investigation_structured_output import (
    GeneratedAnalysisPayload,
    GeneratedDecisionPayload,
    GeneratedFinalTheoryPayload,
    GeneratedHypothesisPayload,
    StructuredGenerationResult,
    StructuredOutputError,
    parse_structured_generation,
)

__all__ = [
    "ConversationResult", "DeterministicInvestigationIdFactory",
    "GeneratedAnalysisPayload", "GeneratedDecisionPayload",
    "GeneratedFinalTheoryPayload", "GeneratedHypothesisPayload",
    "HERCULE_POIROT_ID", "INVESTIGATION_FIXTURE_FILES",
    "IndependentAnalysesResult",
    "InvestigationPromptError", "InvestigationPromptName",
    "InvestigationPromptTemplate", "InvestigationMockBindings",
    "InvestigationMockTask", "PilotPreparationResult", "SHERLOCK_HOLMES_ID",
    "StructuredGenerationResult", "StructuredOutputError", "create_session",
    "build_investigation_mock_bindings", "investigation_analysis_task_name",
    "load_investigation_prompt", "parse_structured_generation",
    "prepare_technical_pilot", "render_analyses", "render_decisions",
    "render_discussion_messages", "render_hypotheses",
    "render_investigation_prompt", "render_persona_context",
    "render_visible_clues", "reveal_clue", "run_independent_analyses",
    "run_mock_conversation",
]
