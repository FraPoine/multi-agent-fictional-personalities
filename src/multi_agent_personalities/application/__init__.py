"""Framework-independent application services."""

from multi_agent_personalities.application.conversation_service import (
    ConversationResult,
    run_mock_conversation,
)

from multi_agent_personalities.application.evaluation_service import (
    PilotPreparationResult,
    prepare_technical_pilot,
)

__all__ = [
    "ConversationResult", "PilotPreparationResult", "prepare_technical_pilot",
    "run_mock_conversation",
]
