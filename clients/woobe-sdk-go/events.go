package woobe

import (
	"encoding/json"
	"fmt"
	"time"
)

const RuntimeStreamProtocolVersion = 2

type RunKind string

const (
	RunKindAgent   RunKind = "AGENT"
	RunKindNetwork RunKind = "NETWORK"
)

type Event struct {
	ProtocolVersion int            `json:"protocol_version"`
	EventID         string         `json:"event_id"`
	RunID           string         `json:"run_id"`
	SessionID       string         `json:"session_id"`
	RunKind         RunKind        `json:"run_kind"`
	Sequence        int64          `json:"sequence"`
	Type            string         `json:"type"`
	OccurredAt      time.Time      `json:"occurred_at"`
	Payload         map[string]any `json:"payload"`
}

func (e Event) Validate() error {
	if e.ProtocolVersion != RuntimeStreamProtocolVersion {
		return fmt.Errorf("unsupported runtime protocol version %d", e.ProtocolVersion)
	}
	if e.EventID == "" || e.RunID == "" || e.SessionID == "" || e.Type == "" {
		return fmt.Errorf("invalid runtime event identity")
	}
	if e.RunKind != RunKindAgent && e.RunKind != RunKindNetwork {
		return fmt.Errorf("invalid run_kind %q", e.RunKind)
	}
	if e.Sequence < 0 { return fmt.Errorf("invalid negative sequence") }
	return nil
}

type ControlFrame struct {
	ProtocolVersion int            `json:"protocol_version"`
	Type            string         `json:"type"`
	OccurredAt      time.Time      `json:"occurred_at"`
	Payload         map[string]any `json:"payload"`
}

func decodeRuntimeFrame(data []byte) (Event, *ControlFrame, error) {
	var probe map[string]json.RawMessage
	if err := json.Unmarshal(data, &probe); err != nil {
		return Event{}, nil, &ProtocolError{Message: "runtime stream frame contains invalid JSON", Cause: err}
	}
	_, hasRun := probe["run_id"]
	_, hasEvent := probe["event_id"]
	if !hasRun || !hasEvent {
		var c ControlFrame
		if err := json.Unmarshal(data, &c); err != nil {
			return Event{}, nil, &ProtocolError{Message: "invalid runtime control frame", Cause: err}
		}
		return Event{}, &c, nil
	}
	var e Event
	if err := json.Unmarshal(data, &e); err != nil {
		return Event{}, nil, &ProtocolError{Message: "invalid runtime semantic event", Cause: err}
	}
	if err := e.Validate(); err != nil { return Event{}, nil, &ProtocolError{Message: err.Error()} }
	if e.Payload == nil { e.Payload = map[string]any{} }
	return e, nil, nil
}
