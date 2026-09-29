from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


ChunkingStrategy = Literal["recursive_text", "paragraph", "markdown_headings"]
ChunkingPreset = Literal["precise", "balanced", "broad", "custom"]
SearchStrategy = Literal["similarity"]
QueryMode = Literal["current_message", "conversation_context"]
GroundingPolicy = Literal["optional", "required"]
ParserImplementation = Literal["woobe-document-parser"]
ParserVersion = Literal["2"]


class RAGParserConfig(BaseModel):
    implementation: ParserImplementation = "woobe-document-parser"
    version: ParserVersion = "2"
    normalize_whitespace: bool = True
    preserve_page_boundaries: bool = True
    include_docx_tables: bool = True


class RAGChunkingConfig(BaseModel):
    preset: ChunkingPreset = "balanced"
    strategy: ChunkingStrategy = "recursive_text"
    chunk_size: int = Field(default=800, ge=200, le=4000)
    chunk_overlap: int = Field(default=120, ge=0, le=1000)
    min_chunk_size: int = Field(default=100, ge=20, le=1000)
    preserve_paragraphs: bool = True
    preserve_headings: bool = True
    preserve_page_boundaries: bool = True

    @model_validator(mode="after")
    def validate_sizes(self) -> "RAGChunkingConfig":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be lower than chunk_size")
        if self.min_chunk_size > self.chunk_size:
            raise ValueError("min_chunk_size cannot be greater than chunk_size")
        return self


class RAGRetrievalConfig(BaseModel):
    search_strategy: SearchStrategy = "similarity"
    candidate_k: int = Field(default=20, ge=1, le=100)
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float | None = Field(default=None, ge=0.0, le=1.0)
    max_context_chunks: int = Field(default=5, ge=1, le=20)
    max_chunks_per_document: int = Field(default=2, ge=1, le=20)
    max_context_chars: int = Field(default=24_000, ge=1000, le=100_000)
    grounding_policy: GroundingPolicy = "optional"

    @model_validator(mode="after")
    def validate_retrieval_limits(self) -> "RAGRetrievalConfig":
        if self.top_k > self.candidate_k:
            raise ValueError("top_k cannot be greater than candidate_k")
        if self.max_context_chunks > self.top_k:
            raise ValueError("max_context_chunks cannot be greater than top_k")
        return self


class RAGRuntimeConfig(RAGRetrievalConfig):
    """Canonical Knowledge/RAG configuration persisted in Agent runtime_config.rag."""

    query_mode: QueryMode = "conversation_context"
    history_turns: int = Field(default=3, ge=1, le=10)
    strategy: str = Field(default="classic", min_length=1, max_length=64)
    strategy_config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("strategy")
    @classmethod
    def normalize_strategy(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("strategy cannot be empty")
        return normalized


class RAGBuildConfig(BaseModel):
    parser: RAGParserConfig = RAGParserConfig()
    chunking: RAGChunkingConfig = RAGChunkingConfig()


class VectorBuildPreviewSample(BaseModel):
    document_id: str
    document_title: str
    chunk_index: int
    character_count: int
    preview: str


class VectorBuildPreviewOutput(BaseModel):
    document_count: int
    estimated_chunk_count: int
    estimated_vector_count: int
    sample_chunks: list[VectorBuildPreviewSample]
