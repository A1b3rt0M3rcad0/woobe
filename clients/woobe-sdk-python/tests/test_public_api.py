from __future__ import annotations

import pytest
from pydantic import BaseModel

from woobe import Woobe


class SupportOutput(BaseModel):
    message: str
    confidence: float


class SupportContext(BaseModel):
    name: str
    age: int


class _ContractTransport:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def validate_contracts(
        self,
        *,
        key: str,
        output_contract: dict | None,
        external_context: dict | None,
    ) -> dict:
        self.calls.append(
            {
                "key": key,
                "output_contract": output_contract,
                "external_context": external_context,
            }
        )

        def comparison(received: dict | None) -> dict:
            return {
                "valid": True,
                "expected": received,
                "received": received,
                "expected_hash": "same-hash",
                "received_hash": "same-hash",
                "issues": [],
            }

        return {
            "valid": True,
            "target_type": "agent",
            "target_id": "agent-1",
            "environment": "production",
            "release_id": "release-1",
            "release_version": "v1.0.0",
            "output_contract": comparison(output_contract),
            "external_context": comparison(external_context),
        }


def test_chat_is_lazy_and_has_no_runtime_identity_before_iteration() -> None:
    woobe = Woobe(base_url="http://localhost:9999")
    agent = woobe.connect.agent(alias="support", key="runtime-key")

    chat = agent.chat(input="Olá")

    assert chat.session_id is None
    assert chat.run_id is None
    assert chat.target_alias == "support"


@pytest.mark.asyncio
async def test_agent_validates_both_runtime_contracts() -> None:
    transport = _ContractTransport()
    woobe = Woobe(base_url="http://unused")
    woobe._transport = transport  # type: ignore[assignment]
    agent = woobe.connect.agent(alias="support", key="runtime-key")

    result = await agent.validate_contracts(
        output_contract=SupportOutput,
        external_context=SupportContext,
    )

    assert result.valid is True
    assert result.output_contract.valid is True
    assert result.external_context.valid is True
    assert result.release_version == "v1.0.0"
    assert transport.calls == [
        {
            "key": "runtime-key",
            "output_contract": {
                "properties": {
                    "message": {"title": "Message", "type": "string"},
                    "confidence": {"title": "Confidence", "type": "number"},
                },
                "required": ["message", "confidence"],
                "title": "SupportOutput",
                "type": "object",
            },
            "external_context": {
                "properties": {
                    "name": {"title": "Name", "type": "string"},
                    "age": {"title": "Age", "type": "integer"},
                },
                "required": ["name", "age"],
                "title": "SupportContext",
                "type": "object",
                "additionalProperties": False,
            },
        }
    ]


@pytest.mark.asyncio
async def test_output_context_validation_remains_backward_compatible() -> None:
    transport = _ContractTransport()
    woobe = Woobe(base_url="http://unused")
    woobe._transport = transport  # type: ignore[assignment]
    agent = woobe.connect.agent(alias="support", key="runtime-key")

    result = await agent.validate_output_context(SupportOutput)

    assert result.valid is True
    assert result.release_version == "v1.0.0"
    assert transport.calls[0]["external_context"] is None


@pytest.mark.asyncio
async def test_agent_validates_external_context_contract() -> None:
    transport = _ContractTransport()
    woobe = Woobe(base_url="http://unused")
    woobe._transport = transport  # type: ignore[assignment]
    agent = woobe.connect.agent(alias="support", key="runtime-key")

    result = await agent.validate_external_context(SupportContext)

    assert result.valid is True
    assert result.expected_external_context is not None
    assert transport.calls[0]["output_contract"] is None


@pytest.mark.asyncio
async def test_network_uses_same_contract_validation_surface() -> None:
    transport = _ContractTransport()
    woobe = Woobe(base_url="http://unused")
    woobe._transport = transport  # type: ignore[assignment]
    network = woobe.connect.network(alias="support-network", key="network-key")

    result = await network.validate_contracts(
        output_contract=None,
        external_context={
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": [],
            "additionalProperties": False,
        },
    )

    assert result.valid is True
    assert transport.calls[0]["key"] == "network-key"
