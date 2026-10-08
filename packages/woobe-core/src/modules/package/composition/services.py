from modules.agent.entrypoint import build_portable_agent_export_reader, build_development_resource_reader
from modules.network.entrypoint import build_portable_network_export_reader, build_development_network_reader
from modules.core.entrypoint import build_portable_environment_reader
from modules.package.application.export_projection import (
    ExportProjection,
    reference_requirements,
)
from modules.package.infra.export_repository import PackageExportRepository
from modules.network.entrypoint import build_network_service
from modules.package.infra.artifact_repository import PackageArtifactRepository
from modules.package.infra.artifact_storage import build_package_artifact_storage
from modules.package.infra.native_inspector import NativePackageInspectorGateway
from modules.package.infra.operation_repository import PackageOperationRepository
from modules.package.infra.plan_repository import PackagePlanRepository
from modules.package.infra.development_registry import DevelopmentRegistry
from modules.package.infra.service import PackageService
from modules.package.application.execution import ExecutePackageOperation
from modules.package.infra.native_materializer import NativePackageMaterializer
from shared.composition_resources import SESSION_FACTORY, SETTINGS


def build_package_service() -> PackageService:
    storage = build_package_artifact_storage(SETTINGS)
    artifacts = PackageArtifactRepository(SESSION_FACTORY, storage)
    inspector = NativePackageInspectorGateway(SESSION_FACTORY, build_network_service())
    registry = DevelopmentRegistry(SESSION_FACTORY, build_development_resource_reader(), build_development_network_reader())
    plans = PackagePlanRepository(SESSION_FACTORY, artifacts, inspector, registry)
    operations = PackageOperationRepository(
        SESSION_FACTORY,
        encryption_key=SETTINGS.encryption_key,
        plan_validator=plans.validate_acceptance,
        registry_reserver=plans.reserve_development,
    )
    exports = PackageExportRepository(
        SESSION_FACTORY,
        storage,
        build_portable_agent_export_reader(),
        build_portable_network_export_reader(),
        build_portable_environment_reader(),
        projection_factory=ExportProjection,
        reference_collector=reference_requirements,
        registry=registry,
    )
    return PackageService(artifacts, plans, operations, inspector, exports)


def build_package_executor() -> ExecutePackageOperation:
    service = build_package_service()
    materializer = NativePackageMaterializer(
        encryption_key=SETTINGS.encryption_key, artifacts=service.artifacts
    )
    return ExecutePackageOperation(
        service.operations,
        materializer,
        heartbeat_seconds=service.operations.lease_seconds / 3,
    )
