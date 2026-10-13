from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
import json

from jsonschema import Draft202012Validator
from pydantic import ValidationError
from shared.contracts.project_configuration import ConfigurationError

from modules.package.application.dtos import DOCUMENT_MODELS
from modules.package.application.configuration_dtos import DOCUMENT_MODELS_V2
from modules.package.domain.errors import PackageError


@lru_cache(maxsize=2)
def schemas(version="1.0"):
    return json.loads(
        files("modules.package.domain.schemas").joinpath("catalog.json" if version == "1.0" else "catalog-v2.json").read_text()
    )


def validate_document(document: dict, file: str = ""):
    if (
        document.get("format") != "woobe-package"
        or document.get("schema_version") not in {"1.0", "2.0"}
    ):
        raise PackageError(
            "PACKAGE_SCHEMA_UNSUPPORTED",
            "Expected woobe-package schema_version string 1.0 or 2.0",
            file=file,
        )
    kind = document.get("kind")
    models = DOCUMENT_MODELS if document["schema_version"] == "1.0" else DOCUMENT_MODELS_V2
    if kind not in models:
        raise PackageError(
            "PACKAGE_SCHEMA_UNSUPPORTED", "Unknown component kind", file=file
        )
    validator = Draft202012Validator(schemas(document["schema_version"])[kind])
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
    try:
        return models[kind].model_validate(document)
    except (ValidationError, ConfigurationError):
        raise PackageError("PACKAGE_SCHEMA_INVALID", "Owning definition constraints failed", file=file) from None
