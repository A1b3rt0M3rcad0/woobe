from __future__ import annotations

from shared.domain.errors import NotFoundError


class PlanNotFoundError(NotFoundError):
    pass


class CustomerNotFoundError(NotFoundError):
    pass


class SubscriptionNotFoundError(NotFoundError):
    pass
