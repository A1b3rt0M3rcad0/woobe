import pytest

from modules.chat_surface.application.dtos import normalize_appearance_config


def test_appearance_config_upgrades_legacy_values_to_schema_v2() -> None:
    appearance = normalize_appearance_config(
        {
            "theme": "dark",
            "primary_color": "#1a2b3c",
            "title": "  Support   Assistant  ",
            "placeholder": " Ask a question ",
            "welcome_message": "  How can I help?  ",
        }
    )

    assert appearance["schema_version"] == 2
    assert appearance["theme"] == "dark"
    assert appearance["primary_color"] == "#1A2B3C"
    assert appearance["title"] == "Support Assistant"
    assert appearance["placeholder"] == "Ask a question"
    assert appearance["welcome_message"] == "How can I help?"
    assert appearance["activity"]["mode"] == "dots"
    assert appearance["response"]["render_mode"] == "rich"
    assert appearance["messages"]["assistant"]["border_width"] == 1


def test_appearance_config_normalizes_granular_component_overrides() -> None:
    appearance = normalize_appearance_config(
        {
            "schema_version": 2,
            "header": {
                "visible": False,
                "background_color": "#101820",
                "height": 64,
                "alignment": "center",
            },
            "messages": {
                "assistant": {
                    "background_color": "#ffffff",
                    "text_color": "#111111",
                    "border_radius": 6,
                    "max_width": 92,
                }
            },
            "input": {
                "border_radius": 18,
                "focus_border_color": "#5b47e0",
            },
            "send_button": {
                "variant": "icon_text",
                "label": "Send now",
                "icon": "arrow_right",
            },
            "activity": {
                "mode": "status",
                "detail_level": "named",
                "labels": {"calling_tool": "Consulting {tool}…"},
            },
            "response": {"render_mode": "plain"},
        }
    )

    assert appearance["header"] == {
        "visible": False,
        "background_color": "#101820",
        "text_color": None,
        "border_color": None,
        "border_width": 0,
        "height": 64,
        "padding": 20,
        "alignment": "center",
    }
    assert appearance["messages"]["assistant"]["background_color"] == "#FFFFFF"
    assert appearance["messages"]["assistant"]["text_color"] == "#111111"
    assert appearance["messages"]["assistant"]["border_radius"] == 6
    assert appearance["messages"]["assistant"]["max_width"] == 92
    assert appearance["input"]["border_radius"] == 18
    assert appearance["input"]["focus_border_color"] == "#5B47E0"
    assert appearance["send_button"]["variant"] == "icon_text"
    assert appearance["send_button"]["label"] == "Send now"
    assert appearance["activity"]["mode"] == "status"
    assert appearance["activity"]["detail_level"] == "named"
    assert appearance["activity"]["labels"]["calling_tool"] == "Consulting {tool}…"
    assert appearance["response"]["render_mode"] == "plain"


def test_appearance_config_rejects_unknown_or_unsafe_values() -> None:
    with pytest.raises(ValueError):
        normalize_appearance_config({"custom_css": "body { display: none }"})
    with pytest.raises(ValueError):
        normalize_appearance_config({"primary_color": "red"})
    with pytest.raises(ValueError):
        normalize_appearance_config({"theme": "neon"})
    with pytest.raises(ValueError):
        normalize_appearance_config({"header": {"custom_html": "<script />"}})
    with pytest.raises(ValueError):
        normalize_appearance_config({"messages": {"assistant": {"border_radius": 99}}})
    with pytest.raises(ValueError):
        normalize_appearance_config({"response": {"render_mode": "html"}})

