from modules.agent.application.use_cases.tool_result_semantics import normalize_tool_result


def test_explicit_failure() -> None:
    result = normalize_tool_result({"success": False, "error": "boom"})
    assert result.success is False
    assert result.error_code == "tool_execution_failed"
    assert result.error_message == "boom"


def test_mcp_failure() -> None:
    result = normalize_tool_result(
        {
            "success": True,
            "output": {
                "mcp": {
                    "isError": True,
                    "message": "Repository not found",
                }
            },
        }
    )
    assert result.success is False
    assert result.error_code == "repository_not_found"


def test_structured_failure_message() -> None:
    result = normalize_tool_result(
        {
            "success": True,
            "output": {
                "mcp": {
                    "isError": False,
                    "structuredContent": {
                        "result": "Invalid repoName format. Use owner/repo."
                    },
                }
            },
        }
    )
    assert result.success is False
    assert result.error_code == "invalid_repository_identifier"


def test_regular_success() -> None:
    result = normalize_tool_result(
        {"success": True, "output": {"result": {"answer": "loaded"}}}
    )
    assert result.success is True
    assert result.error_code is None


def test_regular_result_text_is_not_scanned_as_an_error() -> None:
    result = normalize_tool_result(
        {
            "success": True,
            "output": {
                "result": {
                    "answer": "The documentation explains how repository not found errors are handled."
                }
            },
        }
    )
    assert result.success is True
    assert result.error_code is None
