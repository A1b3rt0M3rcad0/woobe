from fastapi import Depends

from modules.billing.application.providers import BillingProviders
from shared.infra.database.session_manager import SessionManager
from shared.presentation.dependencies import get_session_manager


async def get_billing_providers(
    manager: SessionManager = Depends(get_session_manager),
) -> BillingProviders:
    return BillingProviders(manager.session)
