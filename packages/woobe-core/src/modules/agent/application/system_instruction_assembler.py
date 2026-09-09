from modules.agent.application.dtos.behavior_dtos import canonicalize_behavior_spec
from modules.agent.domain.system_instructions import assemble_canonical_system_instructions


def assemble_system_instructions(
    name: str | None, description: str | None, behavior_spec: dict
) -> str:
    """Compile at the write boundary. Never recompile an immutable snapshot."""
    behavior = canonicalize_behavior_spec(behavior_spec)
    return assemble_canonical_system_instructions(name, description, behavior)
