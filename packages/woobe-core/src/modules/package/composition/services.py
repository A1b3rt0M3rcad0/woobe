from modules.network.entrypoint import build_network_service
from modules.package.infra.artifact_repository import PackageArtifactRepository
from modules.package.infra.artifact_storage import build_package_artifact_storage
from modules.package.infra.native_inspector import NativePackageInspectorGateway
from modules.package.infra.operation_repository import PackageOperationRepository
from modules.package.infra.plan_repository import PackagePlanRepository
from modules.package.infra.service import PackageService
from shared.composition_resources import SESSION_FACTORY, SETTINGS


def build_package_service() -> PackageService:
    storage = build_package_artifact_storage(SETTINGS)
    artifacts = PackageArtifactRepository(SESSION_FACTORY, storage)
    inspector = NativePackageInspectorGateway(SESSION_FACTORY, build_network_service())
    plans = PackagePlanRepository(SESSION_FACTORY, artifacts, inspector)
    operations = PackageOperationRepository(
        SESSION_FACTORY,
        encryption_key=SETTINGS.encryption_key,
        plan_validator=plans.validate_acceptance,
    )
    return PackageService(artifacts, plans, operations, inspector)
