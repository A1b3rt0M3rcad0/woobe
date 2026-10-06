from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.datastructures import UploadFile

from modules.package.entrypoint import (
    PackageError,
    PlanPackageRequest,
    LookupPackageOperationRequest,
    ResumePackageOperationRequest,
    build_package_service,
)
from shared.infra.errors import AuthenticationError
from woobe_api.http.shared.openapi_contracts import request_body_contract

router = APIRouter(prefix="/projects/{project_id}/packages", tags=["packages"])


def principal(request):
    actor = getattr(request.state, "principal", None)
    if actor is None:
        raise AuthenticationError("Administrative authentication is required")
    return actor


def response(data, status=200):
    complete = data.get("terminal", True)
    return JSONResponse(
        jsonable_encoder(
            {
                "success": True,
                "message": "ok",
                "data": data,
                "meta": {"complete": complete},
            }
        ),
        status_code=status,
    )


def failure(error):
    status = 422
    if error.code.endswith("NOT_FOUND"):
        status = 404
    elif error.code in {
        "PACKAGE_REVISION_CONFLICT",
        "PACKAGE_PLAN_MISMATCH",
        "PACKAGE_PRECONDITION_CHANGED",
        "PACKAGE_BINDINGS_CHANGED",
        "PACKAGE_CAPABILITIES_CHANGED",
        "PACKAGE_OPERATION_STATE",
    }:
        status = 409
    elif error.code == "PACKAGE_LIMIT_EXCEEDED":
        status = 413
    elif error.code in {"PACKAGE_SCHEMA_UNSUPPORTED", "PACKAGE_UNSUPPORTED"}:
        status = 501
    return JSONResponse(
        {
            "success": False,
            "message": "Package request could not be completed",
            "data": {"package_schema_version": "1.0", "diagnostics": [error.as_dict()]},
            "meta": {"complete": False},
        },
        status_code=status,
    )


async def validated_body(request, model):
    try:
        return model.model_validate(await request.json())
    except (PydanticValidationError, ValueError) as exc:
        # Pydantic's input snapshots must never echo protected Apply values.
        raise PackageError(
            "PACKAGE_REQUEST_INVALID", "Request does not match its advertised contract"
        ) from exc


@router.get("/capabilities")
async def capabilities(project_id: UUID, request: Request):
    try:
        return response(
            await build_package_service().capabilities(
                project_id=project_id, principal=principal(request)
            )
        )
    except PackageError as exc:
        return failure(exc)


@router.post(
    "/uploads",
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file"],
                        "additionalProperties": False,
                        "properties": {"file": {"type": "string", "format": "binary"}},
                    }
                }
            },
        }
    },
)
async def upload(project_id: UUID, request: Request, locked: bool = False):
    try:
        service, actor = build_package_service(), principal(request)
        await service.artifacts.authorize_read(project_id, actor)
        async with request.form(max_files=1, max_fields=0) as form:
            file = form.get("file")
            if not isinstance(file, UploadFile) or len(form.multi_items()) != 1:
                raise PackageError(
                    "PACKAGE_REQUEST_INVALID", "Upload requires one archive file"
                )
            return response(
                await service.artifacts.upload(
                    project_id=project_id,
                    principal=actor,
                    stream=file.file,
                    locked=locked,
                ),
                201,
            )
    except PackageError as exc:
        return failure(exc)


@router.get("/uploads/{upload_id}")
async def get_upload(project_id: UUID, upload_id: UUID, request: Request):
    try:
        return response(
            await build_package_service().artifacts.get(
                project_id=project_id, principal=principal(request), upload_id=upload_id
            )
        )
    except PackageError as exc:
        return failure(exc)


@router.post(
    "/plan",
    openapi_extra=request_body_contract(
        PlanPackageRequest,
        "/projects/{project_id}/packages/plan",
        "post",
        advertise_path=False,
    ),
)
async def plan(project_id: UUID, request: Request):
    try:
        body = await validated_body(request, PlanPackageRequest)
        return response(
            await build_package_service().plan(
                project_id=project_id,
                principal=principal(request),
                request=body,
                api_origin=str(request.base_url).rstrip("/"),
            )
        )
    except PackageError as exc:
        return failure(exc)


@router.get("/operations/{operation_id}")
async def get_operation(project_id: UUID, operation_id: UUID, request: Request):
    try:
        return response(
            await build_package_service().status(
                project_id=project_id,
                principal=principal(request),
                operation_id=operation_id,
            )
        )
    except PackageError as exc:
        return failure(exc)


@router.post(
    "/operations/lookup",
    openapi_extra=request_body_contract(
        LookupPackageOperationRequest,
        "/projects/{project_id}/packages/operations/lookup",
        "post",
        advertise_path=False,
    ),
)
async def lookup_operation(project_id: UUID, request: Request):
    try:
        body = await validated_body(request, LookupPackageOperationRequest)
        return response(
            await build_package_service().lookup(
                project_id=project_id,
                principal=principal(request),
                key=body.idempotency_key,
            )
        )
    except PackageError as exc:
        return failure(exc)


@router.post("/operations/{operation_id}/cancel")
async def cancel_operation(project_id: UUID, operation_id: UUID, request: Request):
    try:
        return response(
            await build_package_service().cancel(
                project_id=project_id,
                principal=principal(request),
                operation_id=operation_id,
            ),
            202,
        )
    except PackageError as exc:
        return failure(exc)


@router.post(
    "/operations/{operation_id}/resume",
    openapi_extra=request_body_contract(
        ResumePackageOperationRequest,
        "/projects/{project_id}/packages/operations/{operation_id}/resume",
        "post",
        advertise_path=False,
    ),
)
async def resume_operation(project_id: UUID, operation_id: UUID, request: Request):
    try:
        body = await validated_body(request, ResumePackageOperationRequest)
        return response(
            await build_package_service().resume(
                project_id=project_id,
                principal=principal(request),
                operation_id=operation_id,
                expected_revision=body.expected_revision,
            ),
            202,
        )
    except PackageError as exc:
        return failure(exc)
