from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from modules.agent.infra.database.asac_models import ASaCPublicationModel, ASaCEnvironmentSelectionModel, ASaCDeploymentModel
from shared.infra.asac_runtime_provenance import admitted_publication

@pytest.mark.asyncio
async def test_same_native_release_uses_exact_selected_deployment_publication():
    project,resource,snapshot,pub=[uuid4() for _ in range(4)]
    selection=SimpleNamespace(generation=4,selection_authority="asac")
    deployment=SimpleNamespace(id=uuid4(),publication_id=pub)
    publication=SimpleNamespace(id=pub,project_id=project,resource_id=resource,release_id=snapshot,
        resource_uid=uuid4(),revision_id="rv_"+str(uuid4()),evidence={"record_digest":"record", "definition_digest":"definition","runtime_digest":"runtime"})
    session=SimpleNamespace(scalar=AsyncMock(side_effect=[selection,deployment]),get=AsyncMock(return_value=publication))
    identity=await admitted_publication(session,publications=ASaCPublicationModel,selections=ASaCEnvironmentSelectionModel,
        deployments=ASaCDeploymentModel,project_id=project,resource_id=resource,snapshot_id=snapshot,environment="production")
    assert identity["publication_id"]==str(pub) and identity["deployment_id"]==str(deployment.id)
    assert identity["selection_generation_at_admission"]==4
    session.get.assert_awaited_once_with(ASaCPublicationModel,pub)

@pytest.mark.asyncio
@pytest.mark.parametrize("count,status",[(0,"unknown_origin"),(2,"publication_ambiguous")])
async def test_unselected_ambiguous_native_origin_is_never_invented(count,status):
    session=SimpleNamespace(scalar=AsyncMock(return_value=None),scalars=AsyncMock(return_value=SimpleNamespace(all=lambda:[object()]*count)))
    identity=await admitted_publication(session,publications=ASaCPublicationModel,selections=ASaCEnvironmentSelectionModel,
        deployments=ASaCDeploymentModel,project_id=uuid4(),resource_id=uuid4(),snapshot_id=uuid4(),environment="production")
    assert identity=={"provenance_status":status}
