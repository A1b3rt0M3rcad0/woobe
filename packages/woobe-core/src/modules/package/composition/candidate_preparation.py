from modules.package.composition.services import build_package_service
from modules.package.infra.candidate_preparation import PackageCandidatePreparation
from shared.composition_resources import SESSION_FACTORY


def build_candidate_preparation():
    return PackageCandidatePreparation(SESSION_FACTORY, build_package_service())
