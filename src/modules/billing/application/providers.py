from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.billing.domain.entities import Plan, Subscription
from modules.billing.domain.enums import SubscriptionStatus
from modules.billing.infra.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyPlanRepository,
    SQLAlchemySubscriptionRepository,
)
from modules.billing.service.use_cases import (
    CreatePlanUseCase,
    CreateSubscriptionUseCase,
)


class BillingProviders:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def create_plan_use_case(self) -> CreatePlanUseCase:
        return CreatePlanUseCase(
            repo=SQLAlchemyPlanRepository(self._session),
            outbox=SQLAlchemyOutboxEventWriter(self._session),
        )

    def create_subscription_use_case(self) -> CreateSubscriptionUseCase:
        return CreateSubscriptionUseCase(
            repo=SQLAlchemySubscriptionRepository(self._session),
            outbox=SQLAlchemyOutboxEventWriter(self._session),
        )

    async def list_active_plans(self) -> list[Plan]:
        repo = SQLAlchemyPlanRepository(self._session)
        return await repo.list_active()

    async def get_organization_subscription(self, org_id: UUID) -> Subscription | None:
        repo = SQLAlchemySubscriptionRepository(self._session)
        subs = await repo.list_by_organization(org_id)
        for sub in subs:
            if sub.status == SubscriptionStatus.active:
                return sub
        return None
