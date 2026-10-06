from pathlib import Path
import json

import pytest

from modules.package.application.validation import validate_document
from modules.package.domain.errors import PackageError
from modules.package.domain.parsing import decode_document


FIXTURES = json.loads(
    (
        Path(__file__).resolve().parents[3] / "specs/package/v1/fixtures/parity.json"
    ).read_text()
)


@pytest.mark.parametrize("case", FIXTURES, ids=lambda case: case["name"])
def test_shared_parsing_contract(case):
    def check():
        document = decode_document(case["input"].encode(), case["file"])
        if case.get("validate") or case["name"] == "minimal-model":
            validate_document(document, case["file"])
        return document

    if "error" in case:
        with pytest.raises(PackageError) as caught:
            check()
        assert caught.value.code == case["error"]
    else:
        assert check() == case["expected"]


def test_strict_nested_behavior_fields():
    document = decode_document(
        b"""format: woobe-package
schema_version: "1.0"
kind: Agent
metadata: {key: support, name: Support}
spec:
  model: {primary: {ref: primary}}
  behavior: {objective: Answer, unknown: forbidden}
""",
        "agent.yaml",
    )
    with pytest.raises(PackageError) as caught:
        validate_document(document, "agent.yaml")
    assert caught.value.code == "PACKAGE_SCHEMA_INVALID"
    assert caught.value.path == "/spec/behavior"


def test_unknown_file_format_version_rejected_before_domain_validation():
    with pytest.raises(PackageError) as caught:
        validate_document(
            {"format": "https://attacker.invalid/schema", "schema_version": "1.0"}
        )
    assert caught.value.code == "PACKAGE_SCHEMA_UNSUPPORTED"
