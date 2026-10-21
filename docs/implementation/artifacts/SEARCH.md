# Artifact text search

`GET /v1/artifact-workspaces/{id}/search` searches only the authorized Workspace and returns bounded snippets with a `SourceReference` for the exact canonical block and revision. `mode=text` uses PostgreSQL's `simple` text configuration over NFKC-normalized canonical block text and tokenized file paths. `mode=literal` preserves punctuation and the original Unicode text for formulas and code. Generated summaries are not part of this index.

Search filters project, environment, workspace status, the caller's current `search` grant, catalog history, and ready representation generations in SQL before ranking. A signed cursor binds the query, principal and scope. It pins both the immutable catalog version and the Workspace search publication version, so edits and later processing publications do not change subsequent pages. Each revision contributes its newest ready representation within that pinned search version.

Canonical block text is stored in bounded 4,096-character segments alongside its existing exact byte and character ranges. PostgreSQL GIN indexes serve full-text and trigram literal queries; separate path indexes support text and literal matching. The original canonical block remains the source of truth for reads and citations.
