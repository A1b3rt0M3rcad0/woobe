"""Public contract for explicit external-edition composition.

LICENSE NOTICE
--------------
This file is Covered Software under the Woobe Community license in the
repository root ``LICENSE.md``. That license governs this contract itself.

Implementing, importing, satisfying, or composing through this contract does
not grant any license to Woobe Cloud, future Woobe Enterprise code, or any
other proprietary implementation maintained outside this Community
repository. Proprietary implementations remain governed exclusively by the
license distributed with their own source repository or by a separate written
agreement with Woobe.

Community owns only this neutral composition seam. External edition
repositories provide concrete routers and worker entries. Community must never
import proprietary edition implementations.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter

from shared.workers.discovery import ModuleWorkerEntry


@dataclass(frozen=True, slots=True)
class EditionIntegration:
    """Composition payload supplied by an external, separately licensed edition.

    ``name`` is operational metadata only. It is not a license selector and it
    cannot enable proprietary rights or features by configuration alone.
    """

    name: str = "community"
    api_routers: tuple[APIRouter, ...] = ()
    worker_entries: tuple[ModuleWorkerEntry, ...] = ()
