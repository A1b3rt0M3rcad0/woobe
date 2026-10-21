"""Small exact-ID enrichment. Unknown IDs and fine-tunes stay unclassified.

Sources: https://platform.openai.com/docs/models/gpt-4o
https://platform.openai.com/docs/models/gpt-4o-mini
https://platform.openai.com/docs/models/text-embedding-3-small
https://platform.openai.com/docs/models/text-embedding-3-large
Revision: 2026-10-15. Remote explicit evidence wins over these defaults.
"""
REVISION = "2026-10-15.1"

OPENAI_MODEL_EVIDENCE = {
    key: {"model_type": "language", "input_modalities": ["text", "image"],
        "output_modalities": ["text"], "context_window": 128000,
        "max_output_tokens": 16384, "supports_tools": True, "supports_json": True,
        "supports_streaming": True}
    for key in ("gpt-4o", "gpt-4o-2024-08-06", "gpt-4o-2024-11-20", "gpt-4o-mini", "gpt-4o-mini-2024-07-18")
}
OPENAI_MODEL_EVIDENCE.update({
    "text-embedding-3-small": {"model_type": "embedding", "dimensions": 1536},
    "text-embedding-3-large": {"model_type": "embedding", "dimensions": 3072},
})
