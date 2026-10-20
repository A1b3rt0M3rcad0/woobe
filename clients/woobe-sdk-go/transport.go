package woobe

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-sdk-go/internal/sse"
)

type runtimeFrame struct {
	event   Event
	control *ControlFrame
}

func (c *Client) endpoint(path string) string { return c.baseURL + path }
func authHeaders(req *http.Request, key, accept string) {
	req.Header.Set("Authorization", "Bearer "+key)
	req.Header.Set("Accept", accept)
	req.Header.Set("Content-Type", "application/json")
	if accept == "text/event-stream" { req.Header.Set("Accept-Encoding", "identity") }
}

func (c *Client) doJSON(ctx context.Context, method, path, key string, body any, out any) error {
	var r io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil { return err }
		r = bytes.NewReader(b)
	}
	req, err := http.NewRequestWithContext(ctx, method, c.endpoint(path), r)
	if err != nil { return err }
	authHeaders(req, key, "application/json")
	resp, err := c.httpClient.Do(req)
	if err != nil { return &ConnectionError{Message: "Woobe Runtime request failed", Cause: err} }
	defer resp.Body.Close()
	if err = raiseForStatus(resp); err != nil { return err }
	if out == nil { return nil }
	if err = json.NewDecoder(resp.Body).Decode(out); err != nil {
		return &ProtocolError{Message: "Woobe response contains invalid JSON", Cause: err}
	}
	return nil
}
func raiseForStatus(resp *http.Response) error {
	if resp.StatusCode >= 200 && resp.StatusCode < 300 { return nil }
	b, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
	msg := strings.TrimSpace(string(b))
	if msg == "" { msg = http.StatusText(resp.StatusCode) }
	re := &RequestError{StatusCode: resp.StatusCode, Message: msg, Body: string(b)}
	if resp.StatusCode == 401 || resp.StatusCode == 403 { return &AuthenticationError{RequestError: re} }
	return re
}

func (c *Client) openStream(ctx context.Context, method, path, key string, body any, idempotencyKey string) (<-chan runtimeFrame, <-chan error, error) {
	var r io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil { return nil, nil, err }
		r = bytes.NewReader(b)
	}
	req, err := http.NewRequestWithContext(ctx, method, c.endpoint(path), r)
	if err != nil { return nil, nil, err }
	authHeaders(req, key, "text/event-stream")
	if idempotencyKey != "" { req.Header.Set("Idempotency-Key", idempotencyKey) }
	resp, err := c.httpClient.Do(req)
	if err != nil { return nil, nil, &ConnectionError{Message: "Woobe Runtime stream connection failed", Cause: err} }
	if err = raiseForStatus(resp); err != nil { resp.Body.Close(); return nil, nil, err }

	frames := make(chan runtimeFrame)
	errs := make(chan error, 1)
	go func() {
		defer close(frames)
		defer close(errs)
		defer resp.Body.Close()
		sc := bufio.NewScanner(resp.Body)
		sc.Buffer(make([]byte, 64*1024), 16*1024*1024)
		dec := sse.NewDecoder()
		emit := func(f *sse.Frame) bool {
			if f == nil { return true }
			e, ctrl, err := decodeRuntimeFrame(f.Data)
			if err != nil { errs <- err; return false }
			if ctrl == nil && f.ID != "" && fmt.Sprint(e.Sequence) != f.ID {
				errs <- &ProtocolError{Message: "SSE id does not match canonical event sequence"}
				return false
			}
			select {
			case frames <- runtimeFrame{event: e, control: ctrl}: return true
			case <-ctx.Done(): errs <- ctx.Err(); return false
			}
		}
		for sc.Scan() {
			if !emit(dec.Feed(sc.Text())) { return }
		}
		if err := sc.Err(); err != nil {
			errs <- &ConnectionError{Message: "Woobe Runtime stream connection failed", Cause: err}
			return
		}
		emit(dec.Finish())
	}()
	return frames, errs, nil
}

func (c *Client) run(ctx context.Context, key, input string, o RunOptions) (*RunResult, error) {
	body := map[string]any{"message": input}
	addRuntimeOptions(body, o)
	var out RunResult
	if err := c.doJSON(ctx, http.MethodPost, "/v1/run", key, body, &out); err != nil { return nil, err }
	return &out, nil
}
func addRuntimeOptions(body map[string]any, o ChatOptions) {
	if o.SessionID != "" { body["session_id"] = o.SessionID }
	if o.TenantID != "" { body["tenant_id"] = o.TenantID }
	if o.UserID != "" { body["user_id"] = o.UserID }
	if o.Metadata != nil { body["metadata"] = o.Metadata }
	if o.ExternalContext != nil { body["external_context"] = o.ExternalContext }
}
func (c *Client) activeRun(ctx context.Context, key, sessionID string) (*ActiveRun, error) {
	var env struct {
		Success bool       `json:"success"`
		Data    *ActiveRun `json:"data"`
	}
	path := "/v1/sessions/" + url.PathEscape(sessionID) + "/active-run"
	if err := c.doJSON(ctx, http.MethodGet, path, key, nil, &env); err != nil { return nil, err }
	return env.Data, nil
}
func (c *Client) cancelRun(ctx context.Context, key, runID string) error {
	return c.doJSON(ctx, http.MethodPost, "/v1/runs/"+url.PathEscape(runID)+"/cancel", key, nil, nil)
}
func (c *Client) validateContracts(ctx context.Context, key string, in ContractValidationRequest) (*RuntimeContractsValidation, error) {
	var env struct {
		Success bool                       `json:"success"`
		Data    RuntimeContractsValidation `json:"data"`
	}
	if err := c.doJSON(ctx, http.MethodPost, "/v1/contracts/validate", key, in, &env); err != nil { return nil, err }
	if !env.Success { return nil, &ProtocolError{Message: "runtime contract validation response has an invalid envelope"} }
	return &env.Data, nil
}
