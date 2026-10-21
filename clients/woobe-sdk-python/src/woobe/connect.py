from __future__ import annotations

from typing import TYPE_CHECKING

from woobe.targets import Agent, Network

if TYPE_CHECKING:
    from woobe.client import Woobe


class Connect:
    """Namespace used by ``woobe.connect.agent(...)`` and ``network(...)``."""

    def __init__(self, client: Woobe) -> None:
        self._client = client

    def agent(self, *, alias: str, key: str) -> Agent:
        return Agent(client=self._client, alias=alias, key=key)

    def network(self, *, alias: str, key: str) -> Network:
        return Network(client=self._client, alias=alias, key=key)
