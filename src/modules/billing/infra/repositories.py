from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.billing.domain.entities import Customer, PaymentEvent, Plan, Subscription
from modules.billing.domain.repositories import (
    CustomerRepository,
    PaymentEventRepository,
    PlanRepository,
    SubscriptionRepository,
)
from modules.billing.infra.mappers import (
    customer_entity_to_model,
    customer_model_to_entity,
    payment_event_entity_to_model,
    payment_event_model_to_entity,
    plan_entity_to_model,
    plan_model_to_entity,
    subscription_entity_to_model,
    subscription_model_to_entity,
)
from modules.billing.infra.models import (
    CustomerModel,
    OutboxEventModel,
    PaymentEventModel,
    PlanModel,
    SubscriptionModel,
)
from shared.domain.events import OutboxEventWriter
from shared.infra.repositories.base_repository import BaseRepository


class SQLAlchemyPlanRepository(BaseRepository[PlanModel], PlanRepository):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PlanModel)

    async def save(self, plan: Plan) -> Plan:
        model = plan_entity_to_model(plan)
        self.session.add(model)
        return plan_model_to_entity(model)

    async def get_by_id(self, plan_id: UUID) -> Plan | None:
        model = await self.session.get(PlanModel, plan_id)
        if model is None:
            return None
        return plan_model_to_entity(model)

    async def get_by_code(self, code: str) -> Plan | None:
        stmt = select(PlanModel).where(PlanModel.code == code)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return plan_model_to_entity(model)

    async def list_active(self) -> list[Plan]:
        stmt = select(PlanModel).where(PlanModel.status == "active")
        result = await self.session.execute(stmt)
        return [plan_model_to_entity(m) for m in result.scalars().all()]

    async def delete(self, plan_id: UUID) -> None:
        model = await self.session.get(PlanModel, plan_id)
        if model:
            await self.session.delete(model)


class SQLAlchemyCustomerRepository(BaseRepository[CustomerModel], CustomerRepository):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CustomerModel)

    async def save(self, customer: Customer) -> Customer:
        model = customer_entity_to_model(customer)
        self.session.add(model)
        return customer_model_to_entity(model)

    async def get_by_id(self, customer_id: UUID) -> Customer | None:
        model = await self.session.get(CustomerModel, customer_id)
        if model is None:
            return None
        return customer_model_to_entity(model)

    async def get_by_provider(
        self, provider: str, provider_customer_id: str
    ) -> Customer | None:
        stmt = select(CustomerModel).where(
            CustomerModel.provider == provider,
            CustomerModel.provider_customer_id == provider_customer_id,
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return customer_model_to_entity(model)

    async def list_by_organization(self, organization_id: UUID) -> list[Customer]:
        stmt = select(CustomerModel).where(CustomerModel.organization_id == organization_id)
        result = await self.session.execute(stmt)
        return [customer_model_to_entity(m) for m in result.scalars().all()]

    async def delete(self, customer_id: UUID) -> None:
        model = await self.session.get(CustomerModel, customer_id)
        if model:
            await self.session.delete(model)


class SQLAlchemySubscriptionRepository(
    BaseRepository[SubscriptionModel], SubscriptionRepository
):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SubscriptionModel)

    async def save(self, subscription: Subscription) -> Subscription:
        model = subscription_entity_to_model(subscription)
        self.session.add(model)
        return subscription_model_to_entity(model)

    async def get_by_id(self, subscription_id: UUID) -> Subscription | None:
        model = await self.session.get(SubscriptionModel, subscription_id)
        if model is None:
            return None
        return subscription_model_to_entity(model)

    async def list_by_organization(self, organization_id: UUID) -> list[Subscription]:
        stmt = select(SubscriptionModel).where(SubscriptionModel.organization_id == organization_id)
        result = await self.session.execute(stmt)
        return [subscription_model_to_entity(m) for m in result.scalars().all()]

    async def list_by_customer(self, customer_id: UUID) -> list[Subscription]:
        stmt = select(SubscriptionModel).where(SubscriptionModel.customer_id == customer_id)
        result = await self.session.execute(stmt)
        return [subscription_model_to_entity(m) for m in result.scalars().all()]

    async def delete(self, subscription_id: UUID) -> None:
        model = await self.session.get(SubscriptionModel, subscription_id)
        if model:
            await self.session.delete(model)


class SQLAlchemyPaymentEventRepository(
    BaseRepository[PaymentEventModel], PaymentEventRepository
):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PaymentEventModel)

    async def save(self, event: PaymentEvent) -> PaymentEvent:
        model = payment_event_entity_to_model(event)
        self.session.add(model)
        return payment_event_model_to_entity(model)

    async def get_by_id(self, event_id: UUID) -> PaymentEvent | None:
        model = await self.session.get(PaymentEventModel, event_id)
        if model is None:
            return None
        return payment_event_model_to_entity(model)

    async def get_by_provider_event(
        self, provider: str, provider_event_id: str
    ) -> PaymentEvent | None:
        stmt = select(PaymentEventModel).where(
            PaymentEventModel.provider == provider,
            PaymentEventModel.provider_event_id == provider_event_id,
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return payment_event_model_to_entity(model)


class SQLAlchemyOutboxEventWriter(OutboxEventWriter):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def write(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, Any] | None = None,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> None:
        event = OutboxEventModel(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload or {},
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self._session.add(event)
