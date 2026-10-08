from modules.package.composition.services import build_package_service
from modules.package.infra.snapshot_artifact_repository import PackageSnapshotArtifactRepository
from shared.composition_resources import SESSION_FACTORY


def build_snapshot_artifacts():
    service = build_package_service()
    return PackageSnapshotArtifactRepository(SESSION_FACTORY, service.artifacts, service.exports)
