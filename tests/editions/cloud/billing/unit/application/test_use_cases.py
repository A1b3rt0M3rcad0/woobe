from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from editions.cloud.billing.application.use_cases import (
    CreatePlanUseCase,
    CreateSubscriptionUseCase,
    GetOrganizationSubscriptionUseCase,
    ListActivePlansUseCase,
)
from editions.cloud.billing.application.dtos import (
    CreatePlanInput,
    CreateSubscriptionInput,
    GetOrganizationSubscriptionInput,
)
from editions.cloud.billing.domain.entities import Customer, Plan, Subscription
from editions.cloud.billing.domain.enums import BillingProvider, PlanStatus, SubscriptionStatus
from shared.infra.errors import ConflictError


class TestCreatePlanUseCase:
    @pytest.mark.anyio
    async def test_execute_creates_plan(self):
        repo = AsyncMock()
        repo.save.return_value = Plan(id=UUID("00000000-0000-0000-0000-000000000001"), code="pro")
        outbox = AsyncMock()
        use_case = CreatePlanUseCase(repo, outbox)

        result = await use_case.execute(CreatePlanInput(code="pro", name="Pro", price_usd=29.99))

        assert result.plan_id == UUID("00000000-0000-0000-0000-000000000001")
        repo.save.assert_awaited_once()
        outbox.write.assert_awaited_once()


class TestCreateSubscriptionUseCase:
    @pytest.mark.anyio
    async def test_execute_creates_subscription(self):
        organization_id = UUID("00000000-0000-0000-0000-000000000002")
        customer_id = UUID("00000000-0000-0000-0000-000000000003")
        plan_id = UUID("00000000-0000-0000-0000-000000000004")

        repo = AsyncMock()
        repo.save.return_value = Subscription(
            id=UUID("00000000-0000-0000-0000-000000000001"),
        )
        customer_repo = AsyncMock()
        customer_repo.get_by_id.return_value = Customer(
            id=customer_id,
            organization_id=organization_id,
            provider=BillingProvider.custom,
        )
        plan_repo = AsyncMock()
        plan_repo.get_by_id.return_value = Plan(
            id=plan_id,
            code="pro",
            status=PlanStatus.active,
        )
        outbox = AsyncMock()
        use_case = CreateSubscriptionUseCase(repo, customer_repo, plan_repo, outbox)

        result = await use_case.execute(CreateSubscriptionInput(
            organization_id=organization_id,
            customer_id=customer_id,
            plan_id=plan_id,
        ))

        assert result.subscription_id == UUID("00000000-0000-0000-0000-000000000001")
        repo.save.assert_awaited_once()
        outbox.write.assert_awaited_once()

    @pytest.mark.anyio
    async def test_execute_rejects_customer_from_another_organization(self):
        repo = AsyncMock()
        customer_repo = AsyncMock()
        customer_repo.get_by_id.return_value = Customer(
            id=UUID("00000000-0000-0000-0000-000000000003"),
            organization_id=UUID("00000000-0000-0000-0000-000000000099"),
            provider=BillingProvider.custom,
        )
        plan_repo = AsyncMock()
        outbox = AsyncMock()
        use_case = CreateSubscriptionUseCase(repo, customer_repo, plan_repo, outbox)

        with pytest.raises(ConflictError):
            await use_case.execute(CreateSubscriptionInput(
                organization_id=UUID("00000000-0000-0000-0000-000000000002"),
                customer_id=UUID("00000000-0000-0000-0000-000000000003"),
                plan_id=UUID("00000000-0000-0000-0000-000000000004"),
            ))

        repo.save.assert_not_awaited()


class TestListActivePlansUseCase:
    @pytest.mark.anyio
    async def test_execute_returns_plans(self):
        repo = AsyncMock()
        repo.list_active.return_value = [
            Plan(id=UUID("00000000-0000-0000-0000-000000000001"), code="pro", name="Pro", price_usd=29.99, status=PlanStatus.active),
        ]
        use_case = ListActivePlansUseCase(repo)

        result = await use_case.execute()

        assert len(result) == 1
        assert result[0].code == "pro"
        assert result[0].price_usd == 29.99


class TestGetOrganizationSubscriptionUseCase:
    @pytest.mark.anyio
    async def test_execute_returns_subscription(self):
        repo = AsyncMock()
        repo.list_by_organization.return_value = [
            Subscription(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                organization_id=UUID("00000000-0000-0000-0000-000000000002"),
                plan_id=UUID("00000000-0000-0000-0000-000000000003"),
                status=SubscriptionStatus.active,
            ),
        ]
        use_case = GetOrganizationSubscriptionUseCase(repo)

        result = await use_case.execute(GetOrganizationSubscriptionInput(
            organization_id=UUID("00000000-0000-0000-0000-000000000002"),
        ))

        assert result is not None
        assert result.organization_id == UUID("00000000-0000-0000-0000-000000000002")
        assert result.status == "active"

    @pytest.mark.anyio
    async def test_execute_returns_none_when_no_subscription(self):
        repo = AsyncMock()
        repo.list_by_organization.return_value = []
        use_case = GetOrganizationSubscriptionUseCase(repo)

        result = await use_case.execute(GetOrganizationSubscriptionInput(
            organization_id=UUID("00000000-0000-0000-0000-000000000001"),
        ))

        assert result is None
