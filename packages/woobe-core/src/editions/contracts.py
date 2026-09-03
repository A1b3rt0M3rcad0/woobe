"""Public contract for explicit Enterprise composition.

LICENSE NOTICE
--------------
This file is Covered Software under the Woobe Core license in the repository
root ``LICENSE.md``. That license governs this integration contract itself.

Implementing, importing, satisfying, or composing through this contract does
not grant any license to Woobe Enterprise implementation. Enterprise code is
separately licensed under ``LICENSE_EE.md`` and/or a written agreement with
Woobe.

Core owns only this neutral composition seam. Enterprise implementations may
provide concrete routers and worker entries, but Core must never import
Enterprise implementation modules.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter


@dataclass(frozen=True, slots=True)
class EditionIntegration:
    """Composition payload supplied by a separately licensed Enterprise layer.

    ``name`` is operational metadata only. It is not a license selector and it
    cannot enable Enterprise rights or features by configuration alone.
    """

    name: str = "core"
    api_routers: tuple[APIRouter, ...] = ()
