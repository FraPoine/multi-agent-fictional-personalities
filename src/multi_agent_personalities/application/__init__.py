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
    GroupDiscussionResult,
    GroupDecisionResult,
    FinalizationResult,
    IndependentAnalysesResult,
    MAX_DISCUSSION_TURNS,
    create_session,
    create_group_decision,
    finalize_investigation,
    reveal_clue,
    run_group_discussion,
    run_independent_analyses,
)
from multi_agent_personalities.application.investigation_ids import (
    DeterministicInvestigationIdFactory,
)
from multi_agent_personalities.application.investigation_visit_service import (
    LeadDiscussionResult,
    LeadFinalizationResult,
    MAX_LEAD_DISCUSSION_TURNS,
    build_lead_discussion_context,
    continue_lead_discussion,
    finalize_lead_investigation,
    project_lead_conversation,
    reveal_information,
    record_group_decision,
    record_hypothesis,
    record_visit_analysis,
    visit_lead,
)
from multi_agent_personalities.application.investigation_mock import (
    HERCULE_POIROT_ID,
    INVESTIGATION_FIXTURE_FILES,
    SHERLOCK_HOLMES_ID,
    InvestigationMockBindings,
    InvestigationMockTask,
    build_investigation_mock_bindings,
)
from multi_agent_personalities.application.investigation_mock_runtime import (
    InvestigationMockCapabilities,
    InvestigationMockRuntime,
    build_investigation_mock_runtime,
    investigation_mock_capabilities,
)
from multi_agent_personalities.application.investigation_tasks import (
    investigation_analysis_task_name,
    investigation_decision_task_name,
    investigation_discussion_task_name,
    investigation_final_theory_task_name,
    investigation_lead_discussion_task_name,
    investigation_lead_final_theory_task_name,
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
    "FinalizationResult", "GroupDecisionResult", "GroupDiscussionResult",
    "HERCULE_POIROT_ID", "INVESTIGATION_FIXTURE_FILES",
    "IndependentAnalysesResult",
    "InvestigationPromptError", "InvestigationPromptName",
    "InvestigationPromptTemplate", "InvestigationMockBindings",
    "InvestigationMockCapabilities", "InvestigationMockRuntime",
    "InvestigationMockTask", "LeadDiscussionResult", "LeadFinalizationResult",
    "MAX_DISCUSSION_TURNS",
    "MAX_LEAD_DISCUSSION_TURNS", "PilotPreparationResult",
    "SHERLOCK_HOLMES_ID",
    "StructuredGenerationResult", "StructuredOutputError", "create_group_decision",
    "create_session", "continue_lead_discussion",
    "finalize_investigation", "finalize_lead_investigation",
    "build_investigation_mock_runtime",
    "investigation_mock_capabilities",
    "build_investigation_mock_bindings", "investigation_analysis_task_name",
    "investigation_decision_task_name", "investigation_discussion_task_name",
    "investigation_final_theory_task_name",
    "investigation_lead_discussion_task_name",
    "investigation_lead_final_theory_task_name",
    "load_investigation_prompt", "parse_structured_generation",
    "prepare_technical_pilot", "render_analyses", "render_decisions",
    "render_discussion_messages", "render_hypotheses",
    "render_investigation_prompt", "render_persona_context",
    "render_visible_clues", "reveal_clue", "reveal_information",
    "record_group_decision", "record_hypothesis", "record_visit_analysis",
    "run_group_discussion", "project_lead_conversation",
    "build_lead_discussion_context", "visit_lead",
    "run_independent_analyses",
    "run_mock_conversation",
]
