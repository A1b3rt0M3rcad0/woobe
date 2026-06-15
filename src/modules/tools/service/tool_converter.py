"""Backward-compatibility shim: re-exports from canonical path."""
from modules.tools.application.tool_converter import (  # noqa: F401
    safe_tool_name,
    tools_to_openai_definitions,
)
