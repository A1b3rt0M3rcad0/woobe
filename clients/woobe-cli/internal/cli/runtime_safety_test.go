package cli

import (
	"context"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	sdk "github.com/A1b3rt0M3rcad0/woobe-sdk-go"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestRuntimeDryRunNeverStartsOrCancels(t *testing.T) {
	calls := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { calls++; w.WriteHeader(500) }))
	defer s.Close()
	for _, action := range []string{"run", "stream", "cancel", "active", "observe"} {
		args := []string{"runtime", "target", action, "tutor", "--api-url", s.URL, "--dry-run"}
		input := ""
		if action == "run" || action == "stream" {
			args = append(args, "--file", "-")
			input = `{"input":"Study"}`
		} else {
			args = append(args, "resource-id")
		}
		code, v := invoke(t, args, input)
		if code != 0 || v["data"].(map[string]any)["executed"] != false {
			t.Fatal(action, code, v)
		}
	}
	if calls != 0 {
		t.Fatal("runtime dry-run made HTTP call")
	}
}
func TestRuntimeErrorClassification(t *testing.T) {
	for _, c := range []struct {
		err  error
		code int
	}{{context.Canceled, 130}, {context.DeadlineExceeded, 8}, {&sdk.AuthenticationError{RequestError: &sdk.RequestError{StatusCode: 401}}, 3}} {
		e := runtimeError(c.err)
		if e == nil || output.Normalize(e).Code != c.code {
			t.Fatal(e)
		}
	}
}
