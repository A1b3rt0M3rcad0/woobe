import json

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
