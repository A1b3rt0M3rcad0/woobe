from pydantic import ValidationError as PydanticValidationError
import pytest

from modules.agent.application.dtos.rag_config_dtos import RAGRuntimeConfig


def test_rag_runtime_config_defaults_to_classic_with_empty_strategy_config() -> None:
    config = RAGRuntimeConfig()

    assert config.strategy == "classic"
    assert config.strategy_config == {}


def test_rag_runtime_config_preserves_strategy_specific_configuration() -> None:
    config = RAGRuntimeConfig.model_validate(
        {
            "strategy": " Agentic ",
            "strategy_config": {
                "max_iterations": 4,
                "decision_model": "agent-model",
                "nested": {"stop_on_grounded": True},
            },
        }
    )

    assert config.strategy == "agentic"
    assert config.strategy_config == {
        "max_iterations": 4,
        "decision_model": "agent-model",
        "nested": {"stop_on_grounded": True},
    }
    assert config.model_dump()["strategy_config"]["max_iterations"] == 4


def test_rag_runtime_config_rejects_non_object_strategy_config() -> None:
    with pytest.raises(PydanticValidationError):
        RAGRuntimeConfig.model_validate(
            {
                "strategy": "classic",
                "strategy_config": ["not", "an", "object"],
            }
        )
