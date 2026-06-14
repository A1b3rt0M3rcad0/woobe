import warnings

warnings.warn(
    "modules.knowledge.infra.mappers is deprecated. Use modules.agent.infra.database.mappers instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.infra.database.mappers import (  # noqa: E402, F401
    agent_collection_model_to_entity,
    agent_collection_to_model,
    chunk_to_model,
    collection_to_model,
    document_to_model,
    knowledge_version_model_to_entity,
    knowledge_version_to_model,
    model_to_chunk,
    model_to_collection,
    model_to_document,
)
