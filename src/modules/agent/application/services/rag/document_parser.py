from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from modules.agent.domain.enums import ParserType
from shared.infra.errors import ValidationError


PAGE_SEPARATOR = "\n<<<PAGE_BREAK>>>\n"


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    page_count: int | None = None


def _value(value: object) -> str:
    return str(getattr(value, "value", value))


def _normalize_text(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).rstrip() for line in text.splitlines()]
    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


class DocumentParser:
    def parse(
        self,
        *,
        content: bytes,
        parser: ParserType | str,
        file_name: str,
        config: dict[str, Any] | None = None,
    ) -> ParsedDocument:
        parser_value = _value(parser).lower()
        parser_config = config or {}
        normalize_whitespace = bool(parser_config.get("normalize_whitespace", True))
        preserve_page_boundaries = bool(parser_config.get("preserve_page_boundaries", True))

        if parser_value in {"text", "txt", "md", "markdown"}:
            text = content.decode("utf-8")
            if normalize_whitespace:
                text = _normalize_text(text)
            return ParsedDocument(text=text, page_count=None)
        if parser_value == "pdf":
            return self._parse_pdf(
                content,
                normalize_whitespace=normalize_whitespace,
                preserve_page_boundaries=preserve_page_boundaries,
            )
        raise ValidationError(f"Unsupported parser for vector snapshot build: {parser_value}")

    def _parse_pdf(
        self,
        content: bytes,
        *,
        normalize_whitespace: bool,
        preserve_page_boundaries: bool,
    ) -> ParsedDocument:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValidationError("PDF parsing requires pypdf dependency") from exc

        reader = PdfReader(BytesIO(content))
        pages: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            text = _normalize_text(text) if normalize_whitespace else text.strip()
            if text:
                pages.append(text)
        separator = PAGE_SEPARATOR if preserve_page_boundaries else "\n\n"
        text = separator.join(pages)
        if not text.strip():
            raise ValidationError("PDF did not contain extractable text")
        return ParsedDocument(text=text, page_count=len(reader.pages))
