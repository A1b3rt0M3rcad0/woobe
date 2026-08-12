import pytest
from uuid import UUID

from editions.cloud.billing.domain.entities import Customer, PaymentEvent, Plan
from editions.cloud.billing.domain.enums import BillingProvider, PlanStatus, SubscriptionStatus
from editions.cloud.billing.application.dtos import (
    CreatePlanInput,
    CreatePlanOutput,
    CreateCustomerInput,
    CreateCustomerOutput,
    CreateSubscriptionInput,
    CreateSubscriptionOutput,
    CreatePaymentEventInput,
    CreatePaymentEventOutput,
)
from editions.cloud.billing.application.use_cases import (
    CreatePlanUseCase,
    CreateCustomerUseCase,
    CreateSubscriptionUseCase,
    HandlePaymentEventUseCase,
)
from editions.cloud.billing.domain.repositories import (
    PlanRepository,
    CustomerRepository,
    SubscriptionRepository,
    PaymentEventRepository,
)
from shared.messaging.outbox_writer import OutboxEventWriter
from tests.helpers import make_plan, make_subscription, fake_uuid


class TestCreatePlanUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        mock_repo = mocker.AsyncMock(spec=PlanRepository)
        saved = make_plan(code="pro", name="Pro", price_usd=29.99)
        mock_repo.save.return_value = saved
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)
        result = await CreatePlanUseCase(mock_repo, mock_outbox).execute(
            CreatePlanInput(code="pro", name="Pro", price_usd=29.99)
        )
        assert isinstance(result, CreatePlanOutput)
        assert result.plan_id == saved.id
        mock_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()


class TestCreateCustomerUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        mock_repo = mocker.AsyncMock(spec=CustomerRepository)
        saved = Customer(
            organization_id=UUID(fake_uuid()),
            provider=BillingProvider.stripe,
            provider_customer_id="cus_001",
            email="org@test.com",
        )
        mock_repo.save.return_value = saved
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)
        result = await CreateCustomerUseCase(mock_repo, mock_outbox).execute(
            CreateCustomerInput(
                organization_id=saved.organization_id,
                provider="stripe",
                provider_customer_id="cus_001",
                email="org@test.com",
            )
        )
        assert isinstance(result, CreateCustomerOutput)
        assert result.customer_id == saved.id


class TestCreateSubscriptionUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        saved = make_subscription()
        mock_repo = mocker.AsyncMock(spec=SubscriptionRepository)
        mock_repo.save.return_value = saved
        customer_repo = mocker.AsyncMock(spec=CustomerRepository)
        customer_repo.get_by_id.return_value = Customer(
            id=saved.customer_id,
            organization_id=saved.organization_id,
            provider=BillingProvider.custom,
        )
        plan_repo = mocker.AsyncMock(spec=PlanRepository)
        plan_repo.get_by_id.return_value = Plan(
            id=saved.plan_id,
            code="test",
            status=PlanStatus.active,
        )
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)
        result = await CreateSubscriptionUseCase(
            mock_repo, customer_repo, plan_repo, mock_outbox
        ).execute(
            CreateSubscriptionInput(
                organization_id=saved.organization_id,
                customer_id=saved.customer_id,
                plan_id=saved.plan_id,
                provider="custom",
                provider_subscription_id="sub_123",
            )
        )
        assert isinstance(result, CreateSubscriptionOutput)
        assert result.subscription_id == saved.id
        mock_repo.save.assert_awaited_once()


class TestHandlePaymentEventUseCase:
    @pytest.mark.asyncio
    async def test_without_subscription(self, mocker):
        mock_payment_repo = mocker.AsyncMock(spec=PaymentEventRepository)
        saved = PaymentEvent(
            provider=BillingProvider.stripe,
            provider_event_id="evt_001",
            event_type="invoice.paid",
        )
        mock_payment_repo.save.return_value = saved
        mock_sub_repo = mocker.AsyncMock(spec=SubscriptionRepository)
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)
        result = await HandlePaymentEventUseCase(
            mock_payment_repo, mock_sub_repo, mock_outbox
        ).execute(
            CreatePaymentEventInput(
                provider="stripe",
                provider_event_id="evt_001",
                event_type="invoice.paid",
            )
        )
        assert isinstance(result, CreatePaymentEventOutput)
        assert result.event_id == saved.id
        mock_sub_repo.get_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_with_subscription_canceled(self, mocker):
        mock_payment_repo = mocker.AsyncMock(spec=PaymentEventRepository)
        saved = PaymentEvent(
            provider=BillingProvider.stripe,
            provider_event_id="evt_002",
            event_type="subscription.canceled",
        )
        mock_payment_repo.save.return_value = saved
        mock_sub_repo = mocker.AsyncMock(spec=SubscriptionRepository)
        sub = make_subscription()
        mock_sub_repo.get_by_id.return_value = sub
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)
        result = await HandlePaymentEventUseCase(
            mock_payment_repo, mock_sub_repo, mock_outbox
        ).execute(
            CreatePaymentEventInput(
                provider="stripe",
                provider_event_id="evt_002",
                event_type="subscription.canceled",
                subscription_id=sub.id,
            )
        )
        assert result.event_id == saved.id
        assert sub.status == SubscriptionStatus.canceled
        assert sub.canceled_at is not None
        mock_sub_repo.save.assert_awaited_once()
