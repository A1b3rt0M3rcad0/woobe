from __future__ import annotations

import re
from dataclasses import dataclass

from shared.contracts.errors import ValidationError


PAGE_SEPARATOR = "\n<<<PAGE_BREAK>>>\n"


@dataclass(frozen=True)
class TextChunk:
    content: str
    chunk_index: int
    token_count: int | None = None
    page_number: int | None = None
    section_title: str | None = None


class RecursiveTextChunker:
    def chunk(
        self,
        text: str,
        *,
        chunk_size: int,
        chunk_overlap: int,
        strategy: str = "recursive_text",
        min_chunk_size: int = 100,
        preserve_paragraphs: bool = True,
        preserve_headings: bool = True,
        preserve_page_boundaries: bool = True,
    ) -> list[TextChunk]:
        self._validate(chunk_size=chunk_size, chunk_overlap=chunk_overlap, min_chunk_size=min_chunk_size)
        normalized = text.strip()
        if not normalized:
            return []
        pages = normalized.split(PAGE_SEPARATOR) if preserve_page_boundaries else [normalized.replace(PAGE_SEPARATOR, "\n\n")]
        chunks: list[TextChunk] = []
        for page_index, page in enumerate(pages, start=1):
            if not page.strip():
                continue
            page_number = page_index if preserve_page_boundaries and len(pages) > 1 else None
            if strategy == "paragraph":
                page_chunks = self._chunk_paragraphs(page, chunk_size=chunk_size, chunk_overlap=chunk_overlap, page_number=page_number)
            elif strategy == "markdown_headings":
                page_chunks = self._chunk_markdown(page, chunk_size=chunk_size, chunk_overlap=chunk_overlap, page_number=page_number, preserve_headings=preserve_headings)
            elif strategy == "recursive_text":
                page_chunks = self._chunk_recursive(page, chunk_size=chunk_size, chunk_overlap=chunk_overlap, page_number=page_number, preserve_paragraphs=preserve_paragraphs, preserve_headings=preserve_headings)
            else:
                raise ValidationError(f"Unsupported chunking strategy: {strategy}")
            chunks.extend(page_chunks)
        chunks = self._merge_small_chunks(chunks, min_chunk_size=min_chunk_size)
        return [TextChunk(content=chunk.content, chunk_index=index, token_count=max(1, len(chunk.content) // 4), page_number=chunk.page_number, section_title=chunk.section_title) for index, chunk in enumerate(chunks)]

    def _validate(self, *, chunk_size: int, chunk_overlap: int, min_chunk_size: int) -> None:
        if chunk_size <= 0:
            raise ValidationError("chunk_size must be greater than zero")
        if chunk_overlap < 0:
            raise ValidationError("chunk_overlap cannot be negative")
        if chunk_overlap >= chunk_size:
            raise ValidationError("chunk_overlap must be lower than chunk_size")
        if min_chunk_size < 0:
            raise ValidationError("min_chunk_size cannot be negative")
        if min_chunk_size > chunk_size:
            raise ValidationError("min_chunk_size cannot be greater than chunk_size")

    def _chunk_recursive(self, text: str, *, chunk_size: int, chunk_overlap: int, page_number: int | None, preserve_paragraphs: bool, preserve_headings: bool) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            candidate = text[start:end]
            if end < len(text):
                boundaries: list[int] = []
                if preserve_paragraphs:
                    boundaries.append(candidate.rfind("\n\n"))
                if preserve_headings:
                    heading_positions = [match.start() for match in re.finditer(r"(?m)^#{1,6}\s+", candidate)]
                    if heading_positions:
                        boundaries.append(heading_positions[-1])
                boundaries.extend([candidate.rfind("\n"), candidate.rfind(". ")])
                split_at = max(boundaries, default=-1)
                if split_at > chunk_size * 0.5:
                    end = start + split_at + 1
                    candidate = text[start:end]
            content = candidate.strip()
            if content:
                chunks.append(TextChunk(content=content, chunk_index=len(chunks), page_number=page_number, section_title=self._nearest_heading(text, start) if preserve_headings else None))
            if end >= len(text):
                break
            start = max(0, end - chunk_overlap)
        return chunks

    def _chunk_paragraphs(self, text: str, *, chunk_size: int, chunk_overlap: int, page_number: int | None) -> list[TextChunk]:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        return self._pack_units([(paragraph, None) for paragraph in paragraphs], chunk_size=chunk_size, chunk_overlap=chunk_overlap, page_number=page_number)

    def _chunk_markdown(self, text: str, *, chunk_size: int, chunk_overlap: int, page_number: int | None, preserve_headings: bool) -> list[TextChunk]:
        units: list[tuple[str, str | None]] = []
        current_title: str | None = None
        current_lines: list[str] = []
        for line in text.splitlines():
            heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
            if heading:
                if current_lines:
                    units.append(("\n".join(current_lines).strip(), current_title))
                    current_lines = []
                current_title = heading.group(1).strip()
                if preserve_headings:
                    current_lines.append(line)
            else:
                current_lines.append(line)
        if current_lines:
            units.append(("\n".join(current_lines).strip(), current_title))
        return self._pack_units([(content, title) for content, title in units if content], chunk_size=chunk_size, chunk_overlap=chunk_overlap, page_number=page_number)

    def _pack_units(self, units: list[tuple[str, str | None]], *, chunk_size: int, chunk_overlap: int, page_number: int | None) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        buffer = ""
        section_title: str | None = None
        for content, title in units:
            if len(content) > chunk_size:
                if buffer.strip():
                    chunks.append(self._text_chunk(buffer, len(chunks), page_number, section_title))
                    buffer = ""
                chunks.extend(self._chunk_recursive(content, chunk_size=chunk_size, chunk_overlap=chunk_overlap, page_number=page_number, preserve_paragraphs=True, preserve_headings=True))
                section_title = title
                continue
            candidate = f"{buffer}\n\n{content}".strip() if buffer else content
            if buffer and len(candidate) > chunk_size:
                chunks.append(self._text_chunk(buffer, len(chunks), page_number, section_title))
                overlap = buffer[-chunk_overlap:].strip() if chunk_overlap else ""
                buffer = f"{overlap}\n\n{content}".strip() if overlap else content
            else:
                buffer = candidate
            section_title = title or section_title
        if buffer.strip():
            chunks.append(self._text_chunk(buffer, len(chunks), page_number, section_title))
        return chunks

    def _merge_small_chunks(self, chunks: list[TextChunk], *, min_chunk_size: int) -> list[TextChunk]:
        if min_chunk_size <= 0 or len(chunks) < 2:
            return chunks
        merged: list[TextChunk] = []
        for chunk in chunks:
            if len(chunk.content) >= min_chunk_size or not merged:
                merged.append(chunk)
                continue
            previous = merged[-1]
            if previous.page_number == chunk.page_number:
                merged[-1] = TextChunk(content=f"{previous.content}\n\n{chunk.content}".strip(), chunk_index=previous.chunk_index, page_number=previous.page_number, section_title=previous.section_title or chunk.section_title)
            else:
                merged.append(chunk)
        return merged

    def _nearest_heading(self, text: str, position: int) -> str | None:
        headings = list(re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*$", text[:position]))
        return headings[-1].group(1).strip() if headings else None

    def _text_chunk(self, content: str, index: int, page_number: int | None, section_title: str | None) -> TextChunk:
        return TextChunk(content=content.strip(), chunk_index=index, page_number=page_number, section_title=section_title)
