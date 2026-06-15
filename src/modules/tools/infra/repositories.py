"""Backward-compatibility shim: re-exports from canonical path.

Specs 080-089 moved repositories to infra/database/repositories.py
but agent module still imports from this deprecated path.
"""
from modules.tools.infra.database.repositories import (  # noqa: F401
    SQLAlchemyToolRepository,
)
