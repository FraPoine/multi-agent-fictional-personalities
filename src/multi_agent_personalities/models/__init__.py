"""Reusable data models."""

from multi_agent_personalities.case_catalog import (
    CaseCatalog,
    CaseDefinition,
    CaseLeadDefinition,
    CaseResourceDefinition,
    CaseResourceType,
)
from multi_agent_personalities.models.conversation import ConversationRun
from multi_agent_personalities.models.generation import (
    GenerationMetadata,
    GenerationResult,
    TokenUsage,
)
from multi_agent_personalities.models.identifiers import validate_run_id
from multi_agent_personalities.models.investigation import (
    AgentAnalysis,
    Clue,
    EvidenceReference,
    EvidenceRelation,
    FinalTheory,
    GroupDecision,
    GroupDecisionType,
    Hypothesis,
    HypothesisStatus,
    InvestigationRound,
    InvestigationRoundStatus,
    InvestigationLead,
    InvestigationSession,
    InvestigationStatus,
    LeadVisit,
    RevealedInformation,
    CaseChoiceState,
    CasePlayState,
    LeadAccountingEntry,
    ConclusionMode,
    ConclusionPhase,
    ConclusionAnswer,
    OfficialScoreResult,
    RevealedSolution,
    InvestigationConclusionState,
    ResourceConsultation,
    validate_unique_clue_ids,
)
from multi_agent_personalities.models.message import Message
from multi_agent_personalities.models.evaluation import (
    EvaluationTrial,
    PublicEvaluationTrial,
    RaterResponse,
    TrialAnswer,
)
from multi_agent_personalities.models.persona import Persona

__all__ = [
    "AgentAnalysis", "CaseCatalog", "CaseDefinition", "CaseLeadDefinition",
    "CaseResourceDefinition", "CaseResourceType",
    "ConversationRun", "EvidenceReference",
    "EvidenceRelation", "FinalTheory", "GenerationMetadata",
    "GenerationResult", "GroupDecision", "GroupDecisionType", "Hypothesis",
    "HypothesisStatus", "InvestigationLead",
    "InvestigationSession", "InvestigationStatus",
    "LeadVisit", "RevealedInformation", "CaseChoiceState", "CasePlayState", "LeadAccountingEntry",
    "ConclusionMode", "ConclusionPhase", "ConclusionAnswer",
    "OfficialScoreResult", "RevealedSolution", "InvestigationConclusionState",
    "ResourceConsultation",
    "Message", "Persona", "PublicEvaluationTrial", "RaterResponse",
    "TokenUsage", "TrialAnswer", "EvaluationTrial", "validate_run_id",
]

# Legacy round symbols remain directly importable until the Sprint 7 UX rewrite,
# but are deliberately absent from the authoritative wildcard export contract.
LEGACY_ROUND_MODEL_NAMES = (
    "Clue",
    "InvestigationRound",
    "InvestigationRoundStatus",
    "validate_unique_clue_ids",
)
