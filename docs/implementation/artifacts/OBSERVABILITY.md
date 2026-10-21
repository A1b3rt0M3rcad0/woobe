# Artifacts observability

Artifacts uses the existing HTTP, worker, runtime and metering observability
paths. Instrumentation is passive: metrics do not authorize requests, choose a
processor, or alter publication. A metrics failure cannot roll back an already
committed catalog or object-store transaction.

The Prometheus endpoint exposes bounded counters and summaries:

- `woobe_artifact_operations_total{operation,outcome}` and
  `woobe_artifact_operation_duration_seconds_{count,sum}` cover listing, search,
  verified reads, downloads, upload parts, publication, processing, indexing,
  model calls and authorization.
- `woobe_artifact_bytes_total{operation,direction}` distinguishes verified bytes
  read, bytes actually yielded to a download consumer, bytes accepted from an
  upload part and bytes committed to object storage. An incomplete download is
  recorded as an error and only counts bytes yielded before the disconnect.
- Existing HTTP route metrics use FastAPI's route template, not the raw URL.
  Worker failure, queue lag and retry metrics remain shared with other modules.

Artifact metric labels are allow-listed. Project, user, Workspace, Artifact,
revision, Run, request, provider response, file name, query, and document content
are not metric labels. Correlation IDs and exact object references belong only
in authorization-protected event or trace records.

Catalog mutations, upload publication, processing, index publication, model-call
receipts and source consumption already write durable operation events or
metering outbox messages. Document-model costs preserve the statuses `reported`,
`estimated` and `unknown`; estimates are never counted as provider-reported
charges. Storage bytes, transfer bytes, input/output tokens and cost remain
separate measures. Cache hits do not create model-call usage.

The HTTP observability middleware logs route template, method, status, duration,
request ID and correlation ID. It does not log request bodies, authorization
headers, query values, signed storage URLs, or document text. See
[`MODEL_PROCESSING.md`](MODEL_PROCESSING.md),
[`PROCESSING_JOBS.md`](PROCESSING_JOBS.md), and
[`HTTP_API.md`](HTTP_API.md) for the corresponding operation contracts.
