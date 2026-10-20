package packageapi

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/controlplane"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

func TestStructuralNegotiationFailsBeforeMutation(t *testing.T) {
	for _, mode := range []string{"old-server", "wrong-catalog", "not-structural", "supported"} {
		t.Run(mode, func(t *testing.T) {
			writes := 0
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.Method != http.MethodGet || r.URL.Path != "/projects/"+evidenceProjectUUID+"/packages/capabilities" {
					writes++
					w.WriteHeader(500)
					return
				}
				data := map[string]any{"package_schema_version": "1.0"}
				if mode != "old-server" {
					data["supported_package_schemas"] = map[string]string{"2.0": packagefmt.VersionCatalogDigest("2.0")}
					data["structural_installation"] = mode != "not-structural"
				}
				if mode == "wrong-catalog" {
					data["supported_package_schemas"] = map[string]string{"2.0": "wrong"}
				}
				_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
			}))
			defer server.Close()
			control, _ := controlplane.New(server.URL, "", time.Second)
			client, _ := New(control, evidenceProjectUUID)
			err := client.RequireSchema(context.Background(), "2.0", true)
			if (err == nil) != (mode == "supported") || writes != 0 {
				t.Fatalf("negotiation=%v writes=%d", err, writes)
			}
		})
	}
}
