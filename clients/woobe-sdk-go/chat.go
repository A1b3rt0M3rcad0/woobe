package woobe

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

type Chat struct {
	mu             sync.Mutex
	client         *Client
	targetKind     RunKind
	targetAlias    string
	key            string
	input          string
	options        ChatOptions
	runID          string
	sessionID      string
	idempotencyKey string
	started        bool
}

func newChat(t runtimeTarget, input string, o ChatOptions) *Chat {
	return &Chat{
		client: t.client, targetKind: t.kind, targetAlias: t.alias,
		key: t.key, input: input, options: o, sessionID: o.SessionID,
		idempotencyKey: newID(),
	}
}

func newID() string {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil { return fmt.Sprintf("woobe-%d", time.Now().UnixNano()) }
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	dst := make([]byte, 36)
	hex.Encode(dst[0:8], b[0:4]); dst[8] = '-'
	hex.Encode(dst[9:13], b[4:6]); dst[13] = '-'
	hex.Encode(dst[14:18], b[6:8]); dst[18] = '-'
	hex.Encode(dst[19:23], b[8:10]); dst[23] = '-'
	hex.Encode(dst[24:36], b[10:16])
	return string(dst)
}

func (c *Chat) RunID() string { c.mu.Lock(); defer c.mu.Unlock(); return c.runID }
func (c *Chat) SessionID() string { c.mu.Lock(); defer c.mu.Unlock(); return c.sessionID }
func (c *Chat) TargetAlias() string { return c.targetAlias }

func (c *Chat) Stream(ctx context.Context) (*Stream, error) {
	c.mu.Lock()
	if c.started {
		c.mu.Unlock()
		return nil, &ProtocolError{Message: "Chat stream can only be consumed once"}
	}
	c.started = true
	c.mu.Unlock()
	return c.start(ctx, "new")
}

type Stream struct {
	Events    <-chan Event
	events    chan Event
	done      chan struct{}
	mu        sync.RWMutex
	err       error
	result    *ChatResult
	runID     string
	sessionID string
}

func (s *Stream) Done() <-chan struct{} { return s.done }
func (s *Stream) Err() error { s.mu.RLock(); defer s.mu.RUnlock(); return s.err }
func (s *Stream) Result() *ChatResult { s.mu.RLock(); defer s.mu.RUnlock(); return s.result }
func (s *Stream) RunID() string { s.mu.RLock(); defer s.mu.RUnlock(); return s.runID }
func (s *Stream) SessionID() string { s.mu.RLock(); defer s.mu.RUnlock(); return s.sessionID }
func (s *Stream) setErr(err error) { s.mu.Lock(); s.err = err; s.mu.Unlock() }

func (c *Chat) start(ctx context.Context, mode string) (*Stream, error) {
	out := make(chan Event)
	s := &Stream{events: out, Events: out, done: make(chan struct{}), runID: c.runID, sessionID: c.sessionID}
	go c.consume(ctx, s, mode)
	return s, nil
}

func (c *Chat) consume(ctx context.Context, s *Stream, mode string) {
	defer close(s.events)
	defer close(s.done)
	attempt := 0
	var last *int64

	for {
		frames, errs, err := c.open(mode, ctx)
		if err != nil {
			if !c.recoverable(err) { s.setErr(err); return }
			mode, attempt, err = c.recover(ctx, mode, attempt, err)
			if err != nil { s.setErr(err); return }
			continue
		}

		var streamErr error
		for f := range frames {
			if f.control != nil {
				if f.control.Type == "error" {
					msg := "Woobe Runtime rejected the request before Run acceptance"
					if v, ok := f.control.Payload["message"].(string); ok && v != "" { msg = v }
					streamErr = &RequestError{Message: msg}
				}
				continue
			}
			e := f.event
			if e.RunKind != c.targetKind {
				streamErr = &ProtocolError{Message: "runtime returned an unexpected run kind"}
				break
			}

			c.mu.Lock()
			if c.runID != "" && c.runID != e.RunID {
				c.mu.Unlock()
				streamErr = &ProtocolError{Message: "runtime stream changed Run identity"}
				break
			}
			if c.sessionID != "" && c.sessionID != e.SessionID {
				c.mu.Unlock()
				streamErr = &ProtocolError{Message: "runtime stream changed Session identity"}
				break
			}
			c.runID, c.sessionID = e.RunID, e.SessionID
			c.mu.Unlock()

			s.mu.Lock()
			s.runID, s.sessionID = e.RunID, e.SessionID
			s.mu.Unlock()

			accept, gap := acceptSequence(last, e)
			if gap != nil { streamErr = gap; break }
			if !accept { continue }
			v := e.Sequence
			last = &v

			if isResultEvent(e) {
				r, er := chatResultFromEvent(e)
				if er != nil { streamErr = er; break }
				s.mu.Lock()
				s.result = r
				s.mu.Unlock()
			}

			select {
			case s.events <- e:
			case <-ctx.Done():
				s.setErr(ctx.Err())
				return
			}
			if isTerminalEvent(e) { return }
		}

		if streamErr == nil {
			for er := range errs {
				if er != nil { streamErr = er; break }
			}
		}
		if streamErr == nil { streamErr = &ConnectionError{Message: "Runtime stream ended before terminal state"} }
		if !c.recoverable(streamErr) { s.setErr(streamErr); return }

		var recErr error
		mode, attempt, recErr = c.recover(ctx, mode, attempt, streamErr)
		if recErr != nil { s.setErr(recErr); return }
	}
}

func (c *Chat) open(mode string, ctx context.Context) (<-chan runtimeFrame, <-chan error, error) {
	if mode == "reattach" {
		c.mu.Lock(); id := c.runID; c.mu.Unlock()
		if id == "" { return nil, nil, &ProtocolError{Message: "canonical Run ID is not available"} }
		return c.client.openStream(ctx, http.MethodGet, "/v1/runs/"+url.PathEscape(id)+"/stream", c.key, nil, "")
	}
	body := map[string]any{"message": c.input}
	addRuntimeOptions(body, c.options)
	return c.client.openStream(ctx, http.MethodPost, "/v1/run/stream", c.key, body, c.idempotencyKey)
}

func (c *Chat) recoverable(err error) bool {
	var ce *ConnectionError
	var ge *StreamGapError
	var re *RequestError
	return errors.As(err, &ce) || errors.As(err, &ge) || (errors.As(err, &re) && re.Retryable())
}

func (c *Chat) recover(ctx context.Context, mode string, attempt int, cause error) (string, int, error) {
	c.mu.Lock()
	runID, sessionID := c.runID, c.sessionID
	c.mu.Unlock()

	if runID == "" && sessionID != "" {
		ar, err := c.client.activeRun(ctx, c.key, sessionID)
		if err == nil && ar != nil {
			runID = ar.RunID
			c.mu.Lock(); c.runID = runID; c.mu.Unlock()
		}
	}
	if runID == "" {
		if c.targetKind == RunKindNetwork && mode == "new" {
			if attempt >= c.client.maxReconnectAttempts {
				return mode, attempt, &RecoveryError{Message: "Network Run could not be recovered before its canonical ID was observed", Cause: cause}
			}
			if err := sleepContext(ctx, c.client.reconnectBaseDelay*time.Duration(attempt+1)); err != nil { return mode, attempt, err }
			return "new", attempt + 1, nil
		}
		return mode, attempt, &RecoveryError{
			Message: "runtime connection failed before the canonical Run could be recovered; refusing to submit another Agent execution because it could duplicate the Run",
			Cause: cause,
		}
	}
	if attempt >= c.client.maxReconnectAttempts {
		return mode, attempt, &RecoveryError{Message: "Run exceeded the reattach retry budget", Cause: cause}
	}
	if err := sleepContext(ctx, c.client.reconnectBaseDelay*time.Duration(attempt+1)); err != nil { return mode, attempt, err }
	return "reattach", attempt + 1, nil
}

func sleepContext(ctx context.Context, d time.Duration) error {
	if d <= 0 { return nil }
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-t.C: return nil
	case <-ctx.Done(): return ctx.Err()
	}
}

func acceptSequence(last *int64, e Event) (bool, error) {
	if e.Type == "run.state" {
		if v, ok := e.Payload["realtime_available"].(bool); ok && !v { return true, nil }
		if last != nil && e.Sequence < *last { return false, nil }
		return true, nil
	}
	if last != nil {
		if e.Sequence <= *last { return false, nil }
		if e.Sequence != *last+1 { return false, &StreamGapError{Expected: *last + 1, Received: e.Sequence} }
	}
	return true, nil
}

func isTerminalEvent(e Event) bool {
	switch e.Type {
	case "done", "error", "cancelled", "execution_completed", "execution_failed", "execution_cancelled", "execution_timed_out":
		return true
	}
	if e.Type == "run.state" {
		if st, ok := e.Payload["status"].(string); ok {
			switch strings.ToLower(st) {
			case "completed", "failed", "cancelled", "timed_out", "uncertain":
				return true
			}
		}
	}
	return false
}
func isResultEvent(e Event) bool {
	if e.Type == "done" || e.Type == "execution_completed" { return true }
	if e.Type == "run.state" {
		st, _ := e.Payload["status"].(string)
		return strings.EqualFold(st, "completed")
	}
	return false
}
