"""Real configuration authority and provider discovery for every credential kind."""

import json
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from uuid import UUID, uuid4

import httpx
import pytest

from modules.agent.composition.composers.list_available_provider_models_composer import (
    list_available_provider_models_composer,
)
from modules.agent.infra.adapters import model_discovery
from modules.core.infra.database.control_key_models import WorkspaceControlKeyModel
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.presentation.contracts import OperationRequest
from shared.security.principal import ControlPlanePrincipal
from tests.integration.cli.test_control_plane_workflow import cli as _live_cli

cli = _live_cli


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider",
    ["deepseek", "openai", "anthropic", "openrouter", "openai_compatible", "custom"],
)
async def test_catalog_requires_exact_consumer_and_environment_approval(
    cli, monkeypatch, provider
):
    value = "disposable-discovery-authorization-canary"
    sent = []
    model_id = {
        "openai": "gpt-4o-mini",
        "deepseek": "deepseek-chat",
        "anthropic": "claude-fixture",
    }.get(provider, "fixture-language")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            header, expected = (
                ("x-api-key", value)
                if provider == "anthropic"
                else ("authorization", "Bearer " + value)
            )
            sent.append(
                {"path": self.path, "authorized": self.headers.get(header) == expected}
            )
            payload = {
                "data": [
                    {
                        "id": model_id,
                        "object": "model",
                        "model_type": "language",
                        "input_modalities": ["text"],
                        "output_modalities": ["text"],
                        "architecture": {
                            "input_modalities": ["text"],
                            "output_modalities": ["text"],
                        },
                        "supported_parameters": ["tools"],
                        "max_input_tokens": 128000,
                        "max_tokens": 8192,
                    }
                ],
                "has_more": False,
            }
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    destination = f"http://127.0.0.1:{server.server_port}"
    # Native OpenAI's public URL is replaced only in this test process. Its
    # adapter, normalizer, configuration resolver and SQL authority stay real.
    monkeypatch.setattr(model_discovery, "OPENAI_MODELS_URL", destination + "/models")
    try:
        project = await cli.data(
            "project",
            "create",
            body={
                "workspace_id": cli.workspace_id,
                "name": "Provider discovery approval",
                "slug": str(uuid4()),
            },
        )
        cli.project_id = project["id"]
        prefix = f"/core/projects/{cli.project_id}/configuration"
        key_name = provider.upper() + "_API_KEY"
        async with httpx.AsyncClient(
            base_url=cli.origin,
            trust_env=False,
            timeout=30,
            headers={"Authorization": "Bearer " + cli.credential},
        ) as client:
            declared = await client.post(
                prefix + "/keys",
                json={
                    "key": key_name,
                    "kind": "secret",
                    "value_format": "token",
                    "description": "Synthetic provider key",
                },
            )
            assert declared.is_success, declared.text
            key_id = declared.json()["data"]["id"]
            for environment in ("draft", "staging", "production"):
                configured = await client.put(
                    prefix + f"/keys/{key_id}/values/{environment}",
                    json={"expected_revision": 0, "value": value},
                )
                assert configured.is_success
                assert value not in configured.text
            definition = {
                "project_id": cli.project_id,
                "provider": provider,
                "name": provider,
                "metadata": {"base_url": destination},
                "authentication": {
                    "type": "api_key",
                    "fields": {
                        "api_key": {"source": "project_environment", "key": key_name}
                    },
                },
            }
            created = await client.post("/ai/credentials", json=definition)
            sibling = await client.post(
                "/ai/credentials", json={**definition, "name": "Different consumer"}
            )
            assert created.is_success and sibling.is_success
            credential_id = created.json()["data"]["id"]
            params = {
                "project_id": cli.project_id,
                "available_for_credential_id": credential_id,
                "capability": "generation",
                "environment": "draft",
            }

            async def denied(environment="draft"):
                response = await client.get(
                    "/ai/provider-models", params={**params, "environment": environment}
                )
                assert response.status_code == 403, response.text
                assert response.json()["data"]["diagnostics"] == [
                    {
                        "code": "CONFIG_USAGE_NOT_AUTHORIZED",
                        "key": key_name,
                        "environment": environment,
                    }
                ]
                assert value not in response.text

            await denied()
            assert not sent, "Unapproved discovery made a provider request"
            grant = {
                "key_id": key_id,
                "consumer_kind": "provider_credential",
                "consumer_scope": sibling.json()["data"]["id"],
                "destination": destination,
                "environments": ["draft"],
                "field_paths": ["/authentication/fields/api_key"],
                "expected_revision": 0,
            }
            other = await client.post(prefix + "/use-policies", json=grant)
            assert other.is_success, other.text
            await denied()
            assert not sent, "Another connection's approval authorized this credential"

            approval = await client.post(
                prefix + "/use-policies",
                json={**grant, "consumer_scope": credential_id},
            )
            assert approval.is_success, approval.text
            usage_path = prefix + f"/keys/{key_id}/usage"
            usage = await client.get(
                usage_path,
                params={
                    "environment": "draft",
                    "consumer_kind": "provider_credential",
                    "consumer_id": credential_id,
                },
            )
            assert usage.is_success, usage.text
            access = usage.json()["data"]["items"]
            assert len(access) == 1 and access[0]["consumer_id"] == credential_id
            assert access[0]["approval"]["state"] == "approved"
            assert access[0]["approval"]["update_policy"]["revision"] == 1
            assert (
                access[0]["approval"]["update_policy"]["destination"]
                == destination + "/"
            )
            assert value not in usage.text
            staging_usage = await client.get(
                usage_path,
                params={"environment": "staging", "consumer_id": credential_id},
            )
            assert (
                staging_usage.json()["data"]["items"][0]["approval"]["state"]
                == "approval_required"
            )
            if provider == "deepseek":
                _, limited = await cli.issue(
                    "workspace",
                    "control-key",
                    "create",
                    body={
                        "name": "Draft metadata reader",
                        "expires_at": (
                            datetime.now(UTC) + timedelta(minutes=30)
                        ).isoformat(),
                        "on_project_create_permissions": [],
                        "project_grants": [
                            {
                                "project_id": cli.project_id,
                                "permissions": [
                                    "project:read",
                                    "project:environment:read",
                                ],
                                "conditions": {"environments": ["draft"]},
                            }
                        ],
                    },
                )
                limited_headers = {"Authorization": "Bearer " + limited}
                draft_keys = await client.get(
                    prefix + "/keys",
                    params={"environment": "draft"},
                    headers=limited_headers,
                )
                assert draft_keys.is_success, draft_keys.text
                assert (
                    draft_keys.json()["data"]["items"][0]["approval"]["state"]
                    == "approved"
                )
                # Editing evidence includes the full policy's environment set;
                # a Draft-only read must not reveal that unscoped metadata.
                limited_usage = await client.get(
                    usage_path, params={"environment": "draft"}, headers=limited_headers
                )
                assert limited_usage.status_code == 403
                limited_policies = await client.get(prefix + f"/keys/{key_id}/use-policies", headers=limited_headers)
                assert limited_policies.status_code == 403
            # Exercise the complete composed handler for all six providers;
            # only the upstream URL is a fixture, including native OpenAI.
            engine = create_engine(Settings())
            try:
                async with create_session_factory(engine)() as session:
                    root = await session.get(
                        WorkspaceControlKeyModel, UUID(cli.root_control_key_id)
                    )
                    principal = ControlPlanePrincipal(
                        api_key_id=root.id,
                        credential_id=root.credential_id,
                        workspace_id=root.workspace_id,
                        key_prefix=root.key_prefix,
                        permissions=frozenset(root.permissions),
                        expires_at=root.expires_at,
                        delegation_expires_at=root.delegation_expires_at,
                        on_project_create_permissions=frozenset(
                            root.on_project_create_permissions
                        ),
                        authenticated_at=datetime.now(UTC),
                    )
            finally:
                await engine.dispose()
            result = await list_available_provider_models_composer()(
                OperationRequest(principal=principal, query_params=params)
            )
            item = result.body["data"][0]
            assert item["id"] == model_id
            assert item["operations"] == ["language.generate"]
            assert item["model_spec"]["provider"] == (
                "openai_compatible" if provider == "custom" else provider
            )
            assert value not in str(result.body)
            assert sent and all(request["authorized"] for request in sent)
            if provider != "openai":
                # The separate API process uses the credential's local base URL
                # for these adapters; it intentionally keeps native OpenAI's
                # production default rather than monkeypatching subprocesses.
                listed = await client.get("/ai/provider-models", params=params)
                assert listed.status_code == 200, listed.text
                assert listed.json()["data"][0]["id"] == model_id
            calls = len(sent)
            await denied("staging")
            await denied("production")
            assert len(sent) == calls, "Discovery fell back to a different environment"
            policy = approval.json()["data"]
            revoked = await client.delete(
                prefix + "/use-policies/" + policy["id"],
                params={"expected_revision": policy["revision"]},
            )
            assert revoked.is_success, revoked.text
            await denied()
            assert len(sent) == calls, "Revoked approval still sent a provider request"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
