# Woobe SDK for Go

Official Go client for integrating applications and backend services with the Woobe Runtime API.

This SDK targets the public Runtime contract from Woobe `master` and follows the same domain model as the Python SDK: a Runtime Key selects an Agent or Network, a Session is the correlation/continuity boundary, a Run is one finite execution, and Runtime Protocol v2 events are the canonical streaming interface.

## Install

```bash
go get github.com/A1b3rt0M3rcad0/woobe-sdk-go
```

Go 1.22+ is supported. The SDK intentionally uses only the Go standard library.

## Quick start

```go
client, err := woobe.New()
if err != nil { log.Fatal(err) }
defer client.CloseIdleConnections()

agent, err := client.Connect.Agent("support", os.Getenv("WOOBE_RUNTIME_KEY"))
if err != nil { log.Fatal(err) }

chat, err := agent.Chat("Olá", &woobe.ChatOptions{
    ExternalContext: map[string]any{"tenant_id": "acme"},
})
if err != nil { log.Fatal(err) }

stream, err := chat.Stream(context.Background())
if err != nil { log.Fatal(err) }

for event := range stream.Events {
    fmt.Println(event.Type, event.Sequence, event.Payload)
}
if err := stream.Err(); err != nil { log.Fatal(err) }

result := stream.Result()
fmt.Println(result.Answer)
```

The default endpoint is `https://api.woobe.com.br`. Override it with `WOOBE_BASE_URL` or `woobe.WithBaseURL(...)`.

## Agent and Network targets

```go
agent, _ := client.Connect.Agent("assistant", runtimeKey)
network, _ := client.Connect.Network("study-pipeline", runtimeKey)
```

`alias` is local metadata for your application. Authorization and target binding are determined by the Runtime Key, not by the alias.

Both targets expose the same public Runtime capabilities:

- `Chat(...)` + `Stream(ctx)` for streaming execution;
- `Run(ctx, ...)` for the synchronous `/v1/run` endpoint;
- `ObserveRun(ctx, runID)` to attach to an existing Run;
- `ActiveRun(ctx, sessionID)` to recover a Run from a Session;
- `CancelRun(ctx, runID)` for explicit cancellation;
- `ValidateContracts(ctx, ...)` for release contract compatibility.

## Streaming and reattach safety

A stream observes a Run; it does not own it. The SDK implements the Runtime Protocol v2 recovery rules:

1. start through `POST /v1/run/stream`;
2. capture canonical `run_id` and `session_id` from semantic events;
3. validate `run_kind` and monotonic semantic `sequence`;
4. treat `run.state` as replacement/current-state reconciliation;
5. on connection loss or a sequence gap, reattach with `GET /v1/runs/{run_id}/stream`;
6. if only a Session is known, query `GET /v1/sessions/{session_id}/active-run` first;
7. never submit a second Agent Run after canonical Run identity is known.

Network pre-identity retries reuse the same idempotency key. Transport/control frames such as heartbeats remain internal; `Stream.Events` exposes only canonical semantic `Event` values.

## Session and External Context

```go
chat, _ := agent.Chat("continue", &woobe.ChatOptions{
    SessionID: "019...",
    ExternalContext: map[string]any{
        "workspace_id": "ws_123",
        "locale": "pt-BR",
    },
})
```

External Context lifecycle (`session` vs `run`) is enforced by the Woobe release contract. The SDK sends values exactly as supplied and does not silently mutate Session-scoped context.

## Direct run

```go
result, err := agent.Run(ctx, "Generate a summary", &woobe.RunOptions{
    Metadata: map[string]any{"request_id": "req-123"},
})
```

`RunResult.Data` intentionally remains `map[string]any`: Agent and Network synchronous result payloads can evolve independently while the streaming protocol provides the stable cross-target event envelope.

## Contract validation

```go
validation, err := agent.ValidateContracts(ctx, woobe.ContractValidationRequest{
    OutputContract: map[string]any{
        "type": "object",
        "properties": map[string]any{
            "answer": map[string]any{"type": "string"},
        },
        "required": []string{"answer"},
    },
})
```

## Existing Run observation and cancellation

```go
stream, err := agent.ObserveRun(ctx, runID)
active, err := agent.ActiveRun(ctx, sessionID)
err = agent.CancelRun(ctx, runID)
```

Disconnecting a stream does not cancel execution. Cancellation is always explicit.

## Errors

Use `errors.As` with `AuthenticationError`, `RequestError`, `ConnectionError`, `ProtocolError`, `StreamGapError` and `RecoveryError`.

## HTTP customization

```go
client, err := woobe.New(
    woobe.WithBaseURL("https://woobe.internal.example"),
    woobe.WithHTTPClient(httpClient),
    woobe.WithReconnect(6, 200*time.Millisecond),
)
```

The default client deliberately does not set `http.Client.Timeout`, because that timeout covers the whole response and would terminate legitimate long-lived SSE streams. Use `context.Context` deadlines per operation.

## Public Runtime endpoints covered

```text
POST /v1/run
POST /v1/run/stream
GET  /v1/runs/{run_id}/stream
POST /v1/runs/{run_id}/cancel
GET  /v1/sessions/{session_id}/active-run
POST /v1/contracts/validate
```

`/v1/jobs` is intentionally not exposed because Woobe currently returns `501` for Runtime Jobs.

## Automatic Semantic Versioning

Every successful push to `master` is released automatically after the Go test matrix passes.

The CI derives the next stable Semantic Version from commits since the latest `vMAJOR.MINOR.PATCH` tag:

- `BREAKING CHANGE:` or a Conventional Commit `!` marker -> **major**;
- `feat` -> **minor**;
- every other recognized type -> **patch**;
- an unknown type or a non-Conventional Commit subject is classified as `chore` -> **patch**.

The release job creates an immutable Git tag and a GitHub Release from the exact tested `master` commit. For Go consumers, the tag is the module version, so no separate package registry publication is required.

Examples:

```text
feat(runtime): add network observation   -> minor
fix(stream): preserve event sequence     -> patch
feat(client)!: remove legacy option      -> major
Refresh examples                         -> chore -> patch
```

## Development

```bash
gofmt -w .
go vet ./...
go test -race ./...
```

## License

MIT. See [LICENSE](LICENSE).
