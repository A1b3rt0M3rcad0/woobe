# RAG strategies

Each module in this directory implements one complete RAG behavior behind `RAGStrategy`.

`classic.py` is the baseline implementation extracted from the pre-strategy runtime. It intentionally preserves the existing query construction, similarity search, score filtering, per-document diversity, top-k selection, context budget, source construction and grounding behavior.

A future strategy should be added as a sibling module and registered explicitly by the composition root. It must not import infrastructure modules directly.
