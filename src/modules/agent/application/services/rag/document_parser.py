from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from typing import Any
from xml.etree import ElementTree

from modules.agent.domain.enums import ParserType
from shared.contracts.errors import ValidationError


PAGE_SEPARATOR = "\n<<<PAGE_BREAK>>>\n"
_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NS = {"w": _WORD_NS}


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


def _word_tag(local_name: str) -> str:
    return f"{{{_WORD_NS}}}{local_name}"


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
        preserve_page_boundaries = bool(
            parser_config.get("preserve_page_boundaries", True)
        )

        if parser_value in {"text", "txt", "md", "markdown"}:
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValidationError(
                    "Text and Markdown documents must be valid UTF-8"
                ) from exc
            if normalize_whitespace:
                text = _normalize_text(text)
            return ParsedDocument(text=text, page_count=None)
        if parser_value == "pdf":
            return self._parse_pdf(
                content,
                normalize_whitespace=normalize_whitespace,
                preserve_page_boundaries=preserve_page_boundaries,
            )
        if parser_value == "docx":
            return self._parse_docx(
                content,
                normalize_whitespace=normalize_whitespace,
                preserve_page_boundaries=preserve_page_boundaries,
                include_tables=bool(parser_config.get("include_docx_tables", True)),
            )
        raise ValidationError(
            f"Unsupported parser for vector snapshot build: {parser_value}"
        )

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

        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise ValidationError("Encrypted PDF documents are not supported")
            pages: list[str] = []
            has_extractable_text = False
            for page in reader.pages:
                text = page.extract_text() or ""
                text = _normalize_text(text) if normalize_whitespace else text.strip()
                pages.append(text)
                has_extractable_text = has_extractable_text or bool(text)
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError(
                "PDF document is invalid or could not be parsed"
            ) from exc

        if not has_extractable_text:
            raise ValidationError(
                "PDF did not contain extractable text; scanned PDFs require OCR"
            )
        separator = PAGE_SEPARATOR if preserve_page_boundaries else "\n\n"
        text = separator.join(pages)
        return ParsedDocument(text=text, page_count=len(reader.pages))

    def _parse_docx(
        self,
        content: bytes,
        *,
        normalize_whitespace: bool,
        preserve_page_boundaries: bool,
        include_tables: bool,
    ) -> ParsedDocument:
        try:
            with zipfile.ZipFile(BytesIO(content)) as package:
                xml = package.read("word/document.xml")
        except (KeyError, zipfile.BadZipFile, OSError) as exc:
            raise ValidationError("DOCX document is invalid or corrupted") from exc

        try:
            root = ElementTree.fromstring(xml)
        except ElementTree.ParseError as exc:
            raise ValidationError("DOCX document XML is invalid") from exc

        body = root.find("w:body", _NS)
        if body is None:
            raise ValidationError("DOCX document does not contain a body")

        blocks: list[str] = []
        for child in body:
            if child.tag == _word_tag("p"):
                paragraph = self._docx_paragraph(
                    child,
                    preserve_page_boundaries=preserve_page_boundaries,
                )
                if paragraph:
                    blocks.append(paragraph)
            elif child.tag == _word_tag("tbl") and include_tables:
                table = self._docx_table(child)
                if table:
                    blocks.append(table)

        text = "\n\n".join(blocks)
        if normalize_whitespace:
            page_parts = text.split(PAGE_SEPARATOR)
            text = PAGE_SEPARATOR.join(_normalize_text(part) for part in page_parts)
        else:
            text = text.strip()
        if not text.strip():
            raise ValidationError("DOCX did not contain extractable text")
        return ParsedDocument(text=text, page_count=None)

    def _docx_paragraph(
        self,
        paragraph: ElementTree.Element,
        *,
        preserve_page_boundaries: bool,
    ) -> str:
        parts: list[str] = []
        for node in paragraph.iter():
            if node.tag == _word_tag("t"):
                parts.append(node.text or "")
            elif node.tag == _word_tag("tab"):
                parts.append("\t")
            elif node.tag == _word_tag("br"):
                break_type = node.attrib.get(_word_tag("type"))
                if preserve_page_boundaries and break_type == "page":
                    parts.append(PAGE_SEPARATOR)
                else:
                    parts.append("\n")
            elif (
                preserve_page_boundaries
                and node.tag == _word_tag("lastRenderedPageBreak")
            ):
                parts.append(PAGE_SEPARATOR)

        text = "".join(parts).strip()
        if not text:
            return ""

        properties = paragraph.find("w:pPr", _NS)
        style_value = ""
        numbered = False
        if properties is not None:
            style = properties.find("w:pStyle", _NS)
            if style is not None:
                style_value = str(style.attrib.get(_word_tag("val"), ""))
            numbered = properties.find("w:numPr", _NS) is not None

        heading_match = re.search(r"heading\s*([1-6])", style_value, re.IGNORECASE)
        if heading_match:
            return f"{'#' * int(heading_match.group(1))} {text}"
        if style_value.lower() in {"title", "subtitle"}:
            return f"# {text}"
        if numbered:
            return f"- {text}"
        return text

    def _docx_table(self, table: ElementTree.Element) -> str:
        rows: list[str] = []
        for row in table.findall("w:tr", _NS):
            cells: list[str] = []
            for cell in row.findall("w:tc", _NS):
                paragraphs = [
                    self._docx_paragraph(
                        paragraph,
                        preserve_page_boundaries=False,
                    )
                    for paragraph in cell.findall("w:p", _NS)
                ]
                value = " ".join(part for part in paragraphs if part).strip()
                cells.append(value.replace("|", "\\|"))
            if any(cells):
                rows.append(" | ".join(cells))
        return "\n".join(rows)
