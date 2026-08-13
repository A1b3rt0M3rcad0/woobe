"""Public contract for explicit external-edition composition.

This file is Covered Software under the Woobe Community license in the repository
root `LICENSE.md`. Implementing or importing this contract does not grant any
license to proprietary Woobe editions or to code maintained outside this
Community repository, including Woobe Cloud.

Community owns only this composition seam. External edition repositories provide
concrete routers and worker entries. Community must never import proprietary
edition implementations.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter

from shared.workers.discovery import ModuleWorkerEntry


@dataclass(frozen=True, slots=True)
class EditionIntegration:
    """Explicit composition payload supplied by an external edition repository."""

    api_routers: tuple[APIRouter, ...] = ()
    worker_entries: tuple[ModuleWorkerEntry, ...] = ()
