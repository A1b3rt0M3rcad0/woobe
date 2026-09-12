from __future__ import annotations

# Stable storage-version identifiers belong to the shared contract surface so
# application orchestration can reason about persisted Run semantics without
# depending on the runtime implementation package.
EVENT_JOURNAL_STORAGE_VERSION = "event_journal_v1"
LEGACY_RUN_STORAGE_VERSION = "legacy_v1"
