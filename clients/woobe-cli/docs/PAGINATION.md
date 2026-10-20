# Reviewed pagination contracts

The [assistant skill](AGENT_SKILL.md) uses these same bounds and partial-collection
evidence. Skill installation does not change pagination or server permissions.

Body formats reviewed: Woobe `77c53832f0e5b35488d1574b3cf62777486f5189`, 2026-10-05. Control Key authority for Agent session listing is delivered at `8ab9d13953c1cd77462af85a3a3a957395141edc` (catalog revision `2026-10-05.2`). The client uses explicit response contracts rather than guessing from arbitrary fields or item counts.

| Command | Protocol | Response marker | Query marker | Page size |
| --- | --- | --- | --- | --- |
| `workspace authority category list` | cursor-complete | `data.next_cursor` | `cursor` | 1–200 |
| `workspace authority category history CATEGORY` | revision-complete | `data.next_revision` | `before_revision` | 1–200 |
| `workspace authority audit` | cursor-complete | `data.next_cursor` | `cursor` | 1–200 |
| `runtime agent sessions AGENT` | cursor-has-next | `data.next_cursor` | `cursor` | 1–100 |

Agent session reads require `run:read` in the owning Project. The effective environment is the explicit `environment` query, or `draft` when omitted/empty; a staging-only grant must query `environment=staging`. The backend checks Agent ownership, Project consistency and target/environment conditions. Category reads require `categories:read`; audit reads require `audit:read`. These documented requirements are not a client-side authority decision.

Each response requires `success:true`, `data.items` array, an explicit marker (null at the terminal page) and a boolean terminal indicator: `data.complete` or inverted `data.has_next`. A nonterminal page must contain items and an advancing marker. Revisions must be positive integers moving backwards; cursors are opaque strings bounded to 8192 bytes. Missing, contradictory or cyclic continuation fails with received pages retained.

```sh
woobe workspace authority category list --workspace WORKSPACE --limit 50 --all
woobe workspace authority category history CATEGORY --workspace WORKSPACE --limit 1 --all
woobe workspace authority audit --workspace WORKSPACE --cursor CURSOR --all --max-pages 10
woobe runtime agent sessions AGENT --project PROJECT --query environment=production --limit 20 --all
woobe request-pages /identity/workspaces/WORKSPACE/authority-categories --query limit=50
woobe request-pages /custom/items --pagination cursor-complete --max-pages 20
```

`--all` defaults to at most 20 pages, configurable from 1 to 100 using `--max-pages`. The accumulated response payload is limited to 64 MiB, with the existing 32 MiB per-response bound. `--timeout` bounds the whole traversal. Body pagination changes only the continuation query; other filters, repeated values, origin, route and selected credential remain fixed. Conflicting `--query` and named pagination flags are refused. Page-size omission preserves the server default.

A single-page command retains the existing server response shape under the CLI envelope's `data`; collection evidence is added to `meta`. With `--all`, `data.pages` retains each complete server envelope, plus `page_count` and pagination state. Repeated side projections such as `system_categories` are retained per page rather than merged or counted as distinct resources. No snapshot or deduplication of mutable resources is implied.

| Evidence | Meaning |
| --- | --- |
| `collection_complete: verified` | Enumeration began without a continuation marker and reached the contract's terminal page. |
| `collection_complete: remaining` | Traversal after an explicit initial marker reached its terminal page; earlier items were not read. |
| `collection_complete: partial` | Known body collection still has continuation, failed, or reached a client bound. |
| `collection_complete: not_verified` | Generic Link traversal supplies no reviewed body collection-completeness evidence. |
| `traversal_complete` | The selected traversal reached its terminal marker or exhausted advertised next links. |
| `meta.complete` | True only for verified whole-collection traversal; command success alone is insufficient. |
| `consistency: live` | Pages are separate authorized reads. Concurrent creation/deletion can change the collection. |
| `next_query` | Last validated continuation, when available; malformed page metadata clears it. Query secrets are redacted. |

A successful single-page read can have `success:true` and `meta.complete:false`. Bounds and failures after pages were received return exit 10, preserving pages, HTTP status and request ID. Local cancellation/deadline retains exits 130/8. First-request failure uses its ordinary error code. JSON, JSONL and table output expose pagination evidence; partial table output retains received pages.

`request-pages --pagination auto` selects these four reviewed routes, otherwise using Link traversal. Explicit protocols are `link`, `cursor-complete`, `cursor-has-next` and `revision-complete`. A caller selecting a body protocol takes responsibility for its compatibility with that custom endpoint. Generic Link traversal keeps the same origin and route, preserves all filters, and permits changes only to `cursor`, `page`, `offset` or `before_revision`; invalid query encodings and cycles are rejected. Exhausted links keep `collection_complete:not_verified`.

Tests cover all body protocols, initial markers, revision ordering, exact numeric preservation, scope/filter retention, invalid/contradictory markers, loops, max-pages, total deadline, HTTP failures, metadata/secret redaction, discovery, zero-network input refusals and table partial output. Native package smoke exercises two pages and single-page completeness against a loopback fixture on each runner OS. The backend live CLI contract validates category history/list/audit against real persistence and traverses two independent staging Agent sessions using a key scoped by `run:read`, Agent target and environment. It verifies refusal of production, default draft and an unknown Agent.
