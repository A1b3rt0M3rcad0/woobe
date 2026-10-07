from modules.agent.application.portable_export_tools import export_frozen_tool
from modules.agent.application.tool_release_snapshots import tool_to_release_snapshot


def development_tool_projection(tool):
    return export_frozen_tool(tool_to_release_snapshot(tool))
