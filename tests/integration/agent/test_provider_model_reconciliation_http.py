"""Real authorization, configuration pins, discovery HTTP and atomic model writes."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from uuid import uuid4

import httpx
import pytest

from tests.integration.cli.test_control_plane_workflow import cli as _live_cli

cli = _live_cli


@pytest.mark.asyncio
async def test_reconciliation_http_is_explicit_authorized_and_revalidates_evidence(cli):
    catalog = {
        "data": [
            {
                "id": "catalog-language",
                "model_type": "language",
                "input_modalities": ["text"],
                "output_modalities": ["text"],
                "supports_tools": True,
                "supports_streaming": True,
            }
        ]
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(catalog).encode()
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
    try:
        project = await cli.data(
            "project",
            "create",
            body={
                "workspace_id": cli.workspace_id,
                "name": "Provider reconciliation",
                "slug": str(uuid4()),
            },
        )
        cli.project_id = project["id"]
        async with httpx.AsyncClient(
            base_url=cli.origin, trust_env=False, timeout=30
        ) as client:
            headers = {"Authorization": "Bearer " + cli.credential}
            credential_response = await client.post(
                "/ai/credentials",
                headers=headers,
                json={
                    "project_id": cli.project_id,
                    "provider": "custom",
                    "name": "Local catalog",
                    "secret": "disposable-catalog-secret",
                    "metadata": {
                        "base_url": f"http://127.0.0.1:{server.server_port}/v1"
                    },
                },
            )
            assert credential_response.status_code == 201, credential_response.text
            credential = credential_response.json()["data"]
            scope = {
                "project_id": cli.project_id,
                "provider_credential_id": credential["id"],
                "environment": "draft",
                "capability": "generation",
            }
            refused = await client.get("/ai/provider-models/sync-preview", params=scope)
            assert refused.status_code in {401, 403}
            missing = await client.get(
                "/ai/provider-models/sync-preview",
                headers=headers,
                params={**scope, "project_id": str(uuid4())},
            )
            assert missing.status_code in {403, 404}
            preview_response = await client.get(
                "/ai/provider-models/sync-preview", headers=headers, params=scope
            )
            assert preview_response.status_code == 200, preview_response.text
            preview = preview_response.json()["data"]
            assert "disposable-catalog-secret" not in preview_response.text
            assert preview["items"][0]["state"] == "new"
            installed = await client.get(
                "/ai/provider-models",
                headers=headers,
                params={"project_id": cli.project_id},
            )
            assert installed.json()["data"] == []
            candidate = preview["items"][0]
            body = {
                **scope,
                "expected_credential_revision": preview["expected_credential_revision"],
                "expected_configuration_revision": preview[
                    "expected_configuration_revision"
                ],
                "selections": [
                    {
                        key: candidate.get(key)
                        for key in (
                            "model_id",
                            "installed_model_id",
                            "expected_model_revision",
                            "candidate_digest",
                        )
                    }
                ],
            }
            first = await client.post(
                "/ai/provider-models/sync-apply", headers=headers, json=body
            )
            assert first.status_code == 200, first.text
            created_id = first.json()["data"]["items"][0]["provider_model_id"]
            repeated = await client.post(
                "/ai/provider-models/sync-apply", headers=headers, json=body
            )
            assert repeated.status_code == 200, repeated.text
            assert repeated.json()["data"]["items"][0]["result"] == "reused"
            assert (
                repeated.json()["data"]["items"][0]["provider_model_id"] == created_id
            )
            catalog["data"][0]["supports_tools"] = False
            stale = await client.post(
                "/ai/provider-models/sync-apply", headers=headers, json=body
            )
            assert stale.status_code == 409, stale.text
            assert stale.json()["data"]["code"] == "CATALOG_CANDIDATE_CHANGED"
            installed = await client.get(
                "/ai/provider-models",
                headers=headers,
                params={"project_id": cli.project_id},
            )
            assert len(installed.json()["data"]) == 1
            assert (
                installed.json()["data"][0]["spec"]["capabilities"]["tool_calling"][
                    "supported"
                ]
                is True
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
