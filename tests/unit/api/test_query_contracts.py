from enum import Enum
from uuid import UUID

import pytest
from fastapi import FastAPI, APIRouter, Request
from pydantic import BaseModel, Field
from woobe_api.http.shared.openapi_contracts import query_parameter_contract

class Environment(str, Enum):
    draft="draft"
    production="production"

class Query(BaseModel):
    resource_id: UUID
    project_id: UUID
    environment: Environment = Environment.draft
    limit: int = Field(default=50,ge=1,le=100)

def test_query_contract_retains_scope_bounds_and_resolvable_defs():
    path="/test/{resource_id}"
    router=APIRouter()
    @router.get(path,openapi_extra=query_parameter_contract(Query,path))
    async def endpoint(request:Request): return {}
    app=FastAPI();app.include_router(router)
    operation=app.openapi()["paths"][path]["get"]
    params=operation["parameters"]
    assert [(p["name"],p["in"]) for p in params]==[("resource_id","path"),("project_id","query"),("environment","query"),("limit","query")]
    assert params[0]["required"] and params[1]["required"]
    assert params[3]["schema"]["maximum"]==100
    assert params[2]["schema"]["$ref"]=="#/paths/~1test~1{resource_id}/get/parameters/2/schema/$defs/Environment"
    assert params[2]["schema"]["$defs"]["Environment"]["enum"]==["draft","production"]

def test_unconsumed_and_duplicate_query_fields_rejected():
    for fields in [("missing",),("limit","limit"),("resource_id",)]:
        with pytest.raises(ValueError):query_parameter_contract(Query,"/test/{resource_id}",query_fields=fields)
