"""Declared suite identities accompany server-verified content digests."""
import json
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, StrictStr, model_validator

from shared.contracts.asac import asac_digest
from shared.contracts.asac_requests import StrictASaCRequest


class ASaCEvaluationCase(StrictASaCRequest):
    id: StrictStr = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    message: StrictStr = Field(min_length=1, max_length=32768)
    external_context: dict[str, Any] = Field(default_factory=dict)
    expected_output: Any = None


class ASaCEvaluationSuite(StrictASaCRequest):
    schema_version: Literal["1.0"]
    suite_id: StrictStr = Field(min_length=1, max_length=128)
    suite_version: StrictStr = Field(min_length=1, max_length=128)
    dataset_version: StrictStr = Field(min_length=1, max_length=128)
    policy_version: Literal["all-cases-pass@1"] = "all-cases-pass@1"
    cases: list[ASaCEvaluationCase] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def bounded_unique_cases(self):
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Evaluation case identities must be unique")
        if any(not case.message.strip() for case in self.cases):
            raise ValueError("Evaluation messages cannot be blank")
        asac_digest("evaluation-suite", self.model_dump())
        if len(json.dumps(self.model_dump(), ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()) > 1024 * 1024:
            raise ValueError("Evaluation suite exceeds its bounded input size")
        return self

    def evidence_digests(self):
        document = self.model_dump()
        return {
            "suite_digest": asac_digest("evaluation-suite", document),
            "dataset_digest": asac_digest("evaluation-dataset", document["cases"]),
            "policy_digest": asac_digest("evaluation-policy", {"version": self.policy_version}),
        }


class EvaluateASaCCandidate(StrictASaCRequest):
    operation_id: UUID
    suite: ASaCEvaluationSuite
