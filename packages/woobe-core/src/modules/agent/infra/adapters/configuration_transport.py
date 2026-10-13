"""Resolve pinned credentials only at the actual outbound HTTP boundary."""
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import httpx

from shared.contracts.project_configuration import ConfigurationError


@dataclass(frozen=True, slots=True)
class BoundConfigurationCredential:
    # The callback owns only IDs and transaction services, never material.
    resolve: Callable[[str], Awaitable[str]] = field(repr=False)


class ConfigurationTransport(httpx.AsyncBaseTransport):
    def __init__(self, credential: BoundConfigurationCredential, *, header="Authorization", prefix="Bearer ", transport=None):
        self.credential, self.header, self.prefix = credential, header, prefix
        self.transport = transport if transport is not None else httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request):
        # This runs for each SDK retry and each redirect hop, never per token.
        # Revalidation happens before a pooled connection sends any bytes.
        value = await self.credential.resolve(str(request.url))
        if not isinstance(value, str) or not value or any(c in value for c in "\r\n\x00"):
            raise ConfigurationError("CONFIG_VALUE_INVALID")
        request.headers[self.header] = self.prefix + value
        try:
            response = await self.transport.handle_async_request(request)
            if response.status_code >= 400:
                # Providers sometimes echo request headers in error bodies.
                # Preserve status for retry semantics, not untrusted details.
                await response.aclose()
                return httpx.Response(response.status_code, json={"error": {
                    "message": "Provider request failed", "type": "provider_error"}}, request=request)
            return response
        finally:
            request.headers.pop(self.header, None)
            value = None

    async def aclose(self):
        await self.transport.aclose()


class RejectSynchronousConfigurationTransport(httpx.BaseTransport):
    def handle_request(self, request):
        # Runtime resolution is asynchronous; no unauthenticated fallback.
        raise ConfigurationError("CONFIG_USAGE_NOT_AUTHORIZED")


def configuration_client_options(credential):
    if not isinstance(credential, BoundConfigurationCredential):
        return {"api_key": credential}
    return {"api_key": "woobe-runtime-configuration",
        "http_async_client": httpx.AsyncClient(transport=ConfigurationTransport(credential),
            follow_redirects=False, trust_env=False),
        "http_client": httpx.Client(transport=RejectSynchronousConfigurationTransport(),
            follow_redirects=False, trust_env=False)}


async def configuration_get_json(url, credential, *, header="Authorization", prefix="Bearer ", headers=None):
    transport = ConfigurationTransport(credential, header=header, prefix=prefix)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False, trust_env=False, timeout=20) as client:
        response = await client.get(url, headers=headers or {})
        if response.status_code >= 300:
            from shared.contracts.errors import ValidationError
            raise ValidationError("Provider discovery request failed")
        try:
            data = response.json()
        except ValueError:
            from shared.contracts.errors import ValidationError
            raise ValidationError("Provider returned invalid JSON") from None
        if not isinstance(data, dict):
            from shared.contracts.errors import ValidationError
            raise ValidationError("Provider returned an unsupported response")
        return data
