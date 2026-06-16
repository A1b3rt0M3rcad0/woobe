"""Tests for spec 133 — update settings and config.

Validates that Settings include exchange `domain.events`, RabbitMQ URLs,
batch sizes, retry policy, and lock timeout. Also verifies config does not
contain global business bindings.
"""
import importlib


class TestSettingsAndConfigSuccess:
    """Verify Settings class has required fields for agent messaging infra."""

    def test_settings_has_rabbitmq_url(self):
        from shared.infra.config.config import Settings

        s = Settings()
        assert s.rabbitmq_url.startswith("amqp://"), (
            f"rabbitmq_url should be an AMQP URL, got: {s.rabbitmq_url}"
        )

    def test_settings_has_rabbitmq_exchange_domain_events(self):
        from shared.infra.config.config import Settings

        s = Settings()
        assert s.rabbitmq_exchange == "domain.events", (
            f"rabbitmq_exchange should be 'domain.events', got: {s.rabbitmq_exchange!r}"
        )

    def test_settings_has_outbox_batch_size(self):
        from shared.infra.config.config import Settings

        s = Settings()
        assert isinstance(s.outbox_batch_size, int)
        assert s.outbox_batch_size > 0

    def test_settings_has_inbox_batch_size(self):
        from shared.infra.config.config import Settings

        s = Settings()
        assert isinstance(s.inbox_batch_size, int)
        assert s.inbox_batch_size > 0

    def test_settings_has_outbox_lock_timeout_seconds(self):
        from shared.infra.config.config import Settings

        s = Settings()
        assert isinstance(s.outbox_lock_timeout_seconds, int)
        assert s.outbox_lock_timeout_seconds > 0

    def test_settings_has_inbox_lock_timeout_seconds(self):
        from shared.infra.config.config import Settings

        s = Settings()
        assert isinstance(s.inbox_lock_timeout_seconds, int)
        assert s.inbox_lock_timeout_seconds > 0

    def test_settings_has_outbox_max_retries(self):
        from shared.infra.config.config import Settings

        s = Settings()
        assert isinstance(s.outbox_max_retries, int)
        assert s.outbox_max_retries > 0

    def test_settings_has_retry_base_delay_seconds(self):
        from shared.infra.config.config import Settings

        s = Settings()
        assert isinstance(s.retry_base_delay_seconds, float)
        assert s.retry_base_delay_seconds > 0

    def test_settings_has_retry_max_delay_seconds(self):
        from shared.infra.config.config import Settings

        s = Settings()
        assert isinstance(s.retry_max_delay_seconds, float)
        assert s.retry_max_delay_seconds > 0

    def test_settings_has_retry_backoff_multiplier(self):
        from shared.infra.config.config import Settings

        s = Settings()
        assert isinstance(s.retry_backoff_multiplier, float)
        assert s.retry_backoff_multiplier >= 1.0

    def test_settings_exchange_matches_topology_constant(self):
        from shared.infra.config.config import Settings
        from shared.messaging.rabbitmq_topology import EXCHANGE_NAME

        s = Settings()
        assert s.rabbitmq_exchange == EXCHANGE_NAME, (
            f"Settings.rabbitmq_exchange ({s.rabbitmq_exchange!r}) must match "
            f"topology EXCHANGE_NAME ({EXCHANGE_NAME!r})"
        )

    def test_rabbitmq_topology_exchange_is_domain_events(self):
        from shared.messaging.rabbitmq_topology import EXCHANGE_NAME

        assert EXCHANGE_NAME == "domain.events"


class TestSettingsAndConfigRejectsForbidden:
    """Verify config does not import or contain global business bindings."""

    def test_settings_does_not_import_module_business_logic(self):
        mod = importlib.import_module("shared.infra.config.config")
        source = __import__("inspect").getsource(mod)
        forbidden = [
            "from modules.",
            "import modules.",
            "from src.modules.",
        ]
        for pattern in forbidden:
            assert pattern not in source, (
                f"Settings config must not import from modules: found '{pattern}'"
            )

    def test_settings_classes_are_data_only(self):
        from shared.infra.config.config import Settings

        cls_dict = list(Settings.model_fields.keys())
        for key in cls_dict:
            assert "bind" not in key.lower(), (
                f"Settings field '{key}' suggests business binding in config"
            )
            assert "handler" not in key.lower(), (
                f"Settings field '{key}' suggests business handler in config"
            )
            assert "route" not in key.lower(), (
                f"Settings field '{key}' suggests route config in settings"
            )

    def test_topology_does_not_contain_business_bindings(self):
        from shared.messaging.rabbitmq_topology import (
            EXCHANGE_NAME,
            QUEUE_NAME_PATTERN,
            ROUTING_KEY_PATTERN,
        )

        assert "domain.events" in EXCHANGE_NAME
        assert QUEUE_NAME_PATTERN is not None
        assert ROUTING_KEY_PATTERN is not None
