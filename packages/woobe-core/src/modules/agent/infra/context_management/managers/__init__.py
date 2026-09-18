"""Concrete Context Manager implementations.

Runtime resolution lives in resolver.py and is imported explicitly by composition.
"""

from modules.agent.infra.context_management.managers.standard import (
    StandardContextManager,
)

__all__ = ["StandardContextManager"]
