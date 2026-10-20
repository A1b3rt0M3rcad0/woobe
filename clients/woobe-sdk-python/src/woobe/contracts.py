from __future__ import annotations

from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict

RuntimeContractInput: TypeAlias = dict[str, Any] | type[BaseModel] | BaseModel | None
OutputContractInput: TypeAlias = RuntimeContractInput
ExternalContextContractInput: TypeAlias = RuntimeContractInput

# Backward-compatible name kept for pre-release SDK consumers.
OutputContextInput: TypeAlias = OutputContractInput


class RuntimeContractIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    field: str
    expected: Any | None = None
    received: Any | None = None


class RuntimeContractValidation(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    expected: dict[str, Any] | None
    received: dict[str, Any] | None
    expected_hash: str
    received_hash: str
    issues: list[RuntimeContractIssue]


class RuntimeContractsValidation(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    target_type: Literal["agent", "network"]
    target_id: str
    environment: str
    release_id: str
    release_version: str
    output_contract: RuntimeContractValidation
    external_context: RuntimeContractValidation


class OutputContextIssue(BaseModel):
    """Backward-compatible issue shape for validate_output_context()."""

    model_config = ConfigDict(frozen=True)

    code: str
    field: str
    expected: Any | None = None
    received: Any | None = None

    @property
    def message(self) -> str:
        return self.code


class OutputContextValidation(BaseModel):
    """Backward-compatible projection of the unified output contract result."""

    model_config = ConfigDict(frozen=True)

    valid: bool
    target_type: Literal["agent", "network"]
    target_id: str
    environment: str
    release_id: str
    release_version: str
    expected_output_context: dict[str, Any] | None
    received_output_context: dict[str, Any] | None
    expected_hash: str
    received_hash: str
    issues: list[OutputContextIssue]


class ExternalContextValidation(BaseModel):
    """Convenience projection of the unified External Context contract result."""

    model_config = ConfigDict(frozen=True)

    valid: bool
    target_type: Literal["agent", "network"]
    target_id: str
    environment: str
    release_id: str
    release_version: str
    expected_external_context: dict[str, Any] | None
    received_external_context: dict[str, Any] | None
    expected_hash: str
    received_hash: str
    issues: list[RuntimeContractIssue]


def contract_schema(contract: RuntimeContractInput) -> dict[str, Any] | None:
    if contract is None:
        return None
    if isinstance(contract, dict):
        return _inline_local_refs(dict(contract))
    if isinstance(contract, BaseModel):
        return _inline_local_refs(type(contract).model_json_schema())
    if isinstance(contract, type) and issubclass(contract, BaseModel):
        return _inline_local_refs(contract.model_json_schema())
    raise TypeError(
        "contract must be a Pydantic BaseModel type, BaseModel instance, dict, or None"
    )


def output_contract_schema(output_contract: OutputContractInput) -> dict[str, Any] | None:
    return contract_schema(output_contract)


def external_context_contract_schema(
    external_context: ExternalContextContractInput,
) -> dict[str, Any] | None:
    schema = contract_schema(external_context)
    if schema is None:
        return None
    if schema.get("type") == "object" or "properties" in schema:
        schema = dict(schema)
        schema.setdefault("additionalProperties", False)
    return schema


def output_context_schema(output_context: OutputContextInput) -> dict[str, Any] | None:
    """Backward-compatible alias for output_contract_schema()."""

    return output_contract_schema(output_context)


def _inline_local_refs(schema: dict[str, Any]) -> dict[str, Any]:
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict):
        definitions = schema.get("definitions")
    if not isinstance(definitions, dict):
        return schema

    def resolve(value: Any, stack: tuple[str, ...] = ()) -> Any:
        if isinstance(value, list):
            return [resolve(item, stack) for item in value]
        if not isinstance(value, dict):
            return value

        ref = value.get("$ref")
        if isinstance(ref, str):
            name = _local_ref_name(ref)
            if name is not None and name in definitions and name not in stack:
                target = resolve(definitions[name], (*stack, name))
                if isinstance(target, dict):
                    extras = {
                        key: resolve(child, stack)
                        for key, child in value.items()
                        if key != "$ref"
                    }
                    return {**target, **extras}

        return {
            key: resolve(child, stack)
            for key, child in value.items()
            if key not in {"$defs", "definitions"}
        }

    resolved = resolve(schema)
    return resolved if isinstance(resolved, dict) else schema


def _local_ref_name(ref: str) -> str | None:
    for prefix in ("#/$defs/", "#/definitions/"):
        if ref.startswith(prefix):
            return ref.removeprefix(prefix).replace("~1", "/").replace("~0", "~")
    return None
