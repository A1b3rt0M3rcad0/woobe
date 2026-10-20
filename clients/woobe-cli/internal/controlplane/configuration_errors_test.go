package controlplane

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
)

func TestConfigurationDiagnosticsAtRuntimeAndDeploymentBoundaries(t *testing.T) {
	for _, test := range []struct {
		code         string
		status, exit int
	}{
		{"CONFIG_VALUE_MISSING", 409, 6}, {"CONFIG_REVISION_CONFLICT", 409, 6},
		{"CONFIG_STORE_UNAVAILABLE", 503, 9}, {"CONFIG_USAGE_NOT_AUTHORIZED", 403, 4},
	} {
		t.Run(test.code, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(test.status)
				_ = json.NewEncoder(w).Encode(map[string]any{"data": map[string]any{"configuration_schema_version": "project_configuration.v1",
					"diagnostics": []any{map[string]any{"code": test.code, "key": "_primaryKey", "environment": "production", "message": "private-canary", "value": "private-canary"}}}})
			}))
			defer server.Close()
			client, _ := New(server.URL, "", time.Second)
			for _, path := range []string{"/projects/p/agents/a/asac/deployment-plans", "/ai/agents/a/ask", "/core/projects/p/configuration/keys"} {
				_, _, err := client.Request(context.Background(), "POST", path, nil, nil)
				failure := output.Normalize(err)
				raw, _ := json.Marshal(failure)
				if failure.Code != test.exit || failure.DomainCode != test.code || len(failure.Diagnostics) != 1 || strings.Contains(string(raw), "private-canary") {
					t.Fatalf("%s: %s", path, raw)
				}
				if failure.Diagnostics[0].Key != "_primaryKey" || failure.Diagnostics[0].Environment != "production" {
					t.Fatalf("missing scope: %s", raw)
				}
			}
		})
	}
}

func TestConfigurationDiagnosticRejectsUnknownContractAndUntrustedText(t *testing.T) {
	for _, raw := range []string{
		`{"data":{"diagnostics":[{"code":"CONFIG_VALUE_MISSING"}]}}`,
		`{"data":{"configuration_schema_version":"project_configuration.v2","diagnostics":[{"code":"CONFIG_VALUE_MISSING"}]}}`,
		`{"data":{"configuration_schema_version":"project_configuration.v1","diagnostics":[{"code":"CONFIG_PRIVATE_SECRET"}]}}`,
		`{"data":{"configuration_schema_version":"project_configuration.v1","diagnostics":[]}}`,
		`{"data":{"configuration_schema_version":"project_configuration.v1","configuration_schema_version":"project_configuration.v1","diagnostics":[{"code":"CONFIG_VALUE_MISSING"}]}}`,
	} {
		failure := output.New(6, "server rejected request")
		if configurationDiagnostic([]byte(raw), failure) || failure.DomainCode != "" {
			t.Fatal("untrusted diagnostic accepted")
		}
	}
	failure := output.New(6, "server rejected request")
	raw := []byte(`{"data":{"configuration_schema_version":"project_configuration.v1","diagnostics":[{"code":"CONFIG_VALUE_MISSING","key":"private-canary","environment":"private-canary"}]}}`)
	if !configurationDiagnostic(raw, failure) || failure.Diagnostics[0].Key != "" || failure.Diagnostics[0].Environment != "" {
		t.Fatal("unsafe scope was accepted")
	}
}
