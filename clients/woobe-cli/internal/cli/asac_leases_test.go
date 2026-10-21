package cli

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func leaseTestReceipt(body map[string]any, project, id string) map[string]any {
	now := time.Now().UTC()
	return map[string]any{"schema_version": "1.0", "complete": true, "clock_authority": "database", "project_id": project, "resource_id": id, "scope": "resource", "operation_id": body["operation_id"], "write_outcome": "committed", "lease_id": "12345678-1234-4321-8321-123456789019", "workflow_id": body["workflow_id"], "fencing_token": json.Number("9223372036854775807"), "actor": "control:test", "state": "active", "acquired_at": now.Format(time.RFC3339Nano), "expires_at": now.Add(time.Minute).Format(time.RFC3339Nano), "maximum_expires_at": now.Add(5 * time.Minute).Format(time.RFC3339Nano), "server_time": now.Format(time.RFC3339Nano)}
}

func TestWorkflowLeaseLostAcceptanceRetainsProofAndNeverRepeatsMutation(t *testing.T) {
	root, _ := filepath.Abs("../..")
	t.Setenv("WOOBE_TEST_REPOSITORY", root)
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	const native = "01a0a033-5820-770c-854b-902864857273"
	var receipt map[string]any
	writes := 0
	mismatch := true
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var data any
		switch {
		case strings.HasSuffix(r.URL.Path, "/capabilities"):
			data = map[string]any{"asac": map[string]any{"schema_version": "1.0", "operation_leases": true, "lease_clock": "database", "lease_fencing_scope": "owner-authoring-transaction@1"}}
		case strings.HasSuffix(r.URL.Path, "/leases/acquire"):
			writes++
			var body map[string]any
			_ = json.NewDecoder(r.Body).Decode(&body)
			if !uuidReference(body["operation_id"].(string)) || !uuidReference(body["workflow_id"].(string)) {
				t.Error("missing distinct stable workflow identities", body)
			}
			receipt = leaseTestReceipt(body, "project", native)
			w.WriteHeader(500)
			_ = json.NewEncoder(w).Encode(map[string]any{"success": false, "message": "response lost"})
			return
		case strings.Contains(r.URL.Path, "/operations/"):
			copy := map[string]any{}
			for key, value := range receipt {
				copy[key] = value
			}
			if mismatch {
				copy["workflow_id"] = "12345678-1234-4321-8321-123456789088"
			}
			data = map[string]any{"operation_id": receipt["operation_id"], "state": "committed", "result": copy}
		default:
			t.Error("unexpected request", r.Method, r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	c, state, resource := asacWorkspace(t, server.URL)
	flags := []string{"--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json"}
	run := func(action string) (int, map[string]any) {
		return invoke(t, append([]string{"agent", "@support", "lease", action}, flags...), "")
	}
	if code, value := run("acquire"); code == 0 || writes != 1 {
		t.Fatal(code, value, writes)
	}
	if code, value := run("acquire"); code != 9 || writes != 1 {
		t.Fatal("uncertain reservation repeated", code, value, writes)
	}
	if code, value := run("reconcile"); code != 9 {
		t.Fatal("foreign workflow adopted", code, value)
	}
	mismatch = false
	if code, value := invoke(t, append([]string{"agent", "@support", "draft", "reconcile"}, flags...), ""); code != 0 || writes != 1 {
		t.Fatal(code, value, writes)
	}
	proofs, err := authoringLeaseProofs(c, state, resource.UID, native, "")
	if err != nil || len(proofs) != 1 || proofs[0]["workflow_id"] != receipt["workflow_id"] || proofs[0]["fencing_token"] != json.Number("9223372036854775807") {
		t.Fatal("exact private lease proof lost", proofs, err)
	}
	// A historical acceptance must remain a proof that the server can fence;
	// client wall-clock expiry does not silently switch to unreserved writing.
	receipt["acquired_at"] = time.Now().Add(-2 * time.Hour).UTC().Format(time.RFC3339Nano)
	receipt["server_time"] = receipt["acquired_at"]
	receipt["expires_at"] = time.Now().Add(-time.Hour).UTC().Format(time.RFC3339Nano)
	receipt["maximum_expires_at"] = time.Now().Add(-30 * time.Minute).UTC().Format(time.RFC3339Nano)
	if err = storeLeaseObservation(c, state, resource.UID, native, receipt); err != nil {
		t.Fatal(err)
	}
	if proofs, err = authoringLeaseProofs(c, state, resource.UID, native, ""); err != nil || len(proofs) != 1 {
		t.Fatal("expired proof silently dropped", proofs, err)
	}
	receipt["state"] = "released"
	if err = storeLeaseObservation(c, state, resource.UID, native, receipt); err != nil {
		t.Fatal(err)
	}
	if proofs, err = authoringLeaseProofs(c, state, resource.UID, native, ""); err != nil || len(proofs) != 0 {
		t.Fatal("explicit release not honored", proofs, err)
	}
}

func TestNativeWorkflowLeasesRequireExplicitIdentityAndIgnoreDevelopmentConfig(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	t.Setenv("WOOBE_PROJECT_CONFIG", "missing-config")
	writes := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { writes++; t.Error("invalid lease reached server") }))
	defer server.Close()
	flags := []string{"--api-url", server.URL, "--project", "project", "--workspace", "workspace", "--output", "json"}
	for _, args := range [][]string{
		{"agent", "01a0a033-5820-770c-854b-902864857273", "lease", "acquire"},
		{"network", "01a0a033-5820-770c-854b-902864857273", "lease", "release"},
		{"agent", "01a0a033-5820-770c-854b-902864857273", "lease", "break", "--yes", "--reason", "break"},
	} {
		if code, value := invoke(t, append(args, flags...), ""); code != 2 {
			t.Fatal(code, value)
		}
	}
	if writes != 0 {
		t.Fatal("unidentified workflow made requests", writes)
	}
}

func TestWorkflowLeaseCannotOverwriteMalformedPendingCheckpoint(t *testing.T) {
	root, _ := filepath.Abs("../..")
	t.Setenv("WOOBE_TEST_REPOSITORY", root)
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	for _, marker := range []string{"null", `{"unexpected":true}`, "{} {}", `{"operation_id":null}`} {
		t.Run(marker, func(t *testing.T) {
			requests := 0
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				requests++
				t.Error("unresolved checkpoint reached backend")
			}))
			defer server.Close()
			c, state, resource := asacWorkspace(t, server.URL)
			path := asacPrivatePath(c, state, resource.UID, "pending")
			if err := c.WriteOperationalFile(path, []byte(marker)); err != nil {
				t.Fatal(err)
			}
			code, result := invoke(t, []string{"agent", "@support", "lease", "acquire", "--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json"}, "")
			raw, err := c.ReadOperationalFile(path, 16<<20)
			if code != 9 || requests != 0 || err != nil || string(raw) != marker {
				t.Fatal("uncertain operation was discarded", code, result, requests, err)
			}
		})
	}
}

func TestLeaseReceiptRejectsScopeClockAndNumericForgery(t *testing.T) {
	body := map[string]any{"operation_id": "12345678-1234-4321-8321-123456789016", "workflow_id": "12345678-1234-4321-8321-123456789017"}
	for _, change := range []map[string]any{{"scope": "production"}, {"fencing_token": "1"}, {"fencing_token": json.Number("1.5")}, {"fencing_token": json.Number("9223372036854775808")}, {"clock_authority": "client"}, {"expires_at": "invalid"}, {"complete": false}, {"state": "unreserved"}} {
		receipt := leaseTestReceipt(body, "project", "native")
		for key, value := range change {
			receipt[key] = value
		}
		if err := validateLeaseReceipt(receipt, "project", "native", body["operation_id"].(string), "resource", body); err == nil {
			t.Fatal("forged receipt accepted", change)
		}
	}
}
