from sqlalchemy.ext.asyncio import AsyncSession

from modules.billing.domain.repositories import PlanRepository, SubscriptionRepository
from modules.billing.infra.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyPlanRepository,
    SQLAlchemySubscriptionRepository,
)
from modules.billing.service.use_cases import (
    CreatePlanUseCase,
    CreateSubscriptionUseCase,
)
from modules.billing.service.dtos import CreatePlanInput, CreateSubscriptionInput
from shared.domain.events import OutboxEventWriter


class BillingProviders:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def create_plan_use_case(self) -> CreatePlanUseCase:
        repo: PlanRepository = SQLAlchemyPlanRepository(self.session)
        outbox: OutboxEventWriter = SQLAlchemyOutboxEventWriter(self.session)
        return CreatePlanUseCase(repo, outbox)

    async def list_active_plans(self):
        from modules.billing.infra.repositories import SQLAlchemyPlanRepository
        repo = SQLAlchemyPlanRepository(self.session)
        return await repo.list_all()

    def get_organization_subscription(self, org_id):
        from modules.billing.infra.repositories import SQLAlchemySubscriptionRepository
        repo = SQLAlchemySubscriptionRepository(self.session)
        return _GetOrganizationSubscriptionUseCase(repo)

    def create_subscription_use_case(self) -> CreateSubscriptionUseCase:
        org_repo = SQLAlchemyPlanRepository(self.session)
        sub_repo: SubscriptionRepository = SQLAlchemySubscriptionRepository(self.session)
        outbox: OutboxEventWriter = SQLAlchemyOutboxEventWriter(self.session)
        return CreateSubscriptionUseCase(org_repo, sub_repo, outbox)


class _GetOrganizationSubscriptionUseCase:
    def __init__(self, repo):
        self._repo = repo

    async def execute(self, org_id):
        return await self._repo.get_by_organization(org_id)
