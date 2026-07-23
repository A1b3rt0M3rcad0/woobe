from fastapi import APIRouter

from modules.evaluation.presentation.authoring_routes import router as authoring_router
from modules.evaluation.presentation.catalog_routes import router as catalog_router
from modules.evaluation.presentation.comparison_preview_routes import (
    router as comparison_preview_router,
)
from modules.evaluation.presentation.decision_routes import router as decision_router
from modules.evaluation.presentation.evidence_routes import router as evidence_router
from modules.evaluation.presentation.experience_routes import router as experience_router
from modules.evaluation.presentation.pagination_routes import router as pagination_router
from modules.evaluation.presentation.routes import router as resource_router
from modules.evaluation.presentation.secure_version_routes import router as secure_version_router
from modules.evaluation.presentation.version_routes import router as version_router

router = APIRouter()
router.include_router(pagination_router)
# These routes intentionally precede the legacy resource router because both expose
# progress and Judgment retry paths. FastAPI resolves the first matching route, so
# revision capture must be registered first to preserve historical evidence.
router.include_router(experience_router)
router.include_router(resource_router)
router.include_router(version_router)
router.include_router(secure_version_router)
router.include_router(authoring_router)
router.include_router(decision_router)
router.include_router(catalog_router)
router.include_router(comparison_preview_router)
router.include_router(evidence_router)

__all__ = ["router"]
