import warnings

warnings.warn(
    "modules.ai.infra.llm.langchain_factory is deprecated. "
    "Use modules.agent.infra.llm.langchain_factory instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.infra.llm.langchain_factory import create_chat_model  # noqa: F401, E402
