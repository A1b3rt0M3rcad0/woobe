from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from modules.billing.domain.entities import Customer, PaymentEvent, Plan, Subscription


class PlanRepository(ABC):

    @abstractmethod
    async def save(self, plan: Plan) -> Plan: ...

    @abstractmethod
    async def get_by_id(self, plan_id: UUID) -> Plan | None: ...

    @abstractmethod
    async def get_by_code(self, code: str) -> Plan | None: ...

    @abstractmethod
    async def list_active(self) -> list[Plan]: ...

    @abstractmethod
    async def delete(self, plan_id: UUID) -> None: ...


class CustomerRepository(ABC):

    @abstractmethod
    async def save(self, customer: Customer) -> Customer: ...

    @abstractmethod
    async def get_by_id(self, customer_id: UUID) -> Customer | None: ...

    @abstractmethod
    async def get_by_provider(
        self, provider: str, provider_customer_id: str
    ) -> Customer | None: ...

    @abstractmethod
    async def list_by_organization(
        self, organization_id: UUID
    ) -> list[Customer]: ...

    @abstractmethod
    async def delete(self, customer_id: UUID) -> None: ...


class SubscriptionRepository(ABC):

    @abstractmethod
    async def save(self, subscription: Subscription) -> Subscription: ...

    @abstractmethod
    async def get_by_id(self, subscription_id: UUID) -> Subscription | None: ...

    @abstractmethod
    async def list_by_organization(
        self, organization_id: UUID
    ) -> list[Subscription]: ...

    @abstractmethod
    async def list_by_customer(
        self, customer_id: UUID
    ) -> list[Subscription]: ...

    @abstractmethod
    async def delete(self, subscription_id: UUID) -> None: ...


class PaymentEventRepository(ABC):

    @abstractmethod
    async def save(self, event: PaymentEvent) -> PaymentEvent: ...

    @abstractmethod
    async def get_by_id(self, event_id: UUID) -> PaymentEvent | None: ...

    @abstractmethod
    async def get_by_provider_event(
        self, provider: str, provider_event_id: str
    ) -> PaymentEvent | None: ...
