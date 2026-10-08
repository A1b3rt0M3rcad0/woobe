from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
import json

from jsonschema import Draft202012Validator

from modules.package.application.dtos import DOCUMENT_MODELS
from modules.package.domain.errors import PackageError


@lru_cache(maxsize=1)
def schemas():
    return json.loads(
        files("modules.package.domain.schemas").joinpath("catalog.json").read_text()
    )


def validate_document(document: dict, file: str = ""):
    if (
        document.get("format") != "woobe-package"
        or document.get("schema_version") != "1.0"
    ):
        raise PackageError(
            "PACKAGE_SCHEMA_UNSUPPORTED",
            "Expected woobe-package schema_version string 1.0",
            file=file,
        )
    kind = document.get("kind")
    if kind not in DOCUMENT_MODELS:
        raise PackageError(
            "PACKAGE_SCHEMA_UNSUPPORTED", "Unknown component kind", file=file
        )
    validator = Draft202012Validator(schemas()[kind])
    failures = sorted(
        validator.iter_errors(document), key=lambda error: str(error.json_path)
    )
    if failures:
        error = failures[0]
        pointer = "/" + "/".join(
            str(part).replace("~", "~0").replace("/", "~1") for part in error.path
        )
        # Do not echo attacker-controlled values or documents in diagnostics.
        raise PackageError(
            "PACKAGE_SCHEMA_INVALID",
            f"Schema constraint failed: {error.validator}",
            file=file,
            path=pointer,
            line=getattr(document, "locations", {}).get(pointer, (0, 0))[0],
            column=getattr(document, "locations", {}).get(pointer, (0, 0))[1],
        )
    return DOCUMENT_MODELS[kind].model_validate(document)
