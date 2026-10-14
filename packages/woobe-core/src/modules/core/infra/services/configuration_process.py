"""Expiring protocol advertisement for a host; contains no deployment control."""
import asyncio
import logging
import os
import socket
from uuid import uuid4

from sqlalchemy import delete, select, func

from modules.core.infra.database.configuration_fleet import BRIDGE_CAPABILITY, register_configuration_process
from modules.core.infra.database.configuration_models import ConfigurationProcessModel

logger = logging.getLogger(__name__)


class ConfigurationProcessRegistration:
    def __init__(self, session_factory, *, role, interval=30):
        if role not in {"api", "worker"} or not 1 <= interval <= 30:
            raise ValueError("Invalid configuration process registration")
        self.session_factory = session_factory
        self.identity = f"{role}:{socket.gethostname()[:120]}:{os.getpid()}:{uuid4()}"
        self.interval = interval
        self.task = None

    async def heartbeat(self):
        async with self.session_factory() as session, session.begin():
            await register_configuration_process(session, identity=self.identity,
                capabilities=[BRIDGE_CAPABILITY], ttl_seconds=90)

    async def start(self):
        if self.task is not None:
            raise RuntimeError("Configuration process is already registered")
        await self.heartbeat()
        self.task = asyncio.create_task(self._run(), name="configuration-protocol-heartbeat")

    async def _run(self):
        while True:
            await asyncio.sleep(self.interval)
            try:
                await self.heartbeat()
            except Exception:
                # Failure expires the advertisement and prevents migration.
                # SQL exception text may include parameters; never log it.
                logger.warning("Configuration protocol heartbeat unavailable")

    async def stop(self):
        if self.task is not None:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None
        try:
            async with self.session_factory() as session, session.begin():
                await session.execute(select(func.pg_advisory_xact_lock(7470, 1)))
                await session.execute(delete(ConfigurationProcessModel).where(
                    ConfigurationProcessModel.process_identity == self.identity))
        except Exception:
            # TTL still removes authority if the database is unavailable.
            logger.warning("Configuration protocol retirement unavailable")
