import asyncio
from copy import deepcopy
from uuid import uuid4

import pytest

from modules.package.application.planning import (
    PlanPackageUseCase,
    validate_binding_coverage,
)
from modules.package.domain.bundle import resolve_graph
from modules.package.domain.errors import PackageError


def graph():
    manifest = {
        "spec": {
            "entrypoint": {"kind": "Network", "ref": "team"},
            "requires": {
                "credentials": [{"ref": "primary", "provider": "openai_compatible"}]
            },
        }
    }
    documents = {
        "model.yaml": {
            "kind": "Model",
            "metadata": {"key": "model"},
            "spec": {"provider": "openai_compatible", "credential": {"ref": "primary"}},
        },
        "agent.yaml": {
            "kind": "Agent",
            "metadata": {"key": "assistant"},
            "spec": {
                "model": {"primary": {"ref": "model"}},
                "legacy_system_prompt": "Help",
            },
        },
        "team.yaml": {
            "kind": "Network",
            "metadata": {"key": "team"},
            "spec": {
                "root": "root",
                "nodes": [{"key": "root", "agent_ref": "assistant"}],
                "edges": [],
            },
        },
    }
    return resolve_graph(manifest, documents)


def bindings():
    return {
        "format": "woobe-package",
        "schema_version": "1.0",
        "kind": "ImportBindings",
        "metadata": {"name": "B"},
        "spec": {"credentials": {"primary": {"credential_id": str(uuid4())}}},
    }


class Inspector:
    def __init__(self):
        self.validated = []
        self.permissions = []

    async def capabilities(self):
        return {"native": "1"}

    async def inspect_bindings(self, **kwargs):
        return {"credentials": kwargs["bindings"]["credentials"]}

    async def inspect_component(self, **kwargs):
        self.validated.append(kwargs["document"]["metadata"]["key"])
        return {"owner_validated": True}

    async def authorize(self, **kwargs):
        self.permissions = kwargs["permissions"]


def test_network_production_plan_does_not_activate_standalone_agents():
    inspector = Inspector()
    approved = asyncio.run(
        PlanPackageUseCase(inspector).execute(
            project_id=uuid4(),
            principal=object(),
            graph=graph(),
            support={},
            artifact_digest="a" * 64,
            upload_id=uuid4(),
            bindings=bindings(),
            lifecycle="production",
            release_notes="First portable release",
            reason="Reviewed",
            api_origin="https://woobe.test",
        )
    )
    effects = approved.document["effects"]
    assert inspector.validated == ["model", "assistant", "team"]
    activation = [
        effect for effect in effects if effect["action"] == "activate_production"
    ]
    assert len(activation) == 1 and activation[0]["owner"] == "network"
    assert "agent:production" not in inspector.permissions
    assert "network:production" in inspector.permissions
    assert [effect["action"] for effect in effects][:3] == [
        "resolve_model",
        "prepare_inactive_agent",
        "finalize_agent_draft",
    ]
    assert effects[-1]["state"] == "verifying"
    assert len(approved.digest) == 64


def test_bindings_cannot_introduce_unrequested_destination_aliases():
    supplied = bindings()
    supplied["spec"]["credentials"]["extra"] = deepcopy(
        supplied["spec"]["credentials"]["primary"]
    )
    with pytest.raises(PackageError, match="Bindings"):
        validate_binding_coverage(graph().manifest["spec"]["requires"], supplied)


def test_production_requires_explicit_activation_reason_before_inspection():
    inspector = Inspector()
    with pytest.raises(PackageError) as failure:
        asyncio.run(
            PlanPackageUseCase(inspector).execute(
                project_id=uuid4(),
                principal=object(),
                graph=graph(),
                support={},
                artifact_digest="a" * 64,
                upload_id=uuid4(),
                bindings=bindings(),
                lifecycle="production",
                release_notes="Release",
                api_origin="https://woobe.test",
            )
        )
    assert failure.value.code == "PACKAGE_PRODUCTION_REASON_REQUIRED"
    assert inspector.validated == []
