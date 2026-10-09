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
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, select, text

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

CLI_COMMIT = os.environ.get(
    "WOOBE_TEST_CLI_SHA", "247e33ae66f9874e1827877504288944a8898cfe"
)


@pytest.mark.asyncio
async def test_cli_full_registry_matches_the_live_server_schema(cli):
    contract = json.loads(
        (
            Path(__file__).parents[2] / "unit/api/fixtures/woobe_cli_operations.json"
        ).read_text()
    )
    assert contract["cli_commit"] == CLI_COMMIT
    discovery = await cli.run("help")
    actual = [
        {key: item[key] for key in ("command", "method", "path", "body_required")}
        for item in discovery["data"]
        if item.get("method") and item.get("path")
    ]
    assert actual == contract["operations"]
    for operation in actual:
        result = await cli.run("server-schema", "--command", operation["command"])
        definition = result["data"]["definition"]
        assert definition, operation["command"]
        if operation["body_required"]:
            assert definition["requestBody"]["content"]["application/json"]["schema"], (
                operation["command"]
            )
            validation = await cli.run(
                "validate-input",
                "--command",
                operation["command"],
                body={},
                expected=(0, 2),
            )
            # Missing required fields may fail validation. Unsupported schemas,
            # transport errors and accidental mutation never count as compatibility.
            assert not (validation.get("error") or {}).get("http_status")
            if validation.get("success"):
                assert validation["data"]["executed"] is False


class Cli:
    def __init__(self, binary, origin, workspace_id, credential, directory):
        self.binary, self.origin, self.workspace_id = binary, origin, str(workspace_id)
        self.credential, self.directory = credential, directory
        self.project_id = None
        self.secret_values = {credential}
        self.evidence = []
        self.openapi_sha256 = None

    async def run(
        self,
        *arguments,
        body=None,
        key=None,
        runtime_key=None,
        expected=0,
        stdin_bytes=None,
        cwd=None,
    ):
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
            cwd=cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(
                    stdin_bytes
                    if stdin_bytes is not None
                    else json.dumps(body).encode()
                    if body is not None
                    else None
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
        accepted = expected if isinstance(expected, tuple) else (expected,)
        assert process.returncode in accepted, (
            f"CLI command failed: exit={process.returncode}, status={error.get('http_status')}, message={error.get('message')}, domain={error.get('domain_code')}, diagnostics={error.get('diagnostics')}"
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
        database_revision = await session.scalar(
            text("SELECT version_num FROM alembic_version")
        )
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
                await asyncio.create_subprocess_exec(
                    *command, stdout=log, stderr=log,
                    # This contract drives hundreds of deliberate administrative
                    # requests in one minute. Keep throttling enabled with an
                    # explicit harness budget; dedicated security tests exercise
                    # the production/default limit and rejection behavior.
                    env={**os.environ, "WOOBE_API_KEY_RATE_LIMIT_REQUESTS": "1000"},
                )
            )
        async with httpx.AsyncClient(trust_env=False) as client:
            for _ in range(120):
                assert processes[0].returncode is None, "API startup failed"
                try:
                    schema = await client.get(f"{origin}/openapi.json")
                    if schema.status_code == 200:
                        harness.openapi_sha256 = hashlib.sha256(
                            schema.content
                        ).hexdigest()
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
                        "database_revision": database_revision,
                        "openapi_sha256": harness.openapi_sha256,
                        "requests": harness.evidence,
                    },
                    indent=2,
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
async def test_cli_project_configuration_keys_and_knowledge_lifecycle(cli):
    project = await cli.data(
        "project",
        "create",
        "--validate-body",
        body={
            "workspace_id": cli.workspace_id,
            "name": "CLI configuration",
            "slug": str(uuid4()),
        },
    )
    cli.project_id = project["id"]
    await cli.data(
        "project",
        "update",
        cli.project_id,
        "--validate-body",
        "--validate-parameters",
        body={"name": "Updated configuration"},
    )
    observed = await cli.data("project", "get", cli.project_id)
    assert observed["name"] == "Updated configuration"
    assert observed["id"] == project["id"]
    assert datetime.fromisoformat(observed["created_at"]) == datetime.fromisoformat(
        project["created_at"]
    )
    await cli.data("project", "update", cli.project_id, body={"name": "Second edit"})
    assert (await cli.data("project", "get", cli.project_id))["name"] == "Second edit"

    environment_key = await cli.data(
        "project",
        "env",
        "set",
        "--key",
        "CLI_VALUE",
        "--validate-body",
        "--validate-parameters",
        body={"kind": "value", "values": {"staging": "stage", "production": "prod"}},
    )
    keys = await cli.data("project", "env", "list")
    value = next(item for item in keys if item["id"] == environment_key["id"])
    # The pinned CLI conservatively redacts all key/value fields, including
    # environment metadata. Configuration presence remains observable.
    assert value["key"] == "[REDACTED]"
    for environment in ("staging", "production"):
        assert value["values"][environment]["configured"] is True
        assert value["values"][environment]["value"] == "[REDACTED]"
    await cli.data(
        "project",
        "env",
        "set",
        "--key",
        "CLI_VALUE",
        "--validate-body",
        body={"clear_environments": ["staging"]},
    )
    keys = await cli.data("project", "env", "list")
    assert (
        next(item for item in keys if item["id"] == environment_key["id"])["values"][
            "staging"
        ]["configured"]
        is False
    )
    await cli.run("project", "env", "unset", "--key", "CLI_VALUE")
    assert await cli.data("project", "env", "list") == []

    expiry = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    issued, _ = await cli.issue(
        "project",
        "api-key",
        "create",
        "--validate-body",
        "--validate-parameters",
        body={
            "name": "CLI legacy key",
            "scopes": ["runtime:execute"],
            "expires_at": expiry,
        },
    )
    await cli.data(
        "project",
        "api-key",
        "update",
        issued["id"],
        "--validate-body",
        "--validate-parameters",
        body={"name": "Updated key"},
    )
    rotated, _ = await cli.issue(
        "project",
        "api-key",
        "rotate",
        issued["id"],
        "--validate-parameters",
        body=None,
    )
    assert rotated["rotated_from_id"] == issued["id"]
    assert rotated["name"] == "Updated key"
    replacement, _ = await cli.issue(
        "project",
        "api-key",
        "rotate",
        rotated["id"],
        "--validate-body",
        "--validate-parameters",
        body={
            "name": "Replacement key",
            "scopes": ["runtime:execute"],
            "expires_at": expiry,
        },
    )
    assert replacement["rotated_from_id"] == rotated["id"]
    assert replacement["name"] == "Replacement key"
    await cli.data("project", "api-key", "revoke", replacement["id"])
    listed = await cli.data("project", "api-key", "list")
    assert all(item["status"] == "revoked" for item in listed)

    collection = await cli.data(
        "project",
        "knowledge",
        "collection",
        "create",
        "--validate-body",
        body={"project_id": cli.project_id, "name": "CLI collection"},
    )
    await cli.data(
        "project",
        "knowledge",
        "collection",
        "update",
        collection["id"],
        "--validate-body",
        "--validate-parameters",
        body={"name": "Updated collection"},
    )
    observed = await cli.data(
        "project",
        "knowledge",
        "collection",
        "get",
        collection["id"],
    )
    assert observed["name"] == "Updated collection"
    tool = await cli.data(
        "project",
        "tool",
        "create",
        "--validate-body",
        body={
            "project_id": cli.project_id,
            "name": "CLI HTTP metadata",
            "config": {"url": "https://example.com", "method": "GET"},
        },
    )
    edited_tool = await cli.data(
        "project",
        "tool",
        "update",
        tool["id"],
        "--validate-body",
        "--validate-parameters",
        body={"name": "Updated HTTP metadata"},
    )
    assert edited_tool["name"] == "Updated HTTP metadata"
    await cli.data(
        "project",
        "tool",
        "status",
        tool["id"],
        "--validate-body",
        body={"status": "disabled"},
    )
    impact = await cli.data(
        "project", "tool", "usage-impact", tool["id"], "--validate-parameters"
    )
    assert impact["in_use"] is False
    assert impact["can_delete"] is True
    await cli.run("project", "tool", "delete", tool["id"], "--validate-parameters")
    for catalog in (
        "context-assemblers",
        "execution-strategies",
        "knowledge-strategies",
        "rag-strategies",
    ):
        result = await cli.run("project", "catalog", catalog, "--validate-parameters")
        assert result["success"] is True


@pytest.mark.asyncio
async def test_cli_agent_network_publish_execute_and_authority_boundaries(cli):
    unique = str(uuid4())
    project_body = {
        "workspace_id": cli.workspace_id,
        "name": "CLI workflow",
        "slug": unique,
    }
    invalid_project = await cli.run(
        "project",
        "create",
        "--validate-body",
        body={**project_body, "workspace_id": "not-a-uuid"},
        expected=2,
    )
    assert invalid_project["error"]["write_outcome"] == "not_attempted"
    assert invalid_project["error"].get("http_status") is None
    validated_project = await cli.run(
        "validate-input", "--command", "project create", body=project_body
    )
    assert validated_project["data"]["valid"] is True
    assert validated_project["data"]["validation_direction"] == "request"
    assert validated_project["data"]["executed"] is False
    project = await cli.data(
        "project",
        "create",
        "--validate-body",
        "--idempotency-key",
        "project-create",
        body=project_body,
    )
    replay = await cli.data(
        "project", "create", "--idempotency-key", "project-create", body=project_body
    )
    assert project["id"] == replay["id"]
    cli.project_id = project["id"]
    expiry = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    provider_secret = "fake-api-key"
    cli.secret_values.add(provider_secret)
    protected_store = cli.directory / "credentials"
    protected_store.mkdir(mode=0o700)
    protected_file = protected_store / "fake-provider.json"
    protected_file.write_text(provider_secret)
    protected_file.chmod(0o600)
    credential_plan = {
        "schema_version": "1",
        "project_id": cli.project_id,
        "steps": [
            {
                "id": "provider",
                "command": "project provider-credential create",
                "body": {
                    "project_id": cli.project_id,
                    "provider": "custom",
                    "name": "Fake provider",
                    "secret": {"$secret_ref": "fake-provider"},
                    "metadata": {
                        "provider_family": "openai",
                        "compatibility": "compatible",
                        "base_url": os.environ["WOOBE_TEST_FAKE_PROVIDER_URL"],
                        "model_discovery_strategy": "openai_compatible_models",
                    },
                },
            }
        ],
    }
    protected_preflight = await cli.run("manifest", "preflight", body=credential_plan)
    assert protected_preflight["data"]["complete"] is False
    assert (
        protected_preflight["data"]["operations"][0]["body_validation"]
        == "deferred_protected_credential"
    )
    provider_checkpoint = cli.directory / "provider.checkpoint.json"
    applied = await cli.run(
        "manifest",
        "apply",
        "--validate-body",
        "--checkpoint",
        str(provider_checkpoint),
        body=credential_plan,
    )
    credential = applied["data"]["results"]["provider"]
    resumed = await cli.run(
        "manifest",
        "apply",
        "--validate-body",
        "--checkpoint",
        str(provider_checkpoint),
        body=credential_plan,
    )
    assert resumed["data"]["results"]["provider"]["id"] == credential["id"]
    assert provider_secret not in provider_checkpoint.read_text()
    assert provider_checkpoint.stat().st_mode & 0o777 == 0o600
    listed_credentials = await cli.data(
        "project", "provider-credential", "list", "--validate-parameters"
    )
    assert [item["id"] for item in listed_credentials] == [credential["id"]]
    protected_file.write_text("rotated-local-fixture")
    await cli.run(
        "manifest",
        "apply",
        "--checkpoint",
        str(provider_checkpoint),
        body=credential_plan,
        expected=6,
    )
    protected_file.write_text(provider_secret)
    model = await cli.data(
        "project",
        "provider-model",
        "create",
        "--validate-body",
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
        "--validate-body",
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
        "project",
        "agent",
        "update",
        agent_id,
        "--validate-body",
        "--validate-parameters",
        body={"name": "Configured through CLI"},
    )
    draft = await cli.data(
        "project",
        "agent",
        "release",
        "create",
        agent_id,
        body={"project_id": cli.project_id, "agent_id": agent_id, "version": "auto"},
    )
    builder_body = {
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
    }
    invalid_expiration = await cli.run(
        "validate-input",
        "--command",
        "workspace control-key create",
        body={**builder_body, "expires_at": "2026-02-29T00:00:00Z"},
        expected=2,
    )
    assert invalid_expiration["error"].get("http_status") is None
    valid_expiration = await cli.run(
        "validate-input",
        "--command",
        "workspace control-key create",
        body=builder_body,
    )
    assert valid_expiration["data"]["valid"] is True
    assert valid_expiration["data"]["executed"] is False
    builder, builder_key = await cli.issue(
        "workspace",
        "control-key",
        "create",
        "--validate-body",
        body=builder_body,
    )
    staging = await cli.data(
        "project",
        "agent",
        "release",
        "promote",
        "--validate-body",
        "--validate-parameters",
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
        "--validate-body",
        "--validate-parameters",
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
        "--validate-body",
        "--validate-parameters",
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
        "runtime",
        "target",
        "run",
        "staging-agent",
        "--target-kind",
        "agent",
        body={"input": "Second independent session"},
        runtime_key=staging_key,
    )
    assert second_run["data"]["success"] is True
    _, session_reader = await cli.issue(
        "workspace",
        "control-key",
        "create",
        body={
            "name": "Scoped session observer",
            "expires_at": expiry,
            "on_project_create_permissions": [],
            "project_grants": [
                {
                    "project_id": cli.project_id,
                    "permissions": ["run:read"],
                    "conditions": {
                        "environments": ["staging"],
                        "target_types": ["agent"],
                        "target_ids": [agent_id],
                    },
                }
            ],
        },
    )
    sessions_all = await cli.run(
        "runtime",
        "agent",
        "sessions",
        agent_id,
        "--query",
        "environment=staging",
        "--limit",
        "1",
        "--all",
        "--validate-parameters",
        key=session_reader,
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
            "runtime",
            "agent",
            "sessions",
            agent_id,
            *query,
            "--limit",
            "1",
            "--all",
            key=session_reader,
            expected=4,
        )
    await cli.run(
        "runtime",
        "agent",
        "sessions",
        str(uuid4()),
        "--query",
        "environment=staging",
        "--all",
        key=session_reader,
        expected=5,
    )
    # Publication still enforces the Agent lifecycle DTO/domain validation.
    missing_notes = await cli.run(
        "project",
        "agent",
        "release",
        "promote",
        "--validate-body",
        "--validate-parameters",
        agent_id,
        staging["id"],
        body={"target_status": "production"},
        expected=2,
    )
    assert missing_notes["error"]["http_status"] == 422
    production = await cli.data(
        "project",
        "agent",
        "release",
        "promote",
        "--validate-body",
        "--validate-parameters",
        agent_id,
        staging["id"],
        body={
            "target_status": "production",
            "release_notes": "Validated CLI publication",
        },
    )
    assert production["id"] != staging["id"]
    second_draft = await cli.data(
        "project",
        "agent",
        "release",
        "create",
        agent_id,
        "--validate-body",
        "--validate-parameters",
        body={
            "project_id": cli.project_id,
            "agent_id": agent_id,
            "version": "auto",
            "system_prompt": "Second version.",
        },
    )
    second_stage = await cli.data(
        "project",
        "agent",
        "release",
        "promote",
        "--validate-body",
        "--validate-parameters",
        agent_id,
        second_draft["id"],
        body={"target_status": "staging"},
    )
    first_agent_selection = (await cli.run("agent", agent_id, "current", "--env", "production"))["data"]
    second_release = await cli.data(
        "project",
        "agent",
        "release",
        "promote",
        "--validate-body",
        "--validate-parameters",
        agent_id,
        second_stage["id"],
        body={"target_status": "production", "release_notes": "Second CLI publication"},
    )
    assert second_release["id"] != production["id"]
    second_agent_selection = (await cli.run("agent", agent_id, "current", "--env", "production"))["data"]
    assert second_agent_selection["environment_generation"] == first_agent_selection["environment_generation"] + 1
    await cli.run(
        "project",
        "agent",
        "release",
        "rollback",
        "--validate-body",
        "--validate-parameters",
        agent_id,
        production["id"],
        body={"change_description": "Restore first release"},
        key=builder_key,
        expected=4,
    )
    restored = await cli.data(
        "project",
        "agent",
        "release",
        "rollback",
        "--validate-body",
        "--validate-parameters",
        agent_id,
        production["id"],
        body={"change_description": "Restore first release"},
    )
    assert restored["id"] == production["id"]
    observed = (await cli.run("agent", agent_id, "current", "--env", "production"))["data"]
    assert observed["snapshot_id"] == production["id"]
    assert observed["environment_generation"] == second_agent_selection["environment_generation"] + 1
    assert observed["generation_status"] == "monotonic_owner_selection"
    assert observed["snapshot_id"] == first_agent_selection["snapshot_id"]
    repeated_observation = (await cli.run("agent", agent_id, "current", "--env", "production"))["data"]
    assert repeated_observation["environment_generation"] == observed["environment_generation"]
    publication_history = await cli.data("request", "GET", f"/projects/{cli.project_id}/agents/{agent_id}/asac/history", "--query", "limit=1")
    watermark = publication_history["watermark"]
    agent_records = list(publication_history["records"])
    while publication_history["has_more"]:
        publication_history = await cli.data("request", "GET", f"/projects/{cli.project_id}/agents/{agent_id}/asac/history", "--query", "limit=1", "--query", f"cursor={publication_history['next_cursor']}")
        assert publication_history["watermark"] == watermark
        agent_records.extend(publication_history["records"])
    assert {production["id"], second_release["id"]} <= {item["id"] for item in agent_records}
    for item in agent_records:
        from shared.contracts.asac import asac_digest
        payload = {key: value for key, value in item.items() if key != "record_digest"}
        assert item["record_digest"] == asac_digest("history-receipt", payload)
    await cli.run("agent", agent_id, "current", "--env", "production", key=builder_key, expected=4)
    await cli.run("agent", agent_id, "current", "--env", "production", key=staging_key, expected=4)
    activations = await cli.data("project", "agent", "release", "activations", agent_id)
    assert any(
        item["action"] == "rollback" and item["release_id"] == production["id"]
        for item in activations
    )
    agent_publication = await exercise_asac_isolated_drafts(cli, "Agent", agent_id)
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
        "project",
        "network",
        "promotion",
        "preview",
        network_id,
        body={"project_id": cli.project_id, "environment": "production"},
    )
    network_release = await cli.data(
        "project",
        "network",
        "promotion",
        "create",
        network_id,
        body={
            "project_id": cli.project_id,
            "environment": "production",
            "expected_network_version_id": stage_version["id"],
            "approved_action_ids": [
                a["id"] for a in production_preview.get("actions", [])
            ],
        },
    )
    assert network_release["kind"] == "release"
    # Activation restores an existing immutable Release; it does not publish Staging.
    definition["settings"]["max_invocations"] = 5
    network = await cli.data(
        "project",
        "network",
        "draft",
        "update",
        network_id,
        body={
            "project_id": cli.project_id,
            "name": "CLI network second release",
            "expected_revision": network["draft_revision"],
            "definition": definition,
        },
    )
    second_preview = await cli.data(
        "project",
        "network",
        "promotion",
        "preview",
        network_id,
        body={"project_id": cli.project_id, "environment": "staging"},
    )
    second_network_stage = await cli.data(
        "project",
        "network",
        "promotion",
        "create",
        network_id,
        body={
            "project_id": cli.project_id,
            "environment": "staging",
            "expected_revision": network["draft_revision"],
            "approved_action_ids": [a["id"] for a in second_preview.get("actions", [])],
        },
    )
    second_production_preview = await cli.data(
        "project",
        "network",
        "promotion",
        "preview",
        network_id,
        body={"project_id": cli.project_id, "environment": "production"},
    )
    first_network_selection = (await cli.run("network", network_id, "current", "--env", "production"))["data"]
    second_network_release = await cli.data(
        "project",
        "network",
        "promotion",
        "create",
        network_id,
        body={
            "project_id": cli.project_id,
            "environment": "production",
            "expected_network_version_id": second_network_stage["id"],
            "approved_action_ids": [
                a["id"] for a in second_production_preview.get("actions", [])
            ],
        },
    )
    assert second_network_release["id"] != network_release["id"]
    second_network_selection = (await cli.run("network", network_id, "current", "--env", "production"))["data"]
    assert second_network_selection["environment_generation"] == first_network_selection["environment_generation"] + 1
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
    selected_network = (await cli.run("network", network_id, "current", "--env", "production"))["data"]
    assert selected_network["snapshot_id"] == network_release["id"]
    assert selected_network["environment_generation"] == second_network_selection["environment_generation"] + 1
    assert selected_network["generation_status"] == "monotonic_owner_selection"
    network_history = await cli.data("request", "GET", f"/projects/{cli.project_id}/networks/{network_id}/asac/history")
    assert network_history["complete"]
    assert {network_release["id"], second_network_release["id"]} <= {item["id"] for item in network_history["records"]}
    network_deployments = await cli.data("request", "GET", f"/projects/{cli.project_id}/networks/{network_id}/asac/history", "--query", "stream=deployments")
    assert any(item["release_id"] == network_release["id"] and item["action"] == "rollback" for item in network_deployments["records"])
    network_publication = await exercise_asac_isolated_drafts(cli, "Network", network_id)
    _, network_key = await cli.issue(
        "project",
        "runtime-key",
        "create",
        "--validate-body",
        "--validate-parameters",
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
    await exercise_asac_deployments(cli, "Agent", agent_id, agent_publication)
    await exercise_asac_deployments(cli, "Network", network_id, network_publication)
    cli.policy_denied_key=builder_key
    await exercise_asac_project_policy(cli, agent_id, agent_publication, agent_body, definition, network_id, network_publication)
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



async def exercise_asac_isolated_drafts(cli, kind, resource_id):
    """Both owners retain exact objects without rewriting default or Production."""
    import io
    import shutil
    from modules.package.application.asac_definition import portable_definition
    from modules.package.infra.bundles import receive_archive
    from shared.contracts.asac import asac_digest
    base = f"/projects/{cli.project_id}/{kind.lower()}s/{resource_id}/asac"
    export = await cli.data("request", "POST", f"/projects/{cli.project_id}/packages/export", body={
        "kind":kind,"target_id":resource_id,"source":"production","knowledge":"portable","development":True})
    import yaml
    registry = cli.directory / ("asac-" + kind.lower())
    registry.mkdir()
    await cli.run("init", "--root", ".woobe", cwd=registry)
    pulled = await cli.run(kind.lower(), resource_id, "pull", "--alias", "captured", "--env", "production", cwd=registry)
    config = yaml.safe_load((registry / ".woobe-config").read_text())
    root_resource = next(item for item in config["resources"] if item["kind"] == kind and item["alias"] == "captured")
    uid = root_resource["uid"]
    production_before = (await cli.run(kind.lower(), resource_id, "current", "--env", "production"))["data"]
    pushed = (await cli.run(kind.lower(), "@captured", "push", cwd=registry))["data"]
    assert pushed["pushed"] and pushed["environment"] == "draft"
    registered = await cli.data("request", "GET", f"/projects/{cli.project_id}/packages/registries/{config['registry_id']}")
    accepted_root = next(item for item in registered["resources"] if item["resource_uid"] == uid)
    assert accepted_root["generation_scope"] == "accepted_native_phase"
    assert accepted_root["revision"] == accepted_root["accepted_revision"] == accepted_root["current_revision"]
    assert accepted_root["binding_status"] == "unchanged"
    assert accepted_root["operation_id"] == pushed["operation_id"]
    private_state = registry / config["root"] / ".state"
    saved_state = {file.relative_to(private_state): file.read_bytes() for file in private_state.rglob("*") if file.is_file()}
    shutil.rmtree(private_state)
    recovery_preview = (await cli.run(kind.lower(), resource_id, "bindings", "recover", "--dry-run", cwd=registry))["data"]
    assert not recovery_preview["bindings_recovered"]
    assert not list(private_state.glob("*.json"))
    recovery = (await cli.run(kind.lower(), resource_id, "bindings", "recover", cwd=registry))["data"]
    assert recovery["bindings_recovered"] and recovery["author_base"] == "not_recovered"
    assert not recovery["credentials_restored"] and not recovery["remote_changed"] and not recovery["local_files_changed"]
    recovered_state = json.loads(next(private_state.glob("*.json")).read_text())
    assert recovered_state["bindings"][uid]["revision"] == accepted_root["accepted_revision"]
    assert recovered_state["bindings"][uid]["base"] is None and recovered_state["credentials"] == {}
    for binding in registered["resources"]:
        if binding["frozen"]:
            assert recovered_state["bindings"][binding["resource_uid"]]["snapshot_id"] == binding["snapshot_id"]
    # Keep original accepted author bases for the remaining independent history
    # scenarios. Identity recovery itself never supplies those bases.
    shutil.rmtree(private_state)
    for relative, content in saved_state.items():
        target = private_state / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        target.write_bytes(content)
        target.chmod(0o600)
    production_after = (await cli.run(kind.lower(), resource_id, "current", "--env", "production"))["data"]
    assert production_after["snapshot_id"] == production_before["snapshot_id"]
    if kind == "Agent":
        await cli.data("project", "agent", "update", resource_id, body={"description": "Concurrent native edit after accepted synchronization"})
        changed = await cli.data("request", "GET", f"/projects/{cli.project_id}/packages/registries/{config['registry_id']}")
        changed_root = next(item for item in changed["resources"] if item["resource_uid"] == uid)
        assert changed_root["revision"] == accepted_root["accepted_revision"]
        assert changed_root["current_revision"] != changed_root["accepted_revision"]
        assert changed_root["binding_status"] == "resource_changed"
    cli_open = (await cli.run(kind.lower(), "@captured", "draft", "open", "cli-hotfix", "--from", "production", cwd=registry))["data"]
    assert cli_open["resource_uid"] == uid and not cli_open["production_changed"]
    await exercise_asac_workflow_leases(cli,kind,resource_id,cli_open["draft_id"])
    cli_lease = (await cli.run(kind.lower(), "@captured", "lease", "acquire", "--scope", "draft", "--ttl", "60", cwd=registry))["data"]
    assert cli_lease["fencing_token"] == 3 and cli_lease["state"] == "active"
    assert cli_lease["scope"] == "draft:" + cli_open["draft_id"]
    # Same credentials and another workflow cannot inherit the reservation.
    await cli.run(kind.lower(),resource_id,"lease","acquire","--scope","draft","--draft",cli_open["draft_id"],"--ttl","60","--operation",str(uuid4()),"--workflow",str(uuid4()),expected=6)
    cli_saved = (await cli.run(kind.lower(), "@captured", "draft", "push", cwd=registry))["data"]
    assert cli_saved["generation"] == 2
    checkpoint = (await cli.run(kind.lower(), "@captured", "revision", "create", "--message", "CLI exact checkpoint", cwd=registry))["data"]
    cli_revision = (await cli.run(kind.lower(), "@captured", "draft", "checkpoint", checkpoint["revision_id"], cwd=registry))["data"]
    assert cli_revision["record"] == checkpoint
    assert cli_lease["lease_id"] not in json.dumps(checkpoint) and cli_lease["workflow_id"] not in json.dumps(checkpoint)
    renewed = (await cli.run(kind.lower(),"@captured","lease","renew","--scope","draft","--ttl","120",cwd=registry))["data"]
    assert renewed["lease_id"] == cli_lease["lease_id"] and renewed["fencing_token"] == 3
    assert renewed["maximum_expires_at"] == cli_lease["maximum_expires_at"]
    current_lease = (await cli.run(kind.lower(),"@captured","lease","show","--scope","draft",cwd=registry))["data"]
    assert current_lease["workflow_id"] == cli_lease["workflow_id"]
    released_lease = (await cli.run(kind.lower(),"@captured","lease","release","--scope","draft",cwd=registry))["data"]
    assert released_lease["state"] == "released" and released_lease["lease_id"] == cli_lease["lease_id"]
    assert cli_revision["author_artifact_status"] == "retained_custody"
    descriptor = registry / config["root"] / root_resource["path"]
    if descriptor.suffix.lower() not in {".yaml", ".yml", ".json"}:
        descriptor = descriptor / (kind.lower() + ".yaml")
    original_source = descriptor.read_bytes()
    descriptor.write_bytes(b"# local author comment\n" + original_source)
    comment_revision = (await cli.run(kind.lower(), "@captured", "revision", "create", "--message", "Preserve author comment", cwd=registry))["data"]
    assert comment_revision["definition_digest"] == checkpoint["definition_digest"]
    assert comment_revision["author_artifact_digest"] != checkpoint["author_artifact_digest"]
    comment_registered = (await cli.run(kind.lower(), "@captured", "draft", "checkpoint", comment_revision["revision_id"], cwd=registry))["data"]
    assert comment_registered["record"] == comment_revision
    # Stage the registered exact closure in a detached candidate. The existing
    # native Draft, native Staging and Production selection remain unchanged.
    native_draft_before = (await cli.run(kind.lower(), resource_id, "current", "--env", "draft"))["data"]
    native_staging_before = (await cli.run(kind.lower(), resource_id, "current", "--env", "staging"))["data"]
    native_production_before = (await cli.run(kind.lower(), resource_id, "current", "--env", "production"))["data"]
    scoped_state_file = private_state / (hashlib.sha256((cli.origin.rstrip("/") + "\n" + cli.workspace_id + "\n" + cli.project_id).encode()).hexdigest() + ".json")
    state_before_stage = json.loads(scoped_state_file.read_text())
    object_path = registry / config["root"] / "objects" / "sha256" / (comment_revision["artifact_digest"].removeprefix("sha256:") + ".tar.gz")
    with receive_archive(io.BytesIO(object_path.read_bytes()), locked=True) as sealed:
        requirements = sealed.graph.manifest["spec"].get("requires", {})
    binding_spec = {"credentials": {}, "knowledge": {}, "secrets": {}, "project_environment": {}}
    for item in requirements.get("credentials", []):
        binding_spec["credentials"][item["ref"]] = {"credential_id": state_before_stage["credentials"][item["ref"]]}
    for group in ("secrets", "project_environment"):
        for item in requirements.get(group, []):
            alias = item["key" if group == "project_environment" else "ref"]
            binding_spec[group][alias] = {"existing_key": alias}
    stage_body = {"operation_id": str(uuid4()), "draft_id": cli_open["draft_id"],
        "expected_generation": cli_saved["generation"], "revision_id": comment_revision["revision_id"],
        "registry_id": config["registry_id"], "bindings": {"format": "woobe-package", "schema_version": "1.0",
            "kind": "ImportBindings", "metadata": {"name": "Candidate"}, "spec": binding_spec}}
    preview = (await cli.run(kind.lower(), "@captured", "stage", "--revision", comment_revision["revision_id"], "--dry-run", cwd=registry))["data"]
    assert not preview["executed"] and not preview["candidate_prepared"]
    candidate_acceptance = (await cli.run(kind.lower(), "@captured", "stage", "--revision", comment_revision["revision_id"], "--yes", cwd=registry))["data"]
    stage_body["operation_id"] = candidate_acceptance["operation_id"]
    assert candidate_acceptance["state"] == "preparing" and not candidate_acceptance["published"]
    assert candidate_acceptance["snapshot_id"] is None and candidate_acceptance["runtime_digest"] is None
    assert await cli.data("request", "POST", base + "/candidates", body=stage_body) == candidate_acceptance
    candidate_operation = await cli.data("request", "GET", f"/projects/{cli.project_id}/packages/operations/{candidate_acceptance['preparation_operation_id']}")
    for _ in range(120):
        if candidate_operation["state"] in {"succeeded", "failed", "cancelled", "uncertain"}:
            break
        await asyncio.sleep(0.5)
        candidate_operation = await cli.data("request", "GET", f"/projects/{cli.project_id}/packages/operations/{candidate_acceptance['preparation_operation_id']}")
    assert candidate_operation["state"] == "succeeded", candidate_operation
    candidate = (await cli.run(kind.lower(), "@captured", "candidate", candidate_acceptance["candidate_id"], cwd=registry))["data"]
    assert candidate["state"] == "ready" and candidate["snapshot_id"] and candidate["runtime_digest"]
    assert candidate["revision_id"] == comment_revision["revision_id"] and not candidate["published"]
    assert candidate["record_digest"] == comment_revision["record_digest"]
    evaluation_body = {"operation_id": str(uuid4()), "suite": {"schema_version":"1.0",
        "suite_id":"native-cli-smoke", "suite_version":"1", "dataset_version":"1",
        "cases":[{"id":"greeting", "message":"Hello from the exact candidate"}]}}
    evaluation_preview = (await cli.run(kind.lower(), "@captured", "test", "--candidate", candidate["candidate_id"], "--dry-run", body=evaluation_body["suite"], cwd=registry))["data"]
    assert not evaluation_preview["executed"] and not evaluation_preview["production_changed"]
    evaluation = (await cli.run(kind.lower(), "@captured", "test", "--candidate", candidate["candidate_id"], "--yes", body=evaluation_body["suite"], cwd=registry))["data"]
    assert evaluation["state"] == "passed", evaluation
    assert evaluation["runtime_digest"] == candidate["runtime_digest"] and evaluation["record_digest"] == candidate["record_digest"]
    assert evaluation["cases"][0]["state"] == "passed" and evaluation["cases"][0]["run_id"]
    evaluation_body["operation_id"] = evaluation["operation_id"]
    original_evaluation = await cli.data("request", "GET", base + "/operations/" + evaluation["operation_id"])
    evaluation_receipt = original_evaluation["result"]
    assert evaluation_receipt["state"] == "accepted" and not evaluation_receipt["complete"]
    assert await cli.data("request", "POST", base + "/candidates/" + candidate["candidate_id"] + "/evaluations", body=evaluation_body) == evaluation_receipt
    assert (await cli.run(kind.lower(), "@captured", "evaluation", evaluation["evaluation_id"], cwd=registry))["data"] == evaluation
    assert (await cli.run(kind.lower(), "@captured", "evaluation", evaluation["evaluation_id"], "reconcile", "--yes", cwd=registry))["data"] == evaluation
    # The actual PostgreSQL triggers protect the ledger even against paths
    # which bypass the application store. Both failed writes roll back.
    from sqlalchemy.exc import DBAPIError
    evidence_engine = create_engine(Settings())
    evidence_sessions = create_session_factory(evidence_engine)
    owner_schema = kind.lower()
    try:
        for statement in (
            f"UPDATE {owner_schema}.asac_evaluations SET suite_digest = :changed WHERE id = :id",
            f"DELETE FROM {owner_schema}.asac_evaluations WHERE id = :id",
        ):
            with pytest.raises(DBAPIError, match="(immutable|cannot be deleted)"):
                async with evidence_sessions.begin() as evidence_session:
                    await evidence_session.execute(text(statement), {"id": UUID(evaluation["evaluation_id"]), "changed": "sha256:" + "0" * 64})
    finally:
        await evidence_engine.dispose()
    assert (await cli.run(kind.lower(), "@captured", "evaluation", evaluation["evaluation_id"], cwd=registry))["data"] == evaluation
    if kind == "Agent":
        # Moving native current Staging after qualification cannot retarget an
        # exact publication. Native Stage remains an explicitly separate action.
        await cli.run("agent",resource_id,"stage","--yes")
        moved_staging = (await cli.run("agent",resource_id,"current","--env","staging"))["data"]
        assert moved_staging["snapshot_id"] != native_staging_before["snapshot_id"]
        native_staging_before = moved_staging
        publication_body={"operation_id":str(uuid4()),"candidate_id":candidate["candidate_id"],
            "evaluation_id":evaluation["evaluation_id"],"reason":"Publish the exact qualified candidate"}
        publication = (await cli.run("agent", "@captured", "publish", "--candidate", candidate["candidate_id"],
            "--evaluation", evaluation["evaluation_id"], "--notes", publication_body["reason"], "--yes", cwd=registry))["data"]
        publication_body["operation_id"] = publication["operation_id"]
        assert (await cli.run("agent", resource_id, "publication", publication["publication_id"], "--no-project-config"))["data"] == publication
        receipt_files = list(registry.glob(".woobe/**/publications/*.yaml"))
        assert len(receipt_files) == 1
        assert "authenticated_connection_observation" in receipt_files[0].read_text()
        assert (await cli.run("agent", "@captured", "history", "verify", cwd=registry))["data"]["publication_receipts"] == 1
        assert publication["published"] and not publication["production_changed"]
        assert publication["runtime_digest"]==candidate["runtime_digest"]
        assert publication["record_digest"]==candidate["record_digest"]
        assert publication["git"]["status"]=="unavailable"
        assert await cli.data("request","POST",base+"/publications",body=publication_body)==publication
        assert await cli.data("request","GET",base+"/publications/"+publication["publication_id"])==publication
        reused=await cli.data("request","POST",base+"/publications",body={**publication_body,"operation_id":str(uuid4()),"reason":"New provenance for the same exact published snapshot"})
        assert reused["publication_id"]!=publication["publication_id"]
        assert reused["release_id"]==publication["release_id"] and reused["reused"]
        from modules.agent.infra.database.models import AgentReleaseModel
        from modules.agent.infra.database.provider_model_repositories import SQLAlchemyAgentReleaseRepositoryWithProviderModels
        from modules.agent.domain.execution_definition import hash_agent_execution_snapshot
        publication_engine=create_engine(Settings())
        publication_sessions=create_session_factory(publication_engine)
        try:
            async with publication_sessions() as publication_session:
                frozen=await publication_session.get(AgentReleaseModel,UUID(candidate["snapshot_id"]))
                published=await publication_session.get(AgentReleaseModel,UUID(publication["release_id"]))
                assert frozen.snapshot_kind=="candidate" and published.snapshot_kind=="release"
                assert "sha256:"+hash_agent_execution_snapshot(await SQLAlchemyAgentReleaseRepositoryWithProviderModels(publication_session).get_by_id(published.id))==candidate["runtime_digest"]
            for statement in (
                "UPDATE agent.asac_publications SET reason = :changed WHERE id = :id",
                "DELETE FROM agent.asac_publications WHERE id = :id",
            ):
                with pytest.raises(DBAPIError,match="cannot be modified or deleted"):
                    async with publication_sessions.begin() as publication_session:
                        await publication_session.execute(text(statement),{"id":UUID(publication["publication_id"]),"changed":"tamper"})
        finally:
            await publication_engine.dispose()
    else:
        from modules.network.infra.database.models import NetworkVersionModel
        from modules.agent.infra.database.models import AgentReleaseModel
        from modules.network.domain.execution_identity import network_runtime_digest
        publication_engine = create_engine(Settings())
        publication_sessions = create_session_factory(publication_engine)
        async with publication_sessions() as publication_session:
            frozen_network = await publication_session.get(NetworkVersionModel, UUID(candidate["snapshot_id"]))
            constituents = {binding["agent_id"] for binding in frozen_network.resolved_bindings.values()}
        standalone_before = {}
        for agent_id in sorted(constituents):
            for environment in ("draft", "staging", "production"):
                standalone_before[agent_id, environment] = (await cli.run("agent", agent_id, "current", "--env", environment))["data"]
        publication_body = {"operation_id": str(uuid4()), "candidate_id": candidate["candidate_id"],
            "evaluation_id": evaluation["evaluation_id"], "reason": "Publish the exact qualified Network"}
        publication = (await cli.run("network", "@captured", "publish", "--candidate", candidate["candidate_id"],
            "--evaluation", evaluation["evaluation_id"], "--notes", publication_body["reason"], "--yes", cwd=registry))["data"]
        publication_body["operation_id"] = publication["operation_id"]
        inspected = (await cli.run("network", resource_id, "publication", publication["publication_id"], "--no-project-config"))["data"]
        assert (await cli.run("network", "@captured", "history", "verify", cwd=registry))["data"]["publication_receipts"] == 1
        assert len(list(registry.glob(".woobe/**/publications/*.yaml"))) == 1
        assert inspected["state"] == "published", inspected
        assert publication == inspected and publication["published"] and not publication["production_changed"]
        assert publication["runtime_digest"] == candidate["runtime_digest"]
        original_acceptance = (await cli.data("request", "GET", base + "/operations/" + publication_body["operation_id"]))["result"]
        assert original_acceptance["state"] == "preparing" and not original_acceptance["complete"]
        assert await cli.data("request", "POST", base + "/publications", body=publication_body) == original_acceptance
        assert await cli.data("request", "POST", base + "/publications/" + publication["publication_id"] + "/reconcile") == publication
        try:
            async with publication_sessions() as publication_session:
                published_network = await publication_session.get(NetworkVersionModel, UUID(publication["release_id"]))
                assert published_network.kind == "release" and published_network.id != frozen_network.id
                assert published_network.composition_hash != frozen_network.composition_hash
                assert network_runtime_digest(published_network.definition, published_network.resolved_bindings,
                    published_network.effective_external_context_contract) == candidate["runtime_digest"]
                for binding in published_network.resolved_bindings.values():
                    published_agent = await publication_session.get(AgentReleaseModel, UUID(binding["release_id"]))
                    assert published_agent.snapshot_kind == "release" and binding["binding_source"] == "release"
            for statement, identifier in (
                ("UPDATE network.asac_publications SET reason = :changed WHERE id = :id", publication["publication_id"]),
                ("DELETE FROM network.asac_publications WHERE id = :id", publication["publication_id"]),
                ("UPDATE network.network_versions SET version = :changed WHERE id = :id", publication["release_id"]),
                ("UPDATE agent.agent_releases SET model = :changed WHERE id = :id", publication["constituent_releases"][0]["release_id"]),
            ):
                with pytest.raises(DBAPIError, match="(?i)immutable"):
                    async with publication_sessions.begin() as publication_session:
                        await publication_session.execute(text(statement), {"id": UUID(identifier), "changed": "tamper"})
            # Reject only this deliberate final owner commit. Child copies already
            # have durable original receipts in their own owner transactions.
            for cancel in (False, True):
                interrupted_body = {**publication_body, "operation_id": str(uuid4()), "reason": "Exercise recoverable publication phases"}
                fault_name = "asac_test_fail_" + uuid4().hex
                async with publication_sessions.begin() as publication_session:
                    await publication_session.execute(text(f"CREATE FUNCTION network.{fault_name}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'controlled publication fault'; END $$"))
                    await publication_session.execute(text(f"CREATE TRIGGER {fault_name} BEFORE INSERT ON network.asac_publications FOR EACH ROW WHEN (NEW.operation_id = '{interrupted_body['operation_id']}'::uuid) EXECUTE FUNCTION network.{fault_name}()"))
                try:
                    interrupted = await cli.data("request", "POST", base + "/publications", body=interrupted_body)
                    assert interrupted["state"] == "preparing" and not interrupted["published"]
                    pending = await cli.data("request", "GET", base + "/publications/" + interrupted["publication_id"])
                    assert pending["prepared_constituents"] == pending["required_constituents"]
                    assert pending["error_code"] == "ASAC_PUBLICATION_PREPARATION_PENDING"
                finally:
                    async with publication_sessions.begin() as publication_session:
                        await publication_session.execute(text(f"DROP TRIGGER {fault_name} ON network.asac_publications"))
                        await publication_session.execute(text(f"DROP FUNCTION network.{fault_name}()"))
                if cancel:
                    closed = (await cli.run("network", resource_id, "publication", interrupted["publication_id"], "cancel", "--notes", "Discard the blocked publication", "--yes", "--no-project-config"))["data"]
                    assert closed["state"] == "cancelled" and closed["complete"] and not closed["published"]
                    await cli.run("request", "POST", base + "/publications/" + interrupted["publication_id"] + "/reconcile", expected=6)
                else:
                    resumed = (await cli.run("network", resource_id, "publication", interrupted["publication_id"], "reconcile", "--yes", "--no-project-config"))["data"]
                    assert resumed["published"] and resumed["release_id"] == publication["release_id"] and resumed["reused"]
                    assert await cli.data("request", "POST", base + "/publications/" + interrupted["publication_id"] + "/reconcile") == resumed
                async with publication_sessions() as publication_session:
                    count = await publication_session.scalar(text("SELECT count(*) FROM network.asac_publications WHERE project_id = :project AND operation_id = :operation"),
                        {"project": UUID(cli.project_id), "operation": UUID(interrupted_body["operation_id"])})
                    assert count == (0 if cancel else 1)
            for (agent_id, environment), before in standalone_before.items():
                after = (await cli.run("agent", agent_id, "current", "--env", environment))["data"]
                assert {key: value for key, value in after.items() if key != "observed_at"} == {key: value for key, value in before.items() if key != "observed_at"}
        finally:
            await publication_engine.dispose()
    # Counter rollback and deletion cannot hide an A -> B -> A transition.
    generation_engine=create_engine(Settings())
    generation_sessions=create_session_factory(generation_engine)
    try:
        for statement in (
            f"UPDATE {kind.lower()}.asac_environment_selections SET generation=generation-1 WHERE project_id=:project AND resource_id=:root AND environment='production'",
            f"DELETE FROM {kind.lower()}.asac_environment_selections WHERE project_id=:project AND resource_id=:root AND environment='production'",
        ):
            with pytest.raises(DBAPIError,match="(generation must advance|cannot be deleted)"):
                async with generation_sessions.begin() as generation_session:
                    await generation_session.execute(text(statement),{"project":UUID(cli.project_id),"root":UUID(resource_id)})
    finally:
        await generation_engine.dispose()
    # observed_at is a fresh read timestamp, not lifecycle state or generation.
    def selected_state(data):
        return {key: value for key, value in data.items() if key != "observed_at"}
    assert selected_state((await cli.run(kind.lower(), resource_id, "current", "--env", "draft"))["data"]) == selected_state(native_draft_before)
    assert selected_state((await cli.run(kind.lower(), resource_id, "current", "--env", "staging"))["data"]) == selected_state(native_staging_before)
    assert selected_state((await cli.run(kind.lower(), resource_id, "current", "--env", "production"))["data"]) == selected_state(native_production_before)
    assert json.loads(scoped_state_file.read_text()) == state_before_stage
    assert descriptor.read_bytes() == b"# local author comment\n" + original_source
    catalog_first = await cli.data("request", "GET", base + "/revisions", "--query", "limit=1")
    assert catalog_first["has_more"] and not catalog_first["complete"]
    import shutil
    shutil.rmtree(registry / config["root"] / ".state")
    restored = (await cli.run(kind.lower(), "@captured", "checkout", "--revision", checkpoint["revision_id"], cwd=registry))["data"]
    assert restored["working_revision"] == checkpoint["revision_id"] and restored["origin_preserved"]
    assert not restored["remote_changed"] and descriptor.read_bytes() == original_source
    selected = (await cli.run(kind.lower(), "@captured", "draft", "select", "cli-hotfix", cwd=registry))["data"]
    assert selected["selected"] and not selected["remote_changed"] and not selected["local_files_changed"]
    assert selected["draft"]["draft_id"] == cli_open["draft_id"]
    assert descriptor.read_bytes() == original_source
    opening = {"operation_id":str(uuid4()),"resource_uid":uid,"name":"hotfix","source_export_id":export["export_id"]}
    first = await cli.data("request","POST",base+"/drafts",body=opening)
    replay = await cli.data("request","POST",base+"/drafts",body=opening)
    assert first == replay and first["generation"] == 1 and not first["production_changed"]
    feature = await cli.data("request","POST",base+"/drafts",body={**opening,"operation_id":str(uuid4()),"name":"feature"})
    assert feature["draft_id"] != first["draft_id"]
    listing = await cli.data("request","GET",base+"/drafts")
    assert {item["name"] for item in listing["drafts"]} == {"default","hotfix","feature","cli-hotfix"}
    assert next(item for item in listing["drafts"] if item["name"]=="default")["content_status"] == "legacy_native_draft"
    async with httpx.AsyncClient(base_url=cli.origin, headers={"Authorization":"Bearer "+cli.credential}) as http:
        response = await http.get(f"/projects/{cli.project_id}/packages/exports/{export['export_id']}/artifact")
        assert response.status_code == 200
        content = response.content
        uploaded = await http.post(f"/projects/{cli.project_id}/packages/uploads?locked=true", files={"file":("package.tar.gz", content, "application/gzip")})
        assert uploaded.status_code == 201
        upload = uploaded.json()["data"]
    with receive_archive(io.BytesIO(content),locked=True) as bundle:
        definition, components = portable_definition(bundle)
        assert definition == first["definition_digest"]
        entry = bundle.graph.manifest["spec"]["entrypoint"]["ref"]
    save = {"operation_id":str(uuid4()),"expected_generation":1,"upload_id":upload["upload_id"],"artifact_digest":"sha256:"+upload["artifact_digest"]}
    saved = await cli.data("request","PUT",base+"/drafts/"+first["draft_id"],body=save)
    assert saved["generation"] == 2
    assert await cli.data("request","PUT",base+"/drafts/"+first["draft_id"],body=save) == saved
    stale = await cli.run("request","PUT",base+"/drafts/"+first["draft_id"],body={**save,"operation_id":str(uuid4())},expected=6)
    assert stale["error"]["http_status"] == 409
    async with httpx.AsyncClient(base_url=cli.origin, headers={"Authorization":"Bearer "+cli.credential}) as http:
        refused = await http.put(base+"/drafts/"+first["draft_id"],json={**save,"operation_id":str(uuid4())})
        assert refused.status_code == 409
        assert refused.json()["data"]["diagnostics"][0]["code"] == "ASAC_DRAFT_CHANGED"
    component_uids = {key:str(uuid4()) for key in components}; component_uids[entry] = uid
    record = {"format":"woobe-revision","schema_version":"1.0","revision_id":"rv_"+str(uuid4()),"resource_uid":uid,"kind":kind,"parents":[],"message":"Captured exact object","artifact_digest":save["artifact_digest"],"definition_digest":definition,"definition_digest_scope":"woobe-portable-definition@1.0","component_digests":{component_uids[key]:value for key,value in components.items()}}
    record["record_digest"] = asac_digest("record",record)
    registration = {"operation_id":str(uuid4()),"draft_id":first["draft_id"],"expected_generation":2,"record":record,"component_uids":component_uids}
    accepted = await cli.data("request","POST",base+"/revisions",body=registration)
    assert accepted["record"] == record and not accepted["production_changed"]
    # Page one's watermark excludes the independently registered third record.
    catalog_ids = [item["record"]["revision_id"] for item in catalog_first["records"]]
    page = catalog_first
    while page["has_more"]:
        page = await cli.data("request", "GET", base + "/revisions", "--query", "limit=1", "--query", "cursor=" + page["next_cursor"])
        assert page["watermark"] == catalog_first["watermark"]
        catalog_ids.extend(item["record"]["revision_id"] for item in page["records"])
    assert set(catalog_ids) == {checkpoint["revision_id"], comment_revision["revision_id"]}
    fetched = (await cli.run(kind.lower(), "@captured", "history", "fetch", "--revisions", cwd=registry))["data"]
    assert fetched["fetched"] == 3 and fetched["metadata_complete"]
    assert fetched["objects_available"] == "not_downloaded"
    assert not fetched["author_files_changed"] and not fetched["production_changed"]
    hydrated = (await cli.run(kind.lower(), "@captured", "revision", "hydrate", record["revision_id"], cwd=registry))["data"]
    assert hydrated["hydrated"] and hydrated["executable_object"] == "verified"
    assert hydrated["author_object"] == "unavailable" and not hydrated["bindings_restored"]
    assert not hydrated["working_head_changed"] and not hydrated["author_files_changed"]
    assert not hydrated["production_changed"]
    executable_path = registry / config["root"] / "objects" / "sha256" / (record["artifact_digest"].removeprefix("sha256:") + ".tar.gz")
    assert executable_path.is_file()

    assert descriptor.read_bytes() == original_source
    # Recover exact commented source using a different server reader, with no
    # local source objects or private bindings left to supply its original bytes.
    author_root = registry / config["root"] / "objects" / "author"
    shutil.rmtree(author_root)
    _, source_reader = await cli.issue("workspace", "control-key", "create", body={
        "name": "Independent history reader", "expires_at": (datetime.now(UTC) + timedelta(minutes=30)).isoformat(), "on_project_create_permissions": [],
        "project_grants": [{"project_id": cli.project_id, "permissions": ["project:read", kind.lower() + ":read"]}]})
    source_hydrated = (await cli.run(kind.lower(), "@captured", "revision", "hydrate", comment_revision["revision_id"], cwd=registry, key=source_reader))["data"]
    assert source_hydrated["author_object"] == "verified_source_and_compilation"
    assert not source_hydrated["bindings_restored"] and not source_hydrated["author_files_changed"]
    assert descriptor.read_bytes() == original_source
    # Guarded checkout must also verify the current clean source anchor. Do not
    # bypass this protection merely because the target source was recovered.
    await cli.run(kind.lower(), "@captured", "revision", "hydrate", checkpoint["revision_id"], cwd=registry, key=source_reader)
    commented_checkout = (await cli.run(kind.lower(), "@captured", "checkout", "--revision", comment_revision["revision_id"], cwd=registry))["data"]
    assert commented_checkout["working_revision"] == comment_revision["revision_id"] and descriptor.read_bytes() == b"# local author comment\n" + original_source

    reconciled = await cli.data("request","GET",base+"/operations/"+registration["operation_id"])
    assert reconciled["state"] == "committed" and reconciled["result"] == accepted
    unknown = await cli.data("request","GET",base+"/operations/"+str(uuid4()))
    assert not unknown["complete"] and not unknown["retry_authorized"]
    observed = (await cli.run(kind.lower(),resource_id,"current","--env","production"))["data"]
    assert observed["snapshot_id"] == export["source"]["snapshot_id"]
    return {"publication": publication, "registry": registry, "binding_spec": binding_spec}

@pytest.mark.asyncio
async def test_cli_categories_pin_authority_and_preflight_matches_requests(cli):
    project = await cli.data(
        "project",
        "create",
        body={
            "workspace_id": cli.workspace_id,
            "name": "Authority contract",
            "slug": str(uuid4()),
        },
    )
    cli.project_id = project["id"]
    catalog = await cli.data("permission", "list")
    # Seed remote discovery evidence without making an external MCP network call.
    from modules.agent.infra.database.models import AgentToolModel

    tool_id = uuid4()
    tool_engine = create_engine(Settings())
    tool_factory = create_session_factory(tool_engine)
    try:
        async with tool_factory() as session:
            session.add(
                AgentToolModel(
                    id=tool_id,
                    project_id=UUID(cli.project_id),
                    name="CLI MCP permissions",
                    type="mcp",
                    config={
                        "protocol": "mcp",
                        "discovered_tools": [
                            {"name": "search", "permission": {"mode": "review"}},
                            {"name": "write", "permission": {"mode": "deny"}},
                        ],
                    },
                )
            )
            await session.commit()
    finally:
        await tool_engine.dispose()
    for mode in ["allow", "deny", "review"]:
        permissions = await cli.data(
            "project",
            "tool",
            "mcp",
            "set",
            "--validate-body",
            body={
                "tool_id": str(tool_id),
                "permissions": [{"remote_tool_name": "search", "mode": mode}],
            },
        )
        assert {item["name"]: item["mode"] for item in permissions["permissions"]} == {
            "search": mode,
            "write": "deny",
        }
    await cli.run(
        "project",
        "tool",
        "mcp",
        "set",
        body={
            "tool_id": str(tool_id),
            "permissions": [
                {"remote_tool_name": "search", "mode": "allow"},
                {"remote_tool_name": "missing", "mode": "allow"},
            ],
        },
        expected=2,
    )
    observed = await cli.data("project", "tool", "list", "--validate-parameters")
    provider = next(item for item in observed if item["id"] == str(tool_id))
    assert {
        item["name"]: item["permission"]["mode"]
        for item in provider["config"]["discovered_tools"]
    } == {"search": "review", "write": "deny"}
    for mode in ["allow", "deny", "review"]:
        bulk = await cli.data(
            "project",
            "tool",
            "mcp",
            "bulk",
            "--validate-body",
            body={"tool_id": str(tool_id), "mode": mode},
        )
        assert all(item["mode"] == mode for item in bulk["permissions"])

    mcp_permission = {
        "tool_id": str(uuid4()),
        "permissions": [{"remote_tool_name": "search", "mode": "review"}],
    }
    mcp_preflight = await cli.run(
        "validate-input", "--command", "project tool mcp set", body=mcp_permission
    )
    assert mcp_preflight["data"]["valid"] is True
    assert mcp_preflight["data"]["executed"] is False
    invalid_mcp = await cli.run(
        "validate-input",
        "--command",
        "project tool mcp set",
        body={
            **mcp_permission,
            "permissions": [{"remote_tool_name": "search", "mode": "allow-everything"}],
        },
        expected=2,
    )
    assert invalid_mcp["error"].get("http_status") is None
    assert "agent:read" in catalog["permissions"]["project"]
    definition = {
        "schema_version": "2",
        "workspace_id": cli.workspace_id,
        "resources": [
            {
                "key": "reader",
                "kind": "AuthorityCategory",
                "action": "create",
                "spec": {
                    "name": "scoped-reader",
                    "scope": "project",
                    "permissions": ["agent:read"],
                },
            }
        ],
    }
    preflight = await cli.run(
        "manifest",
        "preflight",
        "--validate-parameters",
        "--require-complete",
        body=definition,
    )
    assert preflight["data"]["complete"] is True
    assert preflight["data"]["executed"] is False
    checkpoint = str(cli.directory / "category-create-checkpoint.json")
    imported = await cli.run(
        "manifest",
        "apply",
        "--validate-body",
        "--validate-parameters",
        "--checkpoint",
        checkpoint,
        body=definition,
    )
    category = imported["data"]["results"]["reader"]
    resumed = await cli.run(
        "manifest", "apply", "--checkpoint", checkpoint, body=definition
    )
    assert resumed["data"]["results"]["reader"]["id"] == category["id"]
    category_id = category["id"]
    etag = f'"category:{category_id}:{category["revision"]}"'
    _, reader_key = await cli.issue(
        "workspace",
        "control-key",
        "create",
        body={
            "name": "Pinned reader",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "on_project_create_permissions": [],
            "project_grants": [
                {
                    "project_id": cli.project_id,
                    "category_id": category_id,
                    "category_revision": 1,
                }
            ],
        },
    )
    changed = await cli.data(
        "workspace",
        "authority",
        "category",
        "update",
        category_id,
        "--if-match",
        etag,
        body={"permissions": ["agent:read", "agent:write"]},
    )
    assert changed["revision"] == 2
    revision_diff = await cli.run(
        "workspace",
        "authority",
        "category",
        "diff",
        category_id,
        "--from-revision",
        "1",
        "--to-revision",
        "2",
    )
    assert revision_diff["data"]["grants_changed"] is False
    assert [item["field"] for item in revision_diff["data"]["changes"]] == [
        "permissions"
    ]
    unchanged_definition = {
        "schema_version": "2",
        "workspace_id": cli.workspace_id,
        "resources": [
            {
                "key": "reader",
                "kind": "AuthorityCategory",
                "action": "update",
                "resource_id": category_id,
                "if_match": f'"category:{category_id}:2"',
                "spec": {"permissions": ["agent:write", "agent:read"]},
            }
        ],
    }
    unchanged = await cli.run(
        "manifest",
        "apply",
        "--skip-unchanged",
        "--checkpoint",
        str(cli.directory / "category-unchanged.json"),
        body=unchanged_definition,
    )
    assert unchanged["data"]["steps"]["reader"] == "unchanged"
    observed = await cli.data("workspace", "authority", "category", "get", category_id)
    assert observed["revision"] == 2
    capture = await cli.run(
        "manifest",
        "capture",
        "--kind",
        "AuthorityCategory",
        "--id",
        category_id,
        "--field",
        "name",
        "--field",
        "permissions",
    )
    assert capture["data"]["document"]["workspace_id"] == cli.workspace_id
    assert (
        capture["data"]["document"]["resources"][0]["if_match"]
        == f'"category:{category_id}:2"'
    )
    stale = await cli.run(
        "workspace",
        "authority",
        "category",
        "update",
        category_id,
        "--if-match",
        etag,
        body={"name": "Rejected stale edit"},
        expected=6,
    )
    assert stale["error"]["http_status"] == 412
    pinned = await cli.data(
        "workspace",
        "authority",
        "category",
        "get",
        category_id,
        "--query",
        "revision=1",
    )
    assert pinned["permissions"] == ["agent:read"]
    authority = await cli.data(
        "permission",
        "effective",
        "--query",
        f"project_id={cli.project_id}",
        key=reader_key,
    )
    assert "agent:write" not in authority["permissions"]
    assert authority["origin"]["revision"] == 1
    for method, path, allowed in [
        ("GET", "/ai/agents", True),
        ("POST", "/ai/agents", False),
    ]:
        decision = await cli.data(
            "permission",
            "check",
            key=reader_key,
            body={
                "method": method,
                "path": path,
                "query": {"project_id": cli.project_id},
                "body": {"project_id": cli.project_id},
            },
        )
        assert decision["allowed"] is allowed
        if allowed:
            await cli.run(
                "request",
                method,
                path,
                "--query",
                f"project_id={cli.project_id}",
                key=reader_key,
            )
        else:
            await cli.run(
                "request",
                method,
                path,
                body={"project_id": cli.project_id},
                key=reader_key,
                expected=4,
            )
    history_response = await cli.run(
        "workspace",
        "authority",
        "category",
        "history",
        category_id,
        "--limit",
        "1",
    )
    assert history_response["success"] is True
    assert history_response["meta"]["complete"] is False
    assert history_response["meta"]["collection_complete"] == "partial"
    history = history_response["data"]["data"]
    assert history["complete"] is False
    assert history["next_revision"] == 2
    page = await cli.data(
        "workspace",
        "authority",
        "category",
        "history",
        category_id,
        "--query",
        "limit=1",
        "--query",
        "before_revision=2",
    )
    assert page["complete"] is True
    assert page["items"][0]["permissions"] == ["agent:read"]
    history_all = await cli.run(
        "workspace",
        "authority",
        "category",
        "history",
        category_id,
        "--limit",
        "1",
        "--all",
    )
    assert history_all["meta"]["complete"] is True
    assert history_all["data"]["page_count"] == 2
    assert [
        item["revision"]
        for received in history_all["data"]["pages"]
        for item in received["data"]["items"]
    ] == [2, 1]
    history_remaining = await cli.run(
        "workspace",
        "authority",
        "category",
        "history",
        category_id,
        "--limit",
        "1",
        "--before-revision",
        "2",
        "--all",
    )
    assert history_remaining["meta"]["complete"] is False
    assert history_remaining["meta"]["collection_complete"] == "remaining"
    bounded_history = await cli.run(
        "workspace",
        "authority",
        "category",
        "history",
        category_id,
        "--limit",
        "1",
        "--all",
        "--max-pages",
        "1",
        expected=10,
    )
    assert bounded_history["data"]["page_count"] == 1
    assert bounded_history["data"]["next_query"]["before_revision"] == ["2"]
    assert bounded_history["meta"]["complete"] is False
    clone = await cli.data(
        "workspace",
        "authority",
        "category",
        "clone",
        category_id,
        body={"name": "unused-clone", "revision": 1},
    )
    assert clone["permissions"] == ["agent:read"]
    categories_all = await cli.run(
        "workspace",
        "authority",
        "category",
        "list",
        "--limit",
        "1",
        "--all",
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
        "workspace",
        "authority",
        "audit",
        "--limit",
        "1",
        "--all",
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
        "workspace",
        "authority",
        "category",
        "archive",
        clone["id"],
        "--validate-body",
        "--validate-parameters",
        "--if-match",
        f'"category:{clone["id"]}:1"',
        body={},
    )
    assert archived["status"] == "archived"
    await cli.run(
        "workspace",
        "authority",
        "category",
        "delete",
        clone["id"],
        "--if-match",
        f'"category:{clone["id"]}:{archived["revision"]}"',
    )


@pytest.mark.asyncio
async def test_cli_connection_auth_discovers_scope_and_persists_without_environment(
    cli,
):
    project = await cli.run(
        "project",
        "create",
        body={
            "workspace_id": cli.workspace_id,
            "name": "Auth project",
            "slug": "auth-project",
        },
    )
    project_id = project["data"]["data"]["id"]
    issued, secret = await cli.issue(
        "workspace",
        "control-key",
        "create",
        body={
            "name": "Project-only connection",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "permissions": [],
            "project_grants": [
                {"project_id": project_id, "permissions": ["agent:read"]}
            ],
        },
    )
    known_secrets = [secret]
    config_path = cli.directory / "connection-auth.json"
    clean_env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("WOOBE_CONTEXT")
        and k
        not in {
            "WOOBE_CONTROL_KEY",
            "WOOBE_WORKSPACE_ID",
            "WOOBE_PROJECT_ID",
            "WOOBE_API_URL",
            "WOOBE_CREDENTIAL",
            "WOOBE_RUNTIME_CREDENTIAL",
        }
    }

    async def run(*args, stdin=None, expected=0):
        process = await asyncio.create_subprocess_exec(
            cli.binary,
            "--config",
            str(config_path),
            *args,
            env=clean_env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(process.communicate(stdin), 30)
        assert process.returncode == expected, (out.decode(), err.decode())
        assert all(value.encode() not in out + err for value in known_secrets)
        return json.loads(out)

    invocation_schema = await run("schema", "--command", "auth login", "--kind", "input")
    flags_schema = invocation_schema["data"]["properties"]["flags"]
    assert "file" not in flags_schema["required"]
    assert len(flags_schema["anyOf"]) == 2
    await run("context", "create", "connection", "--api-url", cli.origin)
    await run("context", "use", "connection")
    login = await run("auth", "login", "--cli-key", "--stdin", stdin=secret.encode())
    assert login["data"]["project_id"] == project_id
    saved = json.loads(config_path.read_text())["contexts"]["connection"]
    assert (
        saved["workspace_id"] == cli.workspace_id and saved["project_id"] == project_id
    )
    assert secret not in config_path.read_text()
    status = await run("auth", "status")
    assert status["data"]["identity"]["key_metadata"]["permissions"] == []
    assert status["data"]["state"] == "authenticated"
    assert (await run("project", "agent", "list"))["success"] is True
    await run("auth", "logout", "--cli-key")
    assert (
        json.loads(config_path.read_text())["contexts"]["connection"].get("credential")
        is None
    )
    # Local logout must not revoke the server key.
    async with httpx.AsyncClient(trust_env=False) as client:
        response = await client.get(
            f"{cli.origin}/identity/control-key/me",
            headers={"Authorization": f"Bearer {secret}"},
        )
    assert response.status_code == 200

    other = await cli.data(
        "project",
        "create",
        body={
            "workspace_id": cli.workspace_id,
            "name": "Other auth project",
            "slug": "auth-other",
        },
    )
    _, multi_secret = await cli.issue(
        "workspace",
        "control-key",
        "create",
        body={
            "name": "Multiple projects",
            "permissions": [],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "project_grants": [
                {"project_id": target, "permissions": ["agent:read"]}
                for target in [project_id, other["id"]]
            ],
        },
    )
    known_secrets.append(multi_secret)
    await run("context", "create", "multi", "--api-url", cli.origin)
    await run("context", "use", "multi")
    result = await run(
        "auth", "login", "--cli-key", "--stdin", stdin=multi_secret.encode()
    )
    assert result["data"]["state"] == "project_selection_required"
    assert result["data"]["project_id"] == ""
    await run("context", "project", "select", "auth-other")
    assert (
        json.loads(config_path.read_text())["contexts"]["multi"]["project_id"]
        == other["id"]
    )
    assert (await run("project", "agent", "list"))["success"] is True
    before = config_path.read_bytes()
    await run(
        "auth", "login", "--cli-key", "--stdin", stdin=b"invalid-cli-key", expected=3
    )
    assert config_path.read_bytes() == before
    _, workspace_secret = await cli.issue(
        "workspace",
        "control-key",
        "create",
        body={
            "name": "Workspace only",
            "permissions": [],
            "project_grants": [],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    known_secrets.append(workspace_secret)
    result = await run(
        "auth", "login", "--cli-key", "--stdin", stdin=workspace_secret.encode()
    )
    assert (
        result["data"]["state"] == "authenticated" and result["data"]["projects"] == []
    )
    assert "project_id" not in json.loads(config_path.read_text())["contexts"]["multi"]
    await run("auth", "logout", "--cli-key")


async def exercise_asac_workflow_leases(cli,kind,resource_id,draft_id):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlalchemy.exc import DBAPIError
    from shared.infra.database.session import create_engine
    from shared.infra.config import Settings
    owner=kind.lower()
    base=f"/projects/{cli.project_id}/{owner}s/{resource_id}/asac"
    acquire={"operation_id":str(uuid4()),"workflow_id":str(uuid4()),"scope":"draft","draft_id":draft_id,"ttl_seconds":3}
    first=await cli.data("request","POST",base+"/leases/acquire",body=acquire)
    assert first["clock_authority"]=="database" and first["fencing_token"]==1
    assert await cli.data("request","POST",base+"/leases/acquire",body=acquire)==first
    await cli.run("request","POST",base+"/leases/acquire",body={**acquire,"operation_id":str(uuid4())},expected=6)
    proof={key:first[key] for key in ("lease_id","workflow_id","fencing_token")}
    engine=create_engine(Settings())
    sessions=async_sessionmaker(engine,expire_on_commit=False)
    try:
        # A lease valid at SQL mutation can expire before commit. The deferred
        # database guard must roll back the authoring write, independently of API.
        with pytest.raises(DBAPIError,match="ASAC_LEASE_EXPIRED"):
            async with sessions.begin() as session:
                await session.execute(text("SELECT set_config('woobe.asac_actor',:actor,true),set_config('woobe.asac_lease_proofs',:proofs,true),set_config('woobe.asac_lease_resource',:root,true)"),{"actor":first["actor"],"proofs":json.dumps([proof]),"root":resource_id})
                await session.execute(text(f"UPDATE {owner}.asac_drafts SET generation=generation+1 WHERE id=:draft"),{"draft":UUID(draft_id)})
                await session.execute(text("SELECT pg_sleep(3.1)"))
        expired=await cli.data("request","GET",base+"/leases","--query","scope=draft","--query",f"draft_id={draft_id}")
        assert expired["state"]=="expired"
        await cli.run("request","POST",base+"/leases/renew",body={**proof,"operation_id":str(uuid4()),"scope":"draft","draft_id":draft_id,"ttl_seconds":30},expected=6)
        second=await cli.data("request","POST",base+"/leases/acquire",body={**acquire,"operation_id":str(uuid4()),"workflow_id":str(uuid4()),"ttl_seconds":60})
        assert second["fencing_token"]==2 and second["lease_id"]!=first["lease_id"]
        body={"operation_id":str(uuid4()),"expected_generation":1,"upload_id":str(uuid4()),"artifact_digest":"sha256:"+"0"*64,"leases":[proof]}
        await cli.run("request","PUT",base+"/drafts/"+draft_id,body=body,expected=6)
        second_proof={key:second[key] for key in ("lease_id","workflow_id","fencing_token")}
        # A current authenticated workflow proof passes the real commit guard;
        # this no-op leaves the selected author's CAS unchanged for later cases.
        async with sessions.begin() as session:
            await session.execute(text("SELECT set_config('woobe.asac_actor',:actor,true),set_config('woobe.asac_lease_proofs',:proofs,true),set_config('woobe.asac_lease_resource',:root,true)"),{"actor":second["actor"],"proofs":json.dumps([second_proof]),"root":resource_id})
            await session.execute(text(f"UPDATE {owner}.asac_drafts SET generation=generation WHERE id=:draft"),{"draft":UUID(draft_id)})
        for statement in (
            f"UPDATE {owner}.asac_operation_leases SET fencing_token=fencing_token-1 WHERE project_id=:project AND resource_id=:root",
            f"DELETE FROM {owner}.asac_operation_leases WHERE project_id=:project AND resource_id=:root",
        ):
            with pytest.raises(DBAPIError,match="(cannot regress|cannot be deleted)"):
                async with sessions.begin() as session:
                    await session.execute(text(statement),{"project":UUID(cli.project_id),"root":UUID(resource_id)})
        released=await cli.data("request","POST",base+"/leases/release",body={**second_proof,"operation_id":str(uuid4()),"scope":"draft","draft_id":draft_id})
        assert released["state"]=="released"
        assert (await cli.data("request","GET",base+"/drafts/"+draft_id))["generation"]==1
    finally:
        await engine.dispose()


async def exercise_asac_deployments(cli, kind, resource_id, publication):
    from sqlalchemy.exc import DBAPIError
    registry=publication["registry"];publication=publication["publication"]
    """Real PostgreSQL owner selection/receipt/outbox and exact replay."""
    base=f"/projects/{cli.project_id}/{kind.lower()}s/{resource_id}/asac"
    production=(await cli.run(kind.lower(),resource_id,"current","--env","production"))["data"]
    plan_body={"operation_id":str(uuid4()),"release_id":publication["release_id"],
        "publication_id":publication["publication_id"],"environment":"production",
        "expected_generation":production["environment_generation"],"reason":"Activate the exact qualified Release"}
    plan=(await cli.run(kind.lower(),"@captured","deployment","plan","--release",publication["release_id"],"--publication",publication["publication_id"],"--expected-generation",str(production["environment_generation"]),"--notes",plan_body["reason"],cwd=registry))["data"]
    plan_body["operation_id"]=plan["operation_id"]
    assert not plan["executed"] and plan["release_id"]==publication["release_id"]
    assert await cli.data("request","POST",base+"/deployment-plans",body=plan_body)==plan
    lease=await cli.data("request","POST",base+"/leases/acquire",body={"operation_id":str(uuid4()),
        "workflow_id":str(uuid4()),"scope":"production","ttl_seconds":4})
    proof={key:lease[key] for key in ("lease_id","workflow_id","fencing_token")}
    apply={"operation_id":str(uuid4()),"plan_id":plan["plan_id"],"environment":"production","leases":[proof]}
    # The outbox insert happens after pointer/native-history mutation. Prove
    # that expiry during that insert rejects the entire commit, not just a
    # preliminary check. A sequence survives rollback and proves SQL was reached.
    expiry_engine=create_engine(Settings());expiry_sessions=create_session_factory(expiry_engine)
    owner=kind.lower();outbox="agent_outbox_events" if kind=="Agent" else "outbox_events"
    fault="expiry_"+uuid4().hex; sequence=fault+"_seq"
    async with expiry_sessions.begin() as session:
        await session.execute(text(f"CREATE SEQUENCE {owner}.{sequence}"))
        await session.execute(text(f"CREATE FUNCTION {owner}.{fault}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM nextval('{owner}.{sequence}'); PERFORM pg_sleep(4.2); RETURN NEW; END $$"))
        await session.execute(text(f"CREATE TRIGGER {fault} BEFORE INSERT ON {owner}.{outbox} FOR EACH ROW WHEN (NEW.aggregate_id='{resource_id}'::uuid AND NEW.event_type='{owner}.asac.environment.selected') EXECUTE FUNCTION {owner}.{fault}()"))
    try:
        expired_operation=apply["operation_id"]
        failed=await cli.run("request","POST",base+"/deployments",body=apply,expected=6)
        assert failed["error"]["http_status"]==409
        async with expiry_sessions() as session:
            assert await session.scalar(text(f"SELECT is_called FROM {owner}.{sequence}"))
            observed=await session.scalar(text(f"SELECT generation FROM {owner}.asac_environment_selections WHERE resource_id=:root AND environment='production'"),{"root":UUID(resource_id)})
            assert observed==production["environment_generation"]
            for table in ("asac_deployments","asac_operations"):
                assert await session.scalar(text(f"SELECT count(*) FROM {owner}.{table} WHERE operation_id=:id"),{"id":UUID(expired_operation)})==0
    finally:
        async with expiry_sessions.begin() as session:
            await session.execute(text(f"DROP TRIGGER {fault} ON {owner}.{outbox}"))
            await session.execute(text(f"DROP FUNCTION {owner}.{fault}()"))
            await session.execute(text(f"DROP SEQUENCE {owner}.{sequence}"))
        await expiry_engine.dispose()
    lease=(await cli.run(kind.lower(),"@captured","lease","acquire","--scope","production","--ttl","120",cwd=registry))["data"]
    replacement={key:lease[key] for key in ("lease_id","workflow_id","fencing_token")}
    assert replacement["fencing_token"]==proof["fencing_token"]+1
    await cli.run("request","POST",base+"/deployments",body={**apply,"operation_id":str(uuid4())},expected=6)
    proof=replacement;apply={**apply,"operation_id":str(uuid4()),"leases":[proof]}
    receipt=(await cli.run(kind.lower(),"@captured","deployment","apply",plan["plan_id"],"--yes",cwd=registry))["data"]
    apply["operation_id"]=receipt["operation_id"]
    assert (await cli.run(kind.lower(),"@captured","history","verify",cwd=registry))["data"]["deployment_receipts"]==1
    assert receipt["release_id"]==publication["release_id"] and receipt["state"]=="committed"
    assert receipt["generation_after"]==production["environment_generation"]+1
    assert await cli.data("request","POST",base+"/deployments",body=apply)==receipt
    assert await cli.data("request","GET",base+"/deployments/"+receipt["deployment_id"])==receipt
    assert (await cli.data("request","GET",base+"/operations/"+apply["operation_id"]))["result"]==receipt
    await cli.run("request","POST",base+"/deployments",body={**apply,"operation_id":str(uuid4())},expected=6)
    current=(await cli.run(kind.lower(),resource_id,"current","--env","production"))["data"]
    assert current["snapshot_id"]==publication["release_id"] and current["selection_authority"]=="asac"
    assert current["environment_generation"]==receipt["generation_after"]
    engine=create_engine(Settings());sessions=create_session_factory(engine)
    owner=kind.lower();outbox="agent_outbox_events" if kind=="Agent" else "outbox_events"
    try:
        async with sessions() as session:
            payload=await session.scalar(text(f"SELECT payload FROM {owner}.{outbox} WHERE id=:id"),{"id":UUID(receipt["outbox_id"])})
            assert payload==receipt
            if kind=="Agent":
                from modules.agent.infra.database.asac_runtime_release_repository import SQLAlchemySelectedAgentReleaseRepository
                selected=await SQLAlchemySelectedAgentReleaseRepository(session).get_active_production(UUID(resource_id))
                assert str(selected.id)==publication["release_id"]
        with pytest.raises(DBAPIError,match="immutable"):
            async with sessions.begin() as session:
                await session.execute(text(f"UPDATE {owner}.{outbox} SET payload='{{}}'::jsonb WHERE id=:id"),{"id":UUID(receipt["outbox_id"])})
        with pytest.raises(DBAPIError,match="DEPLOYMENT_RECEIPT_REQUIRED"):
            async with sessions.begin() as session:
                await session.execute(text(f"UPDATE {owner}.asac_environment_selections SET snapshot_id=NULL,execution_fingerprint=NULL,generation=generation+1 WHERE resource_id=:id AND environment='production'"),{"id":UUID(resource_id)})
    finally:
        await engine.dispose()
    await cli.data("request","POST",base+"/leases/release",body={**proof,"operation_id":str(uuid4()),"scope":"production"})

    # Both independent environments can select the same immutable Release.
    staging=(await cli.run(kind.lower(),resource_id,"current","--env","staging"))["data"]
    stage_plan=await cli.data("request","POST",base+"/deployment-plans",body={**plan_body,"operation_id":str(uuid4()),"environment":"staging","expected_generation":staging["environment_generation"]})
    stage_lease=await cli.data("request","POST",base+"/leases/acquire",body={"operation_id":str(uuid4()),"workflow_id":str(uuid4()),"scope":"staging","ttl_seconds":120})
    stage_proof={key:stage_lease[key] for key in ("lease_id","workflow_id","fencing_token")}
    stage_receipt=await cli.data("request","POST",base+"/deployments",body={"operation_id":str(uuid4()),"plan_id":stage_plan["plan_id"],"environment":"staging","leases":[stage_proof]})
    assert stage_receipt["generation_after"]==staging["environment_generation"]+1
    for environment in ("staging","production"):
        selected=(await cli.run(kind.lower(),resource_id,"current","--env",environment))["data"]
        assert selected["snapshot_id"]==publication["release_id"] and selected["selection_authority"]=="asac"
    await cli.data("request","POST",base+"/leases/release",body={**stage_proof,"operation_id":str(uuid4()),"scope":"staging"})
    # Runtime admission and environment export must consume the exact immutable
    # selection, including an Agent Release whose legacy status is still release.
    for environment in ("staging", "production"):
        _, runtime_key = await cli.issue(
            "project", "runtime-key", "create",
            body={"project_id": cli.project_id, "name": "Selected ASaC runtime",
                  "target_type": kind.lower(), "target_id": resource_id,
                  "environment": environment, "interfaces": ["http"],
                  "expires_at": (datetime.now(UTC)+timedelta(hours=1)).isoformat()},
        )
        result = await cli.run(
            "runtime", "target", "run", "selected-asac",
            "--target-kind", kind.lower(), body={"input": "Hello"},
            runtime_key=runtime_key,
        )
        assert result["data"]["success"] is True
        run_engine=create_engine(Settings());run_sessions=create_session_factory(run_engine)
        try:
            async with run_sessions() as session:
                if kind == "Agent":
                    from modules.agent.infra.database.run_models import AgentRunModel
                    run=await session.scalar(select(AgentRunModel).where(
                        AgentRunModel.agent_id==UUID(resource_id),
                        AgentRunModel.environment==environment,
                    ).order_by(AgentRunModel.created_at.desc()).limit(1))
                    assert run and str(run.agent_release_id)==publication["release_id"]
                    assert run.status == "completed"
                else:
                    from modules.network.infra.database.models import NetworkExecutionModel
                    run=await session.get(NetworkExecutionModel,UUID(result["data"]["data"]["execution_id"]))
                    assert run and str(run.network_version_id)==publication["release_id"]
        finally:
            await run_engine.dispose()
        exported=await cli.data("request","POST",f"/projects/{cli.project_id}/packages/export",
            body={"kind":kind,"target_id":resource_id,"source":environment,
                  "knowledge":"portable","development":True})
        assert exported["export_id"]
    # A new audited selection of the same executable is a no-op for generation.
    no_op_plan=await cli.data("request","POST",base+"/deployment-plans",body={**plan_body,"operation_id":str(uuid4()),"expected_generation":receipt["generation_after"]})
    no_op_lease=await cli.data("request","POST",base+"/leases/acquire",body={"operation_id":str(uuid4()),"workflow_id":str(uuid4()),"scope":"production","ttl_seconds":120})
    no_op_proof={key:no_op_lease[key] for key in ("lease_id","workflow_id","fencing_token")}
    no_op=await cli.data("request","POST",base+"/deployments",body={"operation_id":str(uuid4()),"plan_id":no_op_plan["plan_id"],"environment":"production","leases":[no_op_proof]})
    assert not no_op["selection_changed"] and no_op["generation_after"]==receipt["generation_after"]
    await cli.data("request","POST",base+"/leases/release",body={**no_op_proof,"operation_id":str(uuid4()),"scope":"production"})


async def exercise_asac_project_policy(cli, agent_id, publication, agent_body, definition, network_id, network_publication):
    from sqlalchemy.exc import DBAPIError
    policy_path=f"/core/projects/{cli.project_id}/lifecycle-policy"
    base=f"/projects/{cli.project_id}/agents/{agent_id}/asac"
    original=await cli.data("project","lifecycle","show")
    assert original['generation']==0 and not original['managed']
    current=(await cli.run("agent",agent_id,"current","--env","staging"))["data"]
    plan=await cli.data("request","POST",base+"/deployment-plans",body={
        "operation_id":str(uuid4()),"release_id":publication['publication']['release_id'],
        "environment":"staging","expected_generation":current['environment_generation'],
        "reason":"Before policy change"})
    body={'operation_id':str(uuid4()),'expected_generation':0,'managed':True,
          'production_actors':[],'reason':'Enable evaluated lifecycle'}
    await cli.run("request","PUT",policy_path,body=body,key=cli.policy_denied_key,expected=4)
    changed=await cli.data("project","lifecycle","update",body=body)
    assert changed['policy']['generation']==1 and changed['policy']['managed']
    assert await cli.data("request","PUT",policy_path,body=body)==changed
    assert await cli.data("project","lifecycle","operation",body['operation_id'])==changed
    await cli.run("request","PUT",policy_path,body={**body,'operation_id':str(uuid4())},expected=6)
    lease=await cli.data("request","POST",base+"/leases/acquire",body={
        "operation_id":str(uuid4()),"workflow_id":str(uuid4()),"scope":"staging","ttl_seconds":120})
    proof={key:lease[key] for key in ('lease_id','workflow_id','fencing_token')}
    stale=await cli.run("request","POST",base+"/deployments",body={
        'operation_id':str(uuid4()),'plan_id':plan['plan_id'],'environment':'staging','leases':[proof]},expected=6)
    assert stale['error']['http_status']==409
    await cli.data("request","POST",base+"/leases/release",body={
        **proof,'operation_id':str(uuid4()),'scope':'staging'})
    # A new legacy resource is still authorable, but promotion cannot bypass
    # the managed Project gate even before any ASaC selection exists for it.
    legacy=await cli.data('project','agent','create',body={**agent_body,'name':'Managed legacy probe'})
    draft=await cli.data('project','agent','release','create',legacy['id'],body={
        'project_id':cli.project_id,'agent_id':legacy['id'],'version':'auto'})
    rejected=await cli.run('project','agent','release','promote',legacy['id'],draft['id'],
        body={'target_status':'staging'},expected=6)
    assert rejected['error']['http_status']==409
    assert rejected['error']['domain_code']=='ASAC_PROJECT_MANAGED_LIFECYCLE_REQUIRED'
    legacy_network=await cli.data('project','network','create',body={'name':'Managed network probe'})
    legacy_network=await cli.data('project','network','draft','update',legacy_network['id'],body={
        'project_id':cli.project_id,'name':'Managed network probe',
        'expected_revision':legacy_network['draft_revision'],'definition':definition})
    network_preview=await cli.data('project','network','promotion','preview',legacy_network['id'],body={
        'project_id':cli.project_id,'environment':'staging'})
    network_rejected=await cli.run('project','network','promotion','create',legacy_network['id'],body={
        'project_id':cli.project_id,'environment':'staging','expected_revision':legacy_network['draft_revision'],
        'approved_action_ids':[item['id'] for item in network_preview.get('actions',[])]},expected=6)
    assert network_rejected['error']['http_status']==409
    assert network_rejected['error']['domain_code']=='ASAC_PROJECT_MANAGED_LIFECYCLE_REQUIRED'
    restricted=await cli.data('request','PUT',policy_path,body={
        **body,'operation_id':str(uuid4()),'expected_generation':1,
        'production_actors':['control:'+str(uuid4())],'reason':'Restrict production actor'})
    observed=(await cli.run('agent',agent_id,'current','--env','production'))['data']
    await cli.run('request','POST',base+'/deployment-plans',body={
        'operation_id':str(uuid4()),'release_id':publication['publication']['release_id'],
        'expected_generation':observed['environment_generation'],'environment':'production',
        'reason':'Unauthorized production actor'},expected=4)
    allowed=await cli.data('request','PUT',policy_path,body={
        **body,'operation_id':str(uuid4()),'expected_generation':2,
        'production_actors':[changed['actor']],'reason':'Allow the qualified deployer'})
    assert allowed['policy']['generation']==3
    allowed_plan=await cli.data('request','POST',base+'/deployment-plans',body={
        'operation_id':str(uuid4()),'release_id':publication['publication']['release_id'],
        'expected_generation':observed['environment_generation'],'environment':'production',
        'reason':'Authorized production actor'})
    assert allowed_plan['policy']==allowed['policy']
    engine=create_engine(Settings());sessions=create_session_factory(engine)
    try:
        # The public database guard independently enforces the captured policy.
        # These calls exercise the same function as the deferred owner triggers.
        import json
        policy_guard = text("SELECT core.assert_asac_deployment_policy(:project, :environment, :actor, CAST(:evidence AS jsonb))")
        guard_parameters = {'project': UUID(cli.project_id), 'environment': 'production',
                            'actor': changed['actor'],
                            'evidence': json.dumps({'policy': allowed['policy']})}
        async with sessions.begin() as session:
            await session.execute(policy_guard, guard_parameters)
        for captured in ({**allowed['policy'], 'generation': 2},
                         {**allowed['policy'], 'managed': False}, {}):
            with pytest.raises(DBAPIError, match='ASAC_PROJECT_POLICY_STALE'):
                async with sessions.begin() as session:
                    await session.execute(policy_guard, {**guard_parameters,
                        'evidence': json.dumps({'policy': captured})})
        with pytest.raises(DBAPIError, match='ASAC_PROJECT_PRODUCTION_ACTOR_REQUIRED'):
            async with sessions.begin() as session:
                await session.execute(policy_guard, {**guard_parameters,
                    'actor': 'control:' + str(uuid4())})
        async with sessions.begin() as session:
            await session.execute(policy_guard, {**guard_parameters,
                'environment': 'staging', 'actor': 'control:' + str(uuid4())})
        with pytest.raises(DBAPIError,match='ASAC_PROJECT_QUALIFIED_PUBLICATION_REQUIRED'):
            async with sessions.begin() as session:
                await session.execute(text("INSERT INTO agent.agent_releases SELECT (jsonb_populate_record(NULL::agent.agent_releases,to_jsonb(source)||jsonb_build_object('id',gen_random_uuid(),'version','9.9.9','status','released','snapshot_kind','release'))).* FROM agent.agent_releases source WHERE id=:id"),{'id':UUID(draft['id'])})
        with pytest.raises(DBAPIError,match='ASAC_PROJECT_POLICY_STALE'):
            async with sessions.begin() as session:
                await session.execute(text('UPDATE core.asac_project_lifecycle_policies SET generation=generation-1 WHERE project_id=:id'),{'id':UUID(cli.project_id)})
        with pytest.raises(DBAPIError,match='ASAC_PROJECT_POLICY_IMMUTABLE'):
            async with sessions.begin() as session:
                await session.execute(text("UPDATE core.outbox_events SET payload='{}'::jsonb WHERE id=:id"),{'id':UUID(changed['outbox_id'])})
        async with sessions.begin() as session:
            await session.execute(text("UPDATE core.outbox_events SET status='published',published_at=now(),locked_at=now(),locked_by='policy-probe',attempts=attempts+1 WHERE id=:id"),{'id':UUID(changed['outbox_id'])})
    finally:
        await engine.dispose()
    await exercise_managed_qualified_lifecycle(cli, 'Agent', agent_id, publication)
    await exercise_managed_qualified_lifecycle(cli, 'Network', network_id, network_publication)


async def exercise_managed_qualified_lifecycle(cli, kind, resource_id, previous):
    """Author, qualify and select a distinct executable after enabling policy."""
    import yaml
    registry = previous['registry']
    config = yaml.safe_load((registry / '.woobe-config').read_text())
    await cli.run(kind.lower(), '@captured', 'bindings', 'recover', cwd=registry)
    for alias, binding in previous['binding_spec']['credentials'].items():
        provider = next(item for item in config['resources'] if item['kind'] == 'Provider' and item['key'] == alias)
        await cli.run('resources', 'bind', 'provider', '@' + provider['alias'], binding['credential_id'], cwd=registry)
    resource = next(item for item in config['resources']
                    if item['kind'] == kind and item['alias'] == 'captured')
    descriptor = registry / config['root'] / resource['path']
    if descriptor.suffix.lower() not in {'.yaml', '.yml', '.json'}:
        descriptor = descriptor / (kind.lower() + '.yaml')
    document = yaml.safe_load(descriptor.read_text())
    if kind == 'Agent':
        behavior = document['spec'].get('behavior')
        if behavior is not None:
            behavior['objective'] = (behavior.get('objective') or '') + ' Use the managed qualified lifecycle.'
        else:
            assert isinstance(document['spec'].get('legacy_system_prompt'), str)
            document['spec']['legacy_system_prompt'] += ' Use the managed qualified lifecycle.'
    else:
        # The root runtime settings are executable configuration, independent
        # of changes to standalone Agents or metadata.
        settings = document['spec'].setdefault('settings', {})
        settings['max_invocations'] = 63
    descriptor.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True))
    saved = (await cli.run(kind.lower(), '@captured', 'draft', 'push', cwd=registry))['data']
    assert saved['generation'] >= 3
    revision = (await cli.run(kind.lower(), '@captured', 'revision', 'create',
                             '--message', 'Managed qualified change', cwd=registry))['data']
    await cli.run(kind.lower(), '@captured', 'draft', 'checkpoint', revision['revision_id'], cwd=registry)
    accepted = (await cli.run(kind.lower(), '@captured', 'stage', '--revision',
                             revision['revision_id'], cwd=registry))['data']
    base = f"/projects/{cli.project_id}/{kind.lower()}s/{resource_id}/asac"
    for _ in range(120):
        candidate = await cli.data('request', 'GET', base + '/candidates/' + accepted['candidate_id'])
        if candidate['state'] in {'ready', 'failed', 'cancelled', 'uncertain'}:
            break
        await asyncio.sleep(0.5)
    assert candidate['state'] == 'ready'
    suite = {'schema_version':'1.0', 'suite_id':'managed-lifecycle', 'suite_version':'1',
             'dataset_version':'1', 'cases':[{'id':'greeting','message':'Hello managed lifecycle'}]}
    evaluation = (await cli.run(kind.lower(), '@captured', 'test', '--candidate',
                               candidate['candidate_id'], body=suite, cwd=registry))['data']
    assert evaluation['state'] == 'passed'
    published = (await cli.run(kind.lower(), '@captured', 'publish', '--candidate',
                              candidate['candidate_id'], '--evaluation', evaluation['evaluation_id'],
                              '--notes', 'Publish managed qualified change', cwd=registry))['data']
    assert published['state'] == 'published' and not published['production_changed']
    assert published['release_id'] != previous['publication']['release_id']
    current = (await cli.run(kind.lower(), resource_id, 'current', '--env', 'production'))['data']
    plan = await cli.data('request', 'POST', base + '/deployment-plans', body={
        'operation_id':str(uuid4()), 'release_id':published['release_id'], 'environment':'production',
        'expected_generation':current['environment_generation'], 'reason':'Select managed qualified change'})
    lease = await cli.data('request', 'POST', base + '/leases/acquire', body={
        'operation_id':str(uuid4()),'workflow_id':str(uuid4()),'scope':'production','ttl_seconds':120})
    proof = {key:lease[key] for key in ('lease_id','workflow_id','fencing_token')}
    deployed = await cli.data('request', 'POST', base + '/deployments', body={
        'operation_id':str(uuid4()),'plan_id':plan['plan_id'],'environment':'production','leases':[proof]})
    assert deployed['selection_changed'] and deployed['release_id'] == published['release_id']
    await cli.data('request', 'POST', base + '/leases/release', body={
        **proof,'operation_id':str(uuid4()),'scope':'production'})
    # Managed policy gates lifecycle; ordinary closed-package editing still
    # writes a Draft and must remain available for both kinds.
    roundtrip = cli.directory / ('managed-roundtrip-' + kind.lower())
    roundtrip.mkdir()
    await cli.run('init', '--root', '.woobe', cwd=roundtrip)
    await cli.run(kind.lower(), resource_id, 'pull', '--alias', 'roundtrip',
                  '--env', 'production', cwd=roundtrip)
    pushed = (await cli.run(kind.lower(), '@roundtrip', 'push', cwd=roundtrip))['data']
    assert pushed['pushed'] and pushed['environment'] == 'draft'
    selected = (await cli.run(kind.lower(), resource_id, 'current', '--env', 'production'))['data']
    assert selected['snapshot_id'] == published['release_id']
