from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import ValidationError as PydanticValidationError

from woobe.chat import Chat
from woobe.contracts import (
    ExternalContextContractInput,
    ExternalContextValidation,
    OutputContextInput,
    OutputContextIssue,
    OutputContextValidation,
    OutputContractInput,
    RuntimeContractsValidation,
    external_context_contract_schema,
    output_contract_schema,
)
from woobe.errors import WoobeProtocolError

if TYPE_CHECKING:
    from woobe.client import Woobe

TargetKind = Literal["AGENT", "NETWORK"]


class _RuntimeTarget:
    def __init__(self, *, client: Woobe, alias: str, key: str, kind: TargetKind) -> None:
        if not alias.strip():
            raise ValueError("alias must not be empty")
        if not key.strip():
            raise ValueError("key must not be empty")
        self._client = client
        self._alias = alias.strip()
        self._key = key.strip()
        self._kind = kind

    @property
    def alias(self) -> str:
        return self._alias

    async def validate_contracts(
        self,
        *,
        output_contract: OutputContractInput,
        external_context: ExternalContextContractInput,
    ) -> RuntimeContractsValidation:
        data = await self._client._transport.validate_contracts(
            key=self._key,
            output_contract=output_contract_schema(output_contract),
            external_context=external_context_contract_schema(external_context),
        )
        try:
            return RuntimeContractsValidation.model_validate(data)
        except PydanticValidationError as exc:
            raise WoobeProtocolError(
                "Runtime contract validation response has an invalid data envelope"
            ) from exc

    async def validate_output_contract(
        self,
        output_contract: OutputContractInput,
    ) -> OutputContextValidation:
        result = await self.validate_contracts(
            output_contract=output_contract,
            external_context=None,
        )
        comparison = result.output_contract
        return OutputContextValidation(
            valid=comparison.valid,
            target_type=result.target_type,
            target_id=result.target_id,
            environment=result.environment,
            release_id=result.release_id,
            release_version=result.release_version,
            expected_output_context=comparison.expected,
            received_output_context=comparison.received,
            expected_hash=comparison.expected_hash,
            received_hash=comparison.received_hash,
            issues=[
                OutputContextIssue.model_validate(issue.model_dump())
                for issue in comparison.issues
            ],
        )

    async def validate_output_context(
        self,
        output_context: OutputContextInput,
    ) -> OutputContextValidation:
        """Backward-compatible alias for validate_output_contract()."""

        return await self.validate_output_contract(output_context)

    async def validate_external_context(
        self,
        external_context: ExternalContextContractInput,
    ) -> ExternalContextValidation:
        result = await self.validate_contracts(
            output_contract=None,
            external_context=external_context,
        )
        comparison = result.external_context
        return ExternalContextValidation(
            valid=comparison.valid,
            target_type=result.target_type,
            target_id=result.target_id,
            environment=result.environment,
            release_id=result.release_id,
            release_version=result.release_version,
            expected_external_context=comparison.expected,
            received_external_context=comparison.received,
            expected_hash=comparison.expected_hash,
            received_hash=comparison.received_hash,
            issues=comparison.issues,
        )

    def chat(
        self,
        *,
        input: str,
        session_id: str | None = None,
        external_context: dict[str, Any] | None = None,
    ) -> Chat:
        if not input.strip():
            raise ValueError("input must not be empty")
        return Chat(
            transport=self._client._transport,
            target_kind=self._kind,
            target_alias=self._alias,
            key=self._key,
            input=input,
            session_id=session_id,
            external_context=external_context,
            max_reconnect_attempts=self._client._max_reconnect_attempts,
            reconnect_base_delay_seconds=self._client._reconnect_base_delay_seconds,
        )


class Agent(_RuntimeTarget):
    def __init__(self, *, client: Woobe, alias: str, key: str) -> None:
        super().__init__(client=client, alias=alias, key=key, kind="AGENT")


class Network(_RuntimeTarget):
    def __init__(self, *, client: Woobe, alias: str, key: str) -> None:
        super().__init__(client=client, alias=alias, key=key, kind="NETWORK")
