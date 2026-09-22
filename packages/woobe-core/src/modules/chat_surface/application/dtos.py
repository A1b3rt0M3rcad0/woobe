from __future__ import annotations

import copy
import re
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


DEFAULT_CHAT_SURFACE_APPEARANCE: dict[str, Any] = {
    "schema_version": 2,
    "theme": "system",
    "primary_color": "#5B47E0",
    "title": "Woobe",
    "placeholder": "Type a message…",
    "welcome_message": None,
    "surface": {
        "background_color": None,
        "border_color": None,
        "border_width": 0,
        "border_radius": 0,
        "shadow": "none",
    },
    "header": {
        "visible": True,
        "background_color": None,
        "text_color": None,
        "border_color": None,
        "border_width": 0,
        "height": 56,
        "padding": 20,
        "alignment": "left",
    },
    "conversation": {
        "background_color": None,
        "padding": 20,
        "message_gap": 10,
        "max_content_width": 100,
    },
    "messages": {
        "user": {
            "background_color": None,
            "text_color": None,
            "border_color": None,
            "border_width": 0,
            "border_radius": 14,
            "padding_y": 10,
            "padding_x": 13,
            "max_width": 84,
            "show_avatar": False,
        },
        "assistant": {
            "background_color": None,
            "text_color": None,
            "border_color": None,
            "border_width": 1,
            "border_radius": 14,
            "padding_y": 10,
            "padding_x": 13,
            "max_width": 84,
            "show_avatar": False,
        },
        "system": {
            "background_color": None,
            "text_color": None,
            "border_color": None,
            "border_width": 1,
            "border_radius": 14,
            "padding_y": 10,
            "padding_x": 13,
            "max_width": 100,
            "show_avatar": False,
        },
    },
    "composer": {
        "background_color": None,
        "border_color": None,
        "padding": 12,
    },
    "input": {
        "background_color": None,
        "text_color": None,
        "placeholder_color": None,
        "border_color": None,
        "focus_border_color": None,
        "border_radius": 10,
        "font_size": 14,
        "padding_y": 10,
        "padding_x": 12,
    },
    "send_button": {
        "variant": "text",
        "background_color": None,
        "text_color": None,
        "border_color": None,
        "border_width": 0,
        "border_radius": 10,
        "label": "Send",
        "icon": "arrow_up",
    },
    "activity": {
        "mode": "dots",
        "detail_level": "generic",
        "show_icon": True,
        "labels": {
            "preparing": "Preparing response…",
            "planning_tools": "Checking whether tools are needed…",
            "calling_tool": "Using a tool…",
            "processing_tool_result": "Processing tool result…",
            "generating_answer": "Generating response…",
            "formatting_response": "Formatting response…",
        },
    },
    "response": {
        "render_mode": "rich",
    },
}

_APPEARANCE_KEYS = frozenset(DEFAULT_CHAT_SURFACE_APPEARANCE)
_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _mapping(value: Any, *, path: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    return dict(value)


def _reject_unknown(raw: dict[str, Any], allowed: set[str], *, path: str) -> None:
    unsupported = sorted(set(raw) - allowed)
    if unsupported:
        raise ValueError(f"Unsupported {path} fields: {', '.join(unsupported)}")


def _color(value: Any, *, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _HEX_COLOR.fullmatch(value):
        raise ValueError(f"{path} must be null or a #RRGGBB color")
    return value.upper()


def _integer(value: Any, *, path: str, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{path} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{path} must be between {minimum} and {maximum}")
    return value


def _boolean(value: Any, *, path: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{path} must be a boolean")
    return value


def _choice(value: Any, *, path: str, choices: set[str]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise ValueError(f"{path} must be one of: {', '.join(sorted(choices))}")
    return value


def _text(
    value: Any,
    *,
    path: str,
    maximum: int,
    required: bool = True,
) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{path} must be a string")
    normalized = " ".join(value.split())
    if required and not normalized:
        raise ValueError(f"{path} cannot be blank")
    if len(normalized) > maximum:
        raise ValueError(f"{path} must contain at most {maximum} characters")
    return normalized or None


def _normalize_box_section(
    value: Any,
    *,
    path: str,
    defaults: dict[str, Any],
    include_max_width: bool = False,
    include_avatar: bool = False,
) -> dict[str, Any]:
    raw = _mapping(value, path=path)
    allowed = {
        "background_color",
        "text_color",
        "border_color",
        "border_width",
        "border_radius",
        "padding_y",
        "padding_x",
    }
    if include_max_width:
        allowed.add("max_width")
    if include_avatar:
        allowed.add("show_avatar")
    _reject_unknown(raw, allowed, path=path)

    normalized = dict(defaults)
    for field in ("background_color", "text_color", "border_color"):
        if field in raw:
            normalized[field] = _color(raw[field], path=f"{path}.{field}")
    if "border_width" in raw:
        normalized["border_width"] = _integer(
            raw["border_width"], path=f"{path}.border_width", minimum=0, maximum=4
        )
    if "border_radius" in raw:
        normalized["border_radius"] = _integer(
            raw["border_radius"], path=f"{path}.border_radius", minimum=0, maximum=32
        )
    if "padding_y" in raw:
        normalized["padding_y"] = _integer(
            raw["padding_y"], path=f"{path}.padding_y", minimum=4, maximum=24
        )
    if "padding_x" in raw:
        normalized["padding_x"] = _integer(
            raw["padding_x"], path=f"{path}.padding_x", minimum=6, maximum=32
        )
    if include_max_width and "max_width" in raw:
        normalized["max_width"] = _integer(
            raw["max_width"], path=f"{path}.max_width", minimum=40, maximum=100
        )
    if include_avatar and "show_avatar" in raw:
        normalized["show_avatar"] = _boolean(
            raw["show_avatar"], path=f"{path}.show_avatar"
        )
    return normalized


def normalize_appearance_config(value: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(value or {})
    unsupported = sorted(set(raw) - _APPEARANCE_KEYS)
    if unsupported:
        raise ValueError(
            f"Unsupported ChatSurface appearance fields: {', '.join(unsupported)}"
        )

    schema_version = raw.get("schema_version", 1)
    if schema_version not in {1, 2}:
        raise ValueError("appearance_config.schema_version must be 1 or 2")

    normalized = copy.deepcopy(DEFAULT_CHAT_SURFACE_APPEARANCE)

    if "theme" in raw:
        normalized["theme"] = _choice(
            raw["theme"],
            path="appearance_config.theme",
            choices={"light", "dark", "system"},
        )
    if "primary_color" in raw:
        primary = _color(raw["primary_color"], path="appearance_config.primary_color")
        if primary is None:
            raise ValueError("appearance_config.primary_color cannot be null")
        normalized["primary_color"] = primary
    if "title" in raw:
        normalized["title"] = _text(
            raw["title"], path="appearance_config.title", maximum=80
        )
    if "placeholder" in raw:
        normalized["placeholder"] = _text(
            raw["placeholder"], path="appearance_config.placeholder", maximum=120
        )
    if "welcome_message" in raw:
        welcome = raw["welcome_message"]
        if welcome is not None:
            if not isinstance(welcome, str):
                raise ValueError("appearance_config.welcome_message must be a string")
            welcome = welcome.strip()
            if len(welcome) > 500:
                raise ValueError(
                    "appearance_config.welcome_message must contain at most 500 characters"
                )
        normalized["welcome_message"] = welcome or None

    if "surface" in raw:
        section = _mapping(raw["surface"], path="appearance_config.surface")
        _reject_unknown(
            section,
            {"background_color", "border_color", "border_width", "border_radius", "shadow"},
            path="appearance_config.surface",
        )
        target = normalized["surface"]
        for field in ("background_color", "border_color"):
            if field in section:
                target[field] = _color(section[field], path=f"appearance_config.surface.{field}")
        if "border_width" in section:
            target["border_width"] = _integer(
                section["border_width"],
                path="appearance_config.surface.border_width",
                minimum=0,
                maximum=4,
            )
        if "border_radius" in section:
            target["border_radius"] = _integer(
                section["border_radius"],
                path="appearance_config.surface.border_radius",
                minimum=0,
                maximum=32,
            )
        if "shadow" in section:
            target["shadow"] = _choice(
                section["shadow"],
                path="appearance_config.surface.shadow",
                choices={"none", "sm", "md", "lg"},
            )

    if "header" in raw:
        section = _mapping(raw["header"], path="appearance_config.header")
        _reject_unknown(
            section,
            {
                "visible",
                "background_color",
                "text_color",
                "border_color",
                "border_width",
                "height",
                "padding",
                "alignment",
            },
            path="appearance_config.header",
        )
        target = normalized["header"]
        if "visible" in section:
            target["visible"] = _boolean(section["visible"], path="appearance_config.header.visible")
        for field in ("background_color", "text_color", "border_color"):
            if field in section:
                target[field] = _color(section[field], path=f"appearance_config.header.{field}")
        if "border_width" in section:
            target["border_width"] = _integer(
                section["border_width"], path="appearance_config.header.border_width", minimum=0, maximum=4
            )
        if "height" in section:
            target["height"] = _integer(
                section["height"], path="appearance_config.header.height", minimum=40, maximum=96
            )
        if "padding" in section:
            target["padding"] = _integer(
                section["padding"], path="appearance_config.header.padding", minimum=0, maximum=40
            )
        if "alignment" in section:
            target["alignment"] = _choice(
                section["alignment"],
                path="appearance_config.header.alignment",
                choices={"left", "center", "right"},
            )

    if "conversation" in raw:
        section = _mapping(raw["conversation"], path="appearance_config.conversation")
        _reject_unknown(
            section,
            {"background_color", "padding", "message_gap", "max_content_width"},
            path="appearance_config.conversation",
        )
        target = normalized["conversation"]
        if "background_color" in section:
            target["background_color"] = _color(
                section["background_color"], path="appearance_config.conversation.background_color"
            )
        if "padding" in section:
            target["padding"] = _integer(
                section["padding"], path="appearance_config.conversation.padding", minimum=0, maximum=48
            )
        if "message_gap" in section:
            target["message_gap"] = _integer(
                section["message_gap"], path="appearance_config.conversation.message_gap", minimum=0, maximum=32
            )
        if "max_content_width" in section:
            target["max_content_width"] = _integer(
                section["max_content_width"],
                path="appearance_config.conversation.max_content_width",
                minimum=40,
                maximum=100,
            )

    if "messages" in raw:
        section = _mapping(raw["messages"], path="appearance_config.messages")
        _reject_unknown(section, {"user", "assistant", "system"}, path="appearance_config.messages")
        for role in ("user", "assistant", "system"):
            if role in section:
                normalized["messages"][role] = _normalize_box_section(
                    section[role],
                    path=f"appearance_config.messages.{role}",
                    defaults=normalized["messages"][role],
                    include_max_width=True,
                    include_avatar=True,
                )

    if "composer" in raw:
        section = _mapping(raw["composer"], path="appearance_config.composer")
        _reject_unknown(
            section,
            {"background_color", "border_color", "padding"},
            path="appearance_config.composer",
        )
        target = normalized["composer"]
        for field in ("background_color", "border_color"):
            if field in section:
                target[field] = _color(section[field], path=f"appearance_config.composer.{field}")
        if "padding" in section:
            target["padding"] = _integer(
                section["padding"], path="appearance_config.composer.padding", minimum=0, maximum=32
            )

    if "input" in raw:
        section = _mapping(raw["input"], path="appearance_config.input")
        _reject_unknown(
            section,
            {
                "background_color",
                "text_color",
                "placeholder_color",
                "border_color",
                "focus_border_color",
                "border_radius",
                "font_size",
                "padding_y",
                "padding_x",
            },
            path="appearance_config.input",
        )
        target = normalized["input"]
        for field in (
            "background_color",
            "text_color",
            "placeholder_color",
            "border_color",
            "focus_border_color",
        ):
            if field in section:
                target[field] = _color(section[field], path=f"appearance_config.input.{field}")
        if "border_radius" in section:
            target["border_radius"] = _integer(
                section["border_radius"], path="appearance_config.input.border_radius", minimum=0, maximum=32
            )
        if "font_size" in section:
            target["font_size"] = _integer(
                section["font_size"], path="appearance_config.input.font_size", minimum=12, maximum=20
            )
        if "padding_y" in section:
            target["padding_y"] = _integer(
                section["padding_y"], path="appearance_config.input.padding_y", minimum=6, maximum=20
            )
        if "padding_x" in section:
            target["padding_x"] = _integer(
                section["padding_x"], path="appearance_config.input.padding_x", minimum=8, maximum=28
            )

    if "send_button" in raw:
        section = _mapping(raw["send_button"], path="appearance_config.send_button")
        _reject_unknown(
            section,
            {
                "variant",
                "background_color",
                "text_color",
                "border_color",
                "border_width",
                "border_radius",
                "label",
                "icon",
            },
            path="appearance_config.send_button",
        )
        target = normalized["send_button"]
        if "variant" in section:
            target["variant"] = _choice(
                section["variant"],
                path="appearance_config.send_button.variant",
                choices={"text", "icon", "icon_text"},
            )
        for field in ("background_color", "text_color", "border_color"):
            if field in section:
                target[field] = _color(section[field], path=f"appearance_config.send_button.{field}")
        if "border_width" in section:
            target["border_width"] = _integer(
                section["border_width"], path="appearance_config.send_button.border_width", minimum=0, maximum=4
            )
        if "border_radius" in section:
            target["border_radius"] = _integer(
                section["border_radius"], path="appearance_config.send_button.border_radius", minimum=0, maximum=32
            )
        if "label" in section:
            target["label"] = _text(
                section["label"], path="appearance_config.send_button.label", maximum=32
            )
        if "icon" in section:
            target["icon"] = _choice(
                section["icon"],
                path="appearance_config.send_button.icon",
                choices={"arrow_up", "arrow_right", "none"},
            )

    if "activity" in raw:
        section = _mapping(raw["activity"], path="appearance_config.activity")
        _reject_unknown(
            section,
            {"mode", "detail_level", "show_icon", "labels"},
            path="appearance_config.activity",
        )
        target = normalized["activity"]
        if "mode" in section:
            target["mode"] = _choice(
                section["mode"], path="appearance_config.activity.mode", choices={"dots", "status"}
            )
        if "detail_level" in section:
            target["detail_level"] = _choice(
                section["detail_level"],
                path="appearance_config.activity.detail_level",
                choices={"generic", "named"},
            )
        if "show_icon" in section:
            target["show_icon"] = _boolean(
                section["show_icon"], path="appearance_config.activity.show_icon"
            )
        if "labels" in section:
            labels = _mapping(section["labels"], path="appearance_config.activity.labels")
            allowed_labels = set(target["labels"])
            _reject_unknown(labels, allowed_labels, path="appearance_config.activity.labels")
            for key, label in labels.items():
                target["labels"][key] = _text(
                    label,
                    path=f"appearance_config.activity.labels.{key}",
                    maximum=80,
                )

    if "response" in raw:
        section = _mapping(raw["response"], path="appearance_config.response")
        _reject_unknown(section, {"render_mode"}, path="appearance_config.response")
        if "render_mode" in section:
            normalized["response"]["render_mode"] = _choice(
                section["render_mode"],
                path="appearance_config.response.render_mode",
                choices={"plain", "rich"},
            )

    normalized["schema_version"] = 2
    return normalized


class CreateChatSurfaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    target_type: str
    target_id: UUID
    allowed_origins: list[str] = Field(default_factory=list, max_length=32)
    appearance_config: dict[str, Any] = Field(
        default_factory=lambda: copy.deepcopy(DEFAULT_CHAT_SURFACE_APPEARANCE)
    )
    requests_per_minute: int = Field(default=30, ge=1, le=10_000)
    max_concurrent_runs: int = Field(default=10, ge=1, le=100)
    session_token_ttl_seconds: int = Field(default=900, ge=60, le=3600)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("ChatSurface name cannot be blank")
        return normalized

    @field_validator("target_type")
    @classmethod
    def validate_target_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"agent", "network"}:
            raise ValueError("target_type must be agent or network")
        return normalized

    @field_validator("appearance_config")
    @classmethod
    def validate_appearance_config(cls, value: dict[str, Any]) -> dict[str, Any]:
        return normalize_appearance_config(value)


class UpdateChatSurfaceRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    allowed_origins: list[str] | None = Field(default=None, max_length=32)
    appearance_config: dict[str, Any] | None = None
    requests_per_minute: int | None = Field(default=None, ge=1, le=10_000)
    max_concurrent_runs: int | None = Field(default=None, ge=1, le=100)
    session_token_ttl_seconds: int | None = Field(
        default=None,
        ge=60,
        le=3600,
    )

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("ChatSurface name cannot be blank")
        return normalized

    @field_validator("appearance_config")
    @classmethod
    def validate_optional_appearance(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        return normalize_appearance_config(value) if value is not None else None


class CreateSurfaceAccessKeyRequest(BaseModel):
    name: str = Field(default="Default ChatSurface key", min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)


class CreateSurfaceSessionRequest(BaseModel):
    external_reference: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] | None = None


class IssueSessionTokenRequest(BaseModel):
    origin: str = Field(min_length=1, max_length=2048)


class StreamChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=32768)
    metadata: dict[str, Any] | None = None
    external_context: dict[str, Any] | None = None
