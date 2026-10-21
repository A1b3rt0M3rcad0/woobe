package packageapi

import (
	"context"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"net/http"
	"strings"
	"sync/atomic"
	"testing"
)

func applyFixture() ApplyRequest {
	return ApplyRequest{PlanID: "plan", PlanDigest: strings.Repeat("a", 64), UploadID: "upload", ArtifactDigest: strings.Repeat("b", 64), Lifecycle: "draft"}
}

func TestApplyPinsKeyWithoutChangingSharedClientHeaders(t *testing.T) {
	client, close := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Idempotency-Key") != "approved-key" || r.Header.Get("If-Match") != "" {
			t.Error("unexpected apply headers")
		}
		result := operationFixture()
		result["artifact_digest"] = strings.Repeat("b", 64)
		serveOperation(w, result)
	})
	defer close()
	client.Control.Headers.Set("Idempotency-Key", "unrelated-key")
	client.Control.Headers.Set("If-Match", "unrelated-revision")
	if _, err := client.Apply(context.Background(), "approved-key", applyFixture()); err != nil {
		t.Fatal(err)
	}
	if client.Control.Headers.Get("Idempotency-Key") != "unrelated-key" || client.Control.Headers.Get("If-Match") != "unrelated-revision" {
		t.Fatal("apply changed another request")
	}
}

func TestAmbiguousApplyResponseCannotBecomeProofOfRejectionOrTriggerRetry(t *testing.T) {
	var requests atomic.Int32
	client, close := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		requests.Add(1)
		serveOperation(w, map[string]any{"package_schema_version": "1.0", "project_id": "wrong"})
	})
	defer close()
	_, err := client.Apply(context.Background(), "approved-key", applyFixture())
	if err == nil || output.Normalize(err).Outcome != "unknown" || requests.Load() != 1 {
		t.Fatal(err, requests.Load())
	}
}
