from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from modules.agent.domain.enums import ParserType
from shared.infra.errors import ValidationError


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    page_count: int | None = None


def _value(value: object) -> str:
    return str(getattr(value, "value", value))


class DocumentParser:
    def parse(self, *, content: bytes, parser: ParserType | str, file_name: str) -> ParsedDocument:
        parser_value = _value(parser).lower()
        if parser_value in {"text", "txt", "md", "markdown"}:
            return ParsedDocument(text=content.decode("utf-8"), page_count=None)
        if parser_value == "pdf":
            return self._parse_pdf(content)
        raise ValidationError(f"Unsupported parser for vector snapshot build: {parser_value}")

    def _parse_pdf(self, content: bytes) -> ParsedDocument:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValidationError("PDF parsing requires pypdf dependency") from exc

        reader = PdfReader(BytesIO(content))
        pages: list[str] = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        text = "\n\n".join(page.strip() for page in pages if page.strip())
        if not text.strip():
            raise ValidationError("PDF did not contain extractable text")
        return ParsedDocument(text=text, page_count=len(reader.pages))
