"""Compatibility import for the concrete runtime orchestrator.

The implementation lives under application.composers because it assembles
infrastructure repositories, provider adapters and transactional execution.
"""

from modules.agent.application.composers.runtime.ask_use_case import AskAgentUseCase

__all__ = ["AskAgentUseCase"]
