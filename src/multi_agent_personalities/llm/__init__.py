"""Language-model provider interfaces."""

from multi_agent_personalities.llm.base import LLMProvider
from multi_agent_personalities.llm.mock_provider import MockProvider

__all__ = ["LLMProvider", "MockProvider"]
