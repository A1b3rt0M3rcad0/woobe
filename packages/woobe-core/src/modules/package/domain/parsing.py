from __future__ import annotations

import json
import math
import re

import yaml
from yaml.events import (
    AliasEvent,
    MappingStartEvent,
    SequenceStartEvent,
    MappingEndEvent,
    SequenceEndEvent,
)
from yaml.nodes import MappingNode, ScalarNode, SequenceNode

from modules.package.domain.errors import PackageError


MAX_DESCRIPTOR_BYTES = 2 << 20
MAX_DEPTH = 32
MAX_NODES = 200_000
MAX_INTEGER = 9_007_199_254_740_991
NUMBER = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$")


class ParsedDocument(dict):
    locations: dict[str, tuple[int, int]]


def _check_json(text: str, file: str):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        json.loads(
            text,
            object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (ValueError, RecursionError) as exc:
        raise PackageError(
            "PACKAGE_PARSE_INVALID", "Invalid or duplicate-key JSON", file=file
        ) from exc


class JsonScalars(yaml.SafeLoader):
    yaml_implicit_resolvers = {
        key: [
            (tag, pattern)
            for tag, pattern in entries
            if tag not in {"tag:yaml.org,2002:bool", "tag:yaml.org,2002:timestamp"}
        ]
        for key, entries in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }


JsonScalars.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$"), list("tf")
)


def decode_document(data: bytes, file: str = "") -> dict:
    if len(data) > MAX_DESCRIPTOR_BYTES:
        raise PackageError(
            "PACKAGE_LIMIT_EXCEEDED", "Descriptor exceeds 2 MiB", file=file
        )
    try:
        text = data.decode("utf-8", errors="strict")
        if file.endswith(".json"):
            _check_json(text, file)
        depth = count = 0
        for event in yaml.parse(text, Loader=JsonScalars):
            count += 1
            if (
                isinstance(event, AliasEvent)
                or getattr(event, "anchor", None)
                or getattr(event, "tag", None)
            ):
                raise PackageError(
                    "PACKAGE_PARSE_INVALID",
                    "Aliases, anchors and explicit tags are forbidden",
                    file=file,
                )
            if isinstance(event, (MappingStartEvent, SequenceStartEvent)):
                depth += 1
            if isinstance(event, (MappingEndEvent, SequenceEndEvent)):
                depth -= 1
            if depth > MAX_DEPTH or count > MAX_NODES:
                raise PackageError(
                    "PACKAGE_LIMIT_EXCEEDED",
                    "Descriptor exceeds structural limits",
                    file=file,
                )
        node = yaml.compose(text, Loader=JsonScalars)
    except (UnicodeError, yaml.YAMLError, RecursionError) as exc:
        mark = getattr(exc, "problem_mark", None)
        raise PackageError(
            "PACKAGE_PARSE_INVALID",
            "Invalid UTF-8 or YAML/JSON document",
            file=file,
            line=mark.line + 1 if mark else 0,
            column=mark.column + 1 if mark else 0,
        ) from exc

    locations = {}

    def convert(item, pointer=""):
        locations[pointer] = (item.start_mark.line + 1, item.start_mark.column + 1)

        def fail(message):
            raise PackageError(
                "PACKAGE_PARSE_INVALID",
                message,
                file=file,
                path=pointer,
                line=item.start_mark.line + 1,
                column=item.start_mark.column + 1,
            )

        if isinstance(item, MappingNode):
            result = {}
            for key, child in item.value:
                if (
                    not isinstance(key, ScalarNode)
                    or key.tag != "tag:yaml.org,2002:str"
                    or key.value == "<<"
                ):
                    fail("Mapping keys must be strings; merge keys are forbidden")
                if key.value in result:
                    fail("Duplicate mapping key")
                escaped = key.value.replace("~", "~0").replace("/", "~1")
                result[key.value] = convert(child, pointer + "/" + escaped)
            return result
        if isinstance(item, SequenceNode):
            return [
                convert(child, pointer + "/" + str(index))
                for index, child in enumerate(item.value)
            ]
        if not isinstance(item, ScalarNode):
            fail("Unsupported node")
        if item.style is None and NUMBER.fullmatch(item.value):
            number = json.loads(item.value)
            if isinstance(number, int) and abs(number) > MAX_INTEGER:
                fail("Integer exceeds exact interoperable range")
            if isinstance(number, float) and not math.isfinite(number):
                fail("Nonfinite numbers are forbidden")
            return number
        if item.tag == "tag:yaml.org,2002:str":
            return item.value
        if item.tag == "tag:yaml.org,2002:null":
            return None
        if item.tag == "tag:yaml.org,2002:bool":
            return item.value == "true"
        if item.tag in {"tag:yaml.org,2002:int", "tag:yaml.org,2002:float"}:
            if not NUMBER.fullmatch(item.value):
                fail("Only finite JSON numeric syntax is supported")
            number = json.loads(item.value)
            if isinstance(number, int) and abs(number) > MAX_INTEGER:
                fail("Integer exceeds exact interoperable range")
            if isinstance(number, float) and not math.isfinite(number):
                fail("Nonfinite numbers are forbidden")
            return number
        fail("Unsupported scalar")

    value = convert(node) if node is not None else None
    if not isinstance(value, dict):
        raise PackageError(
            "PACKAGE_PARSE_INVALID", "Document root must be a mapping", file=file
        )
    result = ParsedDocument(value)
    result.locations = locations
    return result
