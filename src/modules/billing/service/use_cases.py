from datetime import UTC, datetime

from modules.billing.domain.entities import Customer, PaymentEvent, Plan, Subscription
from modules.billing.domain.enums import (
    BillingInterval,
    BillingProvider,
    PaymentEventStatus,
    PlanStatus,
    SubscriptionStatus,
)
from modules.billing.domain.repositories import (
    CustomerRepository,
    PaymentEventRepository,
    PlanRepository,
    SubscriptionRepository,
)
from modules.billing.service.dtos import (
    CreateCustomerInput,
    CreateCustomerOutput,
    CreatePaymentEventInput,
    CreatePaymentEventOutput,
    CreatePlanInput,
    CreatePlanOutput,
    CreateSubscriptionInput,
    CreateSubscriptionOutput,
)
from shared.domain.events import OutboxEventWriter


class CreatePlanUseCase:

    def __init__(
        self,
        repo: PlanRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._repo = repo
        self._outbox = outbox

    async def execute(self, input_dto: CreatePlanInput) -> CreatePlanOutput:
        plan = Plan(
            code=input_dto.code,
            name=input_dto.name,
            price_usd=input_dto.price_usd,
            billing_interval=BillingInterval(input_dto.billing_interval),
            limits=input_dto.limits,
            status=PlanStatus(input_dto.status),
        )
        saved = await self._repo.save(plan)

        await self._outbox.write(
            aggregate_type="Plan",
            aggregate_id=saved.id,
            event_type="plan.created",
            payload={
                "code": saved.code,
                "name": saved.name,
                "price_usd": saved.price_usd,
            },
        )

        return CreatePlanOutput(plan_id=saved.id)


class CreateCustomerUseCase:

    def __init__(
        self,
        repo: CustomerRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._repo = repo
        self._outbox = outbox

    async def execute(self, input_dto: CreateCustomerInput) -> CreateCustomerOutput:
        customer = Customer(
            organization_id=input_dto.organization_id,
            provider=BillingProvider(input_dto.provider),
            provider_customer_id=input_dto.provider_customer_id,
            email=input_dto.email,
            data=input_dto.data,
        )
        saved = await self._repo.save(customer)

        await self._outbox.write(
            aggregate_type="Customer",
            aggregate_id=saved.id,
            event_type="customer.created",
            payload={
                "organization_id": str(saved.organization_id),
                "provider": saved.provider,
            },
        )

        return CreateCustomerOutput(customer_id=saved.id)


class CreateSubscriptionUseCase:

    def __init__(
        self,
        repo: SubscriptionRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._repo = repo
        self._outbox = outbox

    async def execute(
        self, input_dto: CreateSubscriptionInput
    ) -> CreateSubscriptionOutput:
        subscription = Subscription(
            organization_id=input_dto.organization_id,
            customer_id=input_dto.customer_id,
            plan_id=input_dto.plan_id,
            provider=BillingProvider(input_dto.provider),
            provider_subscription_id=input_dto.provider_subscription_id,
            status=SubscriptionStatus(input_dto.status),
            current_period_start=input_dto.current_period_start,
            current_period_end=input_dto.current_period_end,
            trial_ends_at=input_dto.trial_ends_at,
        )
        saved = await self._repo.save(subscription)

        await self._outbox.write(
            aggregate_type="Subscription",
            aggregate_id=saved.id,
            event_type="subscription.created",
            payload={
                "organization_id": str(saved.organization_id),
                "plan_id": str(saved.plan_id),
                "status": saved.status,
            },
        )

        return CreateSubscriptionOutput(subscription_id=saved.id)


class HandlePaymentEventUseCase:

    def __init__(
        self,
        payment_event_repo: PaymentEventRepository,
        subscription_repo: SubscriptionRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._payment_event_repo = payment_event_repo
        self._subscription_repo = subscription_repo
        self._outbox = outbox

    async def execute(
        self, input_dto: CreatePaymentEventInput
    ) -> CreatePaymentEventOutput:
        event = PaymentEvent(
            provider=BillingProvider(input_dto.provider),
            provider_event_id=input_dto.provider_event_id,
            event_type=input_dto.event_type,
            payload=input_dto.payload,
            status=PaymentEventStatus.processed,
            processed_at=datetime.now(UTC),
        )
        saved = await self._payment_event_repo.save(event)

        if input_dto.subscription_id:
            sub = await self._subscription_repo.get_by_id(input_dto.subscription_id)
            if sub:
                if "canceled" in input_dto.event_type:
                    sub.status = SubscriptionStatus.canceled
                    sub.canceled_at = datetime.now(UTC)
                elif "past_due" in input_dto.event_type:
                    sub.status = SubscriptionStatus.past_due
                await self._subscription_repo.save(sub)

        await self._outbox.write(
            aggregate_type="PaymentEvent",
            aggregate_id=saved.id,
            event_type=f"payment_event.{input_dto.event_type}",
            payload={
                "provider_event_id": input_dto.provider_event_id,
                "subscription_id": str(input_dto.subscription_id) if input_dto.subscription_id else None,
            },
        )

        return CreatePaymentEventOutput(event_id=saved.id)
