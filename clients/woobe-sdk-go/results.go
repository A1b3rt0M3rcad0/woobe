package woobe

import (
	"bytes"
	"encoding/hex"
	"encoding/json"
	"io"
	"strings"
)

type Usage struct {
	InputTokens  *int64   `json:"input_tokens,omitempty"`
	OutputTokens *int64   `json:"output_tokens,omitempty"`
	TotalTokens  *int64   `json:"total_tokens,omitempty"`
	CostUSD      *float64 `json:"cost_usd,omitempty"`
}

// RunArtifactOutput is metadata for a committed exact Artifact revision. It
// contains no file bytes; download remains an explicit Artifacts API call.
type RunArtifactOutput struct {
	SchemaVersion string            `json:"schema_version"`
	Ref           ArtifactReference `json:"ref"`
	Path          string            `json:"path"`
	ContentType   string            `json:"content_type"`
	SizeBytes     int64             `json:"size_bytes"`
	SHA256        string            `json:"sha256"`
	Status        string            `json:"status"`
	RunID         *string           `json:"run_id"`
	NodeID        *string           `json:"node_id"`
	SourceRefs    []ArtifactSource  `json:"source_refs"`
}

type ArtifactOutput = RunArtifactOutput

type ArtifactTransfer struct {
	OperationID     string              `json:"operation_id"`
	State           string              `json:"state"`
	Mode            string              `json:"mode"`
	DestinationHost string              `json:"destination_host"`
	InputRefs       []ArtifactReference `json:"input_refs"`
	FileHashes      []map[string]any    `json:"file_hashes"`
	StatusCode      *int                `json:"status_code,omitempty"`
	ToolID          *string             `json:"tool_id,omitempty"`
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
	PrimaryModel            *string `json:"primary_model,omitempty"`
	PrimaryProvider         *string `json:"primary_provider,omitempty"`
	PrimaryProviderModelID  *string `json:"primary_provider_model_id,omitempty"`
	PrimaryCredentialID     *string `json:"primary_credential_id,omitempty"`
	PrimaryError            *string `json:"primary_error,omitempty"`
	FallbackModel           *string `json:"fallback_model,omitempty"`
	FallbackProvider        *string `json:"fallback_provider,omitempty"`
	FallbackProviderModelID *string `json:"fallback_provider_model_id,omitempty"`
	FallbackCredentialID    *string `json:"fallback_credential_id,omitempty"`
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
	SchemaVersion         *int     `json:"schema_version,omitempty"`
	AgentRuntimeLatencyMS *float64 `json:"agent_runtime_latency_ms,omitempty"`
	TotalLatencyMS        *float64 `json:"total_latency_ms,omitempty"`
	PrepareLatencyMS      *float64 `json:"prepare_latency_ms,omitempty"`
	LLMWorkLatencyMS      *float64 `json:"llm_work_latency_ms,omitempty"`
	LLMRuntimeLatencyMS   *float64 `json:"llm_runtime_latency_ms,omitempty"`
	ToolWallLatencyMS     *float64 `json:"tool_wall_latency_ms,omitempty"`
	ToolWorkLatencyMS     *float64 `json:"tool_work_latency_ms,omitempty"`
	ToolCallCount         *int     `json:"tool_call_count,omitempty"`
	InputTokens           *int64   `json:"input_tokens,omitempty"`
	OutputTokens          *int64   `json:"output_tokens,omitempty"`
	TotalTokens           *int64   `json:"total_tokens,omitempty"`
	CostUSD               *float64 `json:"cost_usd,omitempty"`
	Provider              *string  `json:"provider,omitempty"`
	Model                 *string  `json:"model,omitempty"`
	ProviderModelID       *string  `json:"provider_model_id,omitempty"`
	ProviderCredentialID  *string  `json:"provider_credential_id,omitempty"`
	FallbackUsed          *bool    `json:"fallback_used,omitempty"`
	ExecutionContext      *string  `json:"execution_context,omitempty"`
	ExecutionStrategy     *string  `json:"execution_strategy,omitempty"`
	AgentReleaseID        *string  `json:"agent_release_id,omitempty"`
	AgentReleaseVersion   *string  `json:"agent_release_version,omitempty"`
	Notes                 []string `json:"notes,omitempty"`
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
	OutputArtifacts         []RunArtifactOutput   `json:"output_artifacts,omitempty"`
	SourceRefs              []ArtifactSource      `json:"source_refs,omitempty"`
	ArtifactTransfers       []ArtifactTransfer    `json:"artifact_transfers,omitempty"`
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

// ArtifactAvailable returns typed metadata from an incremental publication
// event. It never fetches the referenced bytes.
func (e Event) ArtifactAvailable() (*RunArtifactOutput, bool, error) {
	if e.Type != "artifact.available" && e.Type != "artifact_available" {
		return nil, false, nil
	}
	encoded, err := json.Marshal(e.Payload)
	if err != nil {
		return nil, true, &ProtocolError{Message: "artifact event payload is invalid", Cause: err}
	}
	var raw map[string]any
	if err := json.Unmarshal(encoded, &raw); err != nil {
		return nil, true, &ProtocolError{Message: "artifact event payload is invalid", Cause: err}
	}
	if _, ok := raw["ref"]; !ok {
		raw["ref"] = map[string]any{
			"artifact_id": raw["artifact_id"],
			"revision_id": raw["revision_id"],
		}
	}
	if _, ok := raw["run_id"]; !ok && e.RunID != "" {
		raw["run_id"] = e.RunID
	}
	raw["schema_version"] = "1"
	encoded, err = json.Marshal(raw)
	if err != nil {
		return nil, true, &ProtocolError{Message: "artifact event payload is invalid", Cause: err}
	}
	var output RunArtifactOutput
	if err := json.Unmarshal(encoded, &output); err != nil {
		return nil, true, &ProtocolError{Message: "artifact event is missing a valid exact revision receipt", Cause: err}
	}
	if output.Ref.ArtifactID == "" || output.Ref.RevisionID == "" || output.SHA256 == "" {
		return nil, true, &ProtocolError{Message: "artifact event is missing its revision identity or checksum"}
	}
	if err := validateChatArtifactReferences(ChatResult{OutputArtifacts: []RunArtifactOutput{output}}); err != nil {
		return nil, true, err
	}
	return &output, true, nil
}

// ArtifactTransferEvent returns the compact, redacted transfer receipt carried
// by the shared runtime projection.
func (e Event) ArtifactTransferEvent() (*ArtifactTransfer, bool, error) {
	if e.Type != "artifact_transfer" && !strings.HasPrefix(e.Type, "artifact.transfer.") {
		return nil, false, nil
	}
	encoded, err := json.Marshal(e.Payload)
	if err != nil {
		return nil, true, &ProtocolError{Message: "artifact transfer event payload is invalid", Cause: err}
	}
	var transfer ArtifactTransfer
	if err := json.Unmarshal(encoded, &transfer); err != nil {
		return nil, true, &ProtocolError{Message: "artifact transfer event payload is invalid", Cause: err}
	}
	if transfer.OperationID == "" || transfer.State == "" {
		return nil, true, &ProtocolError{Message: "artifact transfer event is missing operation identity or state"}
	}
	return &transfer, true, nil
}
func chatResultFromEvent(e Event) (*ChatResult, error) {
	b, err := json.Marshal(e.Payload)
	if err != nil {
		return nil, err
	}
	var r ChatResult
	if err = json.Unmarshal(b, &r); err != nil {
		return nil, err
	}
	if err = validateChatArtifactReferences(r); err != nil {
		return nil, err
	}
	r.RunID, r.SessionID, r.RunKind, r.TerminalEventType = e.RunID, e.SessionID, e.RunKind, e.Type
	if r.Answer == "" {
		if s, ok := e.Payload["output"].(string); ok {
			r.Answer = s
		}
	}
	r.Raw = e.Payload
	return &r, nil
}

func validateChatArtifactReferences(result ChatResult) error {
	for _, output := range result.OutputArtifacts {
		if output.SchemaVersion != "1" || output.Status != "available" || output.Path == "" || output.SizeBytes < 0 || !strings.Contains(output.ContentType, "/") {
			return &ProtocolError{Message: "runtime result contains an invalid Artifact output"}
		}
		if err := requiredArtifactID("artifactID", output.Ref.ArtifactID); err != nil {
			return err
		}
		if err := requiredArtifactID("revisionID", output.Ref.RevisionID); err != nil {
			return err
		}
		if err := validateSourceDigest(output.SHA256); err != nil {
			return err
		}
		for _, source := range output.SourceRefs {
			if err := validateSourceReference(source); err != nil {
				return err
			}
		}
	}
	for _, source := range result.SourceRefs {
		if err := validateSourceReference(source); err != nil {
			return err
		}
	}
	return nil
}

func validateSourceDigest(value string) error {
	if len(value) != 64 || strings.ToLower(value) != value {
		return &ProtocolError{Message: "runtime Artifact reference contains an invalid SHA-256 digest"}
	}
	if _, err := hex.DecodeString(value); err != nil {
		return &ProtocolError{Message: "runtime Artifact reference contains an invalid SHA-256 digest", Cause: err}
	}
	return nil
}

func validateSourceReference(source ArtifactSource) error {
	if err := requiredArtifactID("source artifactID", source.ArtifactID); err != nil {
		return err
	}
	if err := requiredArtifactID("source revisionID", source.RevisionID); err != nil {
		return err
	}
	return validateSourceDigest(source.SourceSHA256)
}

type RunResult struct {
	Success         bool                `json:"success"`
	Message         string              `json:"message"`
	Data            map[string]any      `json:"data"`
	OutputArtifacts []RunArtifactOutput `json:"output_artifacts,omitempty"`
	SourceRefs      []ArtifactSource    `json:"source_refs,omitempty"`
}

func (result *RunResult) UnmarshalJSON(encoded []byte) error {
	type plainRunResult RunResult
	var plain plainRunResult
	decoder := json.NewDecoder(bytes.NewReader(encoded))
	decoder.UseNumber()
	if err := decoder.Decode(&plain); err != nil {
		return err
	}
	if decoder.Decode(new(any)) != io.EOF {
		return &ProtocolError{Message: "Runtime result contains trailing JSON data"}
	}
	*result = RunResult(plain)
	if result.Data != nil {
		if len(result.OutputArtifacts) == 0 {
			if raw, ok := result.Data["output_artifacts"]; ok {
				payload, err := json.Marshal(raw)
				if err != nil {
					return err
				}
				if err := json.Unmarshal(payload, &result.OutputArtifacts); err != nil {
					return err
				}
			}
		}
		if len(result.SourceRefs) == 0 {
			if raw, ok := result.Data["source_refs"]; ok {
				payload, err := json.Marshal(raw)
				if err != nil {
					return err
				}
				if err := json.Unmarshal(payload, &result.SourceRefs); err != nil {
					return err
				}
			}
		}
		if nested, ok := result.Data["result"].(map[string]any); ok {
			if len(result.OutputArtifacts) == 0 {
				if raw, found := nested["output_artifacts"]; found {
					payload, err := json.Marshal(raw)
					if err != nil {
						return err
					}
					if err := json.Unmarshal(payload, &result.OutputArtifacts); err != nil {
						return err
					}
				}
			}
			if len(result.SourceRefs) == 0 {
				if raw, found := nested["source_refs"]; found {
					payload, err := json.Marshal(raw)
					if err != nil {
						return err
					}
					if err := json.Unmarshal(payload, &result.SourceRefs); err != nil {
						return err
					}
				}
			}
		}
	}
	return validateChatArtifactReferences(ChatResult{
		OutputArtifacts: result.OutputArtifacts,
		SourceRefs:      result.SourceRefs,
	})
}

type ActiveRun struct {
	RunID     string  `json:"run_id"`
	SessionID string  `json:"session_id,omitempty"`
	Status    string  `json:"status,omitempty"`
	RunKind   RunKind `json:"run_kind,omitempty"`
}
