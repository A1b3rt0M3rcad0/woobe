"""Package owner metadata guard; accepted work and unexpired plans must drain."""
from sqlalchemy import exists, func, select
from modules.package.domain.operations import TERMINAL_STATES
from modules.package.infra.models import PackageOperationModel, PackagePlanModel
from shared.contracts.project_configuration import ConfigurationError


async def assert_configuration_quiescent(session, *, project_id):
    active = await session.scalar(select(PackageOperationModel.id).where(
        PackageOperationModel.project_id == project_id,
        PackageOperationModel.state.not_in([state.value for state in TERMINAL_STATES])).limit(1))
    pending_plan = await session.scalar(select(PackagePlanModel.id).where(
        PackagePlanModel.project_id == project_id,
        PackagePlanModel.expires_at > func.clock_timestamp(),
        ~exists(select(PackageOperationModel.id).where(
            PackageOperationModel.project_id == project_id,
            PackageOperationModel.plan_id == PackagePlanModel.id))).limit(1))
    if active is not None or pending_plan is not None:
        raise ConfigurationError("CONFIG_MIGRATION_WORK_PENDING")
