from modules.agent.application.portable_export_compiler import (
    PortableAgentExportCompiler,
)

from modules.agent.composition.resources import FILE_STORAGE, SETTINGS
from modules.agent.composition.factories.agent_uow_factory import build_agent_read_uow
from modules.agent.infra.database.portable_export_reader import (
    PortableAgentExportReader,
)


def build_portable_agent_export_reader() -> PortableAgentExportReader:
    return PortableAgentExportReader(
        build_agent_read_uow,
        FILE_STORAGE,
        compiler=PortableAgentExportCompiler(),
        max_document_bytes=SETTINGS.upload_max_mb * 1024 * 1024,
    )
