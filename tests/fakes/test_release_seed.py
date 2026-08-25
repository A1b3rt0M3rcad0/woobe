from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_release_seed_contains_two_disjoint_tenant_graphs() -> None:
    seed = json.loads((ROOT / "e2e/fixtures/release-seed.json").read_text(encoding="utf-8"))
    tenants = seed["tenants"]

    assert seed["schema_version"] == 1
    assert len(tenants) == 2

    for key in ("user", "workspace", "project", "credential", "agent"):
        identifiers = {tenant[key]["id"] for tenant in tenants}
        assert len(identifiers) == 2, f"{key} identifiers must not cross tenants"

    trace_ids = {trace["id"] for tenant in tenants for trace in tenant["traces"]}
    assert trace_ids == {"trace-a", "trace-b"}
    assert all(tenant["usage"]["requests"] > 0 for tenant in tenants)


def test_release_seed_has_no_external_credentials_or_secret_values() -> None:
    raw = (ROOT / "e2e/fixtures/release-seed.json").read_text(encoding="utf-8")
    forbidden = ("sk-", "api_key", "access_token", "refresh_token", "password")
    assert all(value not in raw.lower() for value in forbidden)
    assert "fake-provider" in raw
