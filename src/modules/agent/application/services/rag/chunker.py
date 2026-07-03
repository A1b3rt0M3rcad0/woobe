from __future__ import annotations

from dataclasses import dataclass

from shared.infra.errors import ValidationError


@dataclass(frozen=True)
class TextChunk:
    content: str
    chunk_index: int
    token_count: int | None = None
    page_number: int | None = None
    section_title: str | None = None


class RecursiveTextChunker:
    def chunk(self, text: str, *, chunk_size: int, chunk_overlap: int) -> list[TextChunk]:
        if chunk_size <= 0:
            raise ValidationError("chunk_size must be greater than zero")
        if chunk_overlap < 0:
            raise ValidationError("chunk_overlap cannot be negative")
        if chunk_overlap >= chunk_size:
            raise ValidationError("chunk_overlap must be lower than chunk_size")

        normalized = "\n".join(line.rstrip() for line in text.splitlines()).strip()
        if not normalized:
            return []

        chunks: list[TextChunk] = []
        start = 0
        index = 0
        while start < len(normalized):
            end = min(start + chunk_size, len(normalized))
            candidate = normalized[start:end]
            if end < len(normalized):
                split_at = max(candidate.rfind("\n\n"), candidate.rfind("\n"), candidate.rfind(". "))
                if split_at > chunk_size * 0.5:
                    end = start + split_at + 1
                    candidate = normalized[start:end]
            content = candidate.strip()
            if content:
                chunks.append(
                    TextChunk(
                        content=content,
                        chunk_index=index,
                        token_count=max(1, len(content) // 4),
                    )
                )
                index += 1
            if end >= len(normalized):
                break
            start = max(0, end - chunk_overlap)
        return chunks
