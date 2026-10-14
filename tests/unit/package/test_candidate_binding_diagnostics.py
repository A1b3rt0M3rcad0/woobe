from contextlib import asynccontextmanager
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from modules.package.domain.errors import PackageError
from modules.package.infra.candidate_preparation import PackageCandidatePreparation


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "binding",
    [None, N(resource_id=None, kind="Agent"), N(resource_id=uuid4(), kind="Tool")],
)
async def test_missing_candidate_constituent_locates_author_component_without_accepting(
    binding,
):
    uid, root_uid, artifact_id = (str(uuid4()) for _ in range(3))
    record = {
        "artifact_digest": "artifact",
        "definition_digest": "definition",
        "definition_digest_scope": "woobe-portable-definition@1.0",
        "resource_uid": root_uid,
        "component_digests": {uid: "child", root_uid: "root"},
    }
    evidence = {**record, "component_digests": {"child": "child", "root": "root"}}
    source = {
        "artifact_id": artifact_id,
        "record": record,
        "component_uids": {"child": uid, "root": root_uid},
    }
    graph = N(
        components={"child": {"kind": "Agent"}, "root": {"kind": "Network"}},
        manifest={"spec": {"entrypoint": {"kind": "Network", "ref": "root"}}},
        order=("child", "root"),
        paths={"child": "agents/support.yaml", "root": "network.yaml"},
    )
    bundle = N(graph=graph, close=Mock())
    session = N(scalar=AsyncMock(return_value=binding), add=Mock())

    @asynccontextmanager
    async def begin():
        yield session

    service = N(artifacts=object(), exports=object(), plans=N(create=AsyncMock()))
    preparation = PackageCandidatePreparation(N(begin=begin), service)
    preparation.retained = N(
        get=AsyncMock(return_value=evidence), capture=AsyncMock(return_value=bundle)
    )
    with pytest.raises(PackageError) as caught:
        await preparation.prepare(
            project_id=uuid4(),
            resource_id=uuid4(),
            principal=object(),
            request=N(registry_id=uuid4()),
            source=source,
            kind="Network",
            api_origin="https://example.test",
        )
    assert caught.value.code == "ASAC_CANDIDATE_BINDING_UNAVAILABLE"
    assert caught.value.file == "agents/support.yaml"
    assert caught.value.path == "/metadata/key"
    assert "managed push" in str(caught.value)
    bundle.close.assert_called_once()
    session.add.assert_not_called()
    service.plans.create.assert_not_awaited()
