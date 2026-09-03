from __future__ import annotations

import pytest

from modules.network.infra.runtime.finalizer import NetworkRuntimeFinalizer
from woobe_workers.composition.network_agent_persistence import (
    ProjectRAIAgentInvocationArtifactMaterializer,
)


@pytest.fixture(autouse=True)
def compose_network_agent_artifact_persistence(monkeypatch) -> None:
    """Exercise Network integration tests with the production cross-context adapter.

    Unit-level Network finalizers may omit the adapter, but integration tests that
    assert Agent Run/session/message evidence must use the same outer composition
    used by the worker process.
    """

    original_init = NetworkRuntimeFinalizer.__init__

    def configured_init(
        self,
        session_factory,
        *,
        agent_artifact_materializer=None,
    ) -> None:
        original_init(
            self,
            session_factory,
            agent_artifact_materializer=(
                agent_artifact_materializer
                or ProjectRAIAgentInvocationArtifactMaterializer()
            ),
        )

    monkeypatch.setattr(NetworkRuntimeFinalizer, "__init__", configured_init)
