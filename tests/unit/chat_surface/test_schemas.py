import pytest

from modules.chat_surface.presentation.schemas import normalize_appearance_config


def test_appearance_config_applies_controlled_defaults() -> None:
    appearance = normalize_appearance_config(
        {
            "theme": "dark",
            "primary_color": "#1a2b3c",
            "title": "  Support   Assistant  ",
            "placeholder": " Ask a question ",
            "welcome_message": "  How can I help?  ",
        }
    )

    assert appearance == {
        "theme": "dark",
        "primary_color": "#1A2B3C",
        "title": "Support Assistant",
        "placeholder": "Ask a question",
        "welcome_message": "How can I help?",
    }


def test_appearance_config_rejects_unknown_or_unsafe_values() -> None:
    with pytest.raises(ValueError):
        normalize_appearance_config({"custom_css": "body { display: none }"})
    with pytest.raises(ValueError):
        normalize_appearance_config({"primary_color": "red"})
    with pytest.raises(ValueError):
        normalize_appearance_config({"theme": "neon"})
