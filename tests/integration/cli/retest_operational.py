"""Retest operational boundaries with independent clients and a real HTTP fault.

The clients share a disposable server, not a filesystem/config/registry. This
qualifies distinct processes/workflows, not a multi-machine network benchmark.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
import socket
from uuid import uuid4

import httpx
import uvicorn


def proof(receipt):
    return {key: receipt[key] for key in ("lease_id", "workflow_id", "fencing_token")}


@asynccontextmanager
async def lose_committed_response(origin, path):
    """Forward to the actual API, then truncate exactly one committed response."""
    accepted = []
    async with httpx.AsyncClient(trust_env=False, timeout=90) as upstream:

        async def app(scope, receive, send):
            body = bytearray()
            while True:
                event = await receive()
                body.extend(event.get("body", b""))
                assert len(body) < 1 << 20
                if not event.get("more_body"):
                    break
            headers = {
                key.decode(): value.decode()
                for key, value in scope["headers"]
                if key.lower() not in {b"host", b"content-length", b"connection"}
            }
            url = origin + scope["path"]
            if scope["query_string"]:
                url += "?" + scope["query_string"].decode()
            response = await upstream.request(
                scope["method"], url, content=bytes(body), headers=headers
            )
            lose = scope["method"] == "POST" and scope["path"] == path and not accepted
            if lose:
                assert response.status_code < 300, f"fault must occur after acceptance, status={response.status_code}"
                accepted.append(response.json()["data"])
            content = b"{" if lose else response.content
            await send(
                {
                    "type": "http.response.start",
                    "status": response.status_code,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(response.content)).encode()),
                    ],
                }
            )
            # Simulate connection loss after commit, not a refused preflight.
            await send(
                {"type": "http.response.body", "body": content, "more_body": False}
            )

        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            server = uvicorn.Server(
                uvicorn.Config(
                    app,
                    lifespan="off",
                    log_config=None,
                    log_level="critical",
                    access_log=False,
                )
            )
            task = asyncio.create_task(server.serve(sockets=[listener]))
            try:
                for _ in range(100):
                    if server.started:
                        break
                    assert not task.done(), "fault proxy failed to start"
                    await asyncio.sleep(0.01)
                assert server.started
                yield f"http://127.0.0.1:{listener.getsockname()[1]}", accepted
            finally:
                server.should_exit = True
                await asyncio.wait_for(task, 10)


async def exercise_independent_clients_and_lost_response(
    cli, kind, resource_id, publication
):
    base = f"/projects/{cli.project_id}/{kind.lower()}s/{resource_id}/asac"
    clients = []
    for name in ("client-a", "client-b"):
        directory = cli.directory / (kind.lower() + "-" + name)
        directory.mkdir()
        client = type(cli)(
            cli.binary, cli.origin, cli.workspace_id, cli.credential, directory
        )
        client.project_id = cli.project_id
        client.secret_values = cli.secret_values
        clients.append(client)
    acquisitions = [
        {
            "operation_id": str(uuid4()),
            "workflow_id": str(uuid4()),
            "scope": "production",
            "ttl_seconds": 120,
        }
        for _ in clients
    ]
    raced = await asyncio.gather(
        *[
            client.run(
                "request", "POST", base + "/leases/acquire", body=body, expected=(0, 6)
            )
            for client, body in zip(clients, acquisitions, strict=True)
        ]
    )
    assert sorted(item["success"] for item in raced) == [False, True]
    winner_index = next(index for index, item in enumerate(raced) if item["success"])
    winner, loser = clients[winner_index], clients[1 - winner_index]
    lease = raced[winner_index]["data"]["data"]
    failed = raced[1 - winner_index]["error"]
    assert failed["http_status"] == 409
    # Separate config directories cannot turn a shared credential into workflow
    # ownership. The original acquisition remains exactly replayable.
    assert (
        await winner.data(
            "request", "POST", base + "/leases/acquire", body=acquisitions[winner_index]
        )
        == lease
    )
    current = (
        await winner.run(kind.lower(), resource_id, "current", "--env", "production")
    )["data"]
    plan = await winner.data(
        "request",
        "POST",
        base + "/deployment-plans",
        body={
            "operation_id": str(uuid4()),
            "release_id": publication["release_id"],
            "environment": "production",
            "expected_generation": current["environment_generation"],
            "reason": "Qualify committed-response recovery",
        },
    )
    operation = str(uuid4())
    body = {
        "operation_id": operation,
        "plan_id": plan["plan_id"],
        "environment": "production",
        "leases": [proof(lease)],
    }
    forged = {
        **proof(lease),
        "workflow_id": acquisitions[1 - winner_index]["workflow_id"],
    }
    rejected = await loser.run(
        "request",
        "POST",
        base + "/deployments",
        body={**body, "operation_id": str(uuid4()), "leases": [forged]},
        expected=6,
    )
    assert rejected["error"]["http_status"] == 409
    async with lose_committed_response(cli.origin, base + "/deployments") as (
        proxy,
        accepted,
    ):
        lost = await winner.run(
            "request",
            "POST",
            base + "/deployments",
            "--api-url",
            proxy,
            body=body,
            expected=7,
        )
        assert lost["error"]["write_outcome"] == "unknown"
        assert len(accepted) == 1 and accepted[0]["operation_id"] == operation
        recovered = (
            await winner.run(
                kind.lower(),
                resource_id,
                "deployment",
                "reconcile",
                "--operation",
                operation,
                "--no-project-config",
                "--api-url",
                proxy,
            )
        )["data"]
        recovered_again = (
            await loser.run(
                kind.lower(),
                resource_id,
                "deployment",
                "reconcile",
                "--operation",
                operation,
                "--no-project-config",
                "--api-url",
                proxy,
            )
        )["data"]
        assert recovered == recovered_again == accepted[0]
        assert len(accepted) == 1  # Reconciliation is read-only, no second POST.
    assert (
        await winner.data("request", "POST", base + "/deployments", body=body)
        == recovered
    )
    await winner.data(
        "request",
        "POST",
        base + "/leases/release",
        body={**proof(lease), "operation_id": str(uuid4()), "scope": "production"},
    )
    replacement = await loser.data(
        "request", "POST", base + "/leases/acquire", body=acquisitions[1 - winner_index]
    )
    assert replacement["fencing_token"] == lease["fencing_token"] + 1
    stale = await winner.run(
        "request",
        "POST",
        base + "/deployments",
        body={**body, "operation_id": str(uuid4())},
        expected=6,
    )
    assert stale["error"]["http_status"] == 409
    await loser.data(
        "request",
        "POST",
        base + "/leases/release",
        body={
            **proof(replacement),
            "operation_id": str(uuid4()),
            "scope": "production",
        },
    )
    for client in clients:
        cli.evidence.extend(client.evidence)


async def exercise_non_admin_deployment_grants(cli, kind, resource_id, publication):
    base = f"/projects/{cli.project_id}/{kind.lower()}s/{resource_id}/asac"
    reads = [
        "project:read",
        "agent:read",
        "network:read",
        "provider:read",
        "model:read",
        "tool:read",
        "skill:read",
        "knowledge:read",
        "secret:read",
        "project:environment:read",
    ]
    for role, grants, allowed in (
        ("reader", reads, set()),
        ("staging-operator", reads + [kind.lower() + ":version"], {"staging"}),
        ("production-operator", reads + [kind.lower() + ":production"], {"production"}),
    ):
        issued, key = await cli.issue(
            "workspace",
            "control-key",
            "create",
            body={
                "name": kind + " " + role,
                "permissions": [],
                "on_project_create_permissions": [],
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                "project_grants": [
                    {"project_id": cli.project_id, "permissions": grants}
                ],
            },
        )
        try:
            for environment in ("staging", "production"):
                observed = (
                    await cli.run(
                        kind.lower(),
                        resource_id,
                        "current",
                        "--env",
                        environment,
                        key=key,
                    )
                )["data"]
                body = {
                    "operation_id": str(uuid4()),
                    "release_id": publication["release_id"],
                    "environment": environment,
                    "expected_generation": observed["environment_generation"],
                    "reason": "Qualify explicit non-admin deployment grants",
                }
                if environment not in allowed:
                    denied = await cli.run(
                        "request",
                        "POST",
                        base + "/deployment-plans",
                        body=body,
                        key=key,
                        expected=4,
                    )
                    assert denied["error"]["http_status"] == 403
                    continue
                plan = await cli.data(
                    "request", "POST", base + "/deployment-plans", body=body, key=key
                )
                lease = await cli.data(
                    "request",
                    "POST",
                    base + "/leases/acquire",
                    key=key,
                    body={
                        "operation_id": str(uuid4()),
                        "workflow_id": str(uuid4()),
                        "scope": environment,
                        "ttl_seconds": 120,
                    },
                )
                receipt = await cli.data(
                    "request",
                    "POST",
                    base + "/deployments",
                    key=key,
                    body={
                        "operation_id": str(uuid4()),
                        "plan_id": plan["plan_id"],
                        "environment": environment,
                        "leases": [proof(lease)],
                    },
                )
                assert (
                    receipt["state"] == "committed"
                    and receipt["actor"] == "control:" + issued["credential_id"]
                )
                assert not receipt["selection_changed"]
                await cli.data(
                    "request",
                    "POST",
                    base + "/leases/release",
                    key=key,
                    body={
                        **proof(lease),
                        "operation_id": str(uuid4()),
                        "scope": environment,
                    },
                )
        finally:
            await cli.data(
                "workspace",
                "control-key",
                "revoke",
                issued["id"],
                "--if-match",
                issued["etag"],
            )


async def exercise_managed_rollback(
    cli, kind, resource_id, previous, current_publication
):
    base = f"/projects/{cli.project_id}/{kind.lower()}s/{resource_id}/asac"
    start = (
        await cli.run(kind.lower(), resource_id, "current", "--env", "production")
    )["data"]
    assert start["snapshot_id"] == current_publication["release_id"]
    lease = await cli.data(
        "request",
        "POST",
        base + "/leases/acquire",
        body={
            "operation_id": str(uuid4()),
            "workflow_id": str(uuid4()),
            "scope": "production",
            "ttl_seconds": 120,
        },
    )
    try:
        for offset, (publication, action) in enumerate(
            ((previous, "rollback"), (current_publication, "activate")), 1
        ):
            operation = str(uuid4())
            plan = (
                await cli.run(
                    kind.lower(),
                    resource_id,
                    "deployment",
                    "plan",
                    "--no-project-config",
                    "--operation",
                    operation,
                    "--action",
                    action,
                    "--release",
                    publication["release_id"],
                    "--expected-generation",
                    str(start["environment_generation"] + offset - 1),
                    "--notes",
                    "Qualify managed Production rollback and restore",
                )
            )["data"]
            receipt = await cli.data(
                "request",
                "POST",
                base + "/deployments",
                body={
                    "operation_id": str(uuid4()),
                    "plan_id": plan["plan_id"],
                    "environment": "production",
                    "leases": [proof(lease)],
                },
            )
            assert receipt["action"] == action and receipt["selection_changed"]
            assert (
                receipt["generation_after"] == start["environment_generation"] + offset
            )
            observed = (
                await cli.run(
                    kind.lower(), resource_id, "current", "--env", "production"
                )
            )["data"]
            assert observed["snapshot_id"] == publication["release_id"]
            _, key = await cli.issue(
                "project",
                "runtime-key",
                "create",
                body={
                    "project_id": cli.project_id,
                    "name": "Rollback runtime qualification",
                    "target_type": kind.lower(),
                    "target_id": resource_id,
                    "environment": "production",
                    "interfaces": ["http"],
                    "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                },
            )
            ran = await cli.run(
                "runtime",
                "target",
                "run",
                "rollback-qualification",
                "--target-kind",
                kind.lower(),
                body={"input": "Hello after rollback"},
                runtime_key=key,
            )
            assert (
                ran["data"]["data"]["runtime_identity"]["snapshot_id"]
                == publication["release_id"]
            )
    finally:
        await cli.data(
            "request",
            "POST",
            base + "/leases/release",
            body={**proof(lease), "operation_id": str(uuid4()), "scope": "production"},
        )
