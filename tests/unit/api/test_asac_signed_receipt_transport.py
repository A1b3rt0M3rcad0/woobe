"""Only data returned by an authorized lifecycle owner is attested."""
import json
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock
import pytest
from starlette.requests import Request
from shared.contracts.errors import AuthorizationError, ValidationError
from woobe_api.http.shared import asac_draft_routes as transport


@pytest.mark.asyncio
async def test_signed_revision_uses_authorized_owner_and_never_accepts_client_content(monkeypatch):
    project,resource=uuid4(),uuid4();principal=object()
    receipt={'complete':True,'record':{'revision_id':'rv_'+str(uuid4()),'message':'Owner record'}}
    owner=SimpleNamespace(get_revision=AsyncMock(return_value=receipt))
    signer=SimpleNamespace(attest=lambda **kwargs: {'payload':kwargs['receipt'],'complete':True})
    monkeypatch.setattr(transport,'build_snapshot_artifacts',lambda:object())
    monkeypatch.setattr(transport,'build_asac_receipt_signer',lambda:signer)
    router=transport.draft_router('/test',lambda **kwargs:owner,'Agent')
    endpoint=next(route.endpoint for route in router.routes if route.path.endswith('/signed-receipts/{category}/{receipt_id}'))
    request=Request({'type':'http','method':'GET','path':'/test','query_string':b'','headers':[]})
    request.state.principal=principal
    result=await endpoint(project,resource,request,'revision','rv_requested','production')
    assert json.loads(result.body)['data']['payload']==receipt
    owner.get_revision.assert_awaited_once_with(project_id=project,resource_id=resource,
        revision_id='rv_requested',principal=principal)
    request.state.principal=None
    with pytest.raises(AuthorizationError):
        await endpoint(project,resource,request,'revision','rv_requested','production')
    assert owner.get_revision.await_count==1


@pytest.mark.asyncio
async def test_unsigned_or_nonterminal_record_is_explicitly_rejected(monkeypatch):
    receipt={'complete':False}
    owner=SimpleNamespace(get_revision=AsyncMock(return_value=receipt))
    monkeypatch.setattr(transport,'build_snapshot_artifacts',lambda:object())
    def unavailable(): raise ValidationError('ASAC_SIGNATURES_UNAVAILABLE: not configured')
    monkeypatch.setattr(transport,'build_asac_receipt_signer',unavailable)
    router=transport.draft_router('/test',lambda **kwargs:owner,'Network')
    endpoint=next(route.endpoint for route in router.routes if route.path.endswith('/signed-receipts/{category}/{receipt_id}'))
    request=Request({'type':'http','method':'GET','path':'/test','query_string':b'','headers':[]})
    request.state.principal=object()
    result=await endpoint(uuid4(),uuid4(),request,'revision','rv_requested','production')
    assert result.status_code==409 and b'ASAC_RECEIPT_NOT_TERMINAL' in result.body
    receipt['complete']=True
    result=await endpoint(uuid4(),uuid4(),request,'revision','rv_requested','production')
    assert result.status_code==422 and b'ASAC_SIGNATURES_UNAVAILABLE' in result.body
