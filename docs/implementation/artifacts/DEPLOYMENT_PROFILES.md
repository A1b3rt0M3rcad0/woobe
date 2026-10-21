# Artifact deployment profiles

The default `compose.yaml` is the lightweight profile. It installs the native
text/PDF path and structural indexer; it does not install Docling, PageIndex,
Tesseract, or OCR weights. Existing `/live`, `/ready`, worker-heartbeat, and
Artifact processing-capability endpoints report process health and the actual
installed processing components separately.

For optional model-free Docling processing, merge the document override when
building and starting the stack:

```sh
docker compose -f compose.yaml -f compose.artifacts-documents.yaml build api workers
docker compose -f compose.yaml -f compose.artifacts-documents.yaml up -d
```

For the pinned, local PageIndex outline adapter, use:

```sh
docker compose -f compose.yaml -f compose.artifacts-pageindex.yaml build api workers
docker compose -f compose.yaml -f compose.artifacts-pageindex.yaml up -d
```

These overrides install the same optional extra in API and worker images so
admission and execution report a consistent capability. The default stack stays
available without optional dependencies. Neither profile changes migrations,
downloads a model as a side effect of an Agent run, or publishes an image. OCR
profiles require the separately pinned model acquisition/qualification process;
they are not enabled by either override. Production deployments should use
shared PostgreSQL, queue and object storage, provision bounded scratch space,
and allow graceful worker lease reconciliation before stopping a worker.

Use `GET /v1/artifact-processing-capabilities` with a scoped Project credential
to inspect installed engines and diagnostics. `store_only` remains available
when a parser/indexer is absent; a requested unavailable processor is rejected
before a job is queued. The worker health file proves that loops are alive, not
that a particular optional engine is installed or a queue is being consumed.
