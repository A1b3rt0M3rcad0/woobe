from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

import yaml

from modules.agent.application.dtos.skill_dtos import ImportSkillInput
from shared.contracts.errors import ValidationError

MAX_PACKAGE_BYTES = 1_000_000
MAX_RESOURCE_BYTES = 200_000
SKILL_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def validate_resource_path(path: str) -> str:
    parsed = PurePosixPath(path)
    if (
        not path
        or len(path) > 240
        or "\\" in path
        or "\x00" in path
        or parsed.is_absolute()
        or any(part in {".", "..", ""} for part in path.split("/"))
        or parsed.parts[0] not in {"references", "assets"}
        or parsed.suffix.lower()
        not in {".md", ".txt", ".json", ".yaml", ".yml", ".csv"}
    ):
        raise ValidationError(
            "Skill resources must be text files inside references/ or assets/"
        )
    return path


def parse_skill_package(data: ImportSkillInput) -> dict[str, Any]:
    text = data.skill_md.removeprefix("\ufeff").replace("\r\n", "\n")
    match = re.match(r"\A---\n(.*?)\n---(?:\n|$)(.*)\Z", text, re.DOTALL)
    if match is None:
        raise ValidationError(
            "SKILL.md requires YAML frontmatter followed by Markdown instructions"
        )
    frontmatter, instructions = match.groups()
    if len(frontmatter.encode("utf-8")) > 16_000:
        raise ValidationError("Skill frontmatter exceeds 16 KB")
    try:
        # Aliases are unnecessary for this flat manifest and can hide cyclic data.
        if any(
            isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken))
            for token in yaml.scan(frontmatter)
        ):
            raise ValidationError(
                "Skill frontmatter cannot contain YAML aliases or anchors"
            )
        metadata = yaml.safe_load(frontmatter)
    except yaml.YAMLError as exc:
        raise ValidationError("SKILL.md contains invalid YAML frontmatter") from exc
    if not isinstance(metadata, dict):
        raise ValidationError("Skill frontmatter must be a mapping")
    name, description = metadata.get("name"), metadata.get("description")
    if not isinstance(name, str) or len(name) > 64 or not SKILL_NAME.fullmatch(name):
        raise ValidationError(
            "Skill name must use lowercase letters, numbers and single hyphens (max 64)"
        )
    if (
        not isinstance(description, str)
        or not description.strip()
        or len(description) > 1024
    ):
        raise ValidationError(
            "Skill description must explain when to use it (1–1024 characters)"
        )
    if "\x00" in text:
        raise ValidationError("SKILL.md must be a text file without null bytes")
    if not instructions.strip():
        raise ValidationError("Skill instructions cannot be empty")
    for key in ("license", "compatibility", "allowed-tools"):
        if key in metadata and (
            not isinstance(metadata[key], str) or len(metadata[key]) > 2048
        ):
            raise ValidationError(f"Skill {key} must be a short string")
    resources = {}
    total_bytes = len(text.encode("utf-8"))
    for path, content in data.resources.items():
        validate_resource_path(path)
        size = len(content.encode("utf-8"))
        if size > MAX_RESOURCE_BYTES or "\x00" in content:
            raise ValidationError(
                f"Skill resource is not supported or exceeds 200 KB: {path}"
            )
        total_bytes += size
        resources[path] = content
    if total_bytes > MAX_PACKAGE_BYTES:
        raise ValidationError("Skill package exceeds 1 MB")
    required_tools = sorted({name.strip() for name in data.required_tools})
    if any(not name.strip() or len(name) > 128 for name in required_tools):
        raise ValidationError("Required Tool names must contain 1–128 characters")
    return {
        "name": name,
        "description": description.strip(),
        "instructions": instructions.strip(),
        "skill_md": text,
        "resources": resources,
        "required_tools": required_tools,
        "license": metadata.get("license"),
        "compatibility": metadata.get("compatibility"),
        # Retained for portability only. This field never grants Tool permissions.
        "allowed_tools_hint": metadata.get("allowed-tools"),
    }
