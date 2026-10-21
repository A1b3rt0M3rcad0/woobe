# Optional local PageIndex Flash adapter

Woobe vendors the transitive import closure for upstream PageIndex Flash
`extract_toc` from VectifyAI/PageIndex 0.2.10 at commit
`27f284291724fbbbbe6976388bd53eed4ebe7fca`. The MIT license, upstream attribution
and per-file hashes remain with the vendored source under
`packages/woobe-core/src/shared/infra/vendor/pageindex_flash`.

The adapter currently accepts PDF originals only. It runs the deterministic,
model-free `extract_toc(..., workers=1, use_embedded_toc=False)` path in an owned
Worker subprocess. PageIndex Cloud, chat, storage and model clients are outside the
vendored import closure. Markdown and other formats continue through their
registered Woobe processors and indexers.

Install the optional Python dependencies with `uv sync --extra pageindex-local`,
or build the Worker/API image with `--build-arg WOOBE_PROCESSING_PROFILE=pageindex-local`.
The normal `base` profile remains free of the PageIndex-only PyPDF2,
`sortedcontainers` and `regex` dependencies. Core startup does not import the
vendored package. Without the extra, capabilities report
`pageindex_local_extra_not_installed`; a profile may opt into the native
structural fallback with `parameters.indexer_fallback = "structural"`. The
published index records the engine that actually ran, and PostgreSQL permits that
engine only when the immutable recipe contains the same explicit fallback choice.

The worker verifies the original revision's byte count and SHA-256 before passing
it to the isolated child. It bounds input size, pages, depth, node count, output,
memory and time; it removes proxy/credential environment variables, kills the
child process group on cancellation, and removes per-job scratch on exit. The
adapter maps headings to exact canonical blocks and adds source-owning block nodes
for content that the upstream outline does not recognize. It validates the full
tree's block ownership and ranges before publication.

The adapter does not imply a live model-provider qualification. Any separate
summarization or refinement still uses the governed Woobe model gateway and its
environment-authorized binding.
