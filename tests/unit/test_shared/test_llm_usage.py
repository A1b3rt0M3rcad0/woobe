from __future__ import annotations


from shared.infra.llm_usage import normalize_llm_usage


class _FakeMessage:
    def __init__(
        self,
        usage_metadata: dict | None = None,
        response_metadata: dict | None = None,
    ) -> None:
        self.usage_metadata = usage_metadata
        self.response_metadata = response_metadata


class _NoUsageAttrMessage:
    pass


class TestNormalizeLlmUsage:
    def test_basic_non_zero_tokens(self) -> None:
        msg = _FakeMessage(
            usage_metadata={"input_tokens": 50, "output_tokens": 100, "total_tokens": 150},
        )
        result = normalize_llm_usage(msg)
        assert result == {"input_tokens": 50, "output_tokens": 100, "total_tokens": 150, "cost_usd": None}

    def test_zero_tokens(self) -> None:
        msg = _FakeMessage(
            usage_metadata={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        )
        result = normalize_llm_usage(msg)
        assert result == {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": None}

    def test_zero_input_non_zero_output(self) -> None:
        msg = _FakeMessage(
            usage_metadata={"input_tokens": 0, "output_tokens": 100, "total_tokens": 100},
        )
        result = normalize_llm_usage(msg)
        assert result == {"input_tokens": 0, "output_tokens": 100, "total_tokens": 100, "cost_usd": None}

    def test_no_usage_metadata_attribute(self) -> None:
        msg = _NoUsageAttrMessage()
        result = normalize_llm_usage(msg)
        assert result == {"input_tokens": None, "output_tokens": None, "total_tokens": None, "cost_usd": None}

    def test_usage_metadata_is_none(self) -> None:
        msg = _FakeMessage(usage_metadata=None)
        result = normalize_llm_usage(msg)
        assert result == {"input_tokens": None, "output_tokens": None, "total_tokens": None, "cost_usd": None}

    def test_empty_usage_metadata(self) -> None:
        msg = _FakeMessage(usage_metadata={})
        result = normalize_llm_usage(msg)
        assert result == {"input_tokens": None, "output_tokens": None, "total_tokens": None, "cost_usd": None}

    def test_fallback_to_prompt_completion_tokens(self) -> None:
        msg = _FakeMessage(
            usage_metadata={"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150},
        )
        result = normalize_llm_usage(msg)
        assert result == {"input_tokens": 50, "output_tokens": 100, "total_tokens": 150, "cost_usd": None}

    def test_fallback_to_response_metadata_token_usage(self) -> None:
        msg = _FakeMessage(
            usage_metadata=None,
            response_metadata={
                "token_usage": {"input_tokens": 30, "output_tokens": 60, "total_tokens": 90},
            },
        )
        result = normalize_llm_usage(msg)
        assert result == {"input_tokens": 30, "output_tokens": 60, "total_tokens": 90, "cost_usd": None}

    def test_fallback_to_response_metadata_usage(self) -> None:
        msg = _FakeMessage(
            usage_metadata=None,
            response_metadata={
                "usage": {"input_tokens": 20, "output_tokens": 40, "total_tokens": 60},
            },
        )
        result = normalize_llm_usage(msg)
        assert result == {"input_tokens": 20, "output_tokens": 40, "total_tokens": 60, "cost_usd": None}

    def test_token_usage_precedence_over_usage(self) -> None:
        msg = _FakeMessage(
            usage_metadata=None,
            response_metadata={
                "token_usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                "usage": {"input_tokens": 99, "output_tokens": 99, "total_tokens": 198},
            },
        )
        result = normalize_llm_usage(msg)
        assert result == {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30, "cost_usd": None}

    def test_usage_metadata_precedes_response_metadata(self) -> None:
        msg = _FakeMessage(
            usage_metadata={"input_tokens": 5, "output_tokens": 10, "total_tokens": 15},
            response_metadata={
                "token_usage": {"input_tokens": 99, "output_tokens": 99, "total_tokens": 198},
            },
        )
        result = normalize_llm_usage(msg)
        assert result == {"input_tokens": 5, "output_tokens": 10, "total_tokens": 15, "cost_usd": None}

    def test_missing_total_tokens_calculates_sum(self) -> None:
        msg = _FakeMessage(
            usage_metadata={"input_tokens": 50, "output_tokens": 100},
        )
        result = normalize_llm_usage(msg)
        assert result == {"input_tokens": 50, "output_tokens": 100, "total_tokens": 150, "cost_usd": None}

    def test_missing_total_with_none_input_does_not_sum(self) -> None:
        msg = _FakeMessage(
            usage_metadata={"output_tokens": 100},
        )
        result = normalize_llm_usage(msg)
        assert result["total_tokens"] is None

    def test_cost_calculation(self) -> None:
        msg = _FakeMessage(
            usage_metadata={"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500},
        )
        result = normalize_llm_usage(
            msg,
            cost_per_input_token=0.00001,
            cost_per_output_token=0.00003,
        )
        assert result["input_tokens"] == 1000
        assert result["output_tokens"] == 500
        assert result["total_tokens"] == 1500
        assert isinstance(result["cost_usd"], float)
        assert result["cost_usd"] > 0

    def test_cost_zero_when_no_rate(self) -> None:
        msg = _FakeMessage(
            usage_metadata={"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500},
        )
        result = normalize_llm_usage(msg)
        assert result["cost_usd"] is None
