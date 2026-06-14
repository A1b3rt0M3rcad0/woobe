import warnings

warnings.warn(
    "modules.knowledge.domain.enums is deprecated. "
    "Use modules.agent.domain.enums instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.domain.enums import (  # noqa: F401, E402
    CollectionStatus,
    DocumentStatus,
    KnowledgeVersionStatus,
    ParserType,
)
