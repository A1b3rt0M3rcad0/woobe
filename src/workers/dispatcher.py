import logging

from shared.workers.inbox_dispatcher import InboxDispatcherWorker

logger = logging.getLogger(__name__)


async def handle_project_created(event) -> None:
    logger.info("Project created: %s", event.payload)
    # TODO: criar estrutura inicial do projeto (metering, observability, etc.)


async def handle_organization_created(event) -> None:
    logger.info("Organization created: %s", event.payload)
    # TODO: criar customer no billing, configurar limites iniciais


async def handle_agent_created(event) -> None:
    logger.info("Agent created: %s", event.payload)


async def handle_document_uploaded(event) -> None:
    logger.info("Document uploaded: %s", event.payload)
    # TODO: iniciar worker de ingestão/embedding


async def handle_usage_recorded(event) -> None:
    logger.info("Usage recorded: %s", event.payload)
    # TODO: atualizar agregadores diários


def build_dispatcher(async_engine) -> InboxDispatcherWorker:
    worker = InboxDispatcherWorker(async_engine)

    worker.register_handler("identity.organization_created", handle_organization_created)
    worker.register_handler("core.project_created", handle_project_created)
    worker.register_handler("ai.agent_created", handle_agent_created)
    worker.register_handler("knowledge.document.uploaded", handle_document_uploaded)
    worker.register_handler("metering.usage_recorded", handle_usage_recorded)

    return worker
