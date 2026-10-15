from modules.agent.composition.composers.list_available_provider_models_composer import (
    list_available_provider_models_composer,
)
from modules.agent.composition.factories.agent_uow_factory import build_agent_uow
from modules.agent.infra.adapters.provider_model_reconciliation_handler import (
    ProviderModelReconciliationHandler,
)


def provider_model_reconciliation_composer(*, apply=False):
    return ProviderModelReconciliationHandler(
        build_agent_uow,
        list_available_provider_models_composer(
            additional_permissions=("provider:read", "model:write")
            if apply
            else ("provider:read",)
        ),
        apply=apply,
    )
