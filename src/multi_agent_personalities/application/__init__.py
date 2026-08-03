"""Framework-independent application services."""

from multi_agent_personalities.application.conversation_service import (
    ConversationResult,
    run_mock_conversation,
)

__all__ = ["ConversationResult", "run_mock_conversation"]
