from modules.agent.application.dtos.behavior_dtos import canonicalize_behavior_spec


def assemble_system_instructions(
    name: str | None, description: str | None, behavior_spec: dict
) -> str:
    """Compile at the write boundary. Never recompile an immutable snapshot."""
    behavior = canonicalize_behavior_spec(behavior_spec)
    sections: list[str] = []
    identity = []
    if name and name.strip():
        identity.append(f"Name: {name}")
    if description and description.strip():
        identity.append(f"Description: {description}")
    if identity:
        sections.append("[AGENT IDENTITY]\n\n" + "\n".join(identity))
    for key, title in (
        ("objective", "OBJECTIVE"),
        ("responsibilities", "RESPONSIBILITIES"),
        ("allowed_behaviors", "ALLOWED BEHAVIORS"),
        ("disallowed_behaviors", "DISALLOWED BEHAVIORS"),
        ("operating_instructions", "OPERATING INSTRUCTIONS"),
        ("response_guidelines", "RESPONSE GUIDELINES"),
        ("additional_instructions", "ADDITIONAL INSTRUCTIONS"),
    ):
        value = behavior[key]
        content = "\n".join(f"- {item}" for item in value) if isinstance(value, list) else value
        if content.strip():
            sections.append(f"[{title}]\n\n{content}")
    return "\n\n".join(sections)
