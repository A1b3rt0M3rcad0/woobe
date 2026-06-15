"""Backward-compatibility shim: re-exports from canonical path.

Specs 070-079 moved repositories to infra/database/repositories.py
but agent module still imports from this deprecated path.
"""
from modules.observability.infra.database.repositories import (  # noqa: F401
    SQLAlchemyTraceEventRepository,
    SQLAlchemyTraceRepository,
)
