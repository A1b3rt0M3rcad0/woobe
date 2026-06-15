"""Backward-compatibility shim: re-exports from canonical path.

Specs 060-069 moved repositories to infra/database/repositories.py
but agent module still imports from this deprecated path.
"""
from modules.metering.infra.database.repositories import (  # noqa: F401
    SQLAlchemyUsageEventRepository,
)
