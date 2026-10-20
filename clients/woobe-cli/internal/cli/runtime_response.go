package cli

import (
	"bytes"
	"encoding/json"
	"fmt"
	sdk "github.com/A1b3rt0M3rcad0/woobe-sdk-go"
	"io"
	"net/http"
)

// Retain exact JSON numbers while leaving runtime authentication, execution and
// error semantics with the SDK. Capture only the successful synchronous result.
type runtimeResponseCapture struct {
	base http.RoundTripper
	raw  []byte
}

func (c *runtimeResponseCapture) RoundTrip(request *http.Request) (*http.Response, error) {
	response, err := c.base.RoundTrip(request)
	if err != nil || request.Method != http.MethodPost || request.URL.Path != "/v1/run" || response.StatusCode < 200 || response.StatusCode >= 300 {
		return response, err
	}
	const limit = 16 * 1024 * 1024
	raw, err := io.ReadAll(io.LimitReader(response.Body, limit+1))
	response.Body.Close()
	if err != nil {
		return nil, err
	}
	if len(raw) > limit {
		return nil, fmt.Errorf("runtime response exceeds the supported limit")
	}
	c.raw = raw
	response.Body = io.NopCloser(bytes.NewReader(raw))
	return response, nil
}
func (c *runtimeResponseCapture) preciseResult(fallback *sdk.RunResult) (*sdk.RunResult, error) {
	if len(c.raw) == 0 {
		return fallback, nil
	}
	var result sdk.RunResult
	decoder := json.NewDecoder(bytes.NewReader(c.raw))
	decoder.UseNumber()
	if err := decoder.Decode(&result); err != nil {
		return nil, err
	}
	if decoder.Decode(new(any)) != io.EOF {
		return nil, fmt.Errorf("invalid trailing runtime response")
	}
	return &result, nil
}
