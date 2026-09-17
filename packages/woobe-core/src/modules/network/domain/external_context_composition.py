from __future__ import annotations

from typing import Any

from modules.agent.domain.external_context_contract import compose_external_context_contracts


def compose_effective_external_context_contracts(
    contracts: dict[str, Any],
) -> dict[str, Any]:
    """Compose Agent contracts behind the Network domain boundary.

    Runtime adapters must consume only Network-owned immutable material. The temporary
    Agent-domain dependency remains isolated here alongside the existing release/catalog
    coupling until that broader module-boundary migration is completed.
    """

    return compose_external_context_contracts(contracts)


__all__ = ["compose_effective_external_context_contracts"]
