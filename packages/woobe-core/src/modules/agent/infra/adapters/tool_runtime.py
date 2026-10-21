from __future__ import annotations

import base64
import json
import logging
from copy import deepcopy
from dataclasses import replace
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

from modules.agent.application.interfaces.http_tool_contract import (
    HttpToolContractError,
    compile_http_group_route_contract,
    compile_http_tool_contract,
    http_group_route,
    http_route_permission_mode,
    is_http_tool_group,
)
from modules.agent.application.interfaces.ports import (
    ExecutionResult,
    McpSessionStorePort,
    ToolExecutionPort,
    ToolRuntimePort,
    ToolSecretResolverPort,
)
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.interfaces.tool_runtime import (
    MCP_AGENT_SESSION_INPUT_KEY,
    MCP_REMOTE_TOOL_INPUT_KEY,
    ToolRuntimeRegistry,
)
from modules.agent.application.interfaces.tool_types import HTTP_PROTOCOL, MCP_PROTOCOL
from modules.agent.domain.mcp_permissions import (
    MCP_PERMISSION_ALLOW,
    MCP_PERMISSION_DENY,
    mcp_tool_permission_mode,
    parent_tool_permission_mode,
)
from modules.agent.infra.adapters.http_tool_renderer import render_http_tool_request
from modules.agent.infra.adapters.http_artifact_transfer import (
    prepare_http_artifact_transfer,
    scrub_temporary_urls,
)
from modules.agent.infra.adapters.mcp_artifact_transfer import (
    PreparedMcpTransfer,
    prepare_mcp_artifact_transfer,
    scrub_mcp_temporary_urls,
)
from modules.agent.infra.adapters.external_artifact_output import (
    ExternalOutputError,
    _decode_binding,
    exact_source_refs,
    ingest_http_outputs,
    persist_external_output,
    remove_json_pointer,
    scrub_bound_output,
)

from modules.agent.infra.adapters.tool_configuration_transport import configuration_bound_tool, current_tool_configuration

logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = "2025-06-18"

ERROR_HTTP_ERROR = "HTTP_ERROR"
ERROR_HTTP_ROUTE_CONFIG_ERROR = "HTTP_ROUTE_CONFIG_ERROR"
ERROR_HTTP_ROUTE_DENIED_BY_POLICY = "HTTP_ROUTE_DENIED_BY_POLICY"
ERROR_HTTP_ROUTE_REQUIRES_POLICY = "HTTP_ROUTE_REQUIRES_POLICY"
ERROR_MCP_UNSUPPORTED_TRANSPORT = "MCP_UNSUPPORTED_TRANSPORT"
ERROR_MCP_CONFIG_ERROR = "MCP_CONFIG_ERROR"
ERROR_MCP_INITIALIZE_FAILED = "MCP_INITIALIZE_FAILED"
ERROR_MCP_SESSION_INVALID = "MCP_SESSION_INVALID"
ERROR_MCP_TOOL_ERROR = "MCP_TOOL_ERROR"
ERROR_MCP_TOOL_DENIED_BY_POLICY = "MCP_TOOL_DENIED_BY_POLICY"
ERROR_MCP_TOOL_REQUIRES_POLICY = "MCP_TOOL_REQUIRES_POLICY"
ERROR_MCP_ARTIFACT_SCHEMA_CHANGED = "MCP_ARTIFACT_SCHEMA_CHANGED"
ERROR_MCP_ARTIFACT_TRANSFER = "MCP_ARTIFACT_TRANSFER_ERROR"

_MCP_RESOURCE_LINK_LIMIT = 4
_MCP_RESOURCE_URI_LIMIT = 2048
_MCP_RESOURCE_TEXT_LIMIT = 65536
_MCP_RESULT_NODE_LIMIT = 2048


def _bound_mcp_value(
    value: Any,
    *,
    budget: list[int],
    depth: int = 0,
    strip_binary: bool = True,
) -> Any:
    if budget[0] <= 0 or depth > 12:
        return "[MCP result omitted: output limit]"
    budget[0] -= 1
    if isinstance(value, str):
        return value[:_MCP_RESOURCE_TEXT_LIMIT]
    if isinstance(value, list):
        return [
            _bound_mcp_value(
                item, budget=budget, depth=depth + 1, strip_binary=strip_binary
            )
            for item in value[:128]
        ]
    if isinstance(value, dict):
        return {
            str(key)[:128]: _bound_mcp_value(
                item, budget=budget, depth=depth + 1, strip_binary=strip_binary
            )
            for key, item in list(value.items())[:128]
            if not strip_binary or str(key).lower() not in {"data", "blob", "base64", "bytes"}
        }
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:_MCP_RESOURCE_TEXT_LIMIT]


def _error_output(code: str, message: str, protocol: str) -> dict[str, Any]:
    return {"error_code": code, "message": message, "protocol": protocol}


def _failure(
    code: str,
    message: str,
    protocol: str,
    *,
    status_code: int | None = None,
    duration_ms: float | None = None,
) -> ExecutionResult:
    return ExecutionResult(
        success=False,
        status_code=status_code,
        duration_ms=duration_ms,
        error=message,
        output=_error_output(code, message, protocol),
    )


def _safe_tool_name(tool: Any) -> str:
    name = str(getattr(tool, "name", "")).lower().strip().replace(" ", "_").replace("-", "_")
    name = "".join(c for c in name if c.isalnum() or c == "_")
    if not name or name[0].isdigit():
        name = f"tool_{name}"
    return name


def _parse_json_candidate(value: str) -> Any:
    text = value.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def _parse_sse_payload(value: str) -> Any:
    candidates: list[Any] = []
    data_lines: list[str] = []
    for line in value.splitlines():
        if line.startswith("data:"):
            data_lines.append(line[5:].strip())
            continue
        if line.strip() == "" and data_lines:
            parsed = _parse_json_candidate("\n".join(data_lines))
            if parsed is not None:
                candidates.append(parsed)
            data_lines = []
    if data_lines:
        parsed = _parse_json_candidate("\n".join(data_lines))
        if parsed is not None:
            candidates.append(parsed)
    if not candidates:
        return None
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate.get("result"):
            return candidate
    return candidates[-1]


def _parse_body_value(body: Any) -> Any:
    if isinstance(body, str):
        return _parse_json_candidate(body) or _parse_sse_payload(body) or body
    if isinstance(body, dict) and isinstance(body.get("raw"), str):
        raw = body["raw"]
        return _parse_json_candidate(raw) or _parse_sse_payload(raw) or body
    return body


def _extract_mcp_result_body(result: ExecutionResult) -> Any:
    output = result.output or {}
    if isinstance(output, dict) and "body" in output:
        return _parse_body_value(output["body"])
    if result.body:
        return _parse_body_value(result.body)
    return output


def _extract_headers(output: dict[str, Any] | None) -> dict[str, str]:
    if not output or not isinstance(output.get("headers"), dict):
        return {}
    return {str(k).lower(): str(v) for k, v in output["headers"].items()}


def _extract_session_id(output: dict[str, Any] | None) -> str | None:
    headers = _extract_headers(output)
    return headers.get("mcp-session-id") or headers.get("x-mcp-session-id")


def _session_headers(session_id: str | None) -> dict[str, str]:
    if not session_id:
        return {}
    return {"Mcp-Session-Id": session_id}


def _is_mcp_session_failure(result: ExecutionResult, body: Any) -> bool:
    text = ""
    if result.error:
        text += f" {result.error}"
    if isinstance(body, dict):
        text += f" {body.get('error', '')}"
    elif isinstance(body, str):
        text += f" {body}"
    normalized = text.lower()
    return "session" in normalized and any(
        marker in normalized
        for marker in ("invalid", "expired", "missing", "not found", "unknown")
    )


def _mcp_error_message(body: Any) -> str:
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("code") or error
            return str(message)
        if error is not None:
            return str(error)
    return "MCP tool call failed"


def _mcp_policy_failure(
    config: dict[str, Any],
    tool_name: str,
) -> ExecutionResult | None:
    mode = mcp_tool_permission_mode(config, tool_name)
    if mode == MCP_PERMISSION_ALLOW:
        return None
    if mode == MCP_PERMISSION_DENY:
        return _failure(
            ERROR_MCP_TOOL_DENIED_BY_POLICY,
            f"MCP tool '{tool_name}' is denied by policy",
            MCP_PROTOCOL,
        )
    return _failure(
        ERROR_MCP_TOOL_REQUIRES_POLICY,
        f"MCP tool '{tool_name}' must be allowed before execution",
        MCP_PROTOCOL,
    )


def _http_route_policy_failure(route: dict[str, Any]) -> ExecutionResult | None:
    mode = http_route_permission_mode(route)
    route_name = str(
        route.get("operation_id") or route.get("name") or route.get("id") or "route"
    )
    if mode == MCP_PERMISSION_ALLOW:
        return None
    if mode == MCP_PERMISSION_DENY:
        return _failure(
            ERROR_HTTP_ROUTE_DENIED_BY_POLICY,
            f"HTTP route '{route_name}' is denied by policy",
            HTTP_PROTOCOL,
        )
    return _failure(
        ERROR_HTTP_ROUTE_REQUIRES_POLICY,
        f"HTTP route '{route_name}' must be allowed before execution",
        HTTP_PROTOCOL,
    )


class HttpToolRuntime(ToolRuntimePort):
    def __init__(
        self,
        executor: ToolExecutionPort,
        secret_resolver: ToolSecretResolverPort | None = None,
    ) -> None:
        self._executor = executor
        self._secret_resolver = secret_resolver

    @configuration_bound_tool
    async def execute(
        self,
        tool: Any,
        input_data: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        mode = parent_tool_permission_mode(getattr(tool, "config", None) or {})
        if mode != MCP_PERMISSION_ALLOW:
            return _failure("TOOL_DENIED_BY_POLICY" if mode == MCP_PERMISSION_DENY else "TOOL_REQUIRES_POLICY",
                            "Tool permission does not allow execution", HTTP_PROTOCOL)
        return await self._execute_config(
            config=getattr(tool, "config", None) or {},
            input_schema=getattr(tool, "input_schema", None),
            input_data=input_data or {},
            timeout_ms=getattr(tool, "timeout_ms", None) or 30000,
            project_id=getattr(tool, "project_id", None),
            resolve_secrets=True,
            tool_id=str(getattr(tool, "id", "")) or None,
        )

    async def test(
        self,
        config: dict[str, Any],
        input_data: dict[str, Any] | None = None,
        timeout_ms: int = 30000,
    ) -> ExecutionResult:
        return await self._execute_config(
            config=config or {},
            input_schema=None,
            input_data=input_data or {},
            timeout_ms=timeout_ms,
            project_id=None,
            resolve_secrets=False,
            tool_id=None,
        )

    async def _execute_config(
        self,
        *,
        config: dict[str, Any],
        input_schema: dict[str, Any] | None,
        input_data: dict[str, Any],
        timeout_ms: int,
        project_id: UUID | None,
        resolve_secrets: bool,
        tool_id: str | None,
    ) -> ExecutionResult:
        call_input = dict(input_data or {})
        route_id: str | None = None
        route: dict[str, Any] | None = None
        try:
            if is_http_tool_group(config):
                route_id = str(call_input.pop(MCP_REMOTE_TOOL_INPUT_KEY, "") or "")
                if not route_id:
                    return _failure(
                        ERROR_HTTP_ROUTE_CONFIG_ERROR,
                        "HTTP route id is required for grouped HTTP Tools",
                        HTTP_PROTOCOL,
                    )
                route = http_group_route(config, route_id)
                if route is None:
                    return _failure(
                        ERROR_HTTP_ROUTE_CONFIG_ERROR,
                        f"HTTP route '{route_id}' was not found",
                        HTTP_PROTOCOL,
                    )
                policy_failure = _http_route_policy_failure(route)
                if policy_failure is not None:
                    return policy_failure
                contract = compile_http_group_route_contract(config, route_id)
                effective_timeout_ms = int(
                    route.get("timeout_ms") or config.get("timeout_ms") or timeout_ms
                )
            else:
                contract = compile_http_tool_contract(config, input_schema)
                effective_timeout_ms = int(config.get("timeout_ms") or timeout_ms)
            context = current_execution.get()
            if contract.config.get("output_bindings") and not callable(
                getattr(context, "external_output_ingestor", None) if context else None
            ):
                return _failure(
                    "ARTIFACT_ACCESS_DENIED",
                    "Artifact output publication is not authorized for this Run",
                    HTTP_PROTOCOL,
                )

            method = str(contract.config.get("method", "GET")).upper()
            raw_headers = contract.config.get("headers", []) or []
            if (
                resolve_secrets
                and self._secret_resolver is not None
                and project_id is not None
            ):
                headers = await self._secret_resolver.resolve_headers(
                    raw_headers,
                    project_id,
                )
            else:
                headers = {
                    h.get("key", ""): h.get("value", "")
                    for h in raw_headers
                    if h.get("key")
                }
            render_input = dict(call_input)
            for binding in contract.config.get("file_bindings") or []:
                if binding.get("mode") == "url":
                    render_input[str(binding["input_name"])] = "https://temporary-url.invalid/"
            url, headers, body = render_http_tool_request(contract, render_input, headers)
            transfer = await prepare_http_artifact_transfer(
                contract,
                call_input,
                url=url,
                headers=headers,
                body=body,
                transfer_resolver=(context.artifact_transfer_resolver if context else None),
                url_resolver=(context.artifact_transfer_url_resolver if context else None),
                run_id=str(context.run_id) if context and context.run_id else "",
                tool_id=tool_id or "",
            )
            if transfer is not None and transfer.render_inputs:
                url, rendered_headers, body = render_http_tool_request(
                    contract,
                    {**call_input, **transfer.render_inputs},
                    headers,
                )
                headers = {**transfer.headers, **rendered_headers}
                transfer = replace(transfer, body=body, headers=headers)
        except HttpToolContractError as exc:
            output = _error_output(exc.code, str(exc), HTTP_PROTOCOL)
            if exc.missing:
                output["missing_parameters"] = exc.missing
            if route_id:
                output["http_route_id"] = route_id
            logger.warning(
                "tool_runtime_invalid_input protocol=http tool_id=%s route_id=%s code=%s",
                tool_id,
                route_id,
                exc.code,
            )
            return ExecutionResult(success=False, error=str(exc), output=output)
        except (PermissionError, ValueError) as exc:
            code = "ARTIFACT_TRANSFER_DENIED" if isinstance(exc, PermissionError) else "ARTIFACT_TRANSFER_INVALID"
            output = _error_output(code, str(exc), HTTP_PROTOCOL)
            if route_id:
                output["http_route_id"] = route_id
            return ExecutionResult(success=False, error=str(exc), output=output)

        logger.info(
            "tool_runtime_start protocol=http tool_id=%s route_id=%s method=%s contract_hash=%s",
            tool_id,
            route_id,
            method,
            contract.contract_hash,
        )
        recorder = context.run_event_recorder if context else None
        if transfer is not None and recorder is not None:
            await recorder.emit(
                "artifact.transfer.started",
                {
                    **transfer.receipt("pending"),
                    "tool_id": tool_id,
                },
                durable=True,
            )
        output_bindings = contract.config.get("output_bindings") or []
        response_executor = getattr(self._executor, "execute_with_response_content", None)
        execute_request = (
            response_executor
            if response_executor is not None and any(
                binding.get("mode") == "response_body" for binding in output_bindings
            )
            else self._executor.execute
        )
        result = await execute_request(
            method=method,
            url=url,
            headers=headers,
            body=transfer.body if transfer is not None else body,
            timeout_ms=effective_timeout_ms,
        )
        if transfer is not None:
            result.output = scrub_temporary_urls(result.output, transfer)
            if result.error:
                result.error = scrub_temporary_urls(result.error, transfer)
            effect_state = "completed" if result.success else (
                "uncertain"
                if (
                    (result.output or {}).get("effect_state") == "uncertain"
                    or result.status_code is None
                    or result.status_code >= 500
                )
                else "failed"
            )
            result.output = dict(result.output or {})
            result.output["artifact_transfer"] = transfer.receipt(
                effect_state,
                status_code=result.status_code,
            )
            if recorder is not None:
                event_type = (
                    "artifact.transfer.completed"
                    if effect_state == "completed"
                    else "artifact.transfer.uncertain"
                    if effect_state == "uncertain"
                    else "artifact.transfer.failed"
                )
                try:
                    await recorder.emit(
                        event_type,
                        {
                            **transfer.receipt(effect_state, status_code=result.status_code),
                            "tool_id": tool_id,
                        },
                        durable=True,
                    )
                except Exception:
                    result.success = False
                    result.error = "Artifact transfer outcome could not be durably recorded"
                    result.output["artifact_transfer"] = transfer.receipt(
                        "uncertain", status_code=result.status_code,
                    )
        if output_bindings:
            try:
                result = await ingest_http_outputs(
                    result,
                    config=contract.config,
                    input_data=call_input,
                    transfer=transfer,
                    context=context,
                    tool_id=tool_id or "",
                )
            except ExternalOutputError as exc:
                result.response_content = None
                result.response_content_type = None
                result.success = False
                result.error = str(exc)
                result.output = {**dict(result.output or {}), "error_code": exc.code}
        if isinstance(result.output, dict):
            result.output.setdefault("tool_contract_hash", contract.contract_hash)
            if route is not None:
                result.output.setdefault("http_route_id", str(route.get("id") or route_id))
                result.output.setdefault(
                    "http_operation_id",
                    str(route.get("operation_id") or ""),
                )
                result.output.setdefault("http_method", method)
        if result.success:
            logger.info(
                "tool_runtime_success protocol=http tool_id=%s route_id=%s duration_ms=%s",
                tool_id,
                route_id,
                result.duration_ms,
            )
            return result
        logger.warning(
            "tool_runtime_failure protocol=http tool_id=%s route_id=%s status_code=%s error=%s",
            tool_id,
            route_id,
            result.status_code,
            result.error,
        )
        if isinstance(result.output, dict):
            result.output.setdefault("error_code", ERROR_HTTP_ERROR)
            result.output.setdefault("protocol", HTTP_PROTOCOL)
        else:
            result.output = _error_output(
                ERROR_HTTP_ERROR,
                result.error or "HTTP tool call failed",
                HTTP_PROTOCOL,
            )
            result.output["tool_contract_hash"] = contract.contract_hash
            if route_id:
                result.output["http_route_id"] = route_id
        return result

    def to_openai_definition(self, tool: Any) -> dict[str, Any]:
        config = getattr(tool, "config", None) or {}
        if is_http_tool_group(config):
            return {
                "type": "function",
                "function": {
                    "name": _safe_tool_name(tool),
                    "description": getattr(tool, "description", None)
                    or "Grouped HTTP API",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            }
        contract = compile_http_tool_contract(
            config,
            getattr(tool, "input_schema", None),
        )
        return {
            "type": "function",
            "function": {
                "name": _safe_tool_name(tool),
                "description": getattr(tool, "description", None)
                or f"HTTP {config.get('method', 'GET')} {config.get('url', '')}",
                "parameters": contract.input_schema,
            },
        }


class McpToolRuntime(ToolRuntimePort):
    def __init__(
        self,
        executor: ToolExecutionPort,
        secret_resolver: ToolSecretResolverPort | None = None,
        session_store: McpSessionStorePort | None = None,
        session_ttl_seconds: int = 3600,
        auth_header_provider: Any | None = None,
    ) -> None:
        self._executor = executor
        self._secret_resolver = secret_resolver
        self._session_store = session_store
        self._session_ttl_seconds = session_ttl_seconds
        self._auth_header_provider = auth_header_provider

    @configuration_bound_tool
    async def execute(
        self,
        tool: Any,
        input_data: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        config = getattr(tool, "config", None) or {}
        mode = parent_tool_permission_mode(config)
        if mode != MCP_PERMISSION_ALLOW:
            return _failure("TOOL_DENIED_BY_POLICY" if mode == MCP_PERMISSION_DENY else "TOOL_REQUIRES_POLICY",
                            "Tool permission does not allow execution", MCP_PROTOCOL)
        return await self._call_mcp_tool(
            tool=tool,
            config=config,
            input_data=input_data or {},
            timeout_ms=getattr(tool, "timeout_ms", None)
            or int(config.get("timeout_ms") or 30000),
            project_id=getattr(tool, "project_id", None),
            provider_id=str(getattr(tool, "id", "")) or None,
            resolve_secrets=True,
        )

    async def test(
        self,
        config: dict[str, Any],
        input_data: dict[str, Any] | None = None,
        timeout_ms: int = 30000,
    ) -> ExecutionResult:
        return await self._call_mcp_tool(
            tool=None,
            config=config or {},
            input_data=input_data or {},
            timeout_ms=timeout_ms,
            project_id=None,
            provider_id=None,
            resolve_secrets=False,
        )

    async def _initialize_session(
        self,
        *,
        url: str,
        base_headers: dict[str, str],
        timeout_ms: int,
    ) -> tuple[ExecutionResult | None, str | None, dict[str, str]]:
        initialize_payload = {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "Woobe", "version": "0.14.0"},
            },
        }
        init_result = await self._executor.execute(
            method="POST",
            url=url,
            headers=base_headers,
            body=json.dumps(initialize_payload),
            timeout_ms=timeout_ms,
        )
        if not init_result.success:
            init_result.output = init_result.output or _error_output(
                ERROR_MCP_INITIALIZE_FAILED,
                init_result.error or "MCP initialize failed",
                MCP_PROTOCOL,
            )
            return init_result, None, base_headers
        session_id = _extract_session_id(
            init_result.output if isinstance(init_result.output, dict) else None
        )
        request_headers = {**base_headers, **_session_headers(session_id)}
        initialized_payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        await self._executor.execute(
            method="POST",
            url=url,
            headers=request_headers,
            body=json.dumps(initialized_payload),
            timeout_ms=timeout_ms,
        )
        return None, session_id, request_headers

    async def _call_remote_tool(
        self,
        *,
        url: str,
        headers: dict[str, str],
        tool_name: str,
        arguments: dict[str, Any],
        timeout_ms: int,
    ) -> ExecutionResult:
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        result = await self._executor.execute(
            method="POST",
            url=url,
            headers=headers,
            body=json.dumps(payload),
            timeout_ms=timeout_ms,
        )
        body = _extract_mcp_result_body(result)
        if not result.success:
            if not isinstance(result.output, dict):
                result.output = _error_output(
                    ERROR_MCP_TOOL_ERROR,
                    result.error or "MCP tool call failed",
                    MCP_PROTOCOL,
                )
            return result
        if isinstance(body, dict) and body.get("error"):
            message = _mcp_error_message(body)
            return ExecutionResult(
                success=False,
                status_code=result.status_code,
                output={
                    **body,
                    "error_code": ERROR_MCP_TOOL_ERROR,
                    "protocol": MCP_PROTOCOL,
                },
                duration_ms=result.duration_ms,
                error=message,
            )
        output = body.get("result") if isinstance(body, dict) else body
        if isinstance(output, dict) and output.get("isError") is True:
            return ExecutionResult(
                success=False,
                status_code=result.status_code,
                output={"mcp": output, "error_code": ERROR_MCP_TOOL_ERROR, "protocol": MCP_PROTOCOL},
                duration_ms=result.duration_ms,
                error=_mcp_error_message(output),
            )
        return ExecutionResult(
            success=True,
            status_code=result.status_code,
            output={"mcp": output},
            duration_ms=result.duration_ms,
        )

    async def _remote_jsonrpc(
        self,
        *,
        url: str,
        headers: dict[str, str],
        method: str,
        params: dict[str, Any],
        timeout_ms: int,
    ) -> tuple[ExecutionResult, Any]:
        response = await self._executor.execute(
            method="POST",
            url=url,
            headers=headers,
            body=json.dumps({"jsonrpc": "2.0", "id": str(uuid4()), "method": method, "params": params}),
            timeout_ms=timeout_ms,
        )
        return response, _extract_mcp_result_body(response)

    async def _verify_negotiated_schema(
        self,
        *,
        url: str,
        headers: dict[str, str],
        tool_name: str,
        expected_schema: dict[str, Any],
        timeout_ms: int,
    ) -> bool:
        cursor: str | None = None
        for _page in range(4):
            params = {"cursor": cursor} if cursor else {}
            response, body = await self._remote_jsonrpc(
                url=url,
                headers=headers,
                method="tools/list",
                params=params,
                timeout_ms=timeout_ms,
            )
            if not response.success or not isinstance(body, dict) or body.get("error"):
                return False
            result = body.get("result")
            tools = result.get("tools") if isinstance(result, dict) else None
            if not isinstance(tools, list):
                return False
            for remote_tool in tools:
                if not isinstance(remote_tool, dict) or remote_tool.get("name") != tool_name:
                    continue
                schema = remote_tool.get("inputSchema")
                return isinstance(schema, dict) and schema == expected_schema
            next_cursor = result.get("nextCursor") if isinstance(result, dict) else None
            if not isinstance(next_cursor, str) or not next_cursor or len(next_cursor) > 1024:
                return False
            cursor = next_cursor
        return False

    async def _normalize_resource_links(
        self,
        *,
        url: str,
        headers: dict[str, str],
        result: ExecutionResult,
        timeout_ms: int,
    ) -> ExecutionResult:
        output = result.output
        if not isinstance(output, dict) or not isinstance(output.get("mcp"), dict):
            return result
        mcp_result = dict(output["mcp"])
        mcp_result = {
            key: _bound_mcp_value(
                value,
                budget=[_MCP_RESULT_NODE_LIMIT],
                strip_binary=key == "content",
            )
            for key, value in mcp_result.items()
        }
        content = mcp_result.get("content")
        if not isinstance(content, list):
            return result
        normalized: list[Any] = []
        read_count = 0
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "resource_link":
                normalized.append(block)
                continue
            name = str(block.get("name") or block.get("title") or "MCP resource")[:200]
            uri = block.get("uri")
            try:
                parsed_uri = urlparse(uri) if isinstance(uri, str) else None
            except ValueError:
                parsed_uri = None
            if (
                read_count >= _MCP_RESOURCE_LINK_LIMIT
                or not isinstance(uri, str)
                or not uri
                or len(uri) > _MCP_RESOURCE_URI_LIMIT
                or any(char in uri for char in "\r\n\x00")
                or parsed_uri is None
                or parsed_uri.scheme not in {"mcp", "http", "https"}
                or parsed_uri.username is not None
                or parsed_uri.password is not None
            ):
                normalized.append({"type": "resource", "name": name, "text": "[MCP resource omitted: invalid or over limit]"})
                continue
            read_count += 1
            response, body = await self._remote_jsonrpc(
                url=url,
                headers=headers,
                method="resources/read",
                params={"uri": uri},
                timeout_ms=timeout_ms,
            )
            resource_result = body.get("result") if isinstance(body, dict) else None
            resources = resource_result.get("contents") if isinstance(resource_result, dict) else None
            text_parts: list[str] = []
            remaining = _MCP_RESOURCE_TEXT_LIMIT
            if response.success and isinstance(resources, list):
                for resource in resources[:_MCP_RESOURCE_LINK_LIMIT]:
                    if not isinstance(resource, dict) or not isinstance(resource.get("text"), str):
                        continue
                    text = resource["text"][:remaining]
                    text_parts.append(text)
                    remaining -= len(text)
                    if remaining <= 0:
                        break
            text = "\n".join(text_parts)
            if not text:
                text = "[MCP resource contained no bounded text content]"
            normalized.append({
                "type": "resource",
                "name": name,
                "mimeType": str(block.get("mimeType") or "text/plain")[:128],
                "text": text,
            })
        mcp_result = dict(mcp_result)
        mcp_result["content"] = normalized
        result.output = {**output, "mcp": mcp_result}
        return result

    async def _call_tool_with_artifacts(
        self,
        *,
        url: str,
        headers: dict[str, str],
        tool_name: str,
        arguments: dict[str, Any],
        config: dict[str, Any],
        timeout_ms: int,
        tool_id: str,
    ) -> ExecutionResult:
        context = current_execution.get()
        bindings = config.get("file_bindings") or []
        original_arguments = dict(arguments)
        transfer: PreparedMcpTransfer | None = None
        if bindings:
            expected_schema = config.get("discovered_input_schema")
            if not isinstance(expected_schema, dict) or not await self._verify_negotiated_schema(
                url=url,
                headers=headers,
                tool_name=tool_name,
                expected_schema=expected_schema,
                timeout_ms=timeout_ms,
            ):
                return _failure(
                    ERROR_MCP_ARTIFACT_SCHEMA_CHANGED,
                    "MCP Tool schema changed or could not be verified before Artifact transfer",
                    MCP_PROTOCOL,
                )
            try:
                transfer = await prepare_mcp_artifact_transfer(
                    config,
                    arguments,
                    server_url=url,
                    transfer_resolver=(context.artifact_transfer_resolver if context else None),
                    url_resolver=(context.artifact_transfer_url_resolver if context else None),
                    run_id=str(context.run_id) if context and context.run_id else "",
                    tool_id=tool_id,
                )
            except (PermissionError, ValueError, TypeError) as exc:
                return _failure(ERROR_MCP_ARTIFACT_TRANSFER, str(exc), MCP_PROTOCOL)
            if transfer is None:
                return _failure(ERROR_MCP_ARTIFACT_TRANSFER, "MCP Artifact transfer binding was empty", MCP_PROTOCOL)
            recorder = context.run_event_recorder if context else None
            if recorder is not None:
                await recorder.emit(
                    "artifact.transfer.started",
                    {**transfer.receipt("pending"), "tool_id": tool_id},
                    durable=True,
                )
            arguments = transfer.arguments

        result = await self._call_remote_tool(
            url=url,
            headers=headers,
            tool_name=tool_name,
            arguments=arguments,
            timeout_ms=timeout_ms,
        )
        if transfer is not None:
            result.output = scrub_mcp_temporary_urls(result.output, transfer)
            if result.error:
                result.error = scrub_mcp_temporary_urls(result.error, transfer)
            effect_state = "completed" if result.success else (
                "uncertain" if result.status_code is None or result.status_code >= 500 else "failed"
            )
            result.output = dict(result.output or {})
            result.output["artifact_transfer"] = transfer.receipt(effect_state)
            recorder = context.run_event_recorder if context else None
            if recorder is not None:
                event_type = {
                    "completed": "artifact.transfer.completed",
                    "failed": "artifact.transfer.failed",
                    "uncertain": "artifact.transfer.uncertain",
                }[effect_state]
                try:
                    await recorder.emit(
                        event_type,
                        {**transfer.receipt(effect_state), "tool_id": tool_id},
                        durable=True,
                    )
                except Exception:
                    result.success = False
                    result.error = "Artifact transfer outcome could not be durably recorded"
                    result.output["artifact_transfer"] = transfer.receipt("uncertain")
        if config.get("output_bindings") and result.success:
            try:
                result = await self._ingest_mcp_outputs(
                    result,
                    config=config,
                    url=url,
                    headers=headers,
                    timeout_ms=timeout_ms,
                    input_data=original_arguments,
                    transfer=transfer,
                    context=context,
                    tool_id=tool_id,
                )
            except ExternalOutputError as exc:
                result.success = False
                result.error = str(exc)
                result.output = {**dict(result.output or {}), "error_code": exc.code}
        return await self._normalize_resource_links(
            url=url,
            headers=headers,
            result=result,
            timeout_ms=timeout_ms,
        )

    async def _ingest_mcp_outputs(
        self,
        result: ExecutionResult,
        *,
        config: dict[str, Any],
        url: str,
        headers: dict[str, str],
        timeout_ms: int,
        input_data: dict[str, Any],
        transfer: PreparedMcpTransfer | None,
        context,
        tool_id: str,
    ) -> ExecutionResult:
        raw_bindings = config.get("output_bindings") or []
        bindings = [
            _decode_binding(item, allowed_modes={"json_base64", "mcp_resource"})
            for item in raw_bindings
        ]
        output = result.output if isinstance(result.output, dict) else {}
        mcp_result = output.get("mcp")
        if not isinstance(mcp_result, dict):
            raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "MCP Tool returned no structured output")
        ingestor = getattr(context, "external_output_ingestor", None) if context else None
        if not callable(ingestor):
            raise ExternalOutputError("ARTIFACT_ACCESS_DENIED", "Artifact output publication is not authorized for this Run")
        structured = mcp_result.get("structuredContent")
        source_refs = exact_source_refs(config, input_data, transfer)
        published = []
        consumed_resources: set[str] = set()
        for binding in bindings:
            source = {"body": structured}
            content_type = (
                binding.content_types[0]
                if len(binding.content_types) == 1
                else None
            )
            effective_binding = binding
            if binding.mode == "mcp_resource":
                blocks = mcp_result.get("content")
                links = [
                    block for block in blocks or []
                    if isinstance(block, dict)
                    and block.get("type") == "resource_link"
                    and (block.get("name") or block.get("title")) == binding.resource_name
                ]
                if len(links) != 1 or not isinstance(links[0].get("uri"), str):
                    raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "MCP Tool did not return the configured resource link")
                uri = links[0]["uri"]
                consumed_resources.add(binding.resource_name or "")
                try:
                    parsed_uri = urlparse(uri)
                except ValueError as error:
                    raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "MCP resource URI is invalid") from error
                if (
                    len(uri) > _MCP_RESOURCE_URI_LIMIT
                    or parsed_uri.scheme not in {"mcp", "http", "https"}
                    or parsed_uri.username is not None
                    or parsed_uri.password is not None
                    or any(char in uri for char in "\r\n\x00")
                ):
                    raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "MCP resource URI is outside the negotiated resource contract")
                response, body = await self._remote_jsonrpc(
                    url=url,
                    headers=headers,
                    method="resources/read",
                    params={"uri": uri},
                    timeout_ms=timeout_ms,
                )
                read_result = body.get("result") if isinstance(body, dict) else None
                contents = read_result.get("contents") if isinstance(read_result, dict) else None
                if not response.success or not isinstance(contents, list) or len(contents) != 1 or not isinstance(contents[0], dict):
                    raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "MCP resource result is missing or ambiguous")
                resource = contents[0]
                content_type = resource.get("mimeType") or content_type
                if isinstance(resource.get("text"), str) and "blob" not in resource:
                    raw_content = resource["text"].encode("utf-8")
                elif isinstance(resource.get("blob"), str) and "text" not in resource:
                    try:
                        raw_content = base64.b64decode(resource["blob"], validate=True)
                    except (ValueError, TypeError) as error:
                        raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "MCP resource returned invalid base64") from error
                else:
                    raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "MCP resource must contain one text or binary value")
                if len(raw_content) > binding.max_bytes:
                    raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "MCP resource exceeds its configured byte limit")
                source = {"body": structured, "response_content": raw_content}
                effective_binding = binding.model_copy(update={"mode": "response_body", "resource_name": None})
            elif binding.mode == "json_base64" and content_type is None:
                raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "MCP JSON output binding must select one media type or a content type field")
            published.append(await persist_external_output(
                binding=effective_binding,
                source=source,
                default_content_type=content_type,
                ingestor=ingestor,
                run_id=str(context.run_id) if context and context.run_id else "",
                tool_id=tool_id,
                source_refs=source_refs,
            ))
            if binding.mode == "json_base64" and binding.data_pointer:
                structured = remove_json_pointer(structured, binding.data_pointer)
        result.output = dict(output)
        result.output["output_artifacts"] = published
        mcp_result = dict(mcp_result)
        if consumed_resources and isinstance(mcp_result.get("content"), list):
            mcp_result["content"] = [
                {
                    "type": "text",
                    "text": "[MCP resource persisted as an authorized Artifact output]",
                }
                if isinstance(block, dict)
                and block.get("type") == "resource_link"
                and (block.get("name") or block.get("title")) in consumed_resources
                else block
                for block in mcp_result["content"]
            ]
        if structured is not None:
            mcp_result["structuredContent"] = structured
        result.output["mcp"] = mcp_result
        return result

    async def _auth_headers_for(self, tool: Any | None) -> dict[str, str]:
        if tool is None or self._auth_header_provider is None:
            return {}
        try:
            method = getattr(
                self._auth_header_provider,
                "authorization_" + "headers_for",
            )
            return await method(tool)
        except Exception as exc:
            logger.warning(
                "mcp_auth_header_provider_failed tool_id=%s error=%s",
                getattr(tool, "id", None),
                exc,
            )
            return {}

    async def _call_mcp_tool(
        self,
        *,
        tool: Any | None,
        config: dict[str, Any],
        input_data: dict[str, Any],
        timeout_ms: int,
        project_id: UUID | None,
        provider_id: str | None,
        resolve_secrets: bool,
    ) -> ExecutionResult:
        server = config.get("server", {}) or {}
        transport = server.get("transport", "streamable_http")
        if transport != "streamable_http":
            return _failure(
                ERROR_MCP_UNSUPPORTED_TRANSPORT,
                f"MCP transport '{transport}' is not supported by this runtime",
                MCP_PROTOCOL,
            )
        call_input = dict(input_data or {})
        url = server.get("url") or config.get("url")
        tool_name = call_input.pop(MCP_REMOTE_TOOL_INPUT_KEY, None) or config.get(
            "tool_name"
        )
        agent_session_id = call_input.pop(MCP_AGENT_SESSION_INPUT_KEY, None)
        if not url:
            return _failure(
                ERROR_MCP_CONFIG_ERROR,
                "MCP server.url is required",
                MCP_PROTOCOL,
            )
        if not tool_name:
            return _failure(
                ERROR_MCP_CONFIG_ERROR,
                "MCP tool_name is required",
                MCP_PROTOCOL,
            )
        policy_failure = _mcp_policy_failure(config, str(tool_name))
        if policy_failure is not None:
            return policy_failure
        context = current_execution.get()
        if config.get("output_bindings") and not callable(
            getattr(context, "external_output_ingestor", None) if context else None
        ):
            return _failure(
                "ARTIFACT_ACCESS_DENIED",
                "Artifact output publication is not authorized for this Run",
                MCP_PROTOCOL,
            )
        raw_headers = config.get("server_headers") or server.get("headers") or []
        if (
            resolve_secrets
            and self._secret_resolver is not None
            and project_id is not None
        ):
            configured_headers = await self._secret_resolver.resolve_headers(
                raw_headers,
                project_id,
            )
        else:
            configured_headers = {
                h.get("key", ""): h.get("value", "")
                for h in raw_headers
                if h.get("key")
            }
        base_headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
            **configured_headers,
            **(await self._auth_headers_for(tool)),
        }
        session_cache_key = None
        if agent_session_id and provider_id and self._session_store is not None:
            session_cache_key = f"{agent_session_id}:{provider_id}"
            configuration_binding = current_tool_configuration.get()
            if configuration_binding is not None:
                # Never share authenticated MCP sessions across accepted Runs.
                session_cache_key += ":configuration:" + str(configuration_binding[1])
            cached_session_id = await self._session_store.get(session_cache_key)
            if cached_session_id:
                logger.info(
                    "mcp_session_cache_hit provider_id=%s agent_session_id=%s remote_tool=%s",
                    provider_id,
                    agent_session_id,
                    tool_name,
                )
                cached_headers = {**base_headers, **_session_headers(cached_session_id)}
                if config.get("file_bindings"):
                    result = await self._call_tool_with_artifacts(
                        url=str(url),
                        headers=cached_headers,
                        tool_name=str(tool_name),
                        arguments=call_input,
                        config=config,
                        timeout_ms=timeout_ms,
                        tool_id=provider_id or "",
                    )
                else:
                    result = await self._call_remote_tool(
                        url=str(url),
                        headers=cached_headers,
                        tool_name=str(tool_name),
                        arguments=call_input,
                        timeout_ms=timeout_ms,
                    )
                body = _extract_mcp_result_body(result)
                if result.success or not _is_mcp_session_failure(result, body):
                    return result
                # A transfer may have reached the peer even when the cached
                # session response is invalid. Never retry that side effect.
                if config.get("file_bindings"):
                    return result
                logger.info(
                    "mcp_session_invalidated provider_id=%s agent_session_id=%s",
                    provider_id,
                    agent_session_id,
                )
                await self._session_store.delete(session_cache_key)
            else:
                logger.info(
                    "mcp_session_cache_miss provider_id=%s agent_session_id=%s",
                    provider_id,
                    agent_session_id,
                )
        init_failure, session_id, request_headers = await self._initialize_session(
            url=str(url),
            base_headers=base_headers,
            timeout_ms=timeout_ms,
        )
        if init_failure is not None:
            return init_failure
        if session_cache_key and session_id:
            await self._session_store.set(
                session_cache_key,
                session_id,
                self._session_ttl_seconds,
            )
            logger.info(
                "mcp_session_initialized provider_id=%s agent_session_id=%s",
                provider_id,
                agent_session_id,
            )
        return await self._call_tool_with_artifacts(
            url=str(url),
            headers=request_headers,
            tool_name=str(tool_name),
            arguments=call_input,
            config=config,
            timeout_ms=timeout_ms,
            tool_id=provider_id or "",
        )

    def to_openai_definition(self, tool: Any) -> dict[str, Any]:
        config = getattr(tool, "config", None) or {}
        server = config.get("server", {}) or {}
        input_schema = (
            getattr(tool, "input_schema", None)
            or config.get("discovered_input_schema")
            or config.get("input_schema")
            or {"type": "object", "properties": {}, "required": []}
        )
        input_schema = deepcopy(input_schema)
        if config.get("file_bindings") and isinstance(input_schema, dict):
            properties = input_schema.setdefault("properties", {})
            required = input_schema.setdefault("required", [])
            if isinstance(properties, dict) and isinstance(required, list):
                for binding in config.get("file_bindings") or []:
                    name = str(binding.get("input_name") or "")
                    properties[name] = {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "artifact_id": {"type": "string"},
                            "revision_id": {"type": "string"},
                        },
                        "required": ["artifact_id", "revision_id"],
                        "description": "Exact authorized Artifact revision reference.",
                    }
                    if name not in required:
                        required.append(name)
        tool_name = config.get("tool_name", "")
        server_name = server.get("name") or server.get("url") or "remote-server"
        return {
            "type": "function",
            "function": {
                "name": _safe_tool_name(tool),
                "description": getattr(tool, "description", None)
                or config.get("description")
                or f"MCP {server_name}/{tool_name}",
                "parameters": input_schema,
            },
        }


def build_default_tool_runtime_registry(
    executor: ToolExecutionPort,
    secret_resolver: ToolSecretResolverPort | None = None,
    mcp_session_store: McpSessionStorePort | None = None,
    mcp_session_ttl_seconds: int = 3600,
    mcp_auth_header_provider: Any | None = None,
) -> ToolRuntimeRegistry:
    return ToolRuntimeRegistry(
        {
            HTTP_PROTOCOL: HttpToolRuntime(executor, secret_resolver),
            MCP_PROTOCOL: McpToolRuntime(
                executor,
                secret_resolver,
                session_store=mcp_session_store,
                session_ttl_seconds=mcp_session_ttl_seconds,
                auth_header_provider=mcp_auth_header_provider,
            ),
        }
    )
