package packageapi

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/controlplane"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
)

func operationFixture() map[string]any {
	return map[string]any{"package_schema_version": "1.0", "project_id": "project", "operation_id": "operation", "artifact_digest": strings.Repeat("a", 64),
		"state": "materializing", "terminal": false, "revision": 2, "phases_completed": 1, "phases_total": 4, "next_poll_after_ms": 100}
}
func serveOperation(w http.ResponseWriter, value map[string]any) {
	_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": value})
}
func testClient(t *testing.T, handler http.HandlerFunc) (*Client, func()) {
	t.Helper()
	server := httptest.NewServer(handler)
	control, err := controlplane.New(server.URL, "private-control-key", time.Second)
	if err != nil {
		t.Fatal(err)
	}
	client, err := New(control, "project")
	if err != nil {
		t.Fatal(err)
	}
	return client, server.Close
}

func TestStatusCannotAcceptCrossProjectOrDifferentOperation(t *testing.T) {
	for _, field := range []string{"project_id", "operation_id", "package_schema_version"} {
		t.Run(field, func(t *testing.T) {
			client, close := testClient(t, func(w http.ResponseWriter, r *http.Request) {
				result := operationFixture()
				result[field] = "other"
				serveOperation(w, result)
			})
			defer close()
			if _, err := client.Status(context.Background(), "operation"); err == nil {
				t.Fatal("accepted foreign evidence")
			}
		})
	}
}

func TestLookupKeyStaysInBodyAndUnknownFieldsAreNotExposed(t *testing.T) {
	key := "lost-response-private-key"
	client, close := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.RawQuery != "" || strings.Contains(r.URL.Path, key) {
			t.Fatal("key exposed in URL")
		}
		var body map[string]any
		if json.NewDecoder(r.Body).Decode(&body) != nil || body["idempotency_key"] != key {
			t.Fatal("lookup body")
		}
		result := operationFixture()
		result["protected_payload"] = "never-print-this"
		result["diagnostics"] = []any{map[string]any{"code": "OWNER_REJECTED", "message": "never-print-this"}}
		serveOperation(w, result)
	})
	defer close()
	result, err := client.Lookup(context.Background(), key)
	if err != nil {
		t.Fatal(err)
	}
	encoded, _ := json.Marshal(result)
	if strings.Contains(string(encoded), "never-print-this") {
		t.Fatal("unsafe response projection")
	}
}

func TestPollingTotalDeadlineIncludesSlowGetAndKeepsObservedState(t *testing.T) {
	var requests atomic.Int32
	client, close := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		requests.Add(1)
		<-r.Context().Done()
	})
	defer close()
	initial := Operation{OperationID: "operation", ProjectID: "project", State: "materializing", Revision: 2, NextPollAfterMS: 100}
	ctx, cancel := context.WithTimeout(context.Background(), 180*time.Millisecond)
	defer cancel()
	started := time.Now()
	result, err := client.Wait(ctx, initial, nil)
	if err == nil || output.Normalize(err).Code != 8 || result.Revision != 2 || requests.Load() != 1 || time.Since(started) > time.Second {
		t.Fatal(result, err, requests.Load())
	}
}

func TestPostCancellationIsNotRetriedAfterDisconnect(t *testing.T) {
	var attempts atomic.Int32
	client, close := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		attempts.Add(1)
		connection, _, err := w.(http.Hijacker).Hijack()
		if err != nil {
			t.Fatal(err)
		}
		_ = connection.Close()
	})
	defer close()
	_, err := client.Cancel(context.Background(), "operation")
	if err == nil || output.Normalize(err).Outcome != "unknown" || attempts.Load() != 1 {
		t.Fatal(err, attempts.Load())
	}
}

func TestPackagePollingUsesServerDelayAndBoundedJitteredFallback(t *testing.T) {
	for _, milliseconds := range []int64{1, 100, 45000} {
		if delay := packagePollDelay(milliseconds, 2*time.Second); delay != time.Duration(milliseconds)*time.Millisecond {
			t.Fatal("changed advertised delay", delay)
		}
	}
	for _, base := range []time.Duration{2 * time.Second, 4 * time.Second, 8 * time.Second, 15 * time.Second} {
		for i := 0; i < 100; i++ {
			delay := packagePollDelay(0, base)
			if delay < 2*time.Second || delay > 15*time.Second {
				t.Fatal("unbounded fallback", delay)
			}
		}
	}
}
