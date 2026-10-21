package output

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
)

type DomainDiagnostic struct {
	Key              string `json:"key,omitempty"`
	Environment      string `json:"environment,omitempty"`
	Kind             string `json:"kind,omitempty"`
	ResourceID       string `json:"resource_id,omitempty"`
	ExpectedRevision string `json:"expected_revision,omitempty"`
	ObservedRevision string `json:"observed_revision,omitempty"`
	Code             string `json:"code"`
	File             string `json:"file,omitempty"`
	Path             string `json:"path,omitempty"`
}

type Error struct {
	TestID          string             `json:"test_id,omitempty"`
	RecoveryCommand string             `json:"recovery_command,omitempty"`
	DomainCode      string             `json:"domain_code,omitempty"`
	Diagnostics     []DomainDiagnostic `json:"diagnostics,omitempty"`
	Code            int                `json:"exit_code"`
	Message         string             `json:"message"`
	Status          int                `json:"http_status,omitempty"`
	RequestID       string             `json:"request_id,omitempty"`
	Outcome         string             `json:"write_outcome,omitempty"`
	Cause           error              `json:"-"`
}

func (e *Error) Error() string            { return e.Message }
func (e *Error) Unwrap() error            { return e.Cause }
func New(code int, message string) *Error { return &Error{Code: code, Message: message} }
func Normalize(err error) *Error {
	var e *Error
	if errors.As(err, &e) {
		return e
	}
	if errors.Is(err, context.Canceled) {
		return New(130, "local operation interrupted")
	}
	if errors.Is(err, context.DeadlineExceeded) {
		return New(8, "deadline exceeded")
	}
	return &Error{Code: 1, Message: err.Error(), Cause: err}
}

type Envelope struct {
	SchemaVersion string            `json:"schema_version"`
	Success       bool              `json:"success"`
	Context       map[string]string `json:"context,omitempty"`
	Data          any               `json:"data,omitempty"`
	Error         *Error            `json:"error,omitempty"`
	Meta          map[string]any    `json:"meta"`
}

func Write(w io.Writer, mode string, data any, scope map[string]string, err error) error {
	return WriteWithMeta(w, mode, data, scope, err, nil)
}

// WriteWithMeta adds collection evidence independently of command success.
func WriteWithMeta(w io.Writer, mode string, data any, scope map[string]string, err error, meta map[string]any) error {
	if meta != nil {
		meta = Redact(meta).(map[string]any)
	}
	if mode == "table" {
		if len(meta) > 0 {
			if err != nil {
				meta["complete"] = false
			}
			data = map[string]any{"response": data, "pagination": meta}
			if e := renderTable(w, data, nil); e != nil {
				return e
			}
			if err == nil {
				return nil
			}
		}
		return renderTable(w, data, err)
	}
	e := Envelope{SchemaVersion: "1", Success: err == nil, Context: scope, Data: data, Meta: map[string]any{"complete": err == nil}}
	for key, value := range meta {
		e.Meta[key] = value
	}
	if err != nil {
		e.Error = Normalize(err)
		e.Meta["complete"] = false
	}
	enc := json.NewEncoder(w)
	if mode != "table" && mode != "json" && mode != "jsonl" {
		return New(2, fmt.Sprintf("unsupported output %q", mode))
	}
	return enc.Encode(e)
}

// A fencing token is an integer concurrency counter, never an authentication
// token. Keep this exception value-typed and exact-keyed; textual tokens remain
// secret even when accidentally placed in the concurrency field.
func fencingCounter(value any) bool {
	switch v := value.(type) {
	case json.Number:
		n, err := v.Int64()
		return err == nil && n > 0
	case int:
		return v > 0
	case int64:
		return v > 0
	case int32:
		return v > 0
	case uint:
		return v > 0 && uint64(v) <= math.MaxInt64
	case uint64:
		return v > 0 && v <= math.MaxInt64
	case float64:
		return v >= 1 && v <= 1<<53 && math.Trunc(v) == v
	default:
		return false
	}
}

// Redact recursively protects secret-bearing fields even in generic responses.
func Redact(v any) any {
	switch x := v.(type) {
	case map[string]any:
		out := make(map[string]any, len(x))
		for k, v := range x {
			if k == "authentication" && authenticationReferenceMetadata(v) {
				out[k] = copyAuthenticationReferenceMetadata(v)
				continue
			}
			if Sensitive(k) && !(k == "fencing_token" && fencingCounter(v)) {
				out[k] = "[REDACTED]"
			} else {
				out[k] = Redact(v)
			}
		}
		return out
	case []any:
		out := make([]any, len(x))
		for i, v := range x {
			out[i] = Redact(v)
		}
		return out
	default:
		b, e := json.Marshal(v)
		if e != nil {
			return v
		}
		var decoded any
		d := json.NewDecoder(bytes.NewReader(b))
		d.UseNumber()
		if d.Decode(&decoded) != nil {
			return v
		}
		switch decoded.(type) {
		case map[string]any, []any:
			return Redact(decoded)
		}
		return v
	}
}
