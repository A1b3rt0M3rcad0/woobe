package controlplane

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
)

func TestNetworkExportDiagnosticsRemainActionableWithoutServerSecrets(t *testing.T) {
	for _, suffix := range []string{"BINDING", "CONSTITUENT", "INTEGRITY", "DEFINITION", "CONFLICT"} {
		t.Run(suffix, func(t *testing.T) {
			code := "PACKAGE_EXPORT_NETWORK_" + suffix
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(409)
				json.NewEncoder(w).Encode(map[string]any{"success": false, "data": map[string]any{"package_schema_version": "1.0", "diagnostics": []any{map[string]any{"code": code, "path": "/spec/nodes/0/binding", "file": "network.yaml", "message": "private-provider-secret"}}}})
			}))
			defer server.Close()
			client := &Client{Base: server.URL, HTTP: server.Client(), Headers: make(http.Header)}
			_, _, err := client.Request(context.Background(), "POST", "/projects/project/packages/export", nil, nil)
			failure := output.Normalize(err)
			if failure.Code != 6 || failure.DomainCode != code || len(failure.Diagnostics) != 1 || !strings.Contains(failure.Message, "Network export blocked") || strings.Contains(failure.Message, "private-provider") {
				t.Fatal(failure)
			}
		})
	}
}
