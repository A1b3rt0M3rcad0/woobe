from time import monotonic

from shared.infra.admin_idempotency import AdministrativeIdempotency


class AdministrativeRetentionWorker:
    """Remove expired encrypted replay bodies while retaining conflict tombstones."""

    def __init__(self, session_factory, *, interval_seconds: float = 60) -> None:
        self._session_factory = session_factory
        self._interval_seconds = interval_seconds
        self._next_run = 0.0

    async def run(self) -> None:
        if monotonic() < self._next_run:
            return
        async with self._session_factory() as session:
            await AdministrativeIdempotency(
                session, encryption_key=""
            ).purge_expired_secrets()
            await session.commit()
        self._next_run = monotonic() + self._interval_seconds
