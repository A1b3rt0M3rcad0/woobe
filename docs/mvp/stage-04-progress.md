# MVP Stage 04 closeout status

Stage 04 was merged through PR #21, but its original progress file and PR description still represented the work as in progress. The closeout audit verified that the backend contains a real provider stream, an SSE v1 channel with progressive token events, TTFT measurement, heartbeat support and a single-terminal-event invariant. The frontend contains a chunk-safe SSE parser, session reload support and draft editor state.

## Corrections applied by `mvp-closeout-audit`

- added a visible stop control that aborts the active browser stream;
- restricted new/runtime provider credentials to OpenAI and custom OpenAI-compatible providers;
- made the credential collection stable across `refetch`, so a newly created credential can be selected from the refreshed result instead of the stale render snapshot;
- added backend tests for progressive token delivery, TTFT and exactly one terminal event.

## Remaining release-hardening evidence

The following items are not represented as fully closed by this audit:

- browser-to-provider cancellation persistence must be exercised in a PostgreSQL integration/E2E test and prove the final `cancelled` trace/message state;
- fallback, tool-call and structured-output event ordering need integration contract tests, not only implementation inspection;
- an E2E provider mock must verify session/history recovery after reload;
- production telemetry assertions for TTFT, total duration and provider/tool failures remain part of the release-hardening stage.

Stage 04 is therefore functionally corrected for the confirmed UI gaps, but its complete acceptance matrix remains pending test evidence and must not be represented as fully closed until those tests pass.
