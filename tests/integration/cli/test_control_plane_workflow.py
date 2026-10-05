"""The pinned Go CLI talks to a live API, PostgreSQL, workers and fake provider.

Only the bootstrap authority is seeded. Every business resource is created through
public HTTP commands. CLI absence is a failure in the backend CI contract.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete

from modules.core.infra.database.control_key_models import WorkspaceControlKeyModel
from modules.identity.infra.database.models import WorkspaceModel
from modules.identity.infra.database import authority_models  # noqa: F401 -- register FK targets before bootstrap ORM flush
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.security.api_keys import issue_control_api_key
from shared.security.control_plane import (
    PROJECT_CONTROL_PERMISSIONS,
    WORKSPACE_CONTROL_PERMISSIONS,
)

CLI_COMMIT = "659baea23458380b84bc7059d2a544c9c06fc1f5"


class Cli:
    def __init__(self, binary, origin, workspace_id, credential, directory):
        self.binary, self.origin, self.workspace_id = binary, origin, str(workspace_id)
        self.credential, self.directory = credential, directory
        self.project_id = None
        self.secret_values = {credential}
        self.evidence = []
        self.openapi_sha256 = None

    async def run(self, *arguments, body=None, key=None, runtime_key=None, expected=0):
        args = [
            self.binary,
            "--config",
            str(self.directory / "config.json"),
            "--api-url",
            self.origin,
            "--workspace",
            self.workspace_id,
            "--no-input",
            "--timeout",
            "90s",
            "--yes",
        ]
        if self.project_id:
            args += ["--project", self.project_id]
        if body is not None:
            args += ["--file", "-"]
        args += list(arguments)
        env = {k: v for k, v in os.environ.items() if not k.startswith("WOOBE_")}
        env["WOOBE_CONTROL_KEY"] = key or self.credential
        if runtime_key:
            env["WOOBE_RUNTIME_KEY"] = runtime_key
        process = await asyncio.create_subprocess_exec(
            *args,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(
                    json.dumps(body).encode() if body is not None else None
                ),
                100,
            )
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
        # Never attach secret-bearing command output or input to assertion messages.
        assert all(
            value.encode() not in stdout + stderr for value in self.secret_values
        ), "CLI leaked a credential"
        payload = json.loads(stdout or stderr)
        error = payload.get("error") or {}
        self.evidence.append(
            {
                "command": list(arguments),
                "exit_code": process.returncode,
                "http_status": error.get("http_status"),
                "request_id": error.get("request_id"),
            }
        )
        assert process.returncode == expected, (
            f"CLI command failed: exit={process.returncode}, status={error.get('http_status')}, message={error.get('message')}"
        )
        return payload

    async def data(self, *args, **kwargs):
        payload = await self.run(*args, **kwargs)
        return payload["data"]["data"]

    async def issue(self, *args, body, key=None, **kwargs):
        destination = self.directory / f"secret-{uuid4()}.json"
        result = await self.data(
            *args, "--secret-file", str(destination), body=body, key=key, **kwargs
        )
        secret = json.loads(destination.read_text())["data"]["key"]
        assert destination.stat().st_mode & 0o777 == 0o600
        assert result["key"] == "[REDACTED]"
        self.secret_values.add(secret)
        return result, secret


@pytest_asyncio.fixture
async def cli(tmp_path):
    binary = os.environ.get("WOOBE_CLI_BINARY", "/artifacts/woobe")
    if not Path(binary).is_file():
        if os.environ.get("WOOBE_REQUIRE_CLI_E2E", "false").lower() == "true":
            pytest.fail(
                "Backend CI requires the pinned compiled CLI at WOOBE_CLI_BINARY"
            )
        pytest.skip(
            "Compile the pinned CLI and set WOOBE_CLI_BINARY to run this contract"
        )
    settings = Settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    workspace_id = uuid4()
    issued = issue_control_api_key()
    root_id = uuid4()
    expiration = datetime.now(UTC) + timedelta(hours=3)
    async with factory() as session:
        session.add(
            WorkspaceModel(
                id=workspace_id, name="CLI E2E", slug=str(workspace_id), status="active"
            )
        )
        await session.flush()
        session.add(
            WorkspaceControlKeyModel(
                id=root_id,
                workspace_id=workspace_id,
                credential_id=root_id,
                name="E2E bootstrap",
                key_prefix=issued.public_prefix,
                key_hash=issued.digest,
                key_version=issued.key_version,
                permissions=sorted(WORKSPACE_CONTROL_PERMISSIONS),
                on_project_create_permissions=sorted(PROJECT_CONTROL_PERMISSIONS),
                status="active",
                expires_at=expiration,
            )
        )
        await session.commit()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    processes = []
    logs = []
    harness = Cli(binary, origin, workspace_id, issued.value, tmp_path)
    try:
        for command, name in [
            (
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                "api",
            ),
            ([sys.executable, "-m", "worker_main"], "workers"),
        ]:
            log = (tmp_path / f"{name}.log").open("wb")
            logs.append(log)
            processes.append(
                await asyncio.create_subprocess_exec(*command, stdout=log, stderr=log)
            )
        async with httpx.AsyncClient(trust_env=False) as client:
            for _ in range(120):
                assert processes[0].returncode is None, "API startup failed"
                try:
                    schema = await client.get(f"{origin}/openapi.json")
                    if schema.status_code == 200:
                        harness.openapi_sha256 = hashlib.sha256(schema.content).hexdigest()
                        break
                except httpx.TransportError:
                    pass
                await asyncio.sleep(0.25)
            else:
                pytest.fail("Live API did not become ready")
        version = await harness.run("version")
        assert version["data"]["commit"] == CLI_COMMIT
        yield harness
    finally:
        for process in processes:
            if process.returncode is None:
                process.terminate()
        for process in processes:
            try:
                await asyncio.wait_for(process.wait(), 15)
            except TimeoutError:
                process.kill()
                await process.wait()
        for log in logs:
            log.close()
        # Evidence contains only command/status metadata, never bodies or credentials.
        evidence_dir = Path(os.environ.get("WOOBE_CLI_EVIDENCE_DIR", "/artifacts"))
        if evidence_dir.is_dir():
            (evidence_dir / f"cli-contract-{workspace_id}.json").write_text(
                json.dumps(
                    {
                        "cli_commit": CLI_COMMIT,
                        "server_commit": os.environ.get("WOOBE_TEST_SERVER_SHA"),
                        "database_revision": "0077",
                        "openapi_sha256": harness.openapi_sha256,
                        "requests": harness.evidence,
                    }, indent=2
                )
            )
        # PostgreSQL is disposable in Compose. Retain failed resources for diagnosis;
        # credentials are ephemeral and the live processes have already stopped.
        async with factory() as session:
            await session.execute(
                delete(WorkspaceControlKeyModel).where(
                    WorkspaceControlKeyModel.workspace_id == workspace_id
                )
            )
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_cli_agent_network_publish_execute_and_authority_boundaries(cli):
    unique = str(uuid4())
    project_body = {
        "workspace_id": cli.workspace_id,
        "name": "CLI workflow",
        "slug": unique,
    }
    project = await cli.data(
        "project", "create", "--idempotency-key", "project-create", body=project_body
    )
    replay = await cli.data(
        "project", "create", "--idempotency-key", "project-create", body=project_body
    )
    assert project["id"] == replay["id"]
    cli.project_id = project["id"]
    expiry = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    credential = await cli.data(
        "project",
        "provider-credential",
        "create",
        body={
            "project_id": cli.project_id,
            "provider": "custom",
            "name": "Fake provider",
            "secret": "fake-api-key",
            "metadata": {
                "provider_family": "openai",
                "compatibility": "compatible",
                "base_url": os.environ["WOOBE_TEST_FAKE_PROVIDER_URL"],
                "model_discovery_strategy": "openai_compatible_models",
            },
        },
    )
    model = await cli.data(
        "project",
        "provider-model",
        "create",
        body={
            "project_id": cli.project_id,
            "provider_credential_id": credential["id"],
            "name": "Deterministic",
            "model": "fake-success",
        },
    )
    agent_body = {
        "project_id": cli.project_id,
        "name": "CLI agent",
        "type": "chat",
        "provider": "custom",
        "provider_model_id": model["id"],
        "provider_credential_id": credential["id"],
        "model": "fake-success",
        "system_prompt": "Answer briefly.",
        "session_mode": "stateless",
        "max_output_tokens": 64,
    }
    agent = await cli.data(
        "project",
        "agent",
        "create",
        "--idempotency-key",
        "agent-create",
        body=agent_body,
    )
    agent_replay = await cli.data(
        "project",
        "agent",
        "create",
        "--idempotency-key",
        "agent-create",
        body=agent_body,
    )
    assert agent["id"] == agent_replay["id"]
    agent_id = agent["id"]
    await cli.data(
        "project", "agent", "update", agent_id, body={"name": "Configured through CLI"}
    )
    draft = await cli.data(
        "project",
        "agent",
        "release",
        "create",
        agent_id,
        body={"project_id": cli.project_id, "agent_id": agent_id, "version": "auto"},
    )
    builder, builder_key = await cli.issue(
        "workspace",
        "control-key",
        "create",
        body={
            "name": "Staging builder",
            "expires_at": expiry,
            "on_project_create_permissions": [],
            "project_grants": [
                {
                    "project_id": cli.project_id,
                    "permissions": [
                        "agent:read",
                        "agent:write",
                        "agent:version",
                        "api_key:write",
                        "run:execute",
                    ],
                    "conditions": {"environments": ["staging"]},
                }
            ],
        },
    )
    staging = await cli.data(
        "project",
        "agent",
        "release",
        "promote",
        agent_id,
        draft["id"],
        body={"target_status": "staging"},
        key=builder_key,
    )
    await cli.run(
        "project",
        "agent",
        "release",
        "promote",
        agent_id,
        staging["id"],
        body={"target_status": "production"},
        key=builder_key,
        expected=4,
    )
    _, staging_key = await cli.issue(
        "project",
        "runtime-key",
        "create",
        body={
            "project_id": cli.project_id,
            "name": "Staging runtime",
            "target_type": "agent",
            "target_id": agent_id,
            "environment": "staging",
            "interfaces": ["http", "stream"],
            "expires_at": expiry,
        },
        key=builder_key,
    )
    result = await cli.run(
        "runtime",
        "target",
        "run",
        "staging-agent",
        "--target-kind",
        "agent",
        body={"input": "Hello"},
        runtime_key=staging_key,
    )
    assert result["data"]["success"] is True
    second_run = await cli.run(
        "runtime", "target", "run", "staging-agent", "--target-kind", "agent",
        body={"input": "Second independent session"}, runtime_key=staging_key,
    )
    assert second_run["data"]["success"] is True
    _, session_reader = await cli.issue(
        "workspace", "control-key", "create",
        body={
            "name": "Scoped session observer",
            "expires_at": expiry,
            "on_project_create_permissions": [],
            "project_grants": [{
                "project_id": cli.project_id,
                "permissions": ["run:read"],
                "conditions": {
                    "environments": ["staging"],
                    "target_types": ["agent"],
                    "target_ids": [agent_id],
                },
            }],
        },
    )
    sessions_all = await cli.run(
        "runtime", "agent", "sessions", agent_id, "--query", "environment=staging",
        "--limit", "1", "--all", key=session_reader,
    )
    assert sessions_all["meta"]["complete"] is True
    sessions = [
        item
        for received in sessions_all["data"]["pages"]
        for item in received["data"]["items"]
    ]
    assert len(sessions) >= 2
    assert all(item["runtime_environment"] == "staging" for item in sessions)
    assert len({item["id"] for item in sessions}) == len(sessions)
    for query in ([], ["--query", "environment=production"]):
        await cli.run(
            "runtime", "agent", "sessions", agent_id, *query,
            "--limit", "1", "--all", key=session_reader, expected=4,
        )
    await cli.run(
        "runtime", "agent", "sessions", str(uuid4()),
        "--query", "environment=staging", "--all", key=session_reader, expected=5,
    )
    # Publication still enforces the Agent lifecycle DTO/domain validation.
    missing_notes = await cli.run(
        "project", "agent", "release", "promote", agent_id, staging["id"],
        body={"target_status": "production"}, expected=2,
    )
    assert missing_notes["error"]["http_status"] == 422
    production = await cli.data(
        "project",
        "agent",
        "release",
        "promote",
        agent_id,
        staging["id"],
        body={"target_status": "production", "release_notes": "Validated CLI publication"},
    )
    assert production["id"] != staging["id"]
    second_draft = await cli.data(
        "project", "agent", "release", "create", agent_id,
        body={"project_id": cli.project_id, "agent_id": agent_id, "version": "auto", "system_prompt": "Second version."},
    )
    second_stage = await cli.data(
        "project", "agent", "release", "promote", agent_id, second_draft["id"],
        body={"target_status": "staging"},
    )
    second_release = await cli.data(
        "project", "agent", "release", "promote", agent_id, second_stage["id"],
        body={"target_status": "production", "release_notes": "Second CLI publication"},
    )
    assert second_release["id"] != production["id"]
    await cli.run(
        "project", "agent", "release", "rollback", agent_id, production["id"],
        body={"change_description": "Restore first release"}, key=builder_key, expected=4,
    )
    restored = await cli.data(
        "project", "agent", "release", "rollback", agent_id, production["id"],
        body={"change_description": "Restore first release"},
    )
    assert restored["id"] == production["id"]
    activations = await cli.data("project", "agent", "release", "activations", agent_id)
    assert any(item["action"] == "rollback" and item["release_id"] == production["id"] for item in activations)
    await cli.run("request", "POST", "/v1/run", body={"message": "Hello"}, expected=4)
    await cli.run("project", "agent", "list", key=staging_key, expected=4)
    network_body = {"name": "CLI network"}
    network = await cli.data(
        "project",
        "network",
        "create",
        "--idempotency-key",
        "network-create",
        body=network_body,
    )
    network_replay = await cli.data(
        "project",
        "network",
        "create",
        "--idempotency-key",
        "network-create",
        body=network_body,
    )
    assert network["id"] == network_replay["id"]
    network_id = network["id"]
    node_id = str(uuid4())
    definition = {
        "schema_version": 2,
        "root_node_id": node_id,
        "nodes": [
            {
                "id": node_id,
                "agent_id": agent_id,
                "label": "Root",
                "capability_description": "Answer",
                "position": {"x": 0, "y": 0},
                "binding": {"source": "release", "release_id": production["id"]},
            }
        ],
        "edges": [],
        "settings": {
            "session_mode": "stateless",
            "max_depth": 2,
            "max_invocations": 4,
            "timeout_seconds": 30,
        },
    }
    network = await cli.data(
        "project",
        "network",
        "draft",
        "update",
        network_id,
        body={
            "project_id": cli.project_id,
            "name": "CLI network",
            "expected_revision": network["draft_revision"],
            "definition": definition,
        },
    )
    stale = await cli.run(
        "project",
        "network",
        "draft",
        "update",
        network_id,
        body={
            "project_id": cli.project_id,
            "name": "Stale update",
            "expected_revision": network["draft_revision"] - 1,
            "definition": definition,
        },
        expected=6,
    )
    assert stale["error"]["http_status"] == 409
    preview = await cli.data(
        "project",
        "network",
        "promotion",
        "preview",
        network_id,
        body={"project_id": cli.project_id, "environment": "staging"},
    )
    stage_version = await cli.data(
        "project",
        "network",
        "promotion",
        "create",
        network_id,
        body={
            "project_id": cli.project_id,
            "environment": "staging",
            "expected_revision": network["draft_revision"],
            "approved_action_ids": [a["id"] for a in preview.get("actions", [])],
        },
    )
    production_preview = await cli.data(
        "project", "network", "promotion", "preview", network_id,
        body={"project_id": cli.project_id, "environment": "production"},
    )
    network_release = await cli.data(
        "project", "network", "promotion", "create", network_id,
        body={
            "project_id": cli.project_id,
            "environment": "production",
            "expected_network_version_id": stage_version["id"],
            "approved_action_ids": [a["id"] for a in production_preview.get("actions", [])],
        },
    )
    assert network_release["kind"] == "release"
    # Activation restores an existing immutable Release; it does not publish Staging.
    definition["settings"]["max_invocations"] = 5
    network = await cli.data(
        "project", "network", "draft", "update", network_id,
        body={
            "project_id": cli.project_id,
            "name": "CLI network second release",
            "expected_revision": network["draft_revision"],
            "definition": definition,
        },
    )
    second_preview = await cli.data(
        "project", "network", "promotion", "preview", network_id,
        body={"project_id": cli.project_id, "environment": "staging"},
    )
    second_network_stage = await cli.data(
        "project", "network", "promotion", "create", network_id,
        body={
            "project_id": cli.project_id,
            "environment": "staging",
            "expected_revision": network["draft_revision"],
            "approved_action_ids": [a["id"] for a in second_preview.get("actions", [])],
        },
    )
    second_production_preview = await cli.data(
        "project", "network", "promotion", "preview", network_id,
        body={"project_id": cli.project_id, "environment": "production"},
    )
    second_network_release = await cli.data(
        "project", "network", "promotion", "create", network_id,
        body={
            "project_id": cli.project_id,
            "environment": "production",
            "expected_network_version_id": second_network_stage["id"],
            "approved_action_ids": [a["id"] for a in second_production_preview.get("actions", [])],
        },
    )
    assert second_network_release["id"] != network_release["id"]
    network_restored = await cli.data(
        "project",
        "network",
        "activation",
        "create",
        network_id,
        body={
            "project_id": cli.project_id,
            "source_version_id": network_release["id"],
            "expected_current_production_version_id": second_network_release["id"],
            "change_description": "Restore first CLI Network release",
        },
    )
    assert network_restored["version"]["id"] == network_release["id"]
    assert network_restored["activation"]["activation_kind"] == "rollback"
    _, network_key = await cli.issue(
        "project",
        "runtime-key",
        "create",
        body={
            "project_id": cli.project_id,
            "name": "Production network",
            "target_type": "network",
            "target_id": network_id,
            "environment": "production",
            "interfaces": ["http", "stream"],
            "expires_at": expiry,
        },
    )
    network_result = await cli.run(
        "runtime",
        "target",
        "run",
        "production-network",
        "--target-kind",
        "network",
        body={"input": "Hello"},
        runtime_key=network_key,
    )
    assert network_result["data"]["success"] is True
    execution_id = network_result["data"]["data"]["execution_id"]
    snapshot = await cli.data(
        "project",
        "network",
        "execution",
        "snapshot",
        execution_id,
        "--query",
        f"project_id={cli.project_id}",
    )
    assert snapshot
    # An agent-bound runtime credential must not observe a Network run.
    await cli.run(
        "runtime",
        "target",
        "observe",
        "wrong-target",
        execution_id,
        "--target-kind",
        "agent",
        "--output",
        "jsonl",
        runtime_key=staging_key,
        expected=5,
    )
    # CAS applies before mutation; retrying a completed rotation recovers the same key.
    rotated, rotated_key = await cli.issue(
        "workspace",
        "control-key",
        "rotate",
        builder["id"],
        "--if-match",
        builder["etag"],
        "--idempotency-key",
        "builder-rotation",
        body={},
    )
    replay_rotation, replay_key = await cli.issue(
        "workspace",
        "control-key",
        "rotate",
        builder["id"],
        "--if-match",
        builder["etag"],
        "--idempotency-key",
        "builder-rotation",
        body={},
    )
    assert rotated["id"] == replay_rotation["id"]
    assert rotated_key == replay_key
    await cli.run("project", "agent", "get", agent_id, key=builder_key, expected=3)
    await cli.data("project", "agent", "get", agent_id, key=rotated_key)


@pytest.mark.asyncio
async def test_cli_categories_pin_authority_and_preflight_matches_requests(cli):
    project = await cli.data(
        "project", "create",
        body={"workspace_id": cli.workspace_id, "name": "Authority contract", "slug": str(uuid4())},
    )
    cli.project_id = project["id"]
    catalog = await cli.data("permission", "list")
    assert "agent:read" in catalog["permissions"]["project"]
    category = await cli.data(
        "workspace", "authority", "category", "create",
        body={"name": "scoped-reader", "scope": "project", "permissions": ["agent:read"]},
    )
    category_id = category["id"]
    etag = f'"category:{category_id}:{category["revision"]}"'
    _, reader_key = await cli.issue(
        "workspace", "control-key", "create",
        body={
            "name": "Pinned reader",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "on_project_create_permissions": [],
            "project_grants": [{"project_id": cli.project_id, "category_id": category_id, "category_revision": 1}],
        },
    )
    changed = await cli.data(
        "workspace", "authority", "category", "update", category_id, "--if-match", etag,
        body={"permissions": ["agent:read", "agent:write"]},
    )
    assert changed["revision"] == 2
    stale = await cli.run(
        "workspace", "authority", "category", "update", category_id, "--if-match", etag,
        body={"name": "Rejected stale edit"}, expected=6,
    )
    assert stale["error"]["http_status"] == 412
    pinned = await cli.data(
        "workspace", "authority", "category", "get", category_id, "--query", "revision=1",
    )
    assert pinned["permissions"] == ["agent:read"]
    authority = await cli.data(
        "permission", "effective", "--query", f"project_id={cli.project_id}", key=reader_key,
    )
    assert "agent:write" not in authority["permissions"]
    assert authority["origin"]["revision"] == 1
    for method, path, allowed in [("GET", "/ai/agents", True), ("POST", "/ai/agents", False)]:
        decision = await cli.data(
            "permission", "check", key=reader_key,
            body={"method": method, "path": path, "query": {"project_id": cli.project_id}, "body": {"project_id": cli.project_id}},
        )
        assert decision["allowed"] is allowed
        if allowed:
            await cli.run("request", method, path, "--query", f"project_id={cli.project_id}", key=reader_key)
        else:
            await cli.run("request", method, path, body={"project_id": cli.project_id}, key=reader_key, expected=4)
    history_response = await cli.run(
        "workspace", "authority", "category", "history", category_id, "--limit", "1",
    )
    assert history_response["success"] is True
    assert history_response["meta"]["complete"] is False
    assert history_response["meta"]["collection_complete"] == "partial"
    history = history_response["data"]["data"]
    assert history["complete"] is False
    assert history["next_revision"] == 2
    page = await cli.data(
        "workspace", "authority", "category", "history", category_id,
        "--query", "limit=1", "--query", "before_revision=2",
    )
    assert page["complete"] is True
    assert page["items"][0]["permissions"] == ["agent:read"]
    history_all = await cli.run(
        "workspace", "authority", "category", "history", category_id, "--limit", "1", "--all",
    )
    assert history_all["meta"]["complete"] is True
    assert history_all["data"]["page_count"] == 2
    assert [
        item["revision"]
        for received in history_all["data"]["pages"]
        for item in received["data"]["items"]
    ] == [2, 1]
    history_remaining = await cli.run(
        "workspace", "authority", "category", "history", category_id,
        "--limit", "1", "--before-revision", "2", "--all",
    )
    assert history_remaining["meta"]["complete"] is False
    assert history_remaining["meta"]["collection_complete"] == "remaining"
    bounded_history = await cli.run(
        "workspace", "authority", "category", "history", category_id,
        "--limit", "1", "--all", "--max-pages", "1", expected=10,
    )
    assert bounded_history["data"]["page_count"] == 1
    assert bounded_history["data"]["next_query"]["before_revision"] == ["2"]
    assert bounded_history["meta"]["complete"] is False
    clone = await cli.data(
        "workspace", "authority", "category", "clone", category_id,
        body={"name": "unused-clone", "revision": 1},
    )
    assert clone["permissions"] == ["agent:read"]
    categories_all = await cli.run(
        "workspace", "authority", "category", "list", "--limit", "1", "--all",
    )
    assert categories_all["meta"]["complete"] is True
    assert categories_all["data"]["page_count"] == 2
    assert {
        item["id"]
        for received in categories_all["data"]["pages"]
        for item in received["data"]["items"]
    } == {category_id, clone["id"]}
    # Side projections remain per page; built-in profiles are not counted as
    # separately persisted categories and do not interfere with cursors.
    assert all(
        received["data"]["system_categories"]
        for received in categories_all["data"]["pages"]
    )
    audit_all = await cli.run(
        "workspace", "authority", "audit", "--limit", "1", "--all",
    )
    assert audit_all["meta"]["complete"] is True
    audit_items = [
        item
        for received in audit_all["data"]["pages"]
        for item in received["data"]["items"]
    ]
    assert len(audit_items) >= 3
    assert len({item["id"] for item in audit_items}) == len(audit_items)
    archived = await cli.data(
        "workspace", "authority", "category", "archive", clone["id"],
        "--if-match", f'"category:{clone["id"]}:1"', body={},
    )
    assert archived["status"] == "archived"
    await cli.run(
        "workspace", "authority", "category", "delete", clone["id"],
        "--if-match", f'"category:{clone["id"]}:{archived["revision"]}"',
    )
