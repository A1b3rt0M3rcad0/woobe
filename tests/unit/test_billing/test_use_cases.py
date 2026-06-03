import pytest
from uuid import UUID

from modules.billing.domain.entities import Plan, Customer, Subscription, PaymentEvent
from modules.billing.domain.enums import SubscriptionStatus
from modules.billing.service.dtos import (
    CreatePlanInput,
    CreatePlanOutput,
    CreateCustomerInput,
    CreateCustomerOutput,
    CreateSubscriptionInput,
    CreateSubscriptionOutput,
    CreatePaymentEventInput,
    CreatePaymentEventOutput,
)
from modules.billing.service.use_cases import (
    CreatePlanUseCase,
    CreateCustomerUseCase,
    CreateSubscriptionUseCase,
    HandlePaymentEventUseCase,
)
from modules.billing.domain.repositories import (
    PlanRepository,
    CustomerRepository,
    SubscriptionRepository,
    PaymentEventRepository,
)
from shared.domain.events import OutboxEventWriter
from tests.helpers import make_plan, make_subscription, fake_uuid


class TestCreatePlanUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        mock_repo = mocker.AsyncMock(spec=PlanRepository)
        saved = make_plan(code="pro", name="Pro", price_usd=29.99)
        mock_repo.save.return_value = saved
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)

        input_dto = CreatePlanInput(code="pro", name="Pro", price_usd=29.99)

        uc = CreatePlanUseCase(repo=mock_repo, outbox=mock_outbox)
        result = await uc.execute(input_dto)

        assert isinstance(result, CreatePlanOutput)
        assert result.plan_id == saved.id
        mock_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_limits(self, mocker):
        mock_repo = mocker.AsyncMock(spec=PlanRepository)
        saved = make_plan(code="enterprise", name="Enterprise", price_usd=199.99)
        mock_repo.save.return_value = saved
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)

        input_dto = CreatePlanInput(
            code="enterprise",
            name="Enterprise",
            price_usd=199.99,
            billing_interval="yearly",
            status="active",
            limits={"agents": 50, "tokens": 10_000_000},
        )

        uc = CreatePlanUseCase(repo=mock_repo, outbox=mock_outbox)
        result = await uc.execute(input_dto)

        assert result.plan_id == saved.id
        mock_repo.save.assert_awaited_once()


class TestCreateCustomerUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        mock_repo = mocker.AsyncMock(spec=CustomerRepository)
        saved = Customer(
            organization_id=UUID(fake_uuid()),
            provider="stripe",
            provider_customer_id="cus_001",
            email="org@test.com",
        )
        mock_repo.save.return_value = saved
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)

        input_dto = CreateCustomerInput(
            organization_id=saved.organization_id,
            provider="stripe",
            provider_customer_id="cus_001",
            email="org@test.com",
        )

        uc = CreateCustomerUseCase(repo=mock_repo, outbox=mock_outbox)
        result = await uc.execute(input_dto)

        assert isinstance(result, CreateCustomerOutput)
        assert result.customer_id == saved.id
        mock_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()


class TestCreateSubscriptionUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        mock_repo = mocker.AsyncMock(spec=SubscriptionRepository)
        saved = make_subscription()
        mock_repo.save.return_value = saved
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)

        input_dto = CreateSubscriptionInput(
            organization_id=saved.organization_id,
            customer_id=saved.customer_id,
            plan_id=saved.plan_id,
            provider="custom",
            provider_subscription_id="sub_123",
        )

        uc = CreateSubscriptionUseCase(repo=mock_repo, outbox=mock_outbox)
        result = await uc.execute(input_dto)

        assert isinstance(result, CreateSubscriptionOutput)
        assert result.subscription_id == saved.id
        mock_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_period(self, mocker):
        mock_repo = mocker.AsyncMock(spec=SubscriptionRepository)
        saved = make_subscription()
        mock_repo.save.return_value = saved
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)

        from datetime import datetime
        now = datetime.now()
        input_dto = CreateSubscriptionInput(
            organization_id=saved.organization_id,
            customer_id=saved.customer_id,
            plan_id=saved.plan_id,
            current_period_start=now,
            status="trialing",
        )

        uc = CreateSubscriptionUseCase(repo=mock_repo, outbox=mock_outbox)
        result = await uc.execute(input_dto)

        assert result.subscription_id == saved.id
        mock_repo.save.assert_awaited_once()


class TestHandlePaymentEventUseCase:
    @pytest.mark.asyncio
    async def test_without_subscription(self, mocker):
        mock_payment_repo = mocker.AsyncMock(spec=PaymentEventRepository)
        saved = PaymentEvent(
            provider="stripe",
            provider_event_id="evt_001",
            event_type="invoice.paid",
        )
        mock_payment_repo.save.return_value = saved
        mock_sub_repo = mocker.AsyncMock(spec=SubscriptionRepository)
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)

        input_dto = CreatePaymentEventInput(
            provider="stripe",
            provider_event_id="evt_001",
            event_type="invoice.paid",
        )

        uc = HandlePaymentEventUseCase(
            payment_event_repo=mock_payment_repo,
            subscription_repo=mock_sub_repo,
            outbox=mock_outbox,
        )
        result = await uc.execute(input_dto)

        assert isinstance(result, CreatePaymentEventOutput)
        assert result.event_id == saved.id
        mock_payment_repo.save.assert_awaited_once()
        mock_sub_repo.get_by_id.assert_not_called()
        mock_outbox.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_subscription_canceled(self, mocker):
        mock_payment_repo = mocker.AsyncMock(spec=PaymentEventRepository)
        saved = PaymentEvent(
            provider="stripe",
            provider_event_id="evt_002",
            event_type="subscription.canceled",
        )
        mock_payment_repo.save.return_value = saved
        mock_sub_repo = mocker.AsyncMock(spec=SubscriptionRepository)
        sub = make_subscription()
        mock_sub_repo.get_by_id.return_value = sub
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)

        input_dto = CreatePaymentEventInput(
            provider="stripe",
            provider_event_id="evt_002",
            event_type="subscription.canceled",
            subscription_id=sub.id,
        )

        uc = HandlePaymentEventUseCase(
            payment_event_repo=mock_payment_repo,
            subscription_repo=mock_sub_repo,
            outbox=mock_outbox,
        )
        result = await uc.execute(input_dto)

        assert result.event_id == saved.id
        assert sub.status == SubscriptionStatus.canceled
        assert sub.canceled_at is not None
        mock_sub_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_subscription_past_due(self, mocker):
        mock_payment_repo = mocker.AsyncMock(spec=PaymentEventRepository)
        saved = PaymentEvent(
            provider="stripe",
            provider_event_id="evt_003",
            event_type="subscription.past_due",
        )
        mock_payment_repo.save.return_value = saved
        mock_sub_repo = mocker.AsyncMock(spec=SubscriptionRepository)
        sub = make_subscription()
        mock_sub_repo.get_by_id.return_value = sub
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)

        input_dto = CreatePaymentEventInput(
            provider="stripe",
            provider_event_id="evt_003",
            event_type="subscription.past_due",
            subscription_id=sub.id,
        )

        uc = HandlePaymentEventUseCase(
            payment_event_repo=mock_payment_repo,
            subscription_repo=mock_sub_repo,
            outbox=mock_outbox,
        )
        result = await uc.execute(input_dto)

        assert result.event_id == saved.id
        assert sub.status == SubscriptionStatus.past_due
        mock_sub_repo.save.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_subscription_not_found_skips_update(self, mocker):
        mock_payment_repo = mocker.AsyncMock(spec=PaymentEventRepository)
        saved = PaymentEvent(
            provider="stripe",
            provider_event_id="evt_004",
            event_type="subscription.canceled",
        )
        mock_payment_repo.save.return_value = saved
        mock_sub_repo = mocker.AsyncMock(spec=SubscriptionRepository)
        mock_sub_repo.get_by_id.return_value = None
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)

        input_dto = CreatePaymentEventInput(
            provider="stripe",
            provider_event_id="evt_004",
            event_type="subscription.canceled",
            subscription_id=UUID(fake_uuid()),
        )

        uc = HandlePaymentEventUseCase(
            payment_event_repo=mock_payment_repo,
            subscription_repo=mock_sub_repo,
            outbox=mock_outbox,
        )
        result = await uc.execute(input_dto)

        assert result.event_id == saved.id
        mock_sub_repo.save.assert_not_called()
