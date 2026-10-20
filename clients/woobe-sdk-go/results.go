package woobe

import "encoding/json"

type Usage struct {
	InputTokens  *int64   `json:"input_tokens,omitempty"`
	OutputTokens *int64   `json:"output_tokens,omitempty"`
	TotalTokens  *int64   `json:"total_tokens,omitempty"`
	CostUSD      *float64 `json:"cost_usd,omitempty"`
}
type Source struct {
	DocumentTitle  *string  `json:"document_title,omitempty"`
	DocumentID     *string  `json:"document_id,omitempty"`
	ChunkID        *string  `json:"chunk_id,omitempty"`
	PageNumber     *int     `json:"page_number,omitempty"`
	Score          *float64 `json:"score,omitempty"`
	ContentPreview *string  `json:"content_preview,omitempty"`
}
type ToolCall struct {
	ToolCallID *string  `json:"tool_call_id,omitempty"`
	ToolName   *string  `json:"tool_name,omitempty"`
	Input      any      `json:"input,omitempty"`
	Output     any      `json:"output,omitempty"`
	DurationMS *float64 `json:"duration_ms,omitempty"`
	Success    *bool    `json:"success,omitempty"`
	Status     *string  `json:"status,omitempty"`
	LatencyMS  *float64 `json:"latency_ms,omitempty"`
	Error      *string  `json:"error,omitempty"`
	ErrorCode  *string  `json:"error_code,omitempty"`
}
type FallbackInfo struct {
	PrimaryModel             *string `json:"primary_model,omitempty"`
	PrimaryProvider          *string `json:"primary_provider,omitempty"`
	PrimaryProviderModelID   *string `json:"primary_provider_model_id,omitempty"`
	PrimaryCredentialID      *string `json:"primary_credential_id,omitempty"`
	PrimaryError             *string `json:"primary_error,omitempty"`
	FallbackModel            *string `json:"fallback_model,omitempty"`
	FallbackProvider         *string `json:"fallback_provider,omitempty"`
	FallbackProviderModelID  *string `json:"fallback_provider_model_id,omitempty"`
	FallbackCredentialID     *string `json:"fallback_credential_id,omitempty"`
}
type ExecutionEvent struct {
	SchemaVersion *int           `json:"schema_version,omitempty"`
	EventID       *string        `json:"event_id,omitempty"`
	TraceID       *string        `json:"trace_id,omitempty"`
	RootSpanID    *string        `json:"root_span_id,omitempty"`
	SpanID        *string        `json:"span_id,omitempty"`
	ParentSpanID  *string        `json:"parent_span_id,omitempty"`
	Sequence      *int64         `json:"sequence,omitempty"`
	EventType     *string        `json:"event_type,omitempty"`
	Phase         *string        `json:"phase,omitempty"`
	Status        *string        `json:"status,omitempty"`
	OccurredAt    *string        `json:"occurred_at,omitempty"`
	StartedAt     *string        `json:"started_at,omitempty"`
	EndedAt       *string        `json:"ended_at,omitempty"`
	DurationMS    *float64       `json:"duration_ms,omitempty"`
	Attributes    map[string]any `json:"attributes,omitempty"`
}
type ExecutionDiagnostics struct {
	SchemaVersion          *int     `json:"schema_version,omitempty"`
	AgentRuntimeLatencyMS  *float64 `json:"agent_runtime_latency_ms,omitempty"`
	TotalLatencyMS         *float64 `json:"total_latency_ms,omitempty"`
	PrepareLatencyMS       *float64 `json:"prepare_latency_ms,omitempty"`
	LLMWorkLatencyMS       *float64 `json:"llm_work_latency_ms,omitempty"`
	LLMRuntimeLatencyMS    *float64 `json:"llm_runtime_latency_ms,omitempty"`
	ToolWallLatencyMS      *float64 `json:"tool_wall_latency_ms,omitempty"`
	ToolWorkLatencyMS      *float64 `json:"tool_work_latency_ms,omitempty"`
	ToolCallCount          *int     `json:"tool_call_count,omitempty"`
	InputTokens            *int64   `json:"input_tokens,omitempty"`
	OutputTokens           *int64   `json:"output_tokens,omitempty"`
	TotalTokens            *int64   `json:"total_tokens,omitempty"`
	CostUSD                *float64 `json:"cost_usd,omitempty"`
	Provider               *string  `json:"provider,omitempty"`
	Model                  *string  `json:"model,omitempty"`
	ProviderModelID        *string  `json:"provider_model_id,omitempty"`
	ProviderCredentialID   *string  `json:"provider_credential_id,omitempty"`
	FallbackUsed           *bool    `json:"fallback_used,omitempty"`
	ExecutionContext       *string  `json:"execution_context,omitempty"`
	ExecutionStrategy      *string  `json:"execution_strategy,omitempty"`
	AgentReleaseID         *string  `json:"agent_release_id,omitempty"`
	AgentReleaseVersion    *string  `json:"agent_release_version,omitempty"`
	Notes                  []string `json:"notes,omitempty"`
}
type ChatResult struct {
	RunID                   string                `json:"run_id"`
	SessionID               string                `json:"session_id"`
	RunKind                 RunKind               `json:"run_kind"`
	TerminalEventType       string                `json:"terminal_event_type"`
	Answer                  string                `json:"answer"`
	MessageID               *string               `json:"message_id,omitempty"`
	TraceID                 *string               `json:"trace_id,omitempty"`
	Usage                   *Usage                `json:"usage,omitempty"`
	Sources                 []Source              `json:"sources,omitempty"`
	ToolCalls               []ToolCall            `json:"tool_calls,omitempty"`
	Model                   *string               `json:"model,omitempty"`
	Provider                *string               `json:"provider,omitempty"`
	ProviderModelID         *string               `json:"provider_model_id,omitempty"`
	ProviderCredentialID    *string               `json:"provider_credential_id,omitempty"`
	FallbackProviderModelID *string               `json:"fallback_provider_model_id,omitempty"`
	FallbackCredentialID    *string               `json:"fallback_credential_id,omitempty"`
	FallbackUsed            bool                  `json:"fallback_used"`
	FallbackInfo            *FallbackInfo         `json:"fallback_info,omitempty"`
	LatencyMS               *float64              `json:"latency_ms,omitempty"`
	TTFTMS                  *float64              `json:"ttft_ms,omitempty"`
	ParsedOutput            any                   `json:"parsed_output,omitempty"`
	OutputParseError        *string               `json:"output_parse_error,omitempty"`
	ExecutionEvents         []ExecutionEvent      `json:"execution_events,omitempty"`
	Diagnostics             *ExecutionDiagnostics `json:"diagnostics,omitempty"`
	Raw                     map[string]any        `json:"-"`
}
func chatResultFromEvent(e Event) (*ChatResult, error) {
	b, err := json.Marshal(e.Payload)
	if err != nil { return nil, err }
	var r ChatResult
	if err = json.Unmarshal(b, &r); err != nil { return nil, err }
	r.RunID, r.SessionID, r.RunKind, r.TerminalEventType = e.RunID, e.SessionID, e.RunKind, e.Type
	if r.Answer == "" {
		if s, ok := e.Payload["output"].(string); ok { r.Answer = s }
	}
	r.Raw = e.Payload
	return &r, nil
}

type RunResult struct {
	Success bool           `json:"success"`
	Message string         `json:"message"`
	Data    map[string]any `json:"data"`
}
type ActiveRun struct {
	RunID     string  `json:"run_id"`
	SessionID string  `json:"session_id,omitempty"`
	Status    string  `json:"status,omitempty"`
	RunKind   RunKind `json:"run_kind,omitempty"`
}
