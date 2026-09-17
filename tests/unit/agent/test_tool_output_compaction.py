import json

from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.use_cases.tool_output_compaction import (
    compact_tool_output_for_llm,
)


def test_compact_tool_output_for_llm_bounds_large_payload():
    raw_output = {
        "success": True,
        "output": {
            "body": {
                "repository": {
                    "full_name": "opencode-ai/opencode",
                    "html_url": "https://github.com/opencode-ai/opencode",
                    "description": "AI coding agent",
                },
                "raw": "x" * 200_000,
            }
        },
    }

    content = compact_tool_output_for_llm(raw_output, max_chars=4_000)
    parsed = json.loads(content)

    assert len(content) < 6_000
    assert parsed["_llm_compacted"] is True
    assert parsed["_original_size_chars"] > 200_000
    assert "opencode-ai/opencode" in content
    assert "https://github.com/opencode-ai/opencode" in content
    assert "x" * 10_000 not in content


def test_default_limit_preserves_normal_delegated_agent_response():
    specialist_response = "x" * 1_978

    content = compact_tool_output_for_llm(
        {
            "success": True,
            "result_type": "text",
            "result": specialist_response,
        }
    )
    parsed = json.loads(content)

    assert parsed["_llm_compacted"] is False
    assert parsed["tool_output"]["result"] == specialist_response


def test_run_context_can_lower_tool_result_materialization_limit():
    context = new_execution_context()
    context.tool_result_max_chars = 1_200
    token = current_execution.set(context)
    try:
        content = compact_tool_output_for_llm(
            {
                "success": True,
                "result_type": "text",
                "result": "x" * 5_000,
            }
        )
    finally:
        current_execution.reset(token)

    parsed = json.loads(content)
    assert parsed["_llm_compacted"] is True
    assert parsed["_original_size_chars"] > 5_000
    assert "tool_output_preview" in parsed
