from datetime import UTC, datetime

from editions.cloud.billing.domain.entities import Customer, PaymentEvent, Plan, Subscription
from editions.cloud.billing.domain.enums import (
    BillingInterval,
    BillingProvider,
    PaymentEventStatus,
    PlanStatus,
    SubscriptionStatus,
)
from editions.cloud.billing.domain.repositories import (
    CustomerRepository,
    PaymentEventRepository,
    PlanRepository,
    SubscriptionRepository,
)
from editions.cloud.billing.application.dtos.billing_dtos import (
    CreateCustomerInput,
    CreateCustomerOutput,
    CreatePaymentEventInput,
    CreatePaymentEventOutput,
    CreatePlanInput,
    CreatePlanOutput,
    CreateSubscriptionInput,
    CreateSubscriptionOutput,
    GetOrganizationSubscriptionInput,
    GetOrganizationSubscriptionOutput,
    ListActivePlansOutput,
)
from shared.infra.errors import ConflictError, NotFoundError
from shared.messaging.outbox_writer import OutboxEventWriter


def _value(value: object) -> object:
    return getattr(value, "value", value)


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
            event_type="plan.created.v1",
            payload={
                "code": saved.code,
                "name": saved.name,
                "price_usd": saved.price_usd,
            },
            routing_key="plan.created.v1",
            idempotency_key=f"billing:plan.created.v1:{saved.id}",
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
            event_type="customer.created.v1",
            payload={
                "organization_id": str(saved.organization_id),
                "provider": saved.provider,
            },
            routing_key="customer.created.v1",
            idempotency_key=f"billing:customer.created.v1:{saved.id}",
        )

        return CreateCustomerOutput(customer_id=saved.id)


class CreateSubscriptionUseCase:

    def __init__(
        self,
        repo: SubscriptionRepository,
        customer_repo: CustomerRepository,
        plan_repo: PlanRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._repo = repo
        self._customer_repo = customer_repo
        self._plan_repo = plan_repo
        self._outbox = outbox

    async def execute(
        self, input_dto: CreateSubscriptionInput
    ) -> CreateSubscriptionOutput:
        customer = await self._customer_repo.get_by_id(input_dto.customer_id)
        if customer is None:
            raise NotFoundError("Billing customer not found")
        if customer.organization_id != input_dto.organization_id:
            raise ConflictError("Billing customer belongs to another organization")

        provider = BillingProvider(input_dto.provider)
        if _value(customer.provider) != _value(provider):
            raise ConflictError("Billing customer provider does not match subscription provider")

        plan = await self._plan_repo.get_by_id(input_dto.plan_id)
        if plan is None:
            raise NotFoundError("Billing plan not found")
        if _value(plan.status) != _value(PlanStatus.active):
            raise ConflictError("Billing plan is not active")

        subscription = Subscription(
            organization_id=input_dto.organization_id,
            customer_id=input_dto.customer_id,
            plan_id=input_dto.plan_id,
            provider=provider,
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
            event_type="subscription.created.v1",
            payload={
                "organization_id": str(saved.organization_id),
                "plan_id": str(saved.plan_id),
                "status": saved.status,
            },
            routing_key="subscription.created.v1",
            idempotency_key=f"billing:subscription.created.v1:{saved.id}",
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
            routing_key=f"payment_event.{input_dto.event_type}",
            idempotency_key=f"billing:payment_event.{input_dto.event_type}:{saved.id}",
        )

        return CreatePaymentEventOutput(event_id=saved.id)


class ListActivePlansUseCase:

    def __init__(self, repo: PlanRepository) -> None:
        self._repo = repo

    async def execute(self) -> list[ListActivePlansOutput]:
        plans = await self._repo.list_active()
        return [ListActivePlansOutput(
            id=p.id,
            code=p.code,
            name=p.name,
            price_usd=p.price_usd,
            status=p.status.value if hasattr(p.status, "value") else p.status,
        ) for p in plans]


class GetOrganizationSubscriptionUseCase:

    def __init__(self, repo: SubscriptionRepository) -> None:
        self._repo = repo

    async def execute(self, input_dto: GetOrganizationSubscriptionInput) -> GetOrganizationSubscriptionOutput | None:
        subscriptions = await self._repo.list_by_organization(input_dto.organization_id)
        if not subscriptions:
            return None
        sub = subscriptions[0]
        return GetOrganizationSubscriptionOutput(
            id=sub.id,
            organization_id=sub.organization_id,
            plan_id=sub.plan_id,
            status=sub.status.value if hasattr(sub.status, "value") else sub.status,
            current_period_end=sub.current_period_end,
        )
