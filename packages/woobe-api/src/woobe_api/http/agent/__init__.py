"""Agent HTTP transport assembly."""

from woobe_api.http.agent.context_assembler_routes import (
    router as context_assembler_router,
)
from woobe_api.http.agent.credential_routes import router as credential_router
from woobe_api.http.agent.execution_strategy_routes import (
    router as execution_strategy_router,
)
from woobe_api.http.agent.mcp_tools_routes import router as mcp_tools_router
from woobe_api.http.agent.rag_strategy_routes import router as rag_strategy_router
from woobe_api.http.agent.release_activation_routes import (
    router as release_activation_router,
)
from woobe_api.http.agent.routes import (
    agent_router,
    knowledge_router,
    router as ai_router,
    runtime_router,
    tools_router,
)
from woobe_api.http.agent.run_routes import router as run_router
from woobe_api.http.agent.tool_lifecycle_routes import router as tool_lifecycle_router
from woobe_api.http.agent.vector_snapshot_routes import (
    router as vector_snapshot_router,
)

from woobe_api.http.agent.skill_routes import router as skill_router

HTTP_ROUTERS = (
    skill_router,
    context_assembler_router,
    rag_strategy_router,
    execution_strategy_router,
    credential_router,
    release_activation_router,
    agent_router,
    ai_router,
    knowledge_router,
    vector_snapshot_router,
    runtime_router,
    run_router,
    tools_router,
    tool_lifecycle_router,
    mcp_tools_router,
)

__all__ = ["HTTP_ROUTERS"]
