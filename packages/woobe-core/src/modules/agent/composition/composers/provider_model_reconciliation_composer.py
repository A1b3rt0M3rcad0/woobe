from collections.abc import Callable

from modules.agent.application.use_cases.provider_model_reconciliation import (
    PreviewProviderModelReconciliationUseCase,
    ApplyProviderModelReconciliationUseCase,
)
from modules.agent.composition.factories.agent_uow_factory import build_agent_uow
from modules.agent.composition.factories.provider_discovery_factory import (
    build_provider_discovery_handler,
)
from modules.agent.infra.adapters.provider_model_reconciliation_handler import (
    ProviderModelReconciliationHandler,
)


def provider_model_reconciliation_composer() -> Callable:
    discovery = build_provider_discovery_handler(additional_permissions=("provider:read",))
    return ProviderModelReconciliationHandler(
        build_agent_uow,
        discovery,
        preview_use_case_factory=PreviewProviderModelReconciliationUseCase,
        apply_use_case_factory=ApplyProviderModelReconciliationUseCase,
    )


def apply_provider_model_reconciliation_composer() -> Callable:
    discovery = build_provider_discovery_handler(additional_permissions=("provider:read", "model:write"))
    return ProviderModelReconciliationHandler(
        build_agent_uow,
        discovery,
        preview_use_case_factory=PreviewProviderModelReconciliationUseCase,
        apply_use_case_factory=ApplyProviderModelReconciliationUseCase,
        apply=True,
    )
