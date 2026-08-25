from __future__ import annotations

import pytest

from modules.agent.application.mcp_oauth_metadata_validation import validate_mcp_oauth_metadata
from modules.agent.application.interfaces.ports import ExecutionResult, ToolExecutionPort


class SequenceExecutor(ToolExecutionPort):
    def __init__(self, results: list[ExecutionResult]) -> None:
        self.results = results
        self.calls: list[dict] = []

    async def execute(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_ms: int = 30000,
    ) -> ExecutionResult:
        self.calls.append({"method": method, "url": url, "headers": headers or {}, "body": body, "timeout_ms": timeout_ms})
        if not self.results:
            raise AssertionError("Unexpected executor call")
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_validate_mcp_oauth_metadata_requires_complete_authorization_server_metadata() -> None:
    resource_metadata_url = "https://mcp.example.com/.well-known/oauth-protected-resource"
    executor = SequenceExecutor([
        ExecutionResult(
            success=True,
            status_code=200,
            output={
                "body": {
                    "resource": "https://mcp.example.com",
                    "authorization_servers": ["https://auth.example.com"],
                }
            },
        ),
        ExecutionResult(
            success=True,
            status_code=200,
            output={
                "body": {
                    "issuer": "https://auth.example.com",
                    "authorization_endpoint": "https://auth.example.com/authorize",
                    "token_endpoint": "https://auth.example.com/token",
                }
            },
        ),
    ])

    result = await validate_mcp_oauth_metadata(
        executor,
        server_url="https://mcp.example.com",
        www_authenticate=f"Bearer resource_metadata=\"{resource_metadata_url}\"",
        timeout_ms=5000,
    )

    assert result.status == "valid"
    assert result.authorization_endpoint == "https://auth.example.com/authorize"
    assert result.token_endpoint == "https://auth.example.com/token"
    assert result.protected_resource_metadata == {
        "resource": "https://mcp.example.com",
        "authorization_servers": ["https://auth.example.com"],
    }
    assert [call["method"] for call in executor.calls] == ["GET", "GET"]


@pytest.mark.asyncio
async def test_validate_mcp_oauth_metadata_rejects_incomplete_generic_metadata() -> None:
    resource_metadata_url = "https://mcp.example.com/.well-known/oauth-protected-resource"
    executor = SequenceExecutor([
        ExecutionResult(
            success=True,
            status_code=200,
            output={"body": {"authorization_servers": ["https://auth.example.com"]}},
        ),
        ExecutionResult(success=False, status_code=404, error="Not found"),
        ExecutionResult(success=False, status_code=404, error="Not found"),
    ])

    result = await validate_mcp_oauth_metadata(
        executor,
        server_url="https://mcp.example.com",
        www_authenticate=f"Bearer resource_metadata=\"{resource_metadata_url}\"",
        timeout_ms=5000,
    )

    assert result.status == "invalid_metadata"
    assert result.provider is None
    assert result.authorization_endpoint is None
    assert result.token_endpoint is None
    assert "authorization_endpoint and token_endpoint" in (result.error or "")


@pytest.mark.asyncio
async def test_validate_mcp_oauth_metadata_classifies_run_tools_as_managed_when_incomplete() -> None:
    server_url = "https://skillflow--rafsilva85.run.tools"
    resource_metadata_url = f"{server_url}/.well-known/oauth-protected-resource"
    executor = SequenceExecutor([
        ExecutionResult(
            success=True,
            status_code=200,
            output={"body": {"authorization_servers": ["https://auth.smithery.example"]}},
        ),
        ExecutionResult(success=False, status_code=404, error="Not found"),
        ExecutionResult(success=False, status_code=404, error="Not found"),
    ])

    result = await validate_mcp_oauth_metadata(
        executor,
        server_url=server_url,
        www_authenticate=f"Bearer resource_metadata=\"{resource_metadata_url}\"",
        timeout_ms=5000,
    )

    assert result.status == "provider_managed"
    assert result.provider == "smithery"
    assert result.authorization_endpoint is None
    assert result.token_endpoint is None
