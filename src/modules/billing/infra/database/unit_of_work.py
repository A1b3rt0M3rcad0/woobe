from __future__ import annotations

from typing import Any

from sqlalchemy.exc import PendingRollbackError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.infra.config.interface.unit_of_work import UnitOfWork

from modules.billing.infra.database.repositories import (
    SQLAlchemyCustomerRepository,
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyPaymentEventRepository,
    SQLAlchemyPlanRepository,
    SQLAlchemySubscriptionRepository,
)


class BillingUnitOfWork(UnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._plans: SQLAlchemyPlanRepository | None = None
        self._customers: SQLAlchemyCustomerRepository | None = None
        self._subscriptions: SQLAlchemySubscriptionRepository | None = None
        self._payment_events: SQLAlchemyPaymentEventRepository | None = None
        self._outbox: SQLAlchemyOutboxEventWriter | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("BillingUnitOfWork session not started")
        return self._session

    @property
    def plans(self) -> SQLAlchemyPlanRepository:
        if self._plans is None:
            self._plans = SQLAlchemyPlanRepository(self)
        return self._plans

    @property
    def customers(self) -> SQLAlchemyCustomerRepository:
        if self._customers is None:
            self._customers = SQLAlchemyCustomerRepository(self)
        return self._customers

    @property
    def subscriptions(self) -> SQLAlchemySubscriptionRepository:
        if self._subscriptions is None:
            self._subscriptions = SQLAlchemySubscriptionRepository(self)
        return self._subscriptions

    @property
    def payment_events(self) -> SQLAlchemyPaymentEventRepository:
        if self._payment_events is None:
            self._payment_events = SQLAlchemyPaymentEventRepository(self)
        return self._payment_events

    @property
    def outbox(self) -> SQLAlchemyOutboxEventWriter:
        if self._outbox is None:
            self._outbox = SQLAlchemyOutboxEventWriter(self)
        return self._outbox

    async def commit(self) -> None:
        if self._session is not None:
            try:
                await self._session.commit()
            except PendingRollbackError:
                await self.rollback()
                raise

    async def rollback(self) -> None:
        if self._session is not None:
            await self._session.rollback()

    async def __aenter__(self) -> BillingUnitOfWork:
        self._session = self._session_factory()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()
        if self._session is not None:
            await self._session.close()
            self._session = None
        self._plans = None
        self._customers = None
        self._subscriptions = None
        self._payment_events = None
        self._outbox = None
