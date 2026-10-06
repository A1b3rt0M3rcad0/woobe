from sqlalchemy.ext.asyncio import async_sessionmaker
from modules.agent.application.portable_export_compiler import (
    PortableAgentExportCompiler,
)

from modules.agent.composition.resources import DATABASE_ENGINE, FILE_STORAGE, SETTINGS
from modules.agent.infra.database.portable_export_reader import (
    PortableAgentExportReader,
)


def build_portable_agent_export_reader() -> PortableAgentExportReader:
    return PortableAgentExportReader(
        async_sessionmaker(DATABASE_ENGINE, expire_on_commit=False),
        FILE_STORAGE,
        compiler=PortableAgentExportCompiler(),
        max_document_bytes=SETTINGS.upload_max_mb * 1024 * 1024,
    )
