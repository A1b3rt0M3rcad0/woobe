import warnings

warnings.warn(
    "modules.knowledge.presentation.mappers is deprecated. Use modules.agent.presentation.mappers instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.mappers import (  # noqa: E402, F401
    agent_collection_output_to_response,
    attach_collection_output_to_response,
    chunk_output_to_response,
    collection_to_response,
    create_collection_output_to_response,
    document_to_response,
    knowledge_version_to_response,
    list_knowledge_versions_to_response,
    upload_document_output_to_response,
)
