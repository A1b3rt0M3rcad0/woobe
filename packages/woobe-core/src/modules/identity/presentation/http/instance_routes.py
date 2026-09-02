from fastapi import APIRouter, Request as FastAPIRequest

from modules.identity.composition.composers.instance_composers import (
    bootstrap_instance_composer,
    instance_status_composer,
)
from shared.presentation.http.adapter import request_adapter, response_adapter


router = APIRouter(prefix="/identity/instance", tags=["instance"])


async def _handle(request: FastAPIRequest, handler):
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/status")
async def instance_status(request: FastAPIRequest):
    return await _handle(request, instance_status_composer())


@router.post("/bootstrap", status_code=201)
async def bootstrap_instance(request: FastAPIRequest):
    return await _handle(request, bootstrap_instance_composer())
